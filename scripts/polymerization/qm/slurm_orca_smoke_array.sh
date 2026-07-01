#!/usr/bin/env bash
#SBATCH --job-name=epoxy-amine-orca-smoke
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --array=0-0
#SBATCH --output=slurm-%A_%a.out
#SBATCH --error=slurm-%A_%a.err

set -euo pipefail

# Edit these for your cluster, or set them before sbatch.
# Example:
#   export ORCA_BIN=/path/to/orca
#   export SMOKE_ROOT=$PWD/results/qm/epoxy_amine_smoke/cluster_runs
ORCA_BIN="${ORCA_BIN:-orca}"
SMOKE_ROOT="${SMOKE_ROOT:-$PWD/results/qm/epoxy_amine_smoke/cluster_runs}"

mapfile -t JOB_DIRS < <(find "$SMOKE_ROOT" -mindepth 1 -maxdepth 1 -type d | sort)
JOB_DIR="${JOB_DIRS[$SLURM_ARRAY_TASK_ID]}"

echo "SLURM_JOB_ID=${SLURM_JOB_ID:-}"
echo "SLURM_ARRAY_TASK_ID=${SLURM_ARRAY_TASK_ID:-}"
echo "JOB_DIR=$JOB_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCA_BIN="$ORCA_BIN" "$SCRIPT_DIR/run_orca_smoke_job.sh" "$JOB_DIR"
