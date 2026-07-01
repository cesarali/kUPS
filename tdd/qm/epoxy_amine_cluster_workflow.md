# Cluster workflow for the epoxy-amine ORCA smoke test

## What this tests

This is the first small calculation type needed for MLFF development:

```text
reduced epoxy-amine near-attack geometry -> DFT energy + forces
```

The first job is:

```text
R2 near-attack glycidyl methyl ether + methylamine
B3LYP-D3BJ/def2-SVP
ORCA EnGrad
21 atoms
```

The output label is:

```text
atomic numbers + coordinates + total energy + gradients/forces
```

This tells us:

- whether ORCA runs on the cluster;
- how long a small reactive-motif force label takes;
- how large outputs and scratch files are;
- whether the method is stable enough for a larger label campaign.

## Cluster software requirements

Required on the cluster compute node:

```text
ORCA 6.x
OpenMPI runtime compatible with the ORCA build
/usr/bin/time or equivalent timing command
bash
```

Required only if generating geometries on the cluster:

```text
RDKit
```

Required only if parsing results on the cluster:

```text
Python 3
numpy
```

If geometries and ORCA inputs are generated locally first, the cluster does not need RDKit for the ORCA run itself.

Optional later:

```text
xTB
CREST
ASE
Open Babel
```

Those are useful for conformers, pre-optimization, scans, and conversion, but the first ORCA `EnGrad` smoke job only needs ORCA.

## Prepare jobs

From the repo root:

```bash
conda run -n kups-env python scripts/polymerization/qm/prepare_epoxy_amine_orca_smoke.py \
  --include R2 \
  --out test/polymerization/fixtures/epoxy_amine_orca \
  --nprocs 10 \
  --maxcore 1500
```

To prepare the three cheap labels after R2 succeeds:

```bash
conda run -n kups-env python scripts/polymerization/qm/prepare_epoxy_amine_orca_smoke.py \
  --include R1,R2,P1 \
  --out test/polymerization/fixtures/epoxy_amine_orca \
  --nprocs 10 \
  --maxcore 1500
```

The generated ORCA inputs contain inline coordinates, so each job directory is portable.

## Run one job without SLURM

On the cluster login or compute node, set the ORCA binary:

```bash
export ORCA_BIN=/path/to/orca
```

Run:

```bash
bash scripts/polymerization/qm/run_orca_smoke_job.sh \
  test/polymerization/fixtures/epoxy_amine_orca/r2_near_attack_svp_engrad
```

## Run with SLURM

Use `scripts/Potsdam/orca_epoxy_amine_smoke.job` for the Potsdam cluster setup from `tdd/qm/ORCA_USAGE.md`. The generic fallback is `scripts/polymerization/qm/slurm_orca_smoke_array.sh`.

For one R2 job, keep:

```text
#SBATCH --array=0-0
#SBATCH --cpus-per-task=10
#SBATCH --mem=24G
#SBATCH --time=00:30:00
```

Submit:

```bash
export ORCA_BIN=/path/to/orca
export SMOKE_ROOT=$PWD/test/polymerization/fixtures/epoxy_amine_orca
sbatch scripts/Potsdam/orca_epoxy_amine_smoke.job
```

For three jobs, regenerate with `--include R1,R2,P1` and change:

```text
#SBATCH --array=0-2
```

## Parse results

```bash
conda run -n kups-env python scripts/polymerization/qm/parse_orca_smoke_results.py \
  test/polymerization/fixtures/epoxy_amine_orca
```

This writes:

```text
test/polymerization/fixtures/epoxy_amine_orca/results.csv
```

## Local reference result

On the laptop, the first R2 `EnGrad` label took:

```text
47.38 s
energy = -402.772503791679 Eh
max gradient = 0.146094466658 Eh/bohr
```

Use this as a rough sanity check. The cluster may be faster or slower depending on CPU generation, filesystem, ORCA build, and module configuration.
