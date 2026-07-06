# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path

from kups.polymerization.md_diagnostics import (
    DEFAULT_DIRTY_KUPS_ROOT,
    write_comparison_diagnostics,
    write_kups_diagnostics,
    write_lammps_diagnostics,
)

ROOT = Path(__file__).resolve().parents[2]
LAMMPS_RESULT = ROOT / "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"


def test_lammps_mode_writes_selected_diagnostics_dir(tmp_path: Path) -> None:
    out = tmp_path / "lammps" / "diagnostics"
    artifacts = write_lammps_diagnostics(LAMMPS_RESULT, output_dir=out)

    assert artifacts.output_dir == out
    assert (out / "REPORT.md").exists()
    assert (out / "data" / "lammps_thermo.csv").exists()
    assert (out / "plots" / "energy_timeseries.png").stat().st_size > 0


def test_kups_mode_writes_result_folder_diagnostics_by_default(tmp_path: Path) -> None:
    kups_result = tmp_path / "kups_result"
    artifacts = write_kups_diagnostics(
        kups_result,
        dirty_kups_root=DEFAULT_DIRTY_KUPS_ROOT,
    )

    assert artifacts.output_dir == kups_result / "diagnostics"
    assert artifacts.report.exists()
    assert (artifacts.output_dir / "data" / "kups_tiny0_observables.csv").exists()


def test_comparison_default_and_explicit_output_locations(tmp_path: Path) -> None:
    kups_result = tmp_path / "kups_result"
    default_artifacts = write_comparison_diagnostics(
        lammps_result_dir=LAMMPS_RESULT,
        kups_result_dir=kups_result,
        dirty_kups_root=DEFAULT_DIRTY_KUPS_ROOT,
    )
    explicit = tmp_path / "explicit_comparison"
    explicit_artifacts = write_comparison_diagnostics(
        lammps_result_dir=LAMMPS_RESULT,
        kups_result_dir=kups_result,
        dirty_kups_root=DEFAULT_DIRTY_KUPS_ROOT,
        output_dir=explicit,
    )

    assert default_artifacts.output_dir == kups_result / "diagnostics" / "comparison"
    assert explicit_artifacts.output_dir == explicit
    assert (
        explicit / "plots" / "energy_timeseries_side_by_side.png"
    ).stat().st_size > 0
    assert (explicit / "data" / "lammps_thermo.csv").exists()
