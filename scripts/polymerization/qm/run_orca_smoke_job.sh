#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 JOB_DIR" >&2
  exit 2
fi

JOB_DIR="$1"
ORCA_BIN="${ORCA_BIN:-orca}"

cd "$JOB_DIR"
INPUT="$(ls *.inp | head -n 1)"
BASE="${INPUT%.inp}"

echo "job_dir=$PWD"
echo "orca_bin=$ORCA_BIN"
echo "input=$INPUT"
echo "start_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

/usr/bin/time -p "$ORCA_BIN" "$INPUT" > "${BASE}.out" 2> "${BASE}.time"

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
