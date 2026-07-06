# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

"""CLI for importing resolved LAMMPS/Moltemplate decks."""

from __future__ import annotations

import argparse
from pathlib import Path

from kups.polymerization.lammps import (
    load_lammps_deck,
    load_lammps_deck_directory,
    write_lammps_deck_report,
    write_lammps_deck_yaml,
)


def run(
    *,
    source: Path | None,
    out: Path,
    report: Path | None,
    data_file: Path | None,
    init_file: Path | None,
    settings_file: Path | None,
    charges_file: Path | None,
) -> None:
    """Import a LAMMPS deck and write the resolved representation."""
    if source is not None:
        deck = load_lammps_deck_directory(source, charges_file=charges_file)
    else:
        if data_file is None or init_file is None or settings_file is None:
            raise ValueError(
                "provide --source or all of --data-file, --init-file, and "
                "--settings-file"
            )
        deck = load_lammps_deck(data_file, init_file, settings_file, charges_file)

    out.parent.mkdir(parents=True, exist_ok=True)
    write_lammps_deck_yaml(deck, out)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        write_lammps_deck_report(deck, report)


def main() -> None:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="Import a resolved LAMMPS/Moltemplate deck into kUPS YAML."
    )
    parser.add_argument("--source", type=Path, help="Deck directory with system.* files")
    parser.add_argument("--out", type=Path, required=True, help="Resolved YAML path")
    parser.add_argument("--report", type=Path, help="Optional checker REPORT.md path")
    parser.add_argument("--data-file", type=Path, help="Explicit system.data path")
    parser.add_argument("--init-file", type=Path, help="Explicit system.in.init path")
    parser.add_argument(
        "--settings-file", type=Path, help="Explicit system.in.settings path"
    )
    parser.add_argument(
        "--charges-file",
        type=Path,
        help="Optional explicit system.in.charges path",
    )
    args = parser.parse_args()
    run(
        source=args.source,
        out=args.out,
        report=args.report,
        data_file=args.data_file,
        init_file=args.init_file,
        settings_file=args.settings_file,
        charges_file=args.charges_file,
    )


if __name__ == "__main__":
    main()
