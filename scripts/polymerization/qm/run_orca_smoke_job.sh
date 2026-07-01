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

set +e
/usr/bin/time -p "$ORCA_BIN" "$INPUT" > "${BASE}.out" 2> "${BASE}.time"
ORCA_STATUS=$?
set -e

echo "end_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "orca_exit_status=$ORCA_STATUS"

if [[ "$ORCA_STATUS" -ne 0 ]]; then
  echo "[orca] command failed; inspect ${BASE}.out and ${BASE}.time" >&2
  tail -n 40 "${BASE}.time" >&2 || true
  tail -n 40 "${BASE}.out" >&2 || true
  exit "$ORCA_STATUS"
fi

if ! grep -q "ORCA TERMINATED NORMALLY" "${BASE}.out"; then
  echo "[orca] output does not contain normal termination" >&2
  tail -n 80 "${BASE}.out" >&2 || true
  exit 1
fi

if [[ ! -s "${BASE}.engrad" ]]; then
  echo "[orca] expected gradient file was not written: ${BASE}.engrad" >&2
  ls -la >&2
  exit 1
fi

echo "out_file=${PWD}/${BASE}.out"
echo "engrad_file=${PWD}/${BASE}.engrad"
echo "time_file=${PWD}/${BASE}.time"
