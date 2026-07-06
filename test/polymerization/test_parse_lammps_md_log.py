# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from pathlib import Path

from kups.polymerization.lammps import KCAL_PER_MOL_TO_EV
from kups.polymerization.md_diagnostics import parse_lammps_md_log

ROOT = Path(__file__).resolve().parents[2]
LAMMPS_RESULT = ROOT / "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"


def test_parse_tiny_log_extracts_minimization_and_md_blocks() -> None:
    parsed = parse_lammps_md_log(LAMMPS_RESULT / "log.tiny")

    assert [block.kind for block in parsed.blocks] == ["minimization", "md"]
    assert len(parsed.blocks[0].rows) == 3
    assert [row["step"] for row in parsed.blocks[1].rows] == list(range(2, 13))


def test_tiny_minimization_stats_are_normalized_to_ev() -> None:
    parsed = parse_lammps_md_log(LAMMPS_RESULT / "log.tiny")

    assert math.isclose(
        parsed.minimization_stats["energy_initial_kcal_per_mol"],
        0.169805994760444,
    )
    assert math.isclose(
        parsed.minimization_stats["energy_next_to_last_kcal_per_mol"],
        0.168446472956472,
    )
    assert math.isclose(
        parsed.minimization_stats["energy_final_kcal_per_mol"],
        0.168446472786458,
    )
    assert math.isclose(
        parsed.minimization_stats["energy_final_eV"],
        0.168446472786458 * KCAL_PER_MOL_TO_EV,
    )


def test_energy_drift_is_computed_from_md_rows_only() -> None:
    parsed = parse_lammps_md_log(LAMMPS_RESULT / "log.tiny")
    minimization_rows = parsed.blocks[0].rows
    md_rows = parsed.blocks[1].rows

    assert all(row["energy_drift_eV"] == "" for row in minimization_rows)
    assert md_rows[0]["energy_drift_eV"] == 0.0
    assert math.isclose(
        md_rows[-1]["energy_drift_eV"],
        (0.76534855 - 0.76460848) * KCAL_PER_MOL_TO_EV,
        rel_tol=1e-9,
    )
    assert md_rows[1]["time_fs"] == 0.25


def test_parse_lammps_log_from_arbitrary_path(tmp_path: Path) -> None:
    copied = tmp_path / "renamed_reference.log"
    copied.write_text((LAMMPS_RESULT / "log.tiny").read_text())

    parsed = parse_lammps_md_log(copied)

    assert parsed.path == copied
    assert len(parsed.blocks) == 2


def test_parse_thermo_only_fixture_without_minimization(tmp_path: Path) -> None:
    log = tmp_path / "thermo_only.log"
    log.write_text(
        """LAMMPS
timestep 0.5
run 2
   Step          Temp          PotEng         TotEng         Press
         0   10             1.0            1.5            2.0
         1   11             1.1            1.6            2.1
         2   12             1.2            1.7            2.2
Loop time of 1 on 1 procs for 2 steps with 1 atoms
"""
    )

    parsed = parse_lammps_md_log(log)

    assert len(parsed.blocks) == 1
    assert parsed.blocks[0].kind == "md"
    assert parsed.blocks[0].rows[2]["time_fs"] == 1.0
    assert math.isclose(
        parsed.blocks[0].rows[0]["potential_energy_eV"],
        KCAL_PER_MOL_TO_EV,
    )
