# ORCA epoxy-amine smoke test

## Purpose

This document defines the first chemically relevant QM smoke test after the ORCA, ASE, RDKit, xTB, CREST, and Open Babel setup is working.

The goal is to move from generic water/methylamine checks to the smallest useful epoxy-amine model for the kUPS reactive polymerization project, while staying safe for a small laptop.

This smoke test is split into two parts:

- **Phase 9A: EnGrad label smoke test** for ML force-field data.
- **Phase 9B: scan/barrier prototype** for reaction-rate data.

Run Phase 9A first. Do not start Phase 9B until a single reduced epoxy-amine `EnGrad` label finishes cleanly and its wall time is known.

## Reduced model

Use the smallest local model that still contains the key chemistry:

```text
glycidyl methyl ether + methylamine
```

Useful SMILES:

```text
glycidyl methyl ether:  COCC1CO1
methylamine:            CN
ring-opened product:    COCC(O)CNC
```

This model keeps:

- the epoxide ring;
- an ether substituent on the epoxide side;
- a primary amine nucleophile;
- the beta-amino alcohol product motif.

It removes the large aromatic BFDGE/DGEBA/DETDA groups so the first QM labels are small enough to run locally.

## Why Phase 9A comes first

For MLFF labels, the useful quantum-chemical target is:

```text
{atomic numbers, coordinates, total energy, forces}
```

In ORCA, that means a single-point energy plus gradient:

```text
EnGrad
```

Optimized structures are useful for sanity checks, but they are not enough for MLFF training because the forces near a minimum are small. The first useful label should be a deliberately non-equilibrium near-reaction geometry.

## Phase 9A: EnGrad label smoke test

### Goal

Generate one laptop-safe DFT label for a near-attack epoxy-amine geometry.

The first geometry is:

```text
R2: near-attack reactant complex
```

Target features:

```text
N...C_epoxide distance: 2.2-2.6 A
amine oriented toward an epoxide carbon
epoxide ring still intact
not fully relaxed
nonzero forces expected
```

### First job to run

Run exactly one ORCA job first:

```text
R2, B3LYP-D3BJ/def2-SVP, EnGrad
```

Laptop-safe ORCA input pattern:

```orca
! B3LYP D3BJ def2-SVP TightSCF EnGrad

%pal
  nprocs 1
end

%maxcore 1000

* xyz 0 1
# R2 coordinates here
*
```

Do not start with `nprocs 4` or `%maxcore 3000` on the laptop. Increase only after the first R2 timing is known.

The first local run used the conservative tested keyword line above. A more elaborate `RIJCOSX Grid5` line can be tried later, but the first attempt with that line failed during input parsing on this ORCA 6.1.0 install.

### Phase 9A sequence

1. Build glycidyl methyl ether and methylamine with RDKit.
2. Generate a near-attack R2 complex with N...C distance near 2.4 A.
3. Write `r2_near_attack.xyz`.
4. Write the cluster-ready `r2_near_attack_svp_engrad.inp`.
5. Run the ORCA `EnGrad` job.
6. Confirm normal termination and an `.engrad` file.
7. Record wall time, output size, final energy, and maximum force magnitude.

Only after R2 succeeds:

8. Generate R1 separated reactant complex.
9. Generate P1 ring-opened product.
10. Run R1/R2/P1 at the same cheap level.

### Phase 9A success criteria

The first R2 label is successful if:

- ORCA terminates normally.
- ORCA writes an `.engrad` file.
- The job uses one process.
- The wall time is acceptable for local iteration.
- The geometry has no obvious atom overlap.
- The N...C distance remains in the intended near-attack range.

## Phase 9B: scan/barrier prototype

### Goal

After Phase 9A works, start generating chemistry data for reaction barriers and rate models.

Phase 9B is not primarily an MLFF-label task. It is for:

- reaction-coordinate scans;
- approximate barriers;
- later TS or NEB setup;
- rate-table or learned-rate calibration.

### First scan

Use the same reduced model and scan the forming N-C distance:

```text
r_NC = 3.0, 2.8, 2.6, 2.4, 2.2, 2.0, 1.8, 1.6 A
```

Optionally add the epoxide C-O breaking coordinate later. Do not start with a 2D scan on the laptop.

### Phase 9B job type

The first scan can use constrained optimizations:

```orca
! B3LYP D3BJ def2-SVP RIJCOSX TightSCF Grid5 Opt
```

The exact ORCA constraint syntax should be tested on one point before launching the full scan.

### Phase 9B success criteria

The scan prototype is successful if:

- each point terminates normally or fails clearly;
- the constrained N-C distance is respected;
- relative energies can be extracted;
- there are no discontinuous geometry jumps;
- the scan shape is chemically plausible enough to justify TS/NEB follow-up.

First local Phase 9B gate attempt:

```text
job: R2-NC-2p4-Opt
method: B3LYP-D3BJ/def2-SVP
cores: 1
maxcore: 1000 MB
constraint: N-C = 2.400 A
last completed cycle before interruption: 18
last energy: -402.941793455316 Eh
last RMS gradient: 0.0006245563
last MAX gradient: 0.0028245821
status: interrupted before convergence
```

The important result is that ORCA accepted the N-C bond constraint and preserved the constrained distance, but the constrained optimization did not converge quickly enough for an immediate laptop-scale full scan. The next Phase 9B step should be an xTB or very loose ORCA pre-scan, followed by selected ORCA single-point `EnGrad` or single-point energies on chosen geometries.

