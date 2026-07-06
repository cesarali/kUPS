# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import csv
from pathlib import Path

import yaml

from kups.polymerization.md_diagnostics import (
    DEFAULT_DIRTY_KUPS_ROOT,
    DIRTY_BASELINE_LABEL,
    discover_kups_result,
    read_kups_diagnostics,
    write_kups_diagnostics,
    write_lammps_diagnostics,
)

ROOT = Path(__file__).resolve().parents[2]
LAMMPS_RESULT = ROOT / "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"


def test_report_generation_includes_source_and_normalized_minimization_energies(
    tmp_path: Path,
) -> None:
    artifacts = write_lammps_diagnostics(
        LAMMPS_RESULT, output_dir=tmp_path / "lammps_diagnostics"
    )

    report = artifacts.report.read_text()
    assert "0.16980599476" in report
    assert "0.168446472786" in report
    assert "Step 2 does not claim reproduction" in report
    rows = list(csv.DictReader(artifacts.data_files["static_energy_terms"].open()))
    initial = next(row for row in rows if row["term"] == "potential_total_min_initial")
    assert initial["source_unit"] == "kcal/mol"
    assert initial["value_eV"]


def test_kups_report_generation_succeeds_without_hdf5(tmp_path: Path) -> None:
    kups_result = tmp_path / "kups_result_without_h5"
    artifacts = write_kups_diagnostics(
        kups_result,
        dirty_kups_root=DEFAULT_DIRTY_KUPS_ROOT,
        output_dir=tmp_path / "kups_diagnostics",
    )

    assert artifacts.report.exists()
    report = artifacts.report.read_text()
    assert DIRTY_BASELINE_LABEL in report
    assert "not_available" in artifacts.data_files["status_summary"].read_text()
    assert "full reproduction" not in report.lower()


def test_dirty_baseline_config_records_known_missing_physics() -> None:
    config = yaml.safe_load((DEFAULT_DIRTY_KUPS_ROOT / "methane_lj_only_nve.yaml").read_text())
    result = discover_kups_result(
        ROOT / "results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0",
        dirty_kups_root=DEFAULT_DIRTY_KUPS_ROOT,
    )
    parsed = read_kups_diagnostics(result)

    assert config["lj"]["mixing_rule"] == "lorentz_berthelot"
    assert "bond" not in config
    assert "angle" not in config
    assert "coulomb" not in config
    assert "kspace" not in config
    assert parsed.config["lj"]["mixing_rule"] == "lorentz_berthelot"
