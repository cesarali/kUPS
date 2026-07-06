# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

"""Reusable MD diagnostics for LAMMPS and kUPS result folders.

The diagnostics in this module are intentionally report-side tooling. They parse
existing result files, normalize physical quantities into stable tables, render
plots, and write Markdown reports. They do not change force-field evaluation or
MD semantics.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import math
import os
import subprocess
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from kups.polymerization.lammps import KCAL_PER_MOL_TO_EV

ATM_TO_EV_PER_A3 = 6.324209673e-7
EV_PER_A3_TO_ATM = 1.0 / ATM_TO_EV_PER_A3
BOLTZMANN_CONSTANT_EV_PER_K = 8.617333262145e-5

DEFAULT_LAMMPS_RESULT_DIR = Path(
    "results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal"
)
DEFAULT_DIRTY_KUPS_ROOT = Path(
    "examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0"
)
DEFAULT_KUPS_RESULT_DIR = Path("results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0")
DEFAULT_IMPORT_STEP1_ROOT = Path(
    "examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1"
)
DEFAULT_DIRTY_KUPS_CONFIG = "methane_lj_only_nve.yaml"
DIRTY_BASELINE_LABEL = "kups_tiny0_lj_only_dirty_baseline"

STATUS_VALUES = {
    "pass",
    "fail",
    "not_implemented",
    "not_available",
    "out_of_scope",
    "diagnostic_only",
    "expected_mismatch",
}


@dataclass(frozen=True)
class MdResult:
    """A diagnosed MD result folder."""

    root: Path
    engine: str
    label: str
    files: dict[str, Path] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ThermoBlock:
    """One LAMMPS thermo table plus normalized rows."""

    source: Path
    kind: Literal["minimization", "md", "thermo"]
    columns: list[str]
    source_rows: list[dict[str, float]]
    rows: list[dict[str, Any]]
    start_line: int


@dataclass(frozen=True)
class LammpsLogDiagnostics:
    """Parsed LAMMPS log data."""

    path: Path
    blocks: list[ThermoBlock]
    minimization_stats: dict[str, float]
    special_bonds: dict[str, list[float]]
    pppm_settings: dict[str, Any]


@dataclass(frozen=True)
class StructureData:
    """Minimal structure/topology model for diagnostics."""

    source: Path | None
    box: dict[str, Any]
    masses: dict[int, dict[str, Any]]
    atoms: list[dict[str, Any]]
    bonds: list[dict[str, Any]]
    angles: list[dict[str, Any]]
    coefficients: dict[str, dict[str, Any]]
    semantics: dict[str, Any]


@dataclass(frozen=True)
class KupsDiagnostics:
    """Parsed kUPS result data."""

    result: MdResult
    config: dict[str, Any]
    hdf5_path: Path | None
    thermo_rows: list[dict[str, Any]]
    init_structure: StructureData | None
    hdf5_status: str
    hdf5_message: str


@dataclass(frozen=True)
class DiagnosticTables:
    """Normalized table payload written to ``diagnostics/data``."""

    thermo_rows: list[dict[str, Any]] = field(default_factory=list)
    static_geometry_rows: list[dict[str, Any]] = field(default_factory=list)
    static_energy_rows: list[dict[str, Any]] = field(default_factory=list)
    pair_rows: list[dict[str, Any]] = field(default_factory=list)
    bond_rows: list[dict[str, Any]] = field(default_factory=list)
    angle_rows: list[dict[str, Any]] = field(default_factory=list)
    capability_rows: list[dict[str, Any]] = field(default_factory=list)
    status_rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class DiagnosticsArtifacts:
    """Generated report artifact paths."""

    output_dir: Path
    data_files: dict[str, Path]
    plot_files: dict[str, Path]
    report: Path
    tables: DiagnosticTables


def parse_lammps_md_log(path: str | Path) -> LammpsLogDiagnostics:
    """Parse LAMMPS thermo tables from a log file.

    The parser is block-oriented and does not require the file to be named
    ``log.tiny``. Energy values from LAMMPS ``real`` units are preserved in
    source columns and normalized to eV in companion columns.
    """

    log_path = Path(path)
    lines = log_path.read_text().splitlines()
    blocks: list[ThermoBlock] = []
    minimization_stats: dict[str, float] = {}
    special_bonds: dict[str, list[float]] = {}
    pppm_settings: dict[str, Any] = {}
    next_kind: Literal["minimization", "md", "thermo"] = "thermo"
    timestep_fs: float | None = None

    idx = 0
    while idx < len(lines):
        clean = lines[idx].strip()
        if clean.startswith("minimize "):
            next_kind = "minimization"
        elif clean.startswith("run "):
            next_kind = "md"
        elif clean.startswith("timestep "):
            parts = clean.split()
            if len(parts) >= 2:
                timestep_fs = _to_float(parts[1])
        elif "special bond factors lj:" in clean:
            special_bonds["lj"] = _parse_trailing_floats(clean, expected=3)
        elif "special bond factors coul:" in clean:
            special_bonds["coul"] = _parse_trailing_floats(clean, expected=3)
        elif clean.startswith("G vector"):
            pppm_settings["g_vector_inverse_A"] = _to_float(clean.split("=")[-1])
        elif clean.startswith("grid ="):
            pppm_settings["grid"] = [int(_to_float(x)) for x in clean.split("=")[-1].split()]
        elif clean.startswith("estimated absolute RMS force accuracy"):
            pppm_settings["estimated_absolute_rms_force_accuracy"] = _to_float(
                clean.split("=")[-1]
            )
        elif clean.startswith("Energy initial, next-to-last, final"):
            if idx + 1 < len(lines):
                values = [_to_float(x) for x in lines[idx + 1].split()[:3]]
                if len(values) == 3:
                    minimization_stats.update(
                        {
                            "energy_initial_kcal_per_mol": values[0],
                            "energy_next_to_last_kcal_per_mol": values[1],
                            "energy_final_kcal_per_mol": values[2],
                            "energy_initial_eV": values[0] * KCAL_PER_MOL_TO_EV,
                            "energy_next_to_last_eV": values[1]
                            * KCAL_PER_MOL_TO_EV,
                            "energy_final_eV": values[2] * KCAL_PER_MOL_TO_EV,
                        }
                    )

        if _is_thermo_header(clean):
            columns = clean.split()
            source_rows: list[dict[str, float]] = []
            start_line = idx + 1
            idx += 1
            while idx < len(lines):
                row_line = lines[idx].strip()
                if not row_line:
                    idx += 1
                    continue
                parts = row_line.split()
                if len(parts) < len(columns) or not _all_numeric(parts[: len(columns)]):
                    break
                source_rows.append(
                    {column: _to_float(value) for column, value in zip(columns, parts)}
                )
                idx += 1
            rows = _normalize_lammps_thermo_rows(
                source_rows,
                kind=next_kind,
                timestep_fs=timestep_fs,
            )
            blocks.append(
                ThermoBlock(
                    source=log_path,
                    kind=next_kind,
                    columns=columns,
                    source_rows=source_rows,
                    rows=rows,
                    start_line=start_line,
                )
            )
            next_kind = "thermo"
            continue
        idx += 1

    return LammpsLogDiagnostics(
        path=log_path,
        blocks=blocks,
        minimization_stats=minimization_stats,
        special_bonds=special_bonds,
        pppm_settings=pppm_settings,
    )


def load_lammps_structure(
    data_file: str | Path,
    *,
    init_file: str | Path | None = None,
    settings_file: str | Path | None = None,
    charges_file: str | Path | None = None,
) -> StructureData:
    """Read a LAMMPS data file and optional Moltemplate fragments."""

    data_path = Path(data_file)
    parsed = _parse_lammps_data_file(data_path)
    semantics: dict[str, Any] = {}
    coefficients = parsed["coefficients"]
    charge_overrides: dict[int, float] = {}

    if init_file is not None and Path(init_file).exists():
        semantics = _parse_lammps_init(Path(init_file))
    if settings_file is not None and Path(settings_file).exists():
        settings = _parse_lammps_settings(Path(settings_file))
        coefficients = _merge_coefficients(coefficients, settings["coefficients"])
        charge_overrides.update(settings["charge_overrides"])
    if charges_file is not None and Path(charges_file).exists():
        charges = _parse_lammps_settings(Path(charges_file))
        charge_overrides.update(charges["charge_overrides"])

    atoms = []
    for atom in parsed["atoms"]:
        item = dict(atom)
        if item["type"] in charge_overrides:
            item["original_charge_e"] = item["charge_e"]
            item["charge_e"] = charge_overrides[item["type"]]
            item["charge_source"] = "charge_override"
        atoms.append(item)

    return StructureData(
        source=data_path,
        box=parsed["box"],
        masses=parsed["masses"],
        atoms=sorted(atoms, key=lambda row: row["id"]),
        bonds=sorted(parsed["bonds"], key=lambda row: row["id"]),
        angles=sorted(parsed["angles"], key=lambda row: row["id"]),
        coefficients=coefficients,
        semantics=semantics,
    )


def discover_lammps_result(result_dir: str | Path) -> MdResult:
    """Discover common LAMMPS files in a result directory."""

    root = Path(result_dir)
    files: dict[str, Path] = {}
    log_candidates = sorted(
        [path for path in root.iterdir() if path.is_file() and path.name.startswith("log")]
    )
    if log_candidates:
        preferred = root / "log.tiny"
        files["log"] = preferred if preferred.exists() else log_candidates[0]
    for role, name in {
        "data": "system.data",
        "init": "system.in.init",
        "settings": "system.in.settings",
        "charges": "system.in.charges",
        "final_data": "tiny_oplsaa_methane_final.data",
    }.items():
        path = root / name
        if path.exists():
            files[role] = path
    return MdResult(root=root, engine="lammps", label=root.name, files=files)


def discover_kups_result(
    kups_result_dir: str | Path,
    *,
    dirty_kups_root: str | Path | None = None,
    import_step1_root: str | Path | None = DEFAULT_IMPORT_STEP1_ROOT,
) -> MdResult:
    """Discover common kUPS files in a result directory."""

    root = Path(kups_result_dir)
    dirty_root = Path(dirty_kups_root) if dirty_kups_root is not None else None
    step1_root = Path(import_step1_root) if import_step1_root is not None else None
    files: dict[str, Path] = {}
    for candidate in [
        root / "methane_lj_only_nve.h5",
        *(sorted(root.glob("*.h5")) if root.exists() else []),
    ]:
        if candidate.exists():
            files["hdf5"] = candidate
            break
    for candidate in [
        root / DEFAULT_DIRTY_KUPS_CONFIG,
        *((dirty_root / DEFAULT_DIRTY_KUPS_CONFIG,) if dirty_root is not None else ()),
    ]:
        if candidate.exists():
            files["config"] = candidate
            break
    if dirty_root is not None:
        for role, name in {
            "resolved": "resolved_oplsaa_tiny.yaml",
            "cif": "methane_oplsaa_tiny.cif",
        }.items():
            candidate = dirty_root / name
            if candidate.exists():
                files[role] = candidate
    if step1_root is not None:
        for role, name in {
            "step1_resolved": "resolved.yaml",
            "step1_report": "REPORT.md",
            "step1_expected": "expected.yaml",
        }.items():
            candidate = step1_root / name
            if candidate.exists():
                files[role] = candidate
    return MdResult(
        root=root,
        engine="kups",
        label=DIRTY_BASELINE_LABEL,
        files=files,
        metadata={
            "dirty_kups_root": str(dirty_root) if dirty_root else None,
            "import_step1_root": str(step1_root) if step1_root else None,
        },
    )


def collect_lammps_diagnostics(result: MdResult) -> DiagnosticTables:
    """Collect normalized diagnostics for a LAMMPS result."""

    log = (
        parse_lammps_md_log(result.files["log"])
        if "log" in result.files
        else LammpsLogDiagnostics(
            path=result.root / "log",
            blocks=[],
            minimization_stats={},
            special_bonds={},
            pppm_settings={},
        )
    )
    structure = (
        load_lammps_structure(
            result.files["data"],
            init_file=result.files.get("init"),
            settings_file=result.files.get("settings"),
            charges_file=result.files.get("charges"),
        )
        if "data" in result.files
        else None
    )

    thermo_rows = list(itertools.chain.from_iterable(block.rows for block in log.blocks))
    energy_rows = _static_energy_rows_for_lammps(log)
    geometry_rows: list[dict[str, Any]] = []
    bond_rows: list[dict[str, Any]] = []
    angle_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    if structure is not None:
        geometry_rows = compute_static_geometry_rows(structure)
        bond_rows = compute_bond_diagnostics(structure)
        angle_rows = compute_angle_diagnostics(structure)
        pair_rows = compute_pair_diagnostics(
            structure,
            special_bonds=log.special_bonds
            or structure.semantics.get("special_bonds")
            or {"lj": [0.0, 0.0, 0.5], "coul": [0.0, 0.0, 0.5]},
        )
    return DiagnosticTables(
        thermo_rows=thermo_rows,
        static_geometry_rows=geometry_rows,
        static_energy_rows=energy_rows,
        pair_rows=pair_rows,
        bond_rows=bond_rows,
        angle_rows=angle_rows,
        capability_rows=_capability_rows(),
        status_rows=_status_rows_for_engine("lammps", has_thermo=bool(thermo_rows)),
    )


def collect_kups_diagnostics(result: MdResult) -> DiagnosticTables:
    """Collect normalized diagnostics for a kUPS result."""

    parsed = read_kups_diagnostics(result)
    status_rows = _status_rows_for_engine(
        "kups",
        has_thermo=bool(parsed.thermo_rows),
        hdf5_status=parsed.hdf5_status,
        hdf5_message=parsed.hdf5_message,
    )
    energy_rows = _static_energy_rows_for_kups(parsed)
    geometry_rows: list[dict[str, Any]] = []
    bond_rows: list[dict[str, Any]] = []
    angle_rows: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    if parsed.init_structure is not None:
        geometry_rows = compute_static_geometry_rows(parsed.init_structure)
        bond_rows = compute_bond_diagnostics(parsed.init_structure)
        angle_rows = compute_angle_diagnostics(parsed.init_structure)
        pair_rows = compute_pair_diagnostics(
            parsed.init_structure,
            special_bonds={"lj": [1.0, 1.0, 1.0], "coul": [1.0, 1.0, 1.0]},
            dirty_kups=True,
        )
    return DiagnosticTables(
        thermo_rows=parsed.thermo_rows,
        static_geometry_rows=geometry_rows,
        static_energy_rows=energy_rows,
        pair_rows=pair_rows,
        bond_rows=bond_rows,
        angle_rows=angle_rows,
        capability_rows=_capability_rows(),
        status_rows=status_rows,
    )


def read_kups_diagnostics(result: MdResult) -> KupsDiagnostics:
    """Read kUPS config and optional HDF5 trajectory data."""

    config = _read_yaml_file(result.files.get("config")) if "config" in result.files else {}
    hdf5_path = result.files.get("hdf5")
    thermo_rows: list[dict[str, Any]] = []
    init_structure: StructureData | None = None
    hdf5_status = "not_available"
    hdf5_message = "No kUPS HDF5 file was discovered."

    if hdf5_path is not None:
        try:
            thermo_rows, init_structure = _read_kups_hdf5(
                hdf5_path,
                config=config,
                resolved_path=result.files.get("resolved"),
            )
            hdf5_status = "diagnostic_only"
            hdf5_message = "kUPS HDF5 trajectory was read."
        except ModuleNotFoundError as exc:
            hdf5_status = "not_available"
            hdf5_message = f"HDF5 reader dependency is unavailable: {exc.name}."
        except OSError as exc:
            hdf5_status = "not_available"
            hdf5_message = f"kUPS HDF5 could not be read: {exc}."
        except (KeyError, ValueError) as exc:
            hdf5_status = "not_available"
            hdf5_message = f"kUPS HDF5 layout was not recognized: {exc}."

    if init_structure is None and "resolved" in result.files:
        init_structure = structure_from_resolved_yaml(result.files["resolved"])

    return KupsDiagnostics(
        result=result,
        config=config,
        hdf5_path=hdf5_path,
        thermo_rows=thermo_rows,
        init_structure=init_structure,
        hdf5_status=hdf5_status,
        hdf5_message=hdf5_message,
    )


def structure_from_resolved_yaml(path: str | Path) -> StructureData:
    """Build structure diagnostics from a Step 0/1 resolved YAML file."""

    resolved_path = Path(path)
    data = _read_yaml_file(resolved_path)
    atoms = []
    for atom in data.get("atoms", []):
        atoms.append(
            {
                "id": int(atom["id"]),
                "molecule": int(atom.get("molecule", 1)),
                "type": int(atom["type"]),
                "charge_e": float(atom.get("charge_e", 0.0)),
                "position_A": [
                    float(x)
                    for x in atom.get("position_A", atom.get("position_angstrom", []))
                ],
            }
        )
    masses = {
        int(type_id): {
            "mass_amu": float(value.get("mass_amu", value.get("mass", 1.0))),
            "label": value.get("label"),
        }
        for type_id, value in data.get("atom_types", data.get("masses", {})).items()
    }
    coefficients = {
        "pair": {},
        "bond": {
            str(type_id): {
                "k_eV_per_A2": coeff.get(
                    "k_eV_per_angstrom2",
                    coeff.get("converted_units", {}).get("k_eV_per_A2"),
                ),
                "r0_A": coeff.get(
                    "r0_angstrom",
                    coeff.get("r0_A", coeff.get("converted_units", {}).get("r0_A")),
                ),
                "raw": coeff,
            }
            for type_id, coeff in data.get("bond_types", {}).items()
        },
        "angle": {
            str(type_id): {
                "k_eV_per_rad2": coeff.get(
                    "k_eV_per_rad2",
                    coeff.get("converted_units", {}).get("k_eV_per_rad2"),
                ),
                "theta0_degree": coeff.get(
                    "theta0_degree",
                    coeff.get("converted_units", {}).get("theta0_degree"),
                ),
                "raw": coeff,
            }
            for type_id, coeff in data.get("angle_types", {}).items()
        },
    }
    atom_types = data.get("atom_types", {})
    for type_i, type_data in atom_types.items():
        lj = type_data.get("lj", {})
        if lj:
            key = f"{int(type_i)}-{int(type_i)}"
            coefficients["pair"][key] = {
                "type_i": int(type_i),
                "type_j": int(type_i),
                "epsilon_eV": lj.get("epsilon_eV"),
                "sigma_A": lj.get("sigma_angstrom", lj.get("sigma_A")),
                "raw": type_data,
            }

    box = data.get("box", {})
    if "xlo" in box:
        box = dict(box)
    return StructureData(
        source=resolved_path,
        box=box,
        masses=masses,
        atoms=sorted(atoms, key=lambda row: row["id"]),
        bonds=[dict(row) for row in data.get("bonds", [])],
        angles=[dict(row) for row in data.get("angles", [])],
        coefficients=coefficients,
        semantics=data.get("lammps_semantics", {}),
    )


def compute_static_geometry_rows(structure: StructureData) -> list[dict[str, Any]]:
    """Compute local and global structure diagnostics."""

    rows: list[dict[str, Any]] = []
    atoms_by_id = {atom["id"]: atom for atom in structure.atoms}
    by_molecule: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for atom in structure.atoms:
        by_molecule[int(atom.get("molecule", 1))].append(atom)

    for axis in ("x", "y", "z"):
        lo_key = f"{axis}lo"
        hi_key = f"{axis}hi"
        if lo_key in structure.box and hi_key in structure.box:
            rows.append(
                {
                    "quantity": f"box_length_{axis}",
                    "molecule_id": "",
                    "value": float(structure.box[hi_key]) - float(structure.box[lo_key]),
                    "unit": "Angstrom",
                    "status": "diagnostic_only",
                    "note": "orthogonal periodic box length",
                }
            )

    for molecule_id, atoms in sorted(by_molecule.items()):
        masses = [_atom_mass(structure, atom) for atom in atoms]
        positions = [atom["position_A"] for atom in atoms]
        total_mass = sum(masses) or float(len(masses))
        center = [
            sum(mass * pos[axis] for mass, pos in zip(masses, positions)) / total_mass
            for axis in range(3)
        ]
        rg2 = 0.0
        for mass, pos in zip(masses, positions):
            delta = _minimum_image_vector(
                [pos[axis] - center[axis] for axis in range(3)],
                structure.box,
            )
            rg2 += mass * sum(component * component for component in delta)
        radius = math.sqrt(rg2 / total_mass) if total_mass else 0.0
        for axis, value in zip(("x", "y", "z"), center):
            rows.append(
                {
                    "quantity": f"center_of_mass_{axis}",
                    "molecule_id": molecule_id,
                    "value": value,
                    "unit": "Angstrom",
                    "status": "diagnostic_only",
                    "note": "mass-weighted center of mass",
                }
            )
        rows.append(
            {
                "quantity": "radius_of_gyration",
                "molecule_id": molecule_id,
                "value": radius,
                "unit": "Angstrom",
                "status": "diagnostic_only",
                "note": "mass-weighted molecular radius of gyration",
            }
        )

    for bond in structure.bonds:
        atom_i, atom_j = [atoms_by_id[atom_id] for atom_id in bond["atoms"]]
        rows.append(
            {
                "quantity": "bond_length",
                "molecule_id": atom_i.get("molecule", ""),
                "bond_id": bond["id"],
                "atom_ids": "-".join(str(x) for x in bond["atoms"]),
                "value": _distance(atom_i["position_A"], atom_j["position_A"], structure.box),
                "unit": "Angstrom",
                "status": "diagnostic_only",
                "note": "topology bond length",
            }
        )

    for angle in structure.angles:
        atom_i, atom_j, atom_k = [atoms_by_id[atom_id] for atom_id in angle["atoms"]]
        rows.append(
            {
                "quantity": "angle",
                "molecule_id": atom_j.get("molecule", ""),
                "angle_id": angle["id"],
                "atom_ids": "-".join(str(x) for x in angle["atoms"]),
                "value": _angle_degrees(
                    atom_i["position_A"],
                    atom_j["position_A"],
                    atom_k["position_A"],
                    structure.box,
                ),
                "unit": "degree",
                "status": "diagnostic_only",
                "note": "topology angle",
            }
        )

    if structure.atoms:
        min_distance = min(
            (
                _distance(a["position_A"], b["position_A"], structure.box)
                for a, b in itertools.combinations(structure.atoms, 2)
            ),
            default=math.nan,
        )
        rows.append(
            {
                "quantity": "minimum_image_min_pair_distance",
                "molecule_id": "",
                "value": min_distance,
                "unit": "Angstrom",
                "status": "diagnostic_only",
                "note": "minimum over all unique atom pairs",
            }
        )
    return rows


def compute_bond_diagnostics(structure: StructureData) -> list[dict[str, Any]]:
    """Compute one row per topological bond."""

    atoms_by_id = {atom["id"]: atom for atom in structure.atoms}
    rows = []
    for bond in structure.bonds:
        atom_i, atom_j = [atoms_by_id[atom_id] for atom_id in bond["atoms"]]
        coeff = structure.coefficients.get("bond", {}).get(str(bond["type"]), {})
        length = _distance(atom_i["position_A"], atom_j["position_A"], structure.box)
        r0 = _first_present(coeff, ["r0_A", "r0_angstrom"], nested="converted_units")
        rows.append(
            {
                "bond_id": bond["id"],
                "atom_ids": "-".join(str(x) for x in bond["atoms"]),
                "atom_types": f"{atom_i['type']}-{atom_j['type']}",
                "length_A": length,
                "equilibrium_length_A": r0,
                "deviation_A": _nullable_subtract(length, r0),
                "k_eV_per_A2": _first_present(
                    coeff,
                    ["k_eV_per_A2", "k_eV_per_angstrom2"],
                    nested="converted_units",
                ),
                "energy_eV": "",
                "status": "diagnostic_only",
            }
        )
    return rows


def compute_angle_diagnostics(structure: StructureData) -> list[dict[str, Any]]:
    """Compute one row per topological angle."""

    atoms_by_id = {atom["id"]: atom for atom in structure.atoms}
    rows = []
    for angle in structure.angles:
        atom_i, atom_j, atom_k = [atoms_by_id[atom_id] for atom_id in angle["atoms"]]
        coeff = structure.coefficients.get("angle", {}).get(str(angle["type"]), {})
        value = _angle_degrees(
            atom_i["position_A"], atom_j["position_A"], atom_k["position_A"], structure.box
        )
        theta0 = _first_present(
            coeff,
            ["theta0_degree"],
            nested="converted_units",
        )
        rows.append(
            {
                "angle_id": angle["id"],
                "atom_ids": "-".join(str(x) for x in angle["atoms"]),
                "atom_types": f"{atom_i['type']}-{atom_j['type']}-{atom_k['type']}",
                "angle_degree": value,
                "equilibrium_angle_degree": theta0,
                "deviation_degree": _nullable_subtract(value, theta0),
                "k_eV_per_rad2": _first_present(
                    coeff,
                    ["k_eV_per_rad2"],
                    nested="converted_units",
                ),
                "energy_eV": "",
                "status": "diagnostic_only",
            }
        )
    return rows


def compute_pair_diagnostics(
    structure: StructureData,
    *,
    special_bonds: dict[str, list[float]] | None = None,
    dirty_kups: bool = False,
) -> list[dict[str, Any]]:
    """Compute all unique atom-pair topology classes and nonbonded metadata."""

    atoms_by_id = {atom["id"]: atom for atom in structure.atoms}
    graph_classes = _classify_graph_pairs(structure.bonds)
    special_bonds = special_bonds or {"lj": [1.0, 1.0, 1.0], "coul": [1.0, 1.0, 1.0]}
    rows = []
    for atom_i, atom_j in itertools.combinations(sorted(structure.atoms, key=lambda a: a["id"]), 2):
        pair = tuple(sorted((atom_i["id"], atom_j["id"])))
        topology_class = _pair_topology_class(pair, graph_classes)
        lj_scale = _special_scale(special_bonds.get("lj", [1.0, 1.0, 1.0]), topology_class)
        coul_scale = _special_scale(
            special_bonds.get("coul", [1.0, 1.0, 1.0]), topology_class
        )
        pair_coeff = _mixed_pair_coeff(structure, int(atom_i["type"]), int(atom_j["type"]))
        rows.append(
            {
                "atom_ids": f"{atom_i['id']}-{atom_j['id']}",
                "atom_types": f"{atom_i['type']}-{atom_j['type']}",
                "topology_class": topology_class,
                "distance_A": _distance(
                    atom_i["position_A"], atom_j["position_A"], structure.box
                ),
                "lj_scale": lj_scale,
                "coulomb_scale": coul_scale,
                "epsilon_eV": pair_coeff.get("epsilon_eV", ""),
                "sigma_A": pair_coeff.get("sigma_A", ""),
                "charge_product_e2": atom_i.get("charge_e", 0.0)
                * atom_j.get("charge_e", 0.0),
                "lj_status": "expected_mismatch"
                if dirty_kups and topology_class in {"1-2", "1-3"}
                else "diagnostic_only",
                "coulomb_status": "not_implemented" if dirty_kups else "diagnostic_only",
            }
        )
    return rows


def write_diagnostics(
    result: MdResult,
    tables: DiagnosticTables,
    output_dir: str | Path | None = None,
    *,
    comparison_inputs: tuple[MdResult, MdResult] | None = None,
    comparison_tables: tuple[DiagnosticTables, DiagnosticTables] | None = None,
) -> DiagnosticsArtifacts:
    """Write CSV tables, plot files, and ``REPORT.md`` for diagnostics."""

    out_dir = Path(output_dir) if output_dir is not None else result.root / "diagnostics"
    data_dir = out_dir / "data"
    plots_dir = out_dir / "plots"
    data_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    if result.engine == "comparison":
        thermo_files = {
            "lammps_thermo": data_dir / "lammps_thermo.csv",
            "kups_tiny0_observables": data_dir / "kups_tiny0_observables.csv",
        }
    else:
        prefix = "lammps_thermo" if result.engine == "lammps" else "kups_tiny0_observables"
        thermo_files = {prefix: data_dir / f"{prefix}.csv"}

    data_files = {
        **thermo_files,
        "static_geometry": data_dir / "static_geometry.csv",
        "static_energy_terms": data_dir / "static_energy_terms.csv",
        "pair_diagnostics": data_dir / "pair_diagnostics.csv",
        "bond_diagnostics": data_dir / "bond_diagnostics.csv",
        "angle_diagnostics": data_dir / "angle_diagnostics.csv",
        "capability_matrix": data_dir / "capability_matrix.csv",
        "status_summary": data_dir / "status_summary.csv",
    }
    if result.engine == "comparison":
        _write_csv(
            data_files["lammps_thermo"],
            [row for row in tables.thermo_rows if row.get("engine") == "lammps"],
        )
        _write_csv(
            data_files["kups_tiny0_observables"],
            [row for row in tables.thermo_rows if row.get("engine") == "kups"],
        )
    else:
        _write_csv(next(iter(thermo_files.values())), tables.thermo_rows)
    _write_csv(data_files["static_geometry"], tables.static_geometry_rows)
    _write_csv(data_files["static_energy_terms"], tables.static_energy_rows)
    _write_csv(data_files["pair_diagnostics"], tables.pair_rows)
    _write_csv(data_files["bond_diagnostics"], tables.bond_rows)
    _write_csv(data_files["angle_diagnostics"], tables.angle_rows)
    _write_csv(data_files["capability_matrix"], tables.capability_rows)
    _write_csv(data_files["status_summary"], tables.status_rows)

    if comparison_inputs and comparison_tables:
        plot_files = _write_comparison_plots(
            comparison_inputs,
            comparison_tables,
            plots_dir,
        )
        _write_comparison_report(
            out_dir / "REPORT.md",
            result,
            comparison_inputs,
            comparison_tables,
            data_files,
            plot_files,
        )
    else:
        plot_files = _write_single_result_plots(result, tables, plots_dir)
        _write_report(out_dir / "REPORT.md", result, tables, data_files, plot_files)

    return DiagnosticsArtifacts(
        output_dir=out_dir,
        data_files=data_files,
        plot_files=plot_files,
        report=out_dir / "REPORT.md",
        tables=tables,
    )


def write_lammps_diagnostics(
    lammps_result_dir: str | Path = DEFAULT_LAMMPS_RESULT_DIR,
    *,
    output_dir: str | Path | None = None,
) -> DiagnosticsArtifacts:
    """Discover, collect, and write LAMMPS diagnostics."""

    result = discover_lammps_result(lammps_result_dir)
    tables = collect_lammps_diagnostics(result)
    return write_diagnostics(result, tables, output_dir)


def write_kups_diagnostics(
    kups_result_dir: str | Path = DEFAULT_KUPS_RESULT_DIR,
    *,
    dirty_kups_root: str | Path | None = DEFAULT_DIRTY_KUPS_ROOT,
    import_step1_root: str | Path | None = DEFAULT_IMPORT_STEP1_ROOT,
    output_dir: str | Path | None = None,
) -> DiagnosticsArtifacts:
    """Discover, collect, and write dirty kUPS baseline diagnostics."""

    result = discover_kups_result(
        kups_result_dir,
        dirty_kups_root=dirty_kups_root,
        import_step1_root=import_step1_root,
    )
    tables = collect_kups_diagnostics(result)
    return write_diagnostics(result, tables, output_dir)


def write_comparison_diagnostics(
    *,
    lammps_result_dir: str | Path = DEFAULT_LAMMPS_RESULT_DIR,
    kups_result_dir: str | Path = DEFAULT_KUPS_RESULT_DIR,
    dirty_kups_root: str | Path | None = DEFAULT_DIRTY_KUPS_ROOT,
    import_step1_root: str | Path | None = DEFAULT_IMPORT_STEP1_ROOT,
    output_dir: str | Path | None = None,
) -> DiagnosticsArtifacts:
    """Write side-by-side comparison diagnostics from individual tables."""

    lammps_result = discover_lammps_result(lammps_result_dir)
    kups_result = discover_kups_result(
        kups_result_dir,
        dirty_kups_root=dirty_kups_root,
        import_step1_root=import_step1_root,
    )
    lammps_tables = collect_lammps_diagnostics(lammps_result)
    kups_tables = collect_kups_diagnostics(kups_result)
    comparison_out = (
        Path(output_dir)
        if output_dir is not None
        else Path(kups_result_dir) / "diagnostics" / "comparison"
        if kups_result_dir is not None
        else Path(lammps_result_dir) / "diagnostics" / "comparison"
    )
    combined = _merge_comparison_tables(lammps_tables, kups_tables)
    return write_diagnostics(
        MdResult(
            root=comparison_out,
            engine="comparison",
            label="lammps_vs_kups",
            metadata={"import_step1_root": str(import_step1_root)},
        ),
        combined,
        comparison_out,
        comparison_inputs=(lammps_result, kups_result),
        comparison_tables=(lammps_tables, kups_tables),
    )


def run_dirty_baseline(dirty_kups_root: str | Path) -> subprocess.CompletedProcess[str]:
    """Run the existing dirty baseline config without creating a new config."""

    root = Path(dirty_kups_root)
    config = root / DEFAULT_DIRTY_KUPS_CONFIG
    if not config.exists():
        raise FileNotFoundError(f"dirty baseline config not found: {config}")
    env = os.environ.copy()
    env.setdefault("JAX_PLATFORMS", "cpu")
    return subprocess.run(
        ["conda", "run", "-n", "kups-env", "kups_md_lj", str(config)],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def build_cli_parser() -> argparse.ArgumentParser:
    """Build the diagnostics CLI parser."""

    parser = argparse.ArgumentParser(description="Generate MD diagnostics reports.")
    parser.add_argument(
        "--mode",
        choices=("lammps", "kups", "compare"),
        default="compare",
        help="Diagnostics mode.",
    )
    parser.add_argument(
        "--lammps-result-dir",
        type=Path,
        default=DEFAULT_LAMMPS_RESULT_DIR,
        help="LAMMPS result directory.",
    )
    parser.add_argument(
        "--dirty-kups-root",
        type=Path,
        default=DEFAULT_DIRTY_KUPS_ROOT,
        help="Dirty kUPS tiny_0 example root.",
    )
    parser.add_argument(
        "--kups-result-dir",
        type=Path,
        default=DEFAULT_KUPS_RESULT_DIR,
        help="kUPS result directory.",
    )
    parser.add_argument(
        "--import-step1-root",
        type=Path,
        default=DEFAULT_IMPORT_STEP1_ROOT,
        help="Step 1 import baseline root, recorded in reports when present.",
    )
    parser.add_argument(
        "--comparison-out",
        type=Path,
        default=None,
        help="Explicit comparison diagnostics output directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Explicit output directory for lammps/kups modes.",
    )
    parser.add_argument(
        "--run-dirty-baseline",
        action="store_true",
        help="Run the existing dirty kUPS config before collecting diagnostics.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for diagnostics generation."""

    args = build_cli_parser().parse_args(argv)
    if args.run_dirty_baseline:
        completed = run_dirty_baseline(args.dirty_kups_root)
        if completed.returncode != 0:
            print(completed.stdout)
            print(completed.stderr)
            print(
                "Dirty baseline run failed; continuing diagnostics with available files."
            )

    if args.mode == "lammps":
        artifacts = write_lammps_diagnostics(args.lammps_result_dir, output_dir=args.output_dir)
    elif args.mode == "kups":
        artifacts = write_kups_diagnostics(
            args.kups_result_dir,
            dirty_kups_root=args.dirty_kups_root,
            import_step1_root=args.import_step1_root,
            output_dir=args.output_dir,
        )
    else:
        artifacts = write_comparison_diagnostics(
            lammps_result_dir=args.lammps_result_dir,
            kups_result_dir=args.kups_result_dir,
            dirty_kups_root=args.dirty_kups_root,
            import_step1_root=args.import_step1_root,
            output_dir=args.comparison_out,
        )
    print(f"Wrote diagnostics report: {artifacts.report}")
    return 0


