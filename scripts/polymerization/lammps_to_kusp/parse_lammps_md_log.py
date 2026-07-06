#!/usr/bin/env python
# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

"""Parse a LAMMPS MD log and optionally write normalized thermo CSV."""

from __future__ import annotations

import argparse
import csv
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kups.polymerization.md_diagnostics import parse_lammps_md_log


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--out", type=Path, help="Optional normalized thermo CSV path.")
    args = parser.parse_args(argv)

    parsed = parse_lammps_md_log(args.log)
    rows = list(itertools.chain.from_iterable(block.rows for block in parsed.blocks))
    print(f"blocks: {len(parsed.blocks)}")
    for block in parsed.blocks:
        print(f"- {block.kind}: {len(block.rows)} rows from line {block.start_line}")
    if parsed.minimization_stats:
        print(
            "minimization final eV: "
            f"{parsed.minimization_stats['energy_final_eV']:.12g}"
        )

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with args.out.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
