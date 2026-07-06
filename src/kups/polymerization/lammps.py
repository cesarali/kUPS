# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

"""Parser and checker for resolved LAMMPS/Moltemplate input decks.

This module intentionally stays on the format side of the boundary. It reads
numeric LAMMPS files, records the LAMMPS semantics, converts known ``real`` unit
coefficients into kUPS-ready units, and validates the imported topology. It does
not evaluate energies or construct an MD state.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

KCAL_PER_MOL_TO_EV = 0.0433641153

_DATA_SECTIONS = {
    "Masses",
    "Atoms",
    "Velocities",
    "Bonds",
    "Angles",
    "Dihedrals",
    "Impropers",
}

_COUNT_LABELS = {
    "atoms": "atoms",
    "bonds": "bonds",
    "angles": "angles",
    "dihedrals": "dihedrals",
    "impropers": "impropers",
    "atom types": "atom_types",
    "bond types": "bond_types",
    "angle types": "angle_types",
    "dihedral types": "dihedral_types",
    "improper types": "improper_types",
}

_TOPOLOGY_SPECS = {
    "bonds": 2,
    "angles": 3,
    "dihedrals": 4,
    "impropers": 4,
}


def load_lammps_deck_directory(
    source: str | Path, *, charges_file: str | Path | None = None
) -> dict[str, Any]:
    """Load a standard Moltemplate-generated LAMMPS deck directory.

    Args:
        source: Directory containing ``system.data``, ``system.in.init``,
            ``system.in.settings``, and optionally ``system.in.charges``.
        charges_file: Optional explicit charge override file. If omitted, the
            loader uses ``system.in.charges`` when present.

    Returns:
        Resolved deck dictionary.
    """
    source_path = Path(source)
    inferred_charges = source_path / "system.in.charges"
    return load_lammps_deck(
        source_path / "system.data",
        source_path / "system.in.init",
        source_path / "system.in.settings",
        charges_file=charges_file
        if charges_file is not None
        else inferred_charges
        if inferred_charges.exists()
        else None,
    )


def load_lammps_deck(
    data_file: str | Path,
    init_file: str | Path,
    settings_file: str | Path,
    charges_file: str | Path | None = None,
) -> dict[str, Any]:
    """Load a resolved LAMMPS data deck plus Moltemplate input fragments.

    Args:
        data_file: LAMMPS data file, currently supporting ``atom_style full``.
        init_file: LAMMPS init fragment with style declarations.
        settings_file: Fragment with force-field coefficients.
        charges_file: Optional fragment with ``set type ... charge ...`` rows.

    Returns:
        JSON/YAML-serializable resolved representation.
    """
    data_path = Path(data_file)
    init_path = Path(init_file)
    settings_path = Path(settings_file)
    charges_path = Path(charges_file) if charges_file is not None else None

    data = _parse_data_file(data_path)
    init = _parse_init_file(init_path)
    settings = _parse_settings_file(settings_path)
    charge_overrides = dict(settings["charge_overrides"])
    charge_sources = {
        str(type_id): "settings_file" for type_id in settings["charge_overrides"]
    }

    if charges_path is not None:
        charges = _parse_settings_file(charges_path)
        charge_overrides.update(charges["charge_overrides"])
        charge_sources.update(
            {str(type_id): "charges_file" for type_id in charges["charge_overrides"]}
        )
    else:
        charges = {
            "charge_overrides": {},
            "pair_coeffs": {},
            "bond_coeffs": {},
            "angle_coeffs": {},
            "dihedral_coeffs": {},
            "improper_coeffs": {},
            "unsupported": [],
        }

    atom_type_charges = {
        str(type_id): {"charge_e": charge, "source": charge_sources[str(type_id)]}
        for type_id, charge in sorted(charge_overrides.items())
    }
    atoms = []
    for atom in data["atoms"]:
        atom_type = atom["type"]
        original_charge = atom["charge_e"]
        charge = charge_overrides.get(atom_type, original_charge)
        atom_out = dict(atom)
        atom_out["charge_e"] = charge
        atom_out["original_charge_e"] = original_charge
        atom_out["charge_source"] = (
            charge_sources[str(atom_type)]
            if atom_type in charge_overrides
            else "data_file"
        )
        atoms.append(atom_out)

    deck = {
        "source": {
            "data_file": _as_posix(data_path),
            "init_file": _as_posix(init_path),
            "settings_file": _as_posix(settings_path),
            "charges_file": _as_posix(charges_path) if charges_path is not None else None,
            "include_order": [
                "init_file",
                "data_file",
                "settings_file",
                *([] if charges_path is None else ["charges_file"]),
            ],
        },
        "lammps_semantics": init,
        "counts": data["counts"],
        "box": data["box"],
        "masses": data["masses"],
        "atom_type_charges": atom_type_charges,
        "atoms": atoms,
        "coefficients": {
            "pair": _convert_pair_coeffs(settings["pair_coeffs"], init),
            "bond": _convert_bond_coeffs(settings["bond_coeffs"], init),
            "angle": _convert_angle_coeffs(settings["angle_coeffs"], init),
            "dihedral": _convert_energy_coeffs(
                settings["dihedral_coeffs"], "dihedral", init.get("dihedral_style")
            ),
            "improper": _convert_energy_coeffs(
                settings["improper_coeffs"], "improper", init.get("improper_style")
            ),
        },
        "topology": {
            "bonds": data["bonds"],
            "angles": data["angles"],
            "dihedrals": data["dihedrals"],
            "impropers": data["impropers"],
        },
        "unsupported": {
            "data_sections": data["unsupported"],
            "settings_lines": settings["unsupported"] + charges["unsupported"],
        },
    }
    deck["checker"] = check_lammps_deck(deck)
    return deck


def check_lammps_deck(deck: dict[str, Any]) -> dict[str, Any]:
    """Validate a resolved deck and report readiness for later milestones."""
    errors: list[str] = []
    warnings: list[str] = []
    atom_ids = {atom["id"] for atom in deck.get("atoms", [])}
    used_atom_types = {atom["type"] for atom in deck.get("atoms", [])}
    masses = {int(type_id): value for type_id, value in deck.get("masses", {}).items()}

    for atom_type in sorted(used_atom_types):
        if atom_type not in masses:
            errors.append(f"atom type {atom_type} is used but has no Masses entry")

    coefficients = deck.get("coefficients", {})
    for name, n_atoms in _TOPOLOGY_SPECS.items():
        entries = deck.get("topology", {}).get(name, [])
        coeffs = coefficients.get(name[:-1] if name.endswith("s") else name, {})
        coeff_type_ids = {int(type_id) for type_id in coeffs}
        for item in entries:
            missing_atoms = [atom_id for atom_id in item["atoms"] if atom_id not in atom_ids]
            if missing_atoms:
                errors.append(
                    f"{name[:-1]} {item['id']} references missing atoms {missing_atoms}"
                )
            if len(item["atoms"]) != n_atoms:
                errors.append(
                    f"{name[:-1]} {item['id']} has {len(item['atoms'])} atoms, "
                    f"expected {n_atoms}"
                )
            if item["type"] not in coeff_type_ids:
                errors.append(
                    f"{name[:-1]} {item['id']} uses type {item['type']} "
                    "without a matching coefficient"
                )

    pair_classes = classify_special_pairs(deck.get("topology", {}).get("bonds", []))
    total_charge = sum(atom["charge_e"] for atom in deck.get("atoms", []))
    missing_pair_coeffs = _missing_pair_coeffs(deck, used_atom_types)

    for coeff_kind, table in coefficients.items():
        for type_id, coeff in table.items():
            if "converted_units" not in coeff:
                errors.append(f"{coeff_kind}_coeff {type_id} lacks converted units")

    unsupported = deck.get("unsupported", {})
    if unsupported.get("data_sections"):
        warnings.append(f"unsupported data sections: {unsupported['data_sections']}")
    if unsupported.get("settings_lines"):
        warnings.append(
            f"unsupported settings lines: {len(unsupported['settings_lines'])}"
        )

    blocked = bool(errors)
    future_pair_status = (
        "ready_input"
        if not missing_pair_coeffs
        else "not_implemented"
        if deck.get("lammps_semantics", {})
        .get("pair_modify", {})
        .get("mix")
        in {"geometric", "arithmetic", "lorentz_berthelot"}
        else "blocked_by_import_error"
    )
    readiness = {
        "format_import": "blocked_by_import_error" if blocked else "ready_input",
        "bonded_terms": "blocked_by_import_error"
        if blocked
        else "ready_input"
        if deck.get("topology", {}).get("bonds") or deck.get("topology", {}).get("angles")
        else "not_implemented",
        "lj_pair_matrix": future_pair_status if not blocked else "blocked_by_import_error",
        "special_pair_scaling": "blocked_by_import_error"
        if blocked
        else "ready_input",
        "electrostatics": "blocked_by_import_error"
        if blocked
        else "ready_input"
        if deck.get("atoms")
        else "not_implemented",
        "dynamics": "not_implemented",
    }

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "total_charge_e": total_charge,
        "used_atom_types": sorted(used_atom_types),
        "special_pairs": {
            "one_two": _pairs_to_lists(pair_classes["one_two"]),
            "one_three": _pairs_to_lists(pair_classes["one_three"]),
            "one_four": _pairs_to_lists(pair_classes["one_four"]),
            "counts": {
                "one_two": len(pair_classes["one_two"]),
                "one_three": len(pair_classes["one_three"]),
                "one_four": len(pair_classes["one_four"]),
            },
        },
        "missing_explicit_pair_coefficients": [
            {"types": list(pair), "status": "generated_by_mixing_later"}
            for pair in missing_pair_coeffs
        ],
        "readiness": readiness,
    }


def classify_special_pairs(
    bonds: list[dict[str, Any]],
) -> dict[str, set[tuple[int, int]]]:
    """Classify atom pairs at graph distance 1, 2, and 3 from bonds."""
    graph: dict[int, set[int]] = defaultdict(set)
    for bond in bonds:
        atom_i, atom_j = bond["atoms"]
        graph[atom_i].add(atom_j)
        graph[atom_j].add(atom_i)

    classes: dict[str, set[tuple[int, int]]] = {
        "one_two": set(),
        "one_three": set(),
        "one_four": set(),
    }
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
                next_distance = distance + 1
                seen.add(neighbor)
                pair = tuple(sorted((start, neighbor)))
                if next_distance == 1:
                    classes["one_two"].add(pair)
                elif next_distance == 2:
                    classes["one_three"].add(pair)
                elif next_distance == 3:
                    classes["one_four"].add(pair)
                queue.append((neighbor, next_distance))
    return classes


def write_lammps_deck_yaml(deck: dict[str, Any], path: str | Path) -> None:
    """Write the resolved deck as JSON-formatted YAML."""
    Path(path).write_text(json.dumps(deck, indent=2, sort_keys=True) + "\n")


def write_lammps_deck_report(deck: dict[str, Any], path: str | Path) -> None:
    """Write a compact Markdown checker report for a resolved deck."""
    checker = deck.get("checker", check_lammps_deck(deck))
    counts = deck.get("counts", {})
    special_counts = checker["special_pairs"]["counts"]
    readiness_rows = "\n".join(
        f"| {name} | {status} |" for name, status in checker["readiness"].items()
    )
    errors = checker["errors"] or ["None"]
    warnings = checker["warnings"] or ["None"]
    text = f"""# LAMMPS Deck Import Report