def _normalize_lammps_thermo_rows(
    source_rows: list[dict[str, float]],
    *,
    kind: Literal["minimization", "md", "thermo"],
    timestep_fs: float | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first_step = source_rows[0].get("Step", 0.0) if source_rows else 0.0
    for source in source_rows:
        step = source.get("Step", "")
        pot_kcal = source.get("PotEng", source.get("PE", math.nan))
        total_kcal = source.get("TotEng", source.get("E_total", math.nan))
        temp = source.get("Temp", math.nan)
        pressure = source.get("Press", math.nan)
        row = {
            "engine": "lammps",
            "block": kind,
            "step": int(step) if isinstance(step, float) and step.is_integer() else step,
            "time_fs": (float(step) - first_step) * timestep_fs
            if kind == "md" and timestep_fs is not None and step != ""
            else "",
            "temperature_K": temp,
            "potential_energy_source_kcal_per_mol": pot_kcal,
            "potential_energy_eV": pot_kcal * KCAL_PER_MOL_TO_EV
            if _is_finite(pot_kcal)
            else "",
            "total_energy_source_kcal_per_mol": total_kcal,
            "total_energy_eV": total_kcal * KCAL_PER_MOL_TO_EV
            if _is_finite(total_kcal)
            else "",
            "kinetic_energy_eV": (total_kcal - pot_kcal) * KCAL_PER_MOL_TO_EV
            if _is_finite(total_kcal) and _is_finite(pot_kcal)
            else "",
            "pressure_atm": pressure,
            "pressure_eV_per_A3": pressure * ATM_TO_EV_PER_A3
            if _is_finite(pressure)
            else "",
            "volume_A3": source.get("Volume", ""),
            "energy_drift_eV": "",
            "status": "diagnostic_only",
        }
        rows.append(row)
    if kind == "md" and rows:
        baseline = rows[0]["total_energy_eV"]
        if baseline != "":
            for row in rows:
                row["energy_drift_eV"] = row["total_energy_eV"] - baseline
    return rows


def _read_kups_hdf5(
    hdf5_path: Path,
    *,
    config: dict[str, Any],
    resolved_path: Path | None,
) -> tuple[list[dict[str, Any]], StructureData | None]:
    import h5py
    import numpy as np

    with h5py.File(hdf5_path, "r") as handle:
        step_group = handle["group.step"]
        potential = np.asarray(step_group["array.potential_energy"])[:, 0]
        kinetic = np.asarray(step_group["array.kinetic_energy"])[:, 0]
        volume = np.asarray(step_group["array.volume"])[:, 0]
        stress = np.asarray(step_group["array.stress_tensor"])[:, 0, :, :]
        rows = []
        dt_fs = _config_time_step_fs(config)
        for idx, (pe, ke, vol, tensor) in enumerate(
            zip(potential, kinetic, volume, stress, strict=False)
        ):
            pressure_eva3 = float(np.trace(tensor) / 3.0)
            total = float(pe + ke)
            rows.append(
                {
                    "engine": "kups",
                    "block": "md",
                    "step": idx + 1,
                    "time_fs": idx * dt_fs if dt_fs is not None else "",
                    "temperature_K": _kups_temperature(ke, handle, idx),
                    "potential_energy_eV": float(pe),
                    "kinetic_energy_eV": float(ke),
                    "total_energy_eV": total,
                    "pressure_eV_per_A3": pressure_eva3,
                    "pressure_atm": pressure_eva3 * EV_PER_A3_TO_ATM,
                    "volume_A3": float(vol),
                    "energy_drift_eV": "",
                    "status": "expected_mismatch",
                }
            )
        if rows:
            baseline = rows[0]["total_energy_eV"]
            for row in rows:
                row["energy_drift_eV"] = row["total_energy_eV"] - baseline

        structure = None
        if resolved_path is not None and resolved_path.exists():
            structure = structure_from_resolved_yaml(resolved_path)
        else:
            structure = _structure_from_hdf5(handle, hdf5_path)
    return rows, structure


def _structure_from_hdf5(handle: Any, source: Path) -> StructureData:
    import numpy as np

    init = handle["group.init"]
    positions = np.asarray(init["array.atoms.data.positions"])
    masses_arr = np.asarray(init["array.atoms.data.masses"])
    charges = np.asarray(init["array.atoms.data.charges"])
    atomic_numbers = np.asarray(init["array.atoms.data.atomic_numbers"])
    atoms = []
    masses: dict[int, dict[str, Any]] = {}
    for idx, (position, mass, charge, atomic_number) in enumerate(
        zip(positions, masses_arr, charges, atomic_numbers, strict=False), start=1
    ):
        atom_type = int(atomic_number)
        masses.setdefault(atom_type, {"mass_amu": float(mass), "label": str(atom_type)})
        atoms.append(
            {
                "id": idx,
                "molecule": 1,
                "type": atom_type,
                "charge_e": float(charge),
                "position_A": [float(x) for x in position],
            }
        )
    cell = np.asarray(init["array.systems.data.cell.frame.tril"])[0]
    lx, ly, lz = float(cell[0]), float(cell[1]), float(cell[2])
    return StructureData(
        source=source,
        box={"xlo": -lx / 2, "xhi": lx / 2, "ylo": -ly / 2, "yhi": ly / 2, "zlo": -lz / 2, "zhi": lz / 2},
        masses=masses,
        atoms=atoms,
        bonds=[],
        angles=[],
        coefficients={"pair": {}, "bond": {}, "angle": {}},
        semantics={},
    )


def _kups_temperature(kinetic_energy: float, handle: Any, idx: int) -> float:
    masses = handle["group.step/array.atoms.data.masses"][idx]
    n_atoms = len(masses)
    dof = max(1, 3 * n_atoms - 3)
    return float(2.0 * kinetic_energy / (dof * BOLTZMANN_CONSTANT_EV_PER_K))


def _config_time_step_fs(config: dict[str, Any]) -> float | None:
    try:
        return float(config.get("md", {}).get("time_step"))
    except (TypeError, ValueError):
        return None


def _static_energy_rows_for_lammps(log: LammpsLogDiagnostics) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    stats = log.minimization_stats
    for label, source_key, ev_key in [
        ("potential_total_min_initial", "energy_initial_kcal_per_mol", "energy_initial_eV"),
        (
            "potential_total_min_next_to_last",
            "energy_next_to_last_kcal_per_mol",
            "energy_next_to_last_eV",
        ),
        ("potential_total_min_final", "energy_final_kcal_per_mol", "energy_final_eV"),
    ]:
        rows.append(
            {
                "engine": "lammps",
                "term": label,
                "value_eV": stats.get(ev_key, ""),
                "source_value": stats.get(source_key, ""),
                "source_unit": "kcal/mol",
                "status": "diagnostic_only" if ev_key in stats else "not_available",
                "note": "LAMMPS minimization stats",
            }
        )
    rows.extend(_missing_energy_term_rows("lammps"))
    return rows


def _static_energy_rows_for_kups(parsed: KupsDiagnostics) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first = parsed.thermo_rows[0] if parsed.thermo_rows else {}
    for term, key, status in [
        ("potential total", "potential_energy_eV", "expected_mismatch"),
        ("kinetic", "kinetic_energy_eV", "diagnostic_only"),
        ("total energy", "total_energy_eV", "expected_mismatch"),
    ]:
        rows.append(
            {
                "engine": "kups",
                "term": term,
                "value_eV": first.get(key, ""),
                "source_value": first.get(key, ""),
                "source_unit": "eV",
                "status": status if key in first else "not_available",
                "note": "dirty LJ-only baseline HDF5 first MD row"
                if key in first
                else parsed.hdf5_message,
            }
        )
    for term in [
        "harmonic bond",
        "harmonic angle",
        "Coulomb/PPPM",
        "special-pair correction",
    ]:
        rows.append(
            {
                "engine": "kups",
                "term": term,
                "value_eV": "",
                "source_value": "",
                "source_unit": "",
                "status": "not_implemented",
                "note": "not wired into the dirty tiny_0 LJ-only baseline",
            }
        )
    rows.append(
        {
            "engine": "kups",
            "term": "LJ nonbonded",
            "value_eV": first.get("potential_energy_eV", ""),
            "source_value": first.get("potential_energy_eV", ""),
            "source_unit": "eV",
            "status": "expected_mismatch" if first else "not_available",
            "note": "dirty kUPS LJ uses Lorentz-Berthelot and lacks special-pair exclusions",
        }
    )
    return rows


def _missing_energy_term_rows(engine: str) -> list[dict[str, Any]]:
    rows = []
    for term, status, note in [
        (
            "harmonic bond",
            "diagnostic_only",
            "LAMMPS log does not decompose this term in the current fixture",
        ),
        (
            "harmonic angle",
            "diagnostic_only",
            "LAMMPS log does not decompose this term in the current fixture",
        ),
        (
            "LJ nonbonded",
            "diagnostic_only",
            "LAMMPS log does not decompose this term in the current fixture",
        ),
        (
            "Coulomb/PPPM",
            "diagnostic_only",
            "LAMMPS log does not decompose this term in the current fixture",
        ),
        (
            "special-pair correction",
            "diagnostic_only",
            "implied by topology and special_bonds settings",
        ),
    ]:
        rows.append(
            {
                "engine": engine,
                "term": term,
                "value_eV": "",
                "source_value": "",
                "source_unit": "",
                "status": status,
                "note": note,
            }
        )
    return rows


def _capability_rows() -> list[dict[str, Any]]:
    return [
        {
            "capability": "atom_style full topology",
            "lammps": "yes",
            "step1_import": "yes",
            "dirty_kups_tiny0": "partial",
            "step2_harness": "reads",
        },
        {
            "capability": "harmonic bonds",
            "lammps": "yes",
            "step1_import": "parameters only",
            "dirty_kups_tiny0": "no",
            "step2_harness": "reports missing",
        },
        {
            "capability": "harmonic angles",
            "lammps": "yes",
            "step1_import": "parameters only",
            "dirty_kups_tiny0": "no",
            "step2_harness": "reports missing",
        },
        {
            "capability": "LJ pair coeffs",
            "lammps": "yes",
            "step1_import": "parameters only",
            "dirty_kups_tiny0": "partial",
            "step2_harness": "reports",
        },
        {
            "capability": "geometric mixing",
            "lammps": "yes",
            "step1_import": "recorded",
            "dirty_kups_tiny0": "no",
            "step2_harness": "reports missing",
        },
        {
            "capability": "special_bonds LJ",
            "lammps": "yes",
            "step1_import": "recorded",
            "dirty_kups_tiny0": "no",
            "step2_harness": "reports missing",
        },
        {
            "capability": "charges",
            "lammps": "yes",
            "step1_import": "yes",
            "dirty_kups_tiny0": "no active Coulomb",
            "step2_harness": "reports",
        },
        {
            "capability": "PPPM Coulomb",
            "lammps": "yes",
            "step1_import": "settings only",
            "dirty_kups_tiny0": "no",
            "step2_harness": "reports missing",
        },
        {
            "capability": "minimization",
            "lammps": "yes",
            "step1_import": "protocol only",
            "dirty_kups_tiny0": "no",
            "step2_harness": "out of scope",
        },
        {
            "capability": "exact velocity create",
            "lammps": "yes",
            "step1_import": "protocol only",
            "dirty_kups_tiny0": "no",
            "step2_harness": "out of scope",
        },
        {
            "capability": "NVE smoke test",
            "lammps": "yes",
            "step1_import": "protocol only",
            "dirty_kups_tiny0": "dirty approximation",
            "step2_harness": "diagnostic",
        },
    ]


def _status_rows_for_engine(
    engine: str,
    *,
    has_thermo: bool,
    hdf5_status: str | None = None,
    hdf5_message: str | None = None,
) -> list[dict[str, Any]]:
    rows = [
        {
            "quantity": "thermo_timeseries",
            "status": "diagnostic_only" if has_thermo else "not_available",
            "note": "time-series diagnostics were parsed"
            if has_thermo
            else "no thermo or HDF5 trajectory was available",
        },
        {
            "quantity": "full_reproduction",
            "status": "expected_mismatch" if engine == "kups" else "diagnostic_only",
            "note": "Step 2 does not claim reproduction",
        },
    ]
    if hdf5_status is not None:
        rows.append(
            {
                "quantity": "kups_hdf5",
                "status": hdf5_status,
                "note": hdf5_message or "",
            }
        )
    return rows


def _write_report(
    path: Path,
    result: MdResult,
    tables: DiagnosticTables,
    data_files: dict[str, Path],
    plot_files: dict[str, Path],
) -> None:
    plots_ok = all(file.exists() and file.stat().st_size > 0 for file in plot_files.values())
    missing_files = [
        str(file)
        for file in itertools.chain(data_files.values(), plot_files.values())
        if not file.exists() or file.stat().st_size == 0
    ]
    lammps_ref = "LAMMPS is the current reference."
    dirty = (
        "`moltemplate_oplsaa_tiny_0` is a dirty LJ-only kUPS baseline."
        if result.engine == "kups"
        else "The dirty kUPS baseline is not part of this single-result report."
    )
    energy_lines = _markdown_table(
        ["Term", "Value eV", "Source value", "Source unit", "Status", "Note"],
        [
            [
                row.get("term", ""),
                _format_number(row.get("value_eV", "")),
                _format_number(row.get("source_value", "")),
                row.get("source_unit", ""),
                row.get("status", ""),
                row.get("note", ""),
            ]
            for row in tables.static_energy_rows
        ],
    )
    capability_lines = _markdown_table(
        ["Capability", "LAMMPS", "Step 1 import", "Dirty kUPS tiny_0", "Step 2 harness"],
        [
            [
                row["capability"],
                row["lammps"],
                row["step1_import"],
                row["dirty_kups_tiny0"],
                row["step2_harness"],
            ]
            for row in tables.capability_rows
        ],
    )
    plot_lines = "\n".join(
        f"- [{name}]({path.relative_to(path.parent.parent).as_posix()})"
        for name, path in sorted(plot_files.items())
    )
    status_note = (
        "All data files and plots were generated."
        if not missing_files and plots_ok
        else "Some optional data or plots are unavailable: " + ", ".join(missing_files)
    )
    special_note = ""
    if tables.pair_rows:
        one_four = sum(1 for row in tables.pair_rows if row["topology_class"] == "1-4")
        if one_four == 0:
            special_note = (
                "\nMethane has no 1-4 special pairs, so `special_bonds 0.0 0.0 0.5` "
                "cannot be fully validated by methane alone."
            )

    text = f"""# MD Diagnostics Report

## Summary

{lammps_ref}
{dirty}
Step 2 does not claim reproduction.
{status_note}

- engine: `{result.engine}`
- label: `{result.label}`
- result folder: `{result.root}`

## Source Files

{_source_file_list(result)}

## Capability Matrix

{capability_lines}

## Static Energy

{energy_lines}

Missing physical terms are represented as statuses, not numeric zero.

## Structural Observables

- bond rows: {len(tables.bond_rows)}
- angle rows: {len(tables.angle_rows)}
- pair rows: {len(tables.pair_rows)}
{special_note}

Bond-length deviations primarily exercise bond parameter import and harmonic
bond wiring in later steps. Angle deviations primarily exercise angle parameter
import and degree/radian convention handling. Pair-distance class diagnostics
reveal whether later LJ and Coulomb exclusions are applied to the correct
graph-distance pairs. Center of mass and radius of gyration catch wrapping,
drift, and internal-geometry mistakes.

## Dynamics

- thermo rows: {len(tables.thermo_rows)}
- energy drift is computed from MD rows only when MD rows are available

Potential-energy trends indicate missing or misapplied force-field terms.
Temperature trends are sensitive to initialization and momentum handling.
Total-energy drift is an integration and force-consistency diagnostic, but it
should not be interpreted before the static force field is correct. Pressure is
weak for one methane molecule in a 30 A box but can still catch severe virial or
unit mistakes.

## Local Pair/Bond/Angle Diagnostics

Wrong local classifications corrupt LJ and Coulomb even when a global energy
looks close by accident. Missing 1-2 and 1-3 exclusions explain why the dirty
LJ-only baseline can produce unphysical intramolecular nonbonded energy. Methane
cannot test 1-4 scaling; a later butane-like synthetic fixture should do that.

## Plots

{plot_lines}

## Known Missing Physics

- bonded harmonic bond and angle terms in the dirty kUPS baseline
- Coulomb and PPPM/Ewald electrostatics in the dirty kUPS baseline
- topology-derived special-pair exclusions and scaling
- OPLS geometric LJ mixing in the dirty kUPS baseline
- LAMMPS minimization and exact `velocity create` semantics

## Next Implementation Targets

1. Add harmonic bond and angle energy values to `static_energy_terms.csv`.
2. Add geometric mixing and explicit pair-coefficient provenance.
3. Add special-pair LJ and Coulomb masks from topology classes.
4. Add Coulomb/Ewald diagnostics and compare against LAMMPS PPPM settings.
"""
    path.write_text(text)


def _write_comparison_report(
    path: Path,
    result: MdResult,
    comparison_inputs: tuple[MdResult, MdResult],
    comparison_tables: tuple[DiagnosticTables, DiagnosticTables],
    data_files: dict[str, Path],
    plot_files: dict[str, Path],
) -> None:
    lammps_result, kups_result = comparison_inputs
    lammps_tables, kups_tables = comparison_tables
    plot_lines = "\n".join(
        f"- [{name}]({plot.relative_to(path.parent).as_posix()})"
        for name, plot in sorted(plot_files.items())
    )
    text = f"""# MD Diagnostics Comparison Report

## Summary

LAMMPS is the current reference.
`moltemplate_oplsaa_tiny_0` is a dirty LJ-only kUPS baseline.
Step 2 does not claim reproduction.
Comparison plots use two columns: LAMMPS on the left and kUPS on the right.

- LAMMPS result folder: `{lammps_result.root}`
- kUPS result folder: `{kups_result.root}`
- comparison output: `{result.root}`
- LAMMPS thermo rows: {len(lammps_tables.thermo_rows)}
- kUPS thermo rows: {len(kups_tables.thermo_rows)}

## Source Files

### LAMMPS

{_source_file_list(lammps_result)}

### kUPS

{_source_file_list(kups_result)}

## Capability Matrix

{_markdown_table(
        ["Capability", "LAMMPS", "Step 1 import", "Dirty kUPS tiny_0", "Step 2 harness"],
        [
            [
                row["capability"],
                row["lammps"],
                row["step1_import"],
                row["dirty_kups_tiny0"],
                row["step2_harness"],
            ]
            for row in lammps_tables.capability_rows
        ],
    )}

## Static Energy

{_markdown_table(
        ["Engine", "Term", "Value eV", "Source value", "Source unit", "Status", "Note"],
        [
            [
                row.get("engine", ""),
                row.get("term", ""),
                _format_number(row.get("value_eV", "")),
                _format_number(row.get("source_value", "")),
                row.get("source_unit", ""),
                row.get("status", ""),
                row.get("note", ""),
            ]
            for row in lammps_tables.static_energy_rows + kups_tables.static_energy_rows
        ],
    )}

## Structural Observables

- LAMMPS bond rows: {len(lammps_tables.bond_rows)}
- LAMMPS angle rows: {len(lammps_tables.angle_rows)}
- LAMMPS pair rows: {len(lammps_tables.pair_rows)}
- kUPS bond rows: {len(kups_tables.bond_rows)}
- kUPS angle rows: {len(kups_tables.angle_rows)}
- kUPS pair rows: {len(kups_tables.pair_rows)}

Methane has no 1-4 special pairs, so `special_bonds 0.0 0.0 0.5` cannot be
fully validated by methane alone.

## Dynamics

Energy drift is computed from MD rows only, not minimization rows. The dirty
kUPS trajectory remains `diagnostic_only` or `expected_mismatch` until
minimization, velocity initialization, bonded terms, electrostatics, special
pairs, and geometric mixing are in scope.

## Local Pair/Bond/Angle Diagnostics

The comparison reuses the normalized LAMMPS and kUPS tables written by the
individual diagnostics path. Missing local classifications or special-pair
scales are reported directly in `pair_diagnostics.csv`.

## Plots

{plot_lines}

## Known Missing Physics

- bonded harmonic bond and angle terms in the dirty kUPS baseline
- Coulomb and PPPM/Ewald electrostatics in the dirty kUPS baseline
- topology-derived special-pair exclusions and scaling
- OPLS geometric LJ mixing in the dirty kUPS baseline
- LAMMPS minimization and exact `velocity create` semantics

## Next Implementation Targets

1. Add harmonic bond and angle energy values to the same static energy table.
2. Add geometric mixing and explicit pair coefficient provenance.
3. Add special-pair LJ and Coulomb masks from topology classes.
4. Add Coulomb/Ewald diagnostics against the LAMMPS PPPM settings.
"""
    path.write_text(text)


def _write_single_result_plots(
    result: MdResult, tables: DiagnosticTables, plots_dir: Path
) -> dict[str, Path]:
    plot_files = {
        "energy_timeseries": plots_dir / "energy_timeseries.png",
        "temperature_timeseries": plots_dir / "temperature_timeseries.png",
        "pressure_timeseries": plots_dir / "pressure_timeseries.png",
        "energy_drift": plots_dir / "energy_drift.png",
        "bond_lengths": plots_dir / "bond_lengths.png",
        "angle_distribution": plots_dir / "angle_distribution.png",
        "pair_distance_classes": plots_dir / "pair_distance_classes.png",
        "static_energy_breakdown": plots_dir / "static_energy_breakdown.png",
        "missing_physics_matrix": plots_dir / "missing_physics_matrix.png",
    }
    try:
        _plot_time_series(
            tables.thermo_rows,
            plot_files["energy_timeseries"],
            y_keys=["potential_energy_eV", "total_energy_eV"],
            title=f"{result.label} energy",
            ylabel="Energy (eV)",
        )
        _plot_time_series(
            tables.thermo_rows,
            plot_files["temperature_timeseries"],
            y_keys=["temperature_K"],
            title=f"{result.label} temperature",
            ylabel="Temperature (K)",
        )
        _plot_time_series(
            tables.thermo_rows,
            plot_files["pressure_timeseries"],
            y_keys=["pressure_atm"],
            title=f"{result.label} pressure",
            ylabel="Pressure (atm)",
        )
        _plot_time_series(
            tables.thermo_rows,
            plot_files["energy_drift"],
            y_keys=["energy_drift_eV"],
            title=f"{result.label} total-energy drift",
            ylabel="Energy drift (eV)",
        )
        _plot_bars(
            [row.get("length_A", "") for row in tables.bond_rows],
            plot_files["bond_lengths"],
            title=f"{result.label} bond lengths",
            ylabel="Length (Angstrom)",
            reference=_first_numeric(
                row.get("equilibrium_length_A") for row in tables.bond_rows
            ),
        )
        _plot_bars(
            [row.get("angle_degree", "") for row in tables.angle_rows],
            plot_files["angle_distribution"],
            title=f"{result.label} angles",
            ylabel="Angle (degree)",
            reference=_first_numeric(
                row.get("equilibrium_angle_degree") for row in tables.angle_rows
            ),
        )
        _plot_pair_classes(
            tables.pair_rows,
            plot_files["pair_distance_classes"],
            title=f"{result.label} pair distances",
        )
        _plot_static_energy(
            tables.static_energy_rows,
            plot_files["static_energy_breakdown"],
            title=f"{result.label} static energy",
        )
        _plot_missing_physics_matrix(
            tables.capability_rows,
            plot_files["missing_physics_matrix"],
            title=f"{result.label} capability matrix",
        )
    except ModuleNotFoundError:
        for path in plot_files.values():
            _write_placeholder_png(path)
    return plot_files


def _write_comparison_plots(
    results: tuple[MdResult, MdResult],
    tables: tuple[DiagnosticTables, DiagnosticTables],
    plots_dir: Path,
) -> dict[str, Path]:
    lammps_result, kups_result = results
    lammps_tables, kups_tables = tables
    plot_files = {
        "energy_timeseries_side_by_side": plots_dir
        / "energy_timeseries_side_by_side.png",
        "temperature_timeseries_side_by_side": plots_dir
        / "temperature_timeseries_side_by_side.png",
        "pressure_timeseries_side_by_side": plots_dir
        / "pressure_timeseries_side_by_side.png",
        "energy_drift_side_by_side": plots_dir / "energy_drift_side_by_side.png",
        "bond_lengths_side_by_side": plots_dir / "bond_lengths_side_by_side.png",
        "angle_distribution_side_by_side": plots_dir
        / "angle_distribution_side_by_side.png",
        "pair_distance_classes_side_by_side": plots_dir
        / "pair_distance_classes_side_by_side.png",
        "static_energy_breakdown_side_by_side": plots_dir
        / "static_energy_breakdown_side_by_side.png",
        "missing_physics_matrix_side_by_side": plots_dir
        / "missing_physics_matrix_side_by_side.png",
    }
    try:
        _plot_comparison_time_series(
            [lammps_tables.thermo_rows, kups_tables.thermo_rows],
            [lammps_result.label, kups_result.label],
            plot_files["energy_timeseries_side_by_side"],
            y_keys=["potential_energy_eV", "total_energy_eV"],
            ylabel="Energy (eV)",
        )
        _plot_comparison_time_series(
            [lammps_tables.thermo_rows, kups_tables.thermo_rows],
            [lammps_result.label, kups_result.label],
            plot_files["temperature_timeseries_side_by_side"],
            y_keys=["temperature_K"],
            ylabel="Temperature (K)",
        )
        _plot_comparison_time_series(
            [lammps_tables.thermo_rows, kups_tables.thermo_rows],
            [lammps_result.label, kups_result.label],
            plot_files["pressure_timeseries_side_by_side"],
            y_keys=["pressure_atm"],
            ylabel="Pressure (atm)",
        )
        _plot_comparison_time_series(
            [lammps_tables.thermo_rows, kups_tables.thermo_rows],
            [lammps_result.label, kups_result.label],
            plot_files["energy_drift_side_by_side"],
            y_keys=["energy_drift_eV"],
            ylabel="Energy drift (eV)",
        )
        _plot_comparison_bars(
            [
                [row.get("length_A", "") for row in lammps_tables.bond_rows],
                [row.get("length_A", "") for row in kups_tables.bond_rows],
            ],
            [lammps_result.label, kups_result.label],
            plot_files["bond_lengths_side_by_side"],
            ylabel="Length (Angstrom)",
        )
        _plot_comparison_bars(
            [
                [row.get("angle_degree", "") for row in lammps_tables.angle_rows],
                [row.get("angle_degree", "") for row in kups_tables.angle_rows],
            ],
            [lammps_result.label, kups_result.label],
            plot_files["angle_distribution_side_by_side"],
            ylabel="Angle (degree)",
        )
        _plot_comparison_pair_classes(
            [lammps_tables.pair_rows, kups_tables.pair_rows],
            [lammps_result.label, kups_result.label],
            plot_files["pair_distance_classes_side_by_side"],
        )
        _plot_comparison_static_energy(
            [lammps_tables.static_energy_rows, kups_tables.static_energy_rows],
            [lammps_result.label, kups_result.label],
            plot_files["static_energy_breakdown_side_by_side"],
        )
        _plot_comparison_missing_matrix(
            [lammps_tables.capability_rows, kups_tables.capability_rows],
            [lammps_result.label, kups_result.label],
            plot_files["missing_physics_matrix_side_by_side"],
        )
    except ModuleNotFoundError:
        for path in plot_files.values():
            _write_placeholder_png(path)
    return plot_files


def _plot_time_series(
    rows: list[dict[str, Any]],
    path: Path,
    *,
    y_keys: list[str],
    title: str,
    ylabel: str,
) -> None:
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(6.0, 3.5), dpi=120)
    md_rows = [row for row in rows if row.get("block") == "md"]
    if not md_rows:
        _annotate_missing(ax, "no MD rows available")
    else:
        x = [_numeric_or_none(row.get("time_fs")) for row in md_rows]
        if all(value is None for value in x):
            x = [float(row.get("step", idx)) for idx, row in enumerate(md_rows)]
            xlabel = "Step"
        else:
            x = [float(value or 0.0) for value in x]
            xlabel = "Time (fs)"
        for key in y_keys:
            y = [_numeric_or_none(row.get(key)) for row in md_rows]
            if any(value is not None for value in y):
                ax.plot(x, [value if value is not None else math.nan for value in y], label=key)
        if ax.lines:
            ax.legend(fontsize=8)
        else:
            _annotate_missing(ax, "quantity unavailable")
        ax.set_xlabel(xlabel)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_bars(
    values: list[Any],
    path: Path,
    *,
    title: str,
    ylabel: str,
    reference: float | None = None,
) -> None:
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(6.0, 3.5), dpi=120)
    numeric = [float(value) for value in values if _numeric_or_none(value) is not None]
    if numeric:
        ax.bar(range(1, len(numeric) + 1), numeric, color="#4C78A8")
        if reference is not None:
            ax.axhline(reference, color="#D55E00", linestyle="--", label="reference")
            ax.legend(fontsize=8)
        ax.set_xlabel("Index")
    else:
        _annotate_missing(ax, "no values available")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_pair_classes(rows: list[dict[str, Any]], path: Path, *, title: str) -> None:
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(6.0, 3.5), dpi=120)
    classes = ["1-2", "1-3", "1-4", "normal"]
    values = [
        [
            float(row["distance_A"])
            for row in rows
            if row.get("topology_class") == class_name
            and _numeric_or_none(row.get("distance_A")) is not None
        ]
        for class_name in classes
    ]
    if any(values):
        positions = []
        flat = []
        colors = []
        palette = ["#4C78A8", "#F58518", "#54A24B", "#B279A2"]
        for idx, class_values in enumerate(values, start=1):
            for value in class_values:
                positions.append(idx)
                flat.append(value)
                colors.append(palette[idx - 1])
        ax.scatter(positions, flat, c=colors)
        ax.set_xticks(range(1, len(classes) + 1), classes)
    else:
        _annotate_missing(ax, "no pair rows available")
    ax.set_title(title)
    ax.set_ylabel("Distance (Angstrom)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_static_energy(rows: list[dict[str, Any]], path: Path, *, title: str) -> None:
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(7.0, 3.8), dpi=120)
    numeric_rows = [
        row for row in rows if _numeric_or_none(row.get("value_eV")) is not None
    ]
    if numeric_rows:
        labels = [str(row.get("term", "")) for row in numeric_rows]
        values = [float(row["value_eV"]) for row in numeric_rows]
        ax.bar(range(len(values)), values, color="#4C78A8")
        ax.set_xticks(range(len(values)), labels, rotation=30, ha="right", fontsize=8)
    else:
        _annotate_missing(ax, "no numeric energy terms")
    ax.set_title(title)
    ax.set_ylabel("Energy (eV)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_missing_physics_matrix(
    rows: list[dict[str, Any]], path: Path, *, title: str
) -> None:
    plt = _matplotlib_pyplot()
    fig, ax = plt.subplots(figsize=(7.0, 4.2), dpi=120)
    columns = ["lammps", "step1_import", "dirty_kups_tiny0", "step2_harness"]
    values = []
    for row in rows:
        values.append([_capability_score(row[col]) for col in columns])
    if values:
        ax.imshow(values, cmap="viridis", vmin=0, vmax=2, aspect="auto")
        ax.set_xticks(range(len(columns)), columns, rotation=25, ha="right", fontsize=8)
        ax.set_yticks(range(len(rows)), [row["capability"] for row in rows], fontsize=7)
    else:
        _annotate_missing(ax, "no capability rows")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_comparison_time_series(
    row_sets: list[list[dict[str, Any]]],
    labels: list[str],
    path: Path,
    *,
    y_keys: list[str],
    ylabel: str,
) -> None:
    plt = _matplotlib_pyplot()
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.5), dpi=120)
    y_values: list[float] = []
    for ax, rows, label in zip(axes, row_sets, labels, strict=False):
        md_rows = [row for row in rows if row.get("block") == "md"]
        if not md_rows:
            _annotate_missing(ax, "missing")
        else:
            x = [_numeric_or_none(row.get("time_fs")) for row in md_rows]
            if all(value is None for value in x):
                x = [float(row.get("step", idx)) for idx, row in enumerate(md_rows)]
                xlabel = "Step"
            else:
                x = [float(value or 0.0) for value in x]
                xlabel = "Time (fs)"
            for key in y_keys:
                y = [_numeric_or_none(row.get(key)) for row in md_rows]
                numeric_y = [value for value in y if value is not None]
                y_values.extend(numeric_y)
                if numeric_y:
                    ax.plot(
                        x,
                        [value if value is not None else math.nan for value in y],
                        label=key,
                    )
            if ax.lines:
                ax.legend(fontsize=7)
            ax.set_xlabel(xlabel)
        ax.set_title(label, fontsize=9)
        ax.set_ylabel(ylabel)
    if y_values:
        ymin, ymax = min(y_values), max(y_values)
        if ymin == ymax:
            ymin -= 1
            ymax += 1
        for ax in axes:
            ax.set_ylim(ymin, ymax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_comparison_bars(
    value_sets: list[list[Any]], labels: list[str], path: Path, *, ylabel: str
) -> None:
    plt = _matplotlib_pyplot()
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.5), dpi=120)
    all_values: list[float] = []
    for ax, values, label in zip(axes, value_sets, labels, strict=False):
        numeric = [float(value) for value in values if _numeric_or_none(value) is not None]
        all_values.extend(numeric)
        if numeric:
            ax.bar(range(1, len(numeric) + 1), numeric, color="#4C78A8")
            ax.set_xlabel("Index")
        else:
            _annotate_missing(ax, "missing")
        ax.set_title(label, fontsize=9)
        ax.set_ylabel(ylabel)
    if all_values:
        ymin, ymax = min(all_values), max(all_values)
        if ymin == ymax:
            ymin -= 1
            ymax += 1
        for ax in axes:
            ax.set_ylim(ymin, ymax)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_comparison_pair_classes(
    row_sets: list[list[dict[str, Any]]], labels: list[str], path: Path
) -> None:
    plt = _matplotlib_pyplot()
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.5), dpi=120)
    all_values: list[float] = []
    for ax, rows, label in zip(axes, row_sets, labels, strict=False):
        classes = ["1-2", "1-3", "1-4", "normal"]
        values = []
        for class_name in classes:
            class_values = [
                float(row["distance_A"])
                for row in rows
                if row.get("topology_class") == class_name
                and _numeric_or_none(row.get("distance_A")) is not None
            ]
            values.append(class_values)
            all_values.extend(class_values)
        if any(values):
            for idx, class_values in enumerate(values, start=1):
                ax.scatter([idx] * len(class_values), class_values)
            ax.set_xticks(range(1, len(classes) + 1), classes)
        else:
            _annotate_missing(ax, "missing")
        ax.set_title(label, fontsize=9)
        ax.set_ylabel("Distance (Angstrom)")
    if all_values:
        ymin, ymax = min(all_values), max(all_values)
        for ax in axes:
            ax.set_ylim(ymin * 0.98, ymax * 1.02)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_comparison_static_energy(
    row_sets: list[list[dict[str, Any]]], labels: list[str], path: Path
) -> None:
    plt = _matplotlib_pyplot()
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.8), dpi=120)
    all_values: list[float] = []
    for ax, rows, label in zip(axes, row_sets, labels, strict=False):
        numeric_rows = [
            row for row in rows if _numeric_or_none(row.get("value_eV")) is not None
        ]
        if numeric_rows:
            values = [float(row["value_eV"]) for row in numeric_rows]
            labels_local = [str(row.get("term", "")) for row in numeric_rows]
            all_values.extend(values)
            ax.bar(range(len(values)), values, color="#4C78A8")
            ax.set_xticks(range(len(values)), labels_local, rotation=30, ha="right", fontsize=7)
        else:
            _annotate_missing(ax, "missing")
        ax.set_title(label, fontsize=9)
        ax.set_ylabel("Energy (eV)")
    if all_values:
        ymin, ymax = min(all_values), max(all_values)
        for ax in axes:
            ax.set_ylim(min(0.0, ymin), ymax * 1.05 if ymax else 1.0)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_comparison_missing_matrix(
    row_sets: list[list[dict[str, Any]]], labels: list[str], path: Path
) -> None:
    plt = _matplotlib_pyplot()
    fig, axes = plt.subplots(1, 2, figsize=(10.0, 4.2), dpi=120)
    columns = ["lammps", "step1_import", "dirty_kups_tiny0", "step2_harness"]
    for ax, rows, label in zip(axes, row_sets, labels, strict=False):
        values = [[_capability_score(row[col]) for col in columns] for row in rows]
        if values:
            ax.imshow(values, cmap="viridis", vmin=0, vmax=2, aspect="auto")
            ax.set_xticks(range(len(columns)), columns, rotation=25, ha="right", fontsize=7)
            ax.set_yticks(range(len(rows)), [row["capability"] for row in rows], fontsize=6)
        else:
            _annotate_missing(ax, "missing")
        ax.set_title(label, fontsize=9)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _matplotlib_pyplot() -> Any:
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def _annotate_missing(ax: Any, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])


