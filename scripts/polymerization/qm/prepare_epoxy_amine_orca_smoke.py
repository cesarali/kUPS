#!/usr/bin/env python
"""Prepare self-contained ORCA smoke-test jobs for a cluster.

The generated jobs are intentionally small:
- R2 near-attack EnGrad is the first gate for MLFF labels.
- R1 and P1 are optional follow-up labels.

Each ORCA input contains inline XYZ coordinates, so the job directories can be
copied to a cluster without relying on relative molecule paths.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "results" / "qm" / "epoxy_amine_smoke" / "cluster_runs"


def embed_and_optimize(smiles: str, seed: int) -> Chem.Mol:
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    status = AllChem.EmbedMolecule(mol, randomSeed=seed)
    if status != 0:
        raise RuntimeError(f"RDKit embedding failed for {smiles}")
    AllChem.UFFOptimizeMolecule(mol, maxIters=500)
    return mol


def coords(mol: Chem.Mol) -> np.ndarray:
    conf = mol.GetConformer()
    return np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])


def symbols(mol: Chem.Mol) -> list[str]:
    return [atom.GetSymbol() for atom in mol.GetAtoms()]


def unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        raise ValueError("Cannot normalize near-zero vector")
    return vector / norm


def epoxide_atoms(mol: Chem.Mol) -> tuple[int, int, int]:
    for ring in mol.GetRingInfo().AtomRings():
        if len(ring) != 3:
            continue
        ring_symbols = [mol.GetAtomWithIdx(i).GetSymbol() for i in ring]
        if ring_symbols.count("O") == 1 and ring_symbols.count("C") == 2:
            oxygen = next(i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "O")
            carbons = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "C"]
            return carbons[0], carbons[1], oxygen
    raise RuntimeError("Could not find epoxide C-C-O ring")


def methylamine_nitrogen(mol: Chem.Mol) -> int:
    for atom in mol.GetAtoms():
        if atom.GetSymbol() == "N":
            return atom.GetIdx()
    raise RuntimeError("Could not find methylamine nitrogen")


def combine_near_attack(distance: float) -> tuple[list[str], np.ndarray, dict[str, float | int | str]]:
    epoxy = embed_and_optimize("COCC1CO1", seed=17)
    amine = embed_and_optimize("CN", seed=23)
    epoxy_coords = coords(epoxy)
    amine_coords = coords(amine)

    attacked_c, other_c, epoxide_o = epoxide_atoms(epoxy)
    nitrogen = methylamine_nitrogen(amine)

    c_pos = epoxy_coords[attacked_c]
    axis = unit(c_pos - 0.5 * (epoxy_coords[other_c] + epoxy_coords[epoxide_o]))
    target_n = c_pos + distance * axis
    shifted_amine = amine_coords + (target_n - amine_coords[nitrogen])

    all_symbols = symbols(epoxy) + symbols(amine)
    all_coords = np.vstack([epoxy_coords, shifted_amine])
    n_global = epoxy.GetNumAtoms() + nitrogen
    nc_distance = float(np.linalg.norm(all_coords[n_global] - all_coords[attacked_c]))
    meta = {
        "geometry_id": "R2",
        "description": "near_attack",
        "attacked_c_index_zero_based": attacked_c,
        "nitrogen_index_zero_based": n_global,
        "n_c_distance_a": nc_distance,
    }
    return all_symbols, all_coords, meta


def combine_separated(distance: float) -> tuple[list[str], np.ndarray, dict[str, float | int | str]]:
    all_symbols, all_coords, meta = combine_near_attack(distance)
    meta = dict(meta)
    meta["geometry_id"] = "R1"
    meta["description"] = "separated_reactant_complex"
    return all_symbols, all_coords, meta


def product_geometry() -> tuple[list[str], np.ndarray, dict[str, float | int | str]]:
    product = embed_and_optimize("COCC(O)CNC", seed=31)
    meta = {
        "geometry_id": "P1",
        "description": "ring_opened_product",
        "attacked_c_index_zero_based": "",
        "nitrogen_index_zero_based": "",
        "n_c_distance_a": "",
    }
    return symbols(product), coords(product), meta


def orca_input(
    atom_symbols: list[str],
    atom_coords: np.ndarray,
    method_line: str,
    nprocs: int,
    maxcore: int,
) -> str:
    lines = [
        f"! {method_line}",
        "",
        "%pal",
        f"  nprocs {nprocs}",
        "end",
        "",
        f"%maxcore {maxcore}",
        "",
        "* xyz 0 1",
    ]
    for symbol, xyz in zip(atom_symbols, atom_coords):
        lines.append(f"{symbol:2s} {xyz[0]: .8f} {xyz[1]: .8f} {xyz[2]: .8f}")
    lines.append("*")
    lines.append("")
    return "\n".join(lines)


def write_xyz(path: Path, atom_symbols: list[str], atom_coords: np.ndarray, comment: str) -> None:
    lines = [str(len(atom_symbols)), comment]
    for symbol, xyz in zip(atom_symbols, atom_coords):
        lines.append(f"{symbol:2s} {xyz[0]: .8f} {xyz[1]: .8f} {xyz[2]: .8f}")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--nprocs", type=int, default=1)
    parser.add_argument("--maxcore", type=int, default=1000)
    parser.add_argument("--method-line", default="B3LYP D3BJ def2-SVP TightSCF EnGrad")
    parser.add_argument("--include", default="R2", help="Comma-separated subset of R1,R2,P1")
    args = parser.parse_args()

    requested = {item.strip().upper() for item in args.include.split(",") if item.strip()}
    builders = {
        "R1": lambda: combine_separated(3.4),
        "R2": lambda: combine_near_attack(2.4),
        "P1": product_geometry,
    }
    unknown = requested - builders.keys()
    if unknown:
        raise ValueError(f"Unknown job ids: {sorted(unknown)}")

    args.out.mkdir(parents=True, exist_ok=True)
    manifest_rows = []

    for job_id in ["R1", "R2", "P1"]:
        if job_id not in requested:
            continue
        atom_symbols, atom_coords, meta = builders[job_id]()
        job_name = {
            "R1": "r1_reactant_svp_engrad",
            "R2": "r2_near_attack_svp_engrad",
            "P1": "p1_product_svp_engrad",
        }[job_id]
        job_dir = args.out / job_name
        job_dir.mkdir(parents=True, exist_ok=True)

        comment = (
            f"{job_id} {meta['description']}; "
            f"N_C_distance_A={meta['n_c_distance_a']}"
        )
        write_xyz(job_dir / f"{job_name}.xyz", atom_symbols, atom_coords, comment)
        (job_dir / f"{job_name}.inp").write_text(
            orca_input(atom_symbols, atom_coords, args.method_line, args.nprocs, args.maxcore)
        )
        manifest_rows.append(
            {
                "job_name": job_name,
                "geometry_id": job_id,
                "atoms": len(atom_symbols),
                "method_line": args.method_line,
                "nprocs": args.nprocs,
                "maxcore_mb": args.maxcore,
                **meta,
            }
        )

    with (args.out / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    print(f"Wrote {args.out}")
    print(f"Jobs: {', '.join(row['job_name'] for row in manifest_rows)}")


if __name__ == "__main__":
    main()