## Directory layout

Use repo-local scripts and test fixtures for smoke-test definitions. The first portable ORCA input lives under `test/polymerization/fixtures` so it can be copied to the cluster directly:

```text
scripts/polymerization/qm/
  generate_epoxy_amine_r2_near_attack.py
  prepare_epoxy_amine_orca_smoke.py
  run_orca_smoke_job.sh
  parse_orca_smoke_results.py
  slurm_orca_smoke_array.sh
scripts/Potsdam/
  orca_epoxy_amine_smoke.job
test/polymerization/fixtures/
  epoxy_amine_pre_orca/
    smiles.txt
    r2_near_attack.xyz
    r2_near_attack_metadata.csv
  epoxy_amine_orca/
    manifest.csv
    r2_near_attack_svp_engrad/
      r2_near_attack_svp_engrad.inp
      r2_near_attack_svp_engrad.xyz
```

Large ORCA outputs stay ignored (`*.out`, `*.engrad`, `*.gbw`, and related files are ignored) unless they are later curated into a structured dataset.

For cluster use, start with:

```bash
conda run -n kups-env python scripts/polymerization/qm/prepare_epoxy_amine_orca_smoke.py \
  --include R2 \
  --out test/polymerization/fixtures/epoxy_amine_orca \
  --nprocs 10 \
  --maxcore 1500
```

Then transfer or run `test/polymerization/fixtures/epoxy_amine_orca/r2_near_attack_svp_engrad` with ORCA. The generated `.inp` contains inline coordinates and does not require RDKit at run time.

The cluster-side minimum installation for the first label is ORCA plus its OpenMPI/runtime dependencies. RDKit, xTB, CREST, ASE, and Open Babel are needed for geometry generation and later workflow expansion, not for running this first prepared ORCA input.

## Methods ladder

Start cheap and small:

```text
B3LYP-D3BJ/def2-SVP, EnGrad, nprocs 1, maxcore 1000
```

Only after the R2/R1/P1 cheap labels work, try:

```text
wB97X-V/def2-TZVP, EnGrad
```

Do not use `def2-TZVPP` for the first laptop test.

## Timing table

Record every job:

| Job | Atoms | Method | Basis | Cores | Max memory/core | Wall time | Finished? | Output size | Notes |
|---|---:|---|---|---:|---:|---:|---|---:|---|
| R2-SVP-EnGrad | | B3LYP-D3BJ | def2-SVP | 1 | 1000 MB | | | | first gate |
| R1-SVP-EnGrad | | B3LYP-D3BJ | def2-SVP | 1 | 1000 MB | | | | after R2 |
| P1-SVP-EnGrad | | B3LYP-D3BJ | def2-SVP | 1 | 1000 MB | | | | after R2 |
| R2-TZVP-EnGrad | | wB97X-V | def2-TZVP | 1-2 | 1000-2000 MB | | | | optional |
| P1-TZVP-EnGrad | | wB97X-V | def2-TZVP | 1-2 | 1000-2000 MB | | | | optional |

The first decision number is the wall time for `R2-SVP-EnGrad`.

First local result:

| Job | Atoms | Method | Basis | Cores | Max memory/core | Wall time | Finished? | Energy | Max force | Notes |
|---|---:|---|---|---:|---:|---:|---|---:|---:|---|
| R2-SVP-EnGrad | 21 | B3LYP-D3BJ | def2-SVP | 1 | 1000 MB | 47.38 s | yes | -402.772503791679 Eh | 0.146094466658 Eh/bohr | `.engrad` written |

## Connection to the larger project

Phase 9A supplies the first DFT force labels for a reduced reactive motif. These labels are useful for testing:

- ORCA runtime and output handling;
- force extraction from `.engrad`;
- conversion to `.extxyz`;
- whether near-reactive geometries are numerically stable;
- a first MLFF data schema.

Phase 9B supplies the first reaction-energy and barrier-like data for the later rate model.

The reduced model is not the final chemistry. Later stages must add:

- larger BFDGE/DGEBA-like epoxy fragments;
- DETDA/DDS-like aromatic amines;
- primary vs secondary amine additions;
- product conformer diversity;
- nonreactive packing contacts;
- strained local network fragments.

## Immediate next step

Generate the first R2 near-attack geometry and ORCA input:

```text
test/polymerization/fixtures/epoxy_amine_pre_orca/r2_near_attack.xyz
test/polymerization/fixtures/epoxy_amine_orca/r2_near_attack_svp_engrad/r2_near_attack_svp_engrad.inp
```

Do not run the ORCA job until the generated geometry has been inspected for atom count, N...C distance, and obvious overlaps.

Completed first run:

```text
SCF CONVERGED AFTER 10 CYCLES
FINAL SINGLE POINT ENERGY      -402.772503791679
CARTESIAN GRADIENT
ORCA TERMINATED NORMALLY
```

Output files:

```text
results/qm/epoxy_amine_smoke/orca_outputs/r2_b3lyp_svp_engrad.out
results/qm/epoxy_amine_smoke/orca_inputs_generated/r2_b3lyp_svp_engrad.engrad
results/qm/epoxy_amine_smoke/timing/timing_table.csv
```