def _write_placeholder_png(path: Path) -> None:
    # 1x1 transparent PNG, used only when matplotlib is unavailable.
    path.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000a49444154789c6360000002000100"
            "05fe02fea5579a0000000049454e44ae426082"
        )
    )


def _merge_comparison_tables(
    lammps_tables: DiagnosticTables, kups_tables: DiagnosticTables
) -> DiagnosticTables:
    def with_engine(rows: list[dict[str, Any]], engine: str) -> list[dict[str, Any]]:
        out = []
        for row in rows:
            item = dict(row)
            item.setdefault("engine", engine)
            out.append(item)
        return out

    return DiagnosticTables(
        thermo_rows=with_engine(lammps_tables.thermo_rows, "lammps")
        + with_engine(kups_tables.thermo_rows, "kups"),
        static_geometry_rows=with_engine(lammps_tables.static_geometry_rows, "lammps")
        + with_engine(kups_tables.static_geometry_rows, "kups"),
        static_energy_rows=with_engine(lammps_tables.static_energy_rows, "lammps")
        + with_engine(kups_tables.static_energy_rows, "kups"),
        pair_rows=with_engine(lammps_tables.pair_rows, "lammps")
        + with_engine(kups_tables.pair_rows, "kups"),
        bond_rows=with_engine(lammps_tables.bond_rows, "lammps")
        + with_engine(kups_tables.bond_rows, "kups"),
        angle_rows=with_engine(lammps_tables.angle_rows, "lammps")
        + with_engine(kups_tables.angle_rows, "kups"),
        capability_rows=lammps_tables.capability_rows,
        status_rows=with_engine(lammps_tables.status_rows, "lammps")
        + with_engine(kups_tables.status_rows, "kups"),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["status", "note"]
        rows = [{"status": "not_available", "note": "no rows available"}]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key, "")) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return ""
    return value


