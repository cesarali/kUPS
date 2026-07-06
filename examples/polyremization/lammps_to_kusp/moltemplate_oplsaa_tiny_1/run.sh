#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../../.."

PYTHONPATH=src python -m kups.polymerization.lammps_import \
  --source external/lammps_oplss/moltemplate_oplsaa_tiny \
  --out examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/resolved.yaml \
  --report examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/REPORT.md
