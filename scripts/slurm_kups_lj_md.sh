#!/bin/bash

###############################################################################
# kups-cuda-test.job – check kUPS + JAX CUDA on one GPU
###############################################################################
#SBATCH --partition=gpu
#SBATCH --nodes=1
#SBATCH --gpus=tesla_v100:1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=0-00:20
#SBATCH --chdir=/home/ojedamarin/Projects/Polymerization/kUPS
#SBATCH --mail-type=END,FAIL
#SBATCH --output=/work/ojedamarin/kups-cuda-test-%j.out
#SBATCH --error=/work/ojedamarin/kups-cuda-test-%j.err
###############################################################################

module purge

# Robust conda activation inside SLURM
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate kups-main

# Avoid system CUDA libraries overriding pip-installed JAX CUDA wheels
unset LD_LIBRARY_PATH

# Avoid JAX preallocating all GPU memory
export XLA_PYTHON_CLIENT_PREALLOCATE=false

echo "=== Host ==="
hostname

echo "=== GPU ==="
nvidia-smi

echo "=== Python / JAX / kUPS test ==="
python - <<'PY'
import kups
import jax

print("kUPS import OK")
print("JAX:", jax.__version__)
print("Devices:", jax.devices())

gpu_devices = [d for d in jax.devices() if d.platform == "gpu"]
assert len(gpu_devices) > 0, "No GPU visible to JAX"

print("CUDA/JAX GPU test passed.")
PY