## Summary

Status: `{checker["status"]}`

This report validates the resolved LAMMPS/Moltemplate deck as a format handoff.
It checks source completeness, topology references, coefficient availability,
charge override application, unit-conversion presence, and topology-derived
special-pair classes. It does not evaluate kUPS energies or run dynamics.

## Counts

- atoms: {counts.get("atoms", 0)}
- bonds: {counts.get("bonds", 0)}
- angles: {counts.get("angles", 0)}
- dihedrals: {counts.get("dihedrals", 0)}
- impropers: {counts.get("impropers", 0)}

## Checker

- total charge e: {checker["total_charge_e"]:.12g}
- one-two pairs: {special_counts["one_two"]}
- one-three pairs: {special_counts["one_three"]}
- one-four pairs: {special_counts["one_four"]}
- missing explicit pair coeffs: {len(checker["missing_explicit_pair_coefficients"])}

## Readiness

| Contract | Status |
| --- | --- |
{readiness_rows}

## Errors

{_markdown_list(errors)}

## Warnings

{_markdown_list(warnings)}
"""
    Path(path).write_text(text)


def _parse_data_file(path: Path) -> dict[str, Any]:
    lines = path.read_text().splitlines()
    counts: dict[str, int] = {}
    box: dict[str, Any] = {"pbc": [True, True, True]}
    sections = _split_data_sections(lines)

    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) >= 2:
            count_label = " ".join(parts[1:])
            if parts[0].isdigit() and count_label in _COUNT_LABELS:
                counts[_COUNT_LABELS[count_label]] = int(parts[0])
                continue
        if len(parts) == 4 and parts[2:] == ["xlo", "xhi"]:
            box["xlo"], box["xhi"] = float(parts[0]), float(parts[1])
        elif len(parts) == 4 and parts[2:] == ["ylo", "yhi"]:
            box["ylo"], box["yhi"] = float(parts[0]), float(parts[1])
        elif len(parts) == 4 and parts[2:] == ["zlo", "zhi"]:
            box["zlo"], box["zhi"] = float(parts[0]), float(parts[1])

    unsupported = sorted(set(sections) - _DATA_SECTIONS)
    return {
        "counts": counts,
        "box": box,
        "masses": _parse_masses(sections.get("Masses", [])),
        "atoms": _parse_atoms(sections.get("Atoms", [])),
        "bonds": _parse_topology(sections.get("Bonds", []), 2),
        "angles": _parse_topology(sections.get("Angles", []), 3),
        "dihedrals": _parse_topology(sections.get("Dihedrals", []), 4),
        "impropers": _parse_topology(sections.get("Impropers", []), 4),
        "unsupported": unsupported,
    }


def _split_data_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        clean = _strip_comment(line).strip()
        maybe_section = clean.split()[0] if clean.split() else ""
        if maybe_section in _DATA_SECTIONS:
            current = maybe_section
            sections.setdefault(current, [])
            continue
        if maybe_section and not _first_token_is_number(clean):
            current = None
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def _parse_masses(lines: list[str]) -> dict[str, Any]:
    masses: dict[str, Any] = {}
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) < 2:
            continue
        masses[str(int(parts[0]))] = {
            "mass_amu": float(parts[1]),
            "label": _comment(line),
        }
    return masses


def _parse_atoms(lines: list[str]) -> list[dict[str, Any]]:
    atoms = []
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) < 7:
            raise ValueError(f"atom_style full atom row has too few fields: {line}")
        atom = {
            "id": int(parts[0]),
            "molecule": int(parts[1]),
            "type": int(parts[2]),
            "charge_e": float(parts[3]),
            "position_A": [float(parts[4]), float(parts[5]), float(parts[6])],
        }
        if len(parts) > 7:
            atom["extra_fields"] = parts[7:]
        atoms.append(atom)
    return atoms


def _parse_topology(lines: list[str], n_atoms: int) -> list[dict[str, Any]]:
    items = []
    for line in lines:
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        if len(parts) < 2 + n_atoms:
            raise ValueError(f"topology row has too few fields: {line}")
        items.append(
            {
                "id": int(parts[0]),
                "type": int(parts[1]),
                "atoms": [int(x) for x in parts[2 : 2 + n_atoms]],
            }
        )
    return items


def _parse_init_file(path: Path) -> dict[str, Any]:
    semantics: dict[str, Any] = {}
    unsupported = []
    for line in path.read_text().splitlines():
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        command = parts[0]
        args = parts[1:]
        if command == "units":
            semantics["units"] = args[0]
        elif command == "atom_style":
            semantics["atom_style"] = args[0]
        elif command == "pair_style":
            semantics["pair_style"] = args[0]
            semantics["pair_style_args"] = [_maybe_number(x) for x in args[1:]]
        elif command.endswith("_style") and command != "kspace_style":
            semantics[command] = " ".join(args)
        elif command == "pair_modify":
            semantics["pair_modify"] = _parse_key_value_args(args)
        elif command == "special_bonds":
            semantics["special_bonds"] = _parse_special_bonds(args)
        elif command == "kspace_style":
            semantics["kspace_style"] = {
                "name": args[0],
                "args": [_maybe_number(x) for x in args[1:]],
            }
            if len(args) > 1:
                semantics["kspace_style"]["accuracy"] = float(args[1])
        else:
            unsupported.append(line)
    if unsupported:
        semantics["unsupported"] = unsupported
    return semantics


def _parse_settings_file(path: Path) -> dict[str, Any]:
    parsed = {
        "charge_overrides": {},
        "pair_coeffs": {},
        "bond_coeffs": {},
        "angle_coeffs": {},
        "dihedral_coeffs": {},
        "improper_coeffs": {},
        "unsupported": [],
    }
    for line in path.read_text().splitlines():
        clean = _strip_comment(line).strip()
        if not clean:
            continue
        parts = clean.split()
        command = parts[0]
        try:
            if command == "set" and len(parts) >= 5 and parts[1] == "type":
                if parts[3] != "charge":
                    parsed["unsupported"].append(line)
                    continue
                parsed["charge_overrides"][int(parts[2])] = float(parts[4])
            elif command == "pair_coeff" and len(parts) >= 5:
                type_i, type_j = int(parts[1]), int(parts[2])
                parsed["pair_coeffs"][(type_i, type_j)] = _coeff_payload(line, parts[3:])
            elif command in {
                "bond_coeff",
                "angle_coeff",
                "dihedral_coeff",
                "improper_coeff",
            }:
                type_id = int(parts[1])
                key = f"{command.removesuffix('_coeff')}_coeffs"
                parsed[key][type_id] = _coeff_payload(line, parts[2:])
            else:
                parsed["unsupported"].append(line)
        except (ValueError, IndexError) as exc:
            raise ValueError(f"could not parse LAMMPS settings line: {line}") from exc
    return parsed


def _coeff_payload(line: str, args: list[str]) -> dict[str, Any]:
    return {
        "raw_args": [_maybe_number(arg) for arg in args],
        "comment": _comment(line),
    }


def _convert_pair_coeffs(coeffs: dict[tuple[int, int], Any], init: dict[str, Any]) -> dict[str, Any]:
    converted = {}
    for (type_i, type_j), coeff in sorted(coeffs.items()):
        raw = coeff["raw_args"]
        entry = {
            "type_i": type_i,
            "type_j": type_j,
            "style": init.get("pair_style"),
            "epsilon_kcal_per_mol": raw[0] if len(raw) > 0 else None,
            "sigma_A": raw[1] if len(raw) > 1 else None,
            "raw_args": raw,
            "comment": coeff["comment"],
            "converted_units": {},
        }
        if len(raw) >= 1 and isinstance(raw[0], int | float):
            entry["converted_units"]["epsilon_eV"] = raw[0] * KCAL_PER_MOL_TO_EV
        if len(raw) >= 2 and isinstance(raw[1], int | float):
            entry["converted_units"]["sigma_A"] = raw[1]
        converted[_pair_key(type_i, type_j)] = entry
    return converted


def _convert_bond_coeffs(coeffs: dict[int, Any], init: dict[str, Any]) -> dict[str, Any]:
    converted = {}
    for type_id, coeff in sorted(coeffs.items()):
        raw = coeff["raw_args"]
        entry = {
            "style": init.get("bond_style"),
            "k_kcal_per_mol_per_A2": raw[0] if len(raw) > 0 else None,
            "r0_A": raw[1] if len(raw) > 1 else None,
            "raw_args": raw,
            "comment": coeff["comment"],
            "converted_units": {},
        }
        if len(raw) >= 1 and isinstance(raw[0], int | float):
            entry["converted_units"]["k_eV_per_A2"] = raw[0] * KCAL_PER_MOL_TO_EV
        if len(raw) >= 2 and isinstance(raw[1], int | float):
            entry["converted_units"]["r0_A"] = raw[1]
        converted[str(type_id)] = entry
    return converted


def _convert_angle_coeffs(coeffs: dict[int, Any], init: dict[str, Any]) -> dict[str, Any]:
    converted = {}
    for type_id, coeff in sorted(coeffs.items()):
        raw = coeff["raw_args"]
        entry = {
            "style": init.get("angle_style"),
            "k_kcal_per_mol_per_rad2": raw[0] if len(raw) > 0 else None,
            "theta0_degree": raw[1] if len(raw) > 1 else None,
            "raw_args": raw,
            "comment": coeff["comment"],
            "converted_units": {},
        }
        if len(raw) >= 1 and isinstance(raw[0], int | float):
            entry["converted_units"]["k_eV_per_rad2"] = raw[0] * KCAL_PER_MOL_TO_EV
            entry["converted_units"]["k_eV_per_degree2"] = (
                raw[0] * KCAL_PER_MOL_TO_EV / (180.0 / 3.141592653589793) ** 2
            )
        if len(raw) >= 2 and isinstance(raw[1], int | float):
            entry["converted_units"]["theta0_degree"] = raw[1]
        converted[str(type_id)] = entry
    return converted


def _convert_energy_coeffs(
    coeffs: dict[int, Any], coeff_kind: str, style: str | None
) -> dict[str, Any]:
    converted = {}
    for type_id, coeff in sorted(coeffs.items()):
        raw = coeff["raw_args"]
        energy_indices = _energy_coefficient_indices(coeff_kind, style, raw)
        converted_values = []
        for index, value in enumerate(raw):
            if isinstance(value, int | float) and index in energy_indices:
                converted_values.append(value * KCAL_PER_MOL_TO_EV)
            else:
                converted_values.append(value)
        converted[str(type_id)] = {
            "style": style,
            "raw_args": raw,
            "comment": coeff["comment"],
            "converted_units": {
                "raw_args_with_energy_terms_in_eV": converted_values,
                "energy_term_indices": sorted(energy_indices),
            },
        }
    return converted


def _energy_coefficient_indices(
    coeff_kind: str, style: str | None, raw: list[Any]
) -> set[int]:
    if coeff_kind == "dihedral" and style == "opls":
        return {0, 1, 2, 3}
    if coeff_kind == "improper" and style and style.startswith("cvff"):
        return {0}
    if raw:
        return {0}
    return set()


def _missing_pair_coeffs(
    deck: dict[str, Any], used_atom_types: set[int]
) -> list[tuple[int, int]]:
    explicit_pairs = {
        tuple(sorted((coeff["type_i"], coeff["type_j"])))
        for coeff in deck.get("coefficients", {}).get("pair", {}).values()
    }
    missing = []
    for type_i in sorted(used_atom_types):
        for type_j in sorted(used_atom_types):
            if type_j < type_i:
                continue
            if tuple(sorted((type_i, type_j))) not in explicit_pairs:
                missing.append((type_i, type_j))
    return missing


def _parse_key_value_args(args: list[str]) -> dict[str, Any]:
    parsed = {}
    for idx in range(0, len(args), 2):
        if idx + 1 < len(args):
            parsed[args[idx]] = _maybe_number(args[idx + 1])
        else:
            parsed[args[idx]] = True
    return parsed


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


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0]


def _comment(line: str) -> str | None:
    if "#" not in line:
        return None
    return line.split("#", 1)[1].strip() or None


def _first_token_is_number(line: str) -> bool:
    parts = line.split()
    if not parts:
        return False
    try:
        float(parts[0])
    except ValueError:
        return False
    return True


def _maybe_number(value: str) -> int | float | str:
    try:
        integer = int(value)
    except ValueError:
        pass
    else:
        return integer
    try:
        return float(value)
    except ValueError:
        return value


def _pair_key(type_i: int, type_j: int) -> str:
    low, high = sorted((type_i, type_j))
    return f"{low}-{high}"


def _pairs_to_lists(pairs: set[tuple[int, int]]) -> list[list[int]]:
    return [list(pair) for pair in sorted(pairs)]


def _markdown_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _as_posix(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.as_posix()
