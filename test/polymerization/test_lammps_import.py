# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kups.polymerization.lammps import (
    KCAL_PER_MOL_TO_EV,
    check_lammps_deck,
    classify_special_pairs,
    load_lammps_deck,
    load_lammps_deck_directory,
    write_lammps_deck_report,
    write_lammps_deck_yaml,
)

ROOT = Path(__file__).resolve().parents[2]
TINY_DECK = ROOT / "external/lammps_oplss/moltemplate_oplsaa_tiny"
ALKANE_DECK = ROOT / "external/lammps_oplss/alkane_chain_single_lammps_ready"


def _write_minimal_deck(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    data_file = tmp_path / "system.data"
    init_file = tmp_path / "system.in.init"
    settings_file = tmp_path / "system.in.settings"
    charges_file = tmp_path / "system.in.charges"
    data_file.write_text(
        """LAMMPS Description

4 atoms
3 bonds
0 angles
0 dihedrals
0 impropers

2 atom types
1 bond types
0 angle types
0 dihedral types
0 improper types

0.0 10.0 xlo xhi
0.0 10.0 ylo yhi
0.0 10.0 zlo zhi

Masses

1 12.0 # C
2 1.0 # H

Atoms # full

1 1 1 0.0 0.0 0.0 0.0
2 1 2 0.0 1.0 0.0 0.0
3 1 2 0.0 2.0 0.0 0.0
4 1 2 0.0 3.0 0.0 0.0

Bonds

1 1 1 2
2 1 2 3
3 1 3 4
"""
    )
    init_file.write_text(
        """units real
atom_style full
bond_style harmonic
pair_style lj/charmm/coul/long 9.0 11.0
pair_modify mix geometric
special_bonds lj/coul 0.0 0.0 0.5
kspace_style pppm 0.0001
"""
    )
    settings_file.write_text(
        """pair_coeff 1 1 0.060 3.570
pair_coeff 2 2 0.030 2.500
bond_coeff 1 340. 1.09
set type 1 charge -0.1
set type 2 charge 0.0
"""
    )
    charges_file.write_text(
        """set type 1 charge -0.2
set type 2 charge 0.1
"""
    )
    return data_file, init_file, settings_file, charges_file


def test_charge_file_overrides_settings_and_data_charges(tmp_path: Path) -> None:
    data_file, init_file, settings_file, charges_file = _write_minimal_deck(tmp_path)
    deck = load_lammps_deck(data_file, init_file, settings_file, charges_file)

    assert deck["checker"]["status"] == "pass"
    assert deck["atoms"][0]["original_charge_e"] == 0.0
    assert deck["atoms"][0]["charge_e"] == -0.2
    assert deck["atoms"][0]["charge_source"] == "charges_file"
    assert deck["atoms"][1]["charge_e"] == 0.1


def test_unit_conversions_are_present(tmp_path: Path) -> None:
    data_file, init_file, settings_file, charges_file = _write_minimal_deck(tmp_path)
    deck = load_lammps_deck(data_file, init_file, settings_file, charges_file)

    pair = deck["coefficients"]["pair"]["1-1"]
    bond = deck["coefficients"]["bond"]["1"]
    assert pair["converted_units"]["epsilon_eV"] == pytest.approx(
        0.060 * KCAL_PER_MOL_TO_EV
    )
    assert pair["converted_units"]["sigma_A"] == pytest.approx(3.570)
    assert bond["converted_units"]["k_eV_per_A2"] == pytest.approx(
        340.0 * KCAL_PER_MOL_TO_EV
    )
    assert bond["converted_units"]["r0_A"] == pytest.approx(1.09)


def test_topology_graph_classifies_one_two_one_three_and_one_four_pairs() -> None:
    classes = classify_special_pairs(
        [
            {"id": 1, "type": 1, "atoms": [1, 2]},
            {"id": 2, "type": 1, "atoms": [2, 3]},
            {"id": 3, "type": 1, "atoms": [3, 4]},
        ]
    )

    assert classes["one_two"] == {(1, 2), (2, 3), (3, 4)}
    assert classes["one_three"] == {(1, 3), (2, 4)}
    assert classes["one_four"] == {(1, 4)}


def test_checker_fails_for_missing_topology_atom_reference(tmp_path: Path) -> None:
    data_file, init_file, settings_file, charges_file = _write_minimal_deck(tmp_path)
    deck = load_lammps_deck(data_file, init_file, settings_file, charges_file)
    deck["topology"]["bonds"][0]["atoms"] = [1, 99]

    checked = check_lammps_deck(deck)

    assert checked["status"] == "fail"
    assert any("missing atoms" in error for error in checked["errors"])


def test_tiny_methane_fixture_matches_step_1_contract() -> None:
    deck = load_lammps_deck_directory(TINY_DECK)

    assert deck["checker"]["status"] == "pass"
    assert deck["counts"]["atoms"] == 5
    assert deck["counts"]["bonds"] == 4
    assert deck["counts"]["angles"] == 6
    assert deck["counts"]["dihedrals"] == 0
    assert deck["counts"]["impropers"] == 0
    assert deck["box"]["xlo"] == -15.0
    assert deck["box"]["xhi"] == 15.0
    assert deck["atom_type_charges"]["1"]["charge_e"] == pytest.approx(-0.24)
    assert deck["atom_type_charges"]["2"]["charge_e"] == pytest.approx(0.06)
    assert deck["coefficients"]["pair"]["1-1"]["epsilon_kcal_per_mol"] == 0.060
    assert deck["coefficients"]["pair"]["2-2"]["sigma_A"] == 2.500
    assert deck["coefficients"]["bond"]["1"]["k_kcal_per_mol_per_A2"] == 340.0
    assert deck["coefficients"]["angle"]["1"]["theta0_degree"] == 107.8
    assert deck["lammps_semantics"]["pair_modify"]["mix"] == "geometric"
    assert deck["lammps_semantics"]["special_bonds"]["lj"] == [0.0, 0.0, 0.5]
    assert deck["lammps_semantics"]["kspace_style"]["name"] == "pppm"
    assert deck["checker"]["special_pairs"]["counts"] == {
        "one_two": 4,
        "one_three": 6,
        "one_four": 0,
    }


def test_larger_alkane_fixture_imports_without_methane_assumptions() -> None:
    deck = load_lammps_deck_directory(ALKANE_DECK)

    assert deck["checker"]["status"] == "pass"
    assert deck["counts"]["atoms"] == 152
    assert deck["counts"]["bonds"] == 151
    assert deck["counts"]["angles"] == 300
    assert deck["counts"]["dihedrals"] == 441
    assert deck["checker"]["special_pairs"]["counts"]["one_four"] > 0
    assert len(deck["checker"]["used_atom_types"]) > 2


def test_resolved_yaml_and_report_are_written(tmp_path: Path) -> None:
    deck = load_lammps_deck_directory(TINY_DECK)
    out = tmp_path / "resolved.yaml"
    report = tmp_path / "REPORT.md"

    write_lammps_deck_yaml(deck, out)
    write_lammps_deck_report(deck, report)

    loaded = json.loads(out.read_text())
    assert loaded["checker"]["status"] == "pass"
    assert "LAMMPS Deck Import Report" in report.read_text()
