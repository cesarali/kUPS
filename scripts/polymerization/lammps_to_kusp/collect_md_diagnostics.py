#!/usr/bin/env python
# Copyright 2024-2026 Cusp AI
# SPDX-License-Identifier: Apache-2.0

"""Collect normalized MD diagnostics and write a report."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from kups.polymerization.md_diagnostics import main


if __name__ == "__main__":
    raise SystemExit(main())
