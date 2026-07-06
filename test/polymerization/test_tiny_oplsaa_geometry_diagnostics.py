# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import math
from pathlib import Path

from kups.polymerization.md_diagnostics import (
    compute_angle_diagnostics,
    compute_bond_diagnostics,
    compute_static_geometry_rows,
    load_lammps_structure,
)

ROOT = Path(__file__).resolve().parents[2]
LAMMPS_RESULT = ROOT / "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"


def _tiny_structure():
    return load_lammps_structure(
        LAMMPS_RESULT / "system.data",
        init_file=LAMMPS_RESULT / "system.in.init",
        settings_file=LAMMPS_RESULT / "system.in.settings",
        charges_file=LAMMPS_RESULT / "system.in.charges",
    )


def test_initial_methane_geometry_counts_and_box() -> None:
    structure = _tiny_structure()
    geometry = compute_static_geometry_rows(structure)

    box_lengths = {
        row["quantity"]: row["value"]
        for row in geometry
        if row["quantity"].startswith("box_length")
    }
    assert box_lengths == {
        "box_length_x": 30.0,
        "box_length_y": 30.0,
        "box_length_z": 30.0,
    }
    assert sum(1 for row in geometry if row["quantity"] == "bond_length") == 4
    assert sum(1 for row in geometry if row["quantity"] == "angle") == 6
    assert sum(1 for row in geometry if row["quantity"].startswith("center_of_mass")) == 3
    assert sum(1 for row in geometry if row["quantity"] == "radius_of_gyration") == 1


def test_bond_and_angle_diagnostics_include_imported_references() -> None:
    structure = _tiny_structure()
    bonds = compute_bond_diagnostics(structure)
    angles = compute_angle_diagnostics(structure)

    assert len(bonds) == 4
    assert len(angles) == 6
    assert all(math.isclose(row["equilibrium_length_A"], 1.09) for row in bonds)
    assert all(math.isclose(row["equilibrium_angle_degree"], 107.8) for row in angles)
    assert all(row["status"] == "diagnostic_only" for row in bonds + angles)
