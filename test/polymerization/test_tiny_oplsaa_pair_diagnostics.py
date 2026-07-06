# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections import Counter
from pathlib import Path

from kups.polymerization.md_diagnostics import (
    compute_pair_diagnostics,
    load_lammps_structure,
)

ROOT = Path(__file__).resolve().parents[2]
LAMMPS_RESULT = ROOT / "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"


def test_pair_diagnostics_classify_methane_graph_distances() -> None:
    structure = load_lammps_structure(
        LAMMPS_RESULT / "system.data",
        init_file=LAMMPS_RESULT / "system.in.init",
        settings_file=LAMMPS_RESULT / "system.in.settings",
        charges_file=LAMMPS_RESULT / "system.in.charges",
    )

    rows = compute_pair_diagnostics(
        structure, special_bonds={"lj": [0.0, 0.0, 0.5], "coul": [0.0, 0.0, 0.5]}
    )
    counts = Counter(row["topology_class"] for row in rows)

    assert len(rows) == 10
    assert counts["1-2"] == 4
    assert counts["1-3"] == 6
    assert counts["1-4"] == 0
    assert counts["normal"] == 0
    assert {row["lj_scale"] for row in rows if row["topology_class"] == "1-2"} == {0.0}
    assert {row["coulomb_scale"] for row in rows if row["topology_class"] == "1-3"} == {
        0.0
    }


def test_dirty_pair_diagnostics_keep_lj_and_coulomb_statuses_independent() -> None:
    structure = load_lammps_structure(
        LAMMPS_RESULT / "system.data",
        init_file=LAMMPS_RESULT / "system.in.init",
        settings_file=LAMMPS_RESULT / "system.in.settings",
        charges_file=LAMMPS_RESULT / "system.in.charges",
    )

    rows = compute_pair_diagnostics(
        structure,
        special_bonds={"lj": [1.0, 1.0, 1.0], "coul": [1.0, 1.0, 1.0]},
        dirty_kups=True,
    )

    assert all("lj_scale" in row and "coulomb_scale" in row for row in rows)
    assert any(row["lj_status"] == "expected_mismatch" for row in rows)
    assert all(row["coulomb_status"] == "not_implemented" for row in rows)