def _parse_lammps_data_file(path: Path) -> dict[str, Any]:
    lines = path.read_text().splitlines()
    sections = _split_data_sections(lines)
    box: dict[str, Any] = {"pbc": [True, True, True]}
    for line in lines:
        clean = _strip_comment(line).strip()
        parts = clean.split()
        if len(parts) == 4 and parts[2:] == ["xlo", "xhi"]:
            box["xlo"], box["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) == 4 and parts[2:] == ["ylo", "yhi"]:
            box["ylo"], box["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) == 4 and parts[2:] == ["zlo", "zhi"]:
            box["zlo"], box["zhi"] = float(parts[0]), float(parts[1])
    return {
        "box": box,
        "masses": _parse_masses(sections.get("Masses", [])),
        "atoms": _parse_atoms(sections.get("Atoms", [])),
        "bonds": _parse_topology(sections.get("Bonds", []), 2),
        "angles": _parse_topology(sections.get("Angles", []), 3),
        "coefficients": {
            "pair": _parse_pair_coeff_section(sections.get("Pair Coeffs", [])),
            "bond": _parse_bond_coeff_section(sections.get("Bond Coeffs", [])),
            "angle": _parse_angle_coeff_section(sections.get("Angle Coeffs", [])),
        },
    }


def _split_data_sections(lines: list[str]) -> dict[str, list[str]]:
    known = {
        "Masses",
        "Pair Coeffs",
        "Bond Coeffs",
        "Angle Coeffs",
        "Atoms",
        "Velocities",
        "Bonds",
        "Angles",
        "Dihedrals",
        "Impropers",
    }
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            if current is not None:
                sections[current].append(line)
            continue
        section = clean
        if section in known:
            current = section
            sections.setdefault(current, [])
            continue
        if current is not None and not _first_token_is_number(clean):
            current = None
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _parse_masses(lines: list[str]) -> dict[int, dict[str, Any]]:
    masses = {}
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 2:
            masses[int(parts[0])] = {"mass_amu": float(parts[1]), "label": _comment(line)}
    return masses


def _parse_atoms(lines: list[str]) -> list[dict[str, Any]]:
    atoms = []
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) < 7:
            continue
        atoms.append(
            {
                "id": int(parts[0]),
                "molecule": int(parts[1]),
                "type": int(parts[2]),
                "charge_e": float(parts[3]),
                "position_A": [float(parts[4]), float(parts[5]), float(parts[6])],
            }
        )
    return atoms


def _parse_topology(lines: list[str], n_atoms: int) -> list[dict[str, Any]]:
    items = []
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 2 + n_atoms:
            items.append(
                {
                    "id": int(parts[0]),
                    "type": int(parts[1]),
                    "atoms": [int(x) for x in parts[2 : 2 + n_atoms]],
                }
            )
    return items


def _parse_pair_coeff_section(lines: list[str]) -> dict[str, dict[str, Any]]:
    coeffs = {}
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 3:
            type_id = int(parts[0])
            coeffs[f"{type_id}-{type_id}"] = {
                "type_i": type_id,
                "type_j": type_id,
                "epsilon_kcal_per_mol": float(parts[1]),
                "epsilon_eV": float(parts[1]) * KCAL_PER_MOL_TO_EV,
                "sigma_A": float(parts[2]),
            }
    return coeffs


def _parse_bond_coeff_section(lines: list[str]) -> dict[str, dict[str, Any]]:
    coeffs = {}
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 3:
            coeffs[str(int(parts[0]))] = {
                "k_kcal_per_mol_per_A2": float(parts[1]),
                "k_eV_per_A2": float(parts[1]) * KCAL_PER_MOL_TO_EV,
                "r0_A": float(parts[2]),
            }
    return coeffs


def _parse_angle_coeff_section(lines: list[str]) -> dict[str, dict[str, Any]]:
    coeffs = {}
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 3:
            coeffs[str(int(parts[0]))] = {
                "k_kcal_per_mol_per_rad2": float(parts[1]),
                "k_eV_per_rad2": float(parts[1]) * KCAL_PER_MOL_TO_EV,
                "theta0_degree": float(parts[2]),
            }
    return coeffs


def _parse_lammps_init(path: Path) -> dict[str, Any]:
    semantics: dict[str, Any] = {}
    for line in path.read_text().splitlines():
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if parts[0] == "special_bonds":
            semantics["special_bonds"] = _parse_special_bonds(parts[1:])
        elif parts[0] == "pair_modify":
            semantics["pair_modify"] = {
                parts[i]: _maybe_number(parts[i + 1])
                for i in range(1, len(parts) - 1, 2)
            }
        elif parts[0] == "pair_style":
            semantics["pair_style"] = parts[1]
        elif parts[0].endswith("_style"):
            semantics[parts[0]] = " ".join(parts[1:])
        elif parts[0] == "units":
            semantics["units"] = parts[1]
        elif parts[0] == "atom_style":
            semantics["atom_style"] = parts[1]
    return semantics


def _parse_lammps_settings(path: Path) -> dict[str, Any]:
    charge_overrides: dict[int, float] = {}
    coefficients: dict[str, dict[str, Any]] = {"pair": {}, "bond": {}, "angle": {}}
    for line in path.read_text().splitlines():
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if parts[0] == "set" and len(parts) >= 5 and parts[1] == "type" and parts[3] == "charge":
            charge_overrides[int(parts[2])] = float(parts[4])
        elif parts[0] == "pair_coeff" and len(parts) >= 5:
            type_i, type_j = int(parts[1]), int(parts[2])
            coefficients["pair"][f"{min(type_i, type_j)}-{max(type_i, type_j)}"] = {
                "type_i": type_i,
                "type_j": type_j,
                "epsilon_kcal_per_mol": float(parts[3]),
                "epsilon_eV": float(parts[3]) * KCAL_PER_MOL_TO_EV,
                "sigma_A": float(parts[4]),
            }
        elif parts[0] == "bond_coeff" and len(parts) >= 4:
            coefficients["bond"][str(int(parts[1]))] = {
                "k_kcal_per_mol_per_A2": float(parts[2]),
                "k_eV_per_A2": float(parts[2]) * KCAL_PER_MOL_TO_EV,
                "r0_A": float(parts[3]),
            }
        elif parts[0] == "angle_coeff" and len(parts) >= 4:
            coefficients["angle"][str(int(parts[1]))] = {
                "k_kcal_per_mol_per_rad2": float(parts[2]),
                "k_eV_per_rad2": float(parts[2]) * KCAL_PER_MOL_TO_EV,
                "theta0_degree": float(parts[3]),
            }
    return {"charge_overrides": charge_overrides, "coefficients": coefficients}


def _merge_coefficients(
    first: dict[str, dict[str, Any]], second: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    out = {key: dict(value) for key, value in first.items()}
    for kind, table in second.items():
        out.setdefault(kind, {})
        out[kind].update(table)
    return out


def _parse_special_bonds(args: list[str]) -> dict[str, list[float]]:
    parsed: dict[str, list[float]] = {}
    idx = 0
    while idx < len(args):
        token = args[idx]
        if token in {"lj", "coul"}:
            parsed[token] = [float(x) for x in args[idx + 1 : idx + 4]]
            idx += 4
        elif token == "lj/coul":
            values = [float(x) for x in args[idx + 1 : idx + 4]]
            parsed["lj"] = values
            parsed["coul"] = values
            idx += 4
        else:
            idx += 1
    return parsed


def _classify_graph_pairs(bonds: list[dict[str, Any]]) -> dict[str, set[tuple[int, int]]]:
    graph: dict[int, set[int]] = defaultdict(set)
    for bond in bonds:
        atom_i, atom_j = bond["atoms"]
        graph[atom_i].add(atom_j)
        graph[atom_j].add(atom_i)
    classes = {"1-2": set(), "1-3": set(), "1-4": set()}
    for start in graph:
        queue: deque[tuple[int, int]] = deque([(start, 0)])
        seen = {start}
        while queue:
            atom_id, distance = queue.popleft()
            if distance == 3:
                continue
            for neighbor in graph[atom_id]:
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                next_distance = distance + 1
                pair = tuple(sorted((start, neighbor)))
                if next_distance == 1:
                    classes["1-2"].add(pair)
                elif next_distance == 2:
                    classes["1-3"].add(pair)
                elif next_distance == 3:
                    classes["1-4"].add(pair)
                queue.append((neighbor, next_distance))
    return classes


def _pair_topology_class(
    pair: tuple[int, int], classes: dict[str, set[tuple[int, int]]]
) -> str:
    for class_name in ("1-2", "1-3", "1-4"):
        if pair in classes[class_name]:
            return class_name
    return "normal"


def _special_scale(values: list[float], topology_class: str) -> float:
    index = {"1-2": 0, "1-3": 1, "1-4": 2}.get(topology_class)
    if index is None:
        return 1.0
    return values[index] if len(values) > index else 1.0


def _mixed_pair_coeff(structure: StructureData, type_i: int, type_j: int) -> dict[str, Any]:
    pair = f"{min(type_i, type_j)}-{max(type_i, type_j)}"
    explicit = structure.coefficients.get("pair", {}).get(pair)
    if explicit:
        return {
            "epsilon_eV": _first_present(
                explicit, ["epsilon_eV"], nested="converted_units"
            ),
            "sigma_A": _first_present(explicit, ["sigma_A"], nested="converted_units"),
        }
    same_i = structure.coefficients.get("pair", {}).get(f"{type_i}-{type_i}", {})
    same_j = structure.coefficients.get("pair", {}).get(f"{type_j}-{type_j}", {})
    eps_i = _first_present(same_i, ["epsilon_eV"], nested="converted_units")
    eps_j = _first_present(same_j, ["epsilon_eV"], nested="converted_units")
    sig_i = _first_present(same_i, ["sigma_A"], nested="converted_units")
    sig_j = _first_present(same_j, ["sigma_A"], nested="converted_units")
    if eps_i is None or eps_j is None or sig_i is None or sig_j is None:
        return {}
    mix = structure.semantics.get("pair_modify", {}).get("mix", "geometric")
    if mix == "geometric":
        return {"epsilon_eV": math.sqrt(eps_i * eps_j), "sigma_A": math.sqrt(sig_i * sig_j)}
    return {"epsilon_eV": math.sqrt(eps_i * eps_j), "sigma_A": 0.5 * (sig_i + sig_j)}


def _distance(a: list[float], b: list[float], box: dict[str, Any]) -> float:
    delta = _minimum_image_vector([a[i] - b[i] for i in range(3)], box)
    return math.sqrt(sum(component * component for component in delta))


def _angle_degrees(
    a: list[float], b: list[float], c: list[float], box: dict[str, Any]
) -> float:
    ba = _minimum_image_vector([a[i] - b[i] for i in range(3)], box)
    bc = _minimum_image_vector([c[i] - b[i] for i in range(3)], box)
    norm_ba = math.sqrt(sum(x * x for x in ba))
    norm_bc = math.sqrt(sum(x * x for x in bc))
    if norm_ba == 0.0 or norm_bc == 0.0:
        return math.nan
    cosine = sum(x * y for x, y in zip(ba, bc)) / (norm_ba * norm_bc)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _minimum_image_vector(delta: list[float], box: dict[str, Any]) -> list[float]:
    out = list(delta)
    for axis, idx in zip(("x", "y", "z"), range(3), strict=True):
        lo_key, hi_key = f"{axis}lo", f"{axis}hi"
        if lo_key in box and hi_key in box:
            length = float(box[hi_key]) - float(box[lo_key])
            if length > 0:
                out[idx] -= round(out[idx] / length) * length
    return out


def _atom_mass(structure: StructureData, atom: dict[str, Any]) -> float:
    mass = structure.masses.get(int(atom["type"]), {}).get("mass_amu")
    return float(mass if mass is not None else 1.0)


def _read_yaml_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        import yaml
    except ModuleNotFoundError:
        return _minimal_yaml_mapping(Path(path).read_text())
    data = yaml.safe_load(Path(path).read_text())
    return data if isinstance(data, dict) else {}


def _minimal_yaml_mapping(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        clean = line.split("#", 1)[0].rstrip()
        if not clean:
            continue
        if not line.startswith(" ") and ":" in clean:
            key, value = clean.split(":", 1)
            if value.strip():
                data[key.strip()] = _maybe_number(value.strip().strip('"'))
                current = None
            else:
                current = {}
                data[key.strip()] = current
        elif current is not None and ":" in clean:
            key, value = clean.split(":", 1)
            current[key.strip()] = _maybe_number(value.strip().strip('"'))
    return data


def _is_thermo_header(line: str) -> bool:
    parts = line.split()
    return bool(parts and parts[0] == "Step" and all(not _is_number(p) for p in parts))


def _all_numeric(values: list[str]) -> bool:
    return all(_is_number(value) for value in values)


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def _to_float(value: str) -> float:
    return float(value)


def _parse_trailing_floats(line: str, *, expected: int) -> list[float]:
    values = []
    for token in line.split():
        try:
            values.append(float(token))
        except ValueError:
            continue
    return values[-expected:]


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def _comment(line: str) -> str | None:
    if "#" not in line:
        return None
    return line.split("#", 1)[1].strip() or None


def _first_token_is_number(line: str) -> bool:
    parts = line.split()
    return bool(parts and _is_number(parts[0]))


def _maybe_number(value: str) -> int | float | str:
    try:
        integer = int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value
    return integer


def _first_present(
    mapping: dict[str, Any], keys: list[str], *, nested: str | None = None
) -> Any:
    for key in keys:
        if key in mapping and mapping[key] is not None:
            return mapping[key]
    if nested and isinstance(mapping.get(nested), dict):
        for key in keys:
            if key in mapping[nested] and mapping[nested][key] is not None:
                return mapping[nested][key]
    return None


def _nullable_subtract(value: float, reference: Any) -> float | str:
    return value - float(reference) if reference not in (None, "") else ""


def _is_finite(value: Any) -> bool:
    return isinstance(value, int | float) and math.isfinite(float(value))


def _numeric_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _first_numeric(values: Any) -> float | None:
    for value in values:
        number = _numeric_or_none(value)
        if number is not None:
            return number
    return None


def _capability_score(value: str) -> int:
    value = value.lower()
    if value in {"yes", "reads", "reports", "diagnostic"}:
        return 2
    if "partial" in value or "parameters" in value or "recorded" in value:
        return 1
    return 0


def _format_number(value: Any) -> str:
    number = _numeric_or_none(value)
    if number is None:
        return ""
    return f"{number:.12g}"


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(item) for item in row) + " |")
    return "\n".join(lines)


def _source_file_list(result: MdResult) -> str:
    if not result.files:
        return "- No source files discovered."
    return "\n".join(
        f"- {role}: `{path}`" for role, path in sorted(result.files.items())
    )


if __name__ == "__main__":
    raise SystemExit(main())
