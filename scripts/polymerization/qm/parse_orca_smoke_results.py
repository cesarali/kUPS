#!/usr/bin/env python
"""Parse ORCA smoke-test outputs into a compact CSV summary."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import numpy as np


ENERGY_RE = re.compile(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)")
NORMAL_RE = re.compile(r"ORCA TERMINATED NORMALLY")
REAL_TIME_RE = re.compile(r"real\s+(\d+(?:\.\d+)?)")
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ROOT = (
    REPO_ROOT
    / "test"
    / "polymerization"
    / "fixtures"
    / "epoxy_amine_orca"
)


def parse_time(path: Path) -> float | None:
    if not path.exists():
        return None
    match = REAL_TIME_RE.search(path.read_text(errors="ignore"))
    return float(match.group(1)) if match else None


def parse_energy_and_status(path: Path) -> tuple[float | None, bool]:
    if not path.exists():
        return None, False
    text = path.read_text(errors="ignore")
    energies = ENERGY_RE.findall(text)
    energy = float(energies[-1]) if energies else None
    return energy, bool(NORMAL_RE.search(text))


def parse_engrad(path: Path) -> tuple[int | None, float | None, float | None]:
    if not path.exists():
        return None, None, None
    lines = path.read_text(errors="ignore").splitlines()
    try:
        atoms = int(lines[3])
        start = lines.index("# The current gradient in Eh/bohr") + 2
    except (ValueError, IndexError):
        return None, None, None
    gradients = np.array([float(lines[start + i]) for i in range(3 * atoms)]).reshape(atoms, 3)
    norms = np.linalg.norm(gradients, axis=1)
    return atoms, float(norms.max()), float((norms**2).mean() ** 0.5)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=DEFAULT_ROOT)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    rows = []
    for job_dir in sorted(path for path in args.root.iterdir() if path.is_dir()):
        inp_files = list(job_dir.glob("*.inp"))
        if not inp_files:
            continue
        base = inp_files[0].with_suffix("")
        energy, normal = parse_energy_and_status(base.with_suffix(".out"))
        atoms, max_grad, rms_grad = parse_engrad(base.with_suffix(".engrad"))
        rows.append(
            {
                "job_name": job_dir.name,
                "finished": normal,
                "wall_time_s": parse_time(base.with_suffix(".time")),
                "energy_hartree": energy,
                "atoms": atoms,
                "max_gradient_eh_bohr": max_grad,
                "rms_gradient_eh_bohr": rms_grad,
                "out_file": str(base.with_suffix(".out")),
                "engrad_file": str(base.with_suffix(".engrad")),
            }
        )

    out = args.out or (args.root / "results.csv")
    if rows:
        with out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
