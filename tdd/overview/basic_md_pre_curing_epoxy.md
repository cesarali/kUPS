# Minimal non-reactive MD setup before epoxy curing / topology-transfer MC

This note extracts the **plain molecular-dynamics part** of the thermoset-hardening workflow of Meißner et al. and removes the Monte Carlo curing step, the QM/MM reaction-energy check, and the smooth topology-transfer reaction move. The goal is only to prepare and equilibrate a **neat, uncured epoxy/amine mixture** that could later be handed to a reactive/topology-changing algorithm.

## 1. Physical system

### Chemistry

Use the same simplified epoxy resin system as the paper:

- **Epoxy monomer:** bisphenol F diglycidyl ether, abbreviated **BFDGE**.
- **Amine hardener:** 4,6-diethyl-2-methylbenzene-1,3-diamine, abbreviated **DETDA**.
- **Solvent:** none. This is a neat thermoset precursor mixture, not a solution.
- **Initial state:** uncured, randomly packed BFDGE + DETDA molecules with no cross-links.
- **Boundary conditions:** 3D periodic boundary conditions.

### Stoichiometry

Use the functional stoichiometry of epoxy groups to amine hydrogens:

- Each BFDGE has **2 epoxide groups**.
- Each DETDA has **2 primary amines**, therefore **4 reactive N-H hydrogens** in the idealized model.
- Stoichiometric functional ratio: **2 BFDGE : 1 DETDA**.

For a first cluster/HPC test, use one of these sizes:

| Label | BFDGE molecules | DETDA molecules | Approximate purpose |
|---|---:|---:|---|
| tiny debug | 8 | 4 | check topology, charges, minimization |
| small pilot | 32 | 16 | minimal meaningful mixture, still cheap |
| medium pilot | 64 | 32 | better density/RDF statistics |
| production-like small cell | 128 | 64 | more stable amorphous packing |

The ReaxFF paper using the same chemistry reports a system with **32 bis F + 16 DETDA = 1872 atoms**, so the `32:16` case is a sensible first atomistic pilot size. For the non-reactive OPLS-AA setup of Meißner et al., the paper does not give one explicit molecule count in the visible methods text, so the table above should be treated as a practical reconstruction rather than an exact reproduction.

## 2. Force-field model

### Recommended first implementation

Use a **fixed-topology all-atom force field** for the pre-curing MD:

- Force field: **OPLS-AA** or another fixed-topology organic force field that supports the two monomers.
- Charges: use **1.14\*CM1A-LBCC** partial charges, as in the paper, or a consistent replacement such as RESP/AM1-BCC if your workflow is built around GAFF/OpenFF.
- Topology generation: LigParGen was used in the paper for OPLS-AA topologies and charges.
- Simulation engine: LAMMPS is natural because the later paper workflow also uses LAMMPS.

Important practical detail: before running MD, make sure each molecule is **charge neutral**. The paper notes that LigParGen can produce very small non-neutrality and non-identical charges for symmetry-equivalent atoms; they corrected these by charge compensation and averaging equivalent atoms. Do the same, otherwise energy offsets can pollute later topology-change comparisons.

## 3. Initial coordinates

### Packing

Generate a random, uncured mixture with PACKMOL, then convert it to a LAMMPS data file with moltemplate, tleap, InterMol, ParmEd, or your preferred route.

Target an initially loose density, because the system will be compressed/relaxed by NPT:

- Initial density: **0.4--0.6 g/cm³**.
- Suggested default: **0.5 g/cm³**.
- Minimum intermolecular distance in PACKMOL: start with **2.0--2.5 Å**.

Example PACKMOL logic, not exact syntax for your files:

```text
tolerance 2.2
filetype pdb
output uncured_mix.pdb

structure BFDGE.pdb
  number 32
  inside box 0. 0. 0. L L L
end structure

structure DETDA.pdb
  number 16
  inside box 0. 0. 0. L L L
end structure
```

Choose `L` from the desired mass density. For the `32 BFDGE + 16 DETDA` system, compute the total mass from the molecular weights and solve

```text
V = mass / rho_initial
L = V^(1/3)
```

Use consistent units; if mass is in g and density in g/cm³, convert the volume to Å³ with `1 cm³ = 1e24 Å³`.

## 4. Minimal MD protocol before any Monte Carlo/reaction step

This is the core minimal protocol. It gives you a relaxed, mixed, uncured liquid/resin precursor.

### Stage 0: energy minimization

Purpose: remove packing overlaps.

- Ensemble: minimization, no thermostat.
- Boundary: periodic.
- Stop criteria: standard LAMMPS minimization tolerances, e.g. `1e-4` energy and `1e-6` force, or stricter if stable.
- Use neighbor-list settings appropriate for all-atom organics.

### Stage 1: short restrained/soft relaxation, optional but recommended

Purpose: avoid explosions from bad random contacts.

- Ensemble: NVT.
- Temperature: start at **300 K** or the intended curing temperature.
- Time step: **0.25 fs** for the first few ps if the packing is bad; then move to **0.5 fs**.
- Duration: **5--20 ps**.
- Thermostat: Nosé-Hoover or Langevin.

This stage is not explicitly central in the paper, but it is a practical safety layer for cluster runs.

### Stage 2: density relaxation / mixing

This corresponds to the pre-reaction relaxation described in the paper.

- Ensemble: **NPT**.
- Pressure: **1 atm**.
- Temperature: choose one target temperature:
  - 300 K for a room-temperature initial model.
  - 380 K, 420 K, or 460 K if you want to match the curing-temperature cases discussed in the paper.
  - 260--460 K if you later want to reproduce the temperature series.
- Time step: **0.5 fs**.
- Duration: **0.2 ns** = 200 ps.
- Number of steps: `0.2 ns / 0.5 fs = 400,000 steps`.
- Thermostat: Nosé-Hoover, damping time about **50 fs**.
- Barostat: Nosé-Hoover / Martyna-Tobias-Klein style, damping time typically **500--1000 fs**.

The output after this stage is your first useful **uncured equilibrated mixture**.

### Stage 3: constant-volume sampling for RDF / nearest-neighbor structure

The paper follows the 0.2 ns relaxation by a short constant-volume run to sample radial pair distribution functions of the uncured thermoset mixture. For your non-reactive setup this is useful for diagnosing whether epoxide and amine sites are spatially mixed.

- Ensemble: **NVT**.
- Volume: fixed to the final box from Stage 2.
- Temperature: same as Stage 2.
- Time step: **0.5 fs**.
- Duration: **0.05 ns** = 50 ps.
- Number of steps: `0.05 ns / 0.5 fs = 100,000 steps`.
- Thermostat: Nosé-Hoover, damping time about **50 fs**.

Suggested outputs:

- trajectory every 0.5--1 ps;
- thermodynamics every 100--1000 steps;
- RDF between epoxide reactive carbon/oxygen atoms and amine nitrogen/hydrogen atoms;
- final restart/data file.

## 5. What this protocol intentionally does *not* include

This minimal MD file excludes:

- Monte Carlo trial selection;
- Metropolis acceptance/rejection;
- QM/MM correction terms;
- bond creation;
- proton transfer;
- atom-type changes;
- switching between reactant and product topologies;
- reactive ReaxFF acceleration or bond-boost terms.

So the chemistry is **frozen**: the molecules move, rotate, collide, mix, and densify, but they do not polymerize.

## 6. LAMMPS input skeleton

This is a schematic template, not a directly runnable input file because atom types, pair coefficients, bonded coefficients, and groups depend on your generated topology.

```lammps
units           real
atom_style      full
boundary        p p p

read_data       uncured_mix.data

# OPLS-like nonbonded settings; adapt to your actual force-field export.
pair_style      lj/cut/coul/long 10.0
bond_style      harmonic
angle_style     harmonic
dihedral_style  opls
improper_style  harmonic
kspace_style    pppm 1.0e-4

neighbor        2.0 bin
neigh_modify    every 1 delay 0 check yes

# ---------- minimization ----------
reset_timestep  0
thermo          500
min_style       cg
minimize        1.0e-4 1.0e-6 1000 10000

# ---------- optional safe NVT ----------
timestep        0.25
velocity        all create 300.0 4928459 mom yes rot yes dist gaussian
fix             pre all nvt temp 300.0 300.0 50.0
run             20000     # 5 ps with 0.25 fs
unfix           pre

# ---------- NPT density relaxation ----------
timestep        0.5
fix             eq all npt temp 300.0 300.0 50.0 iso 1.0 1.0 1000.0
thermo_style    custom step temp press density pe ke etotal vol
thermo          1000
dump            d1 all custom 2000 traj_npt.lammpstrj id type mol x y z
run             400000    # 0.2 ns
unfix           eq
undump          d1

# ---------- NVT structural sampling ----------
fix             sample all nvt temp 300.0 300.0 50.0
dump            d2 all custom 2000 traj_nvt.lammpstrj id type mol x y z
run             100000    # 0.05 ns
unfix           sample
undump          d2

write_data      uncured_equilibrated.data
write_restart   uncured_equilibrated.restart
```

For 380, 420, or 460 K, replace the temperature values consistently, for example:

```lammps
fix eq all npt temp 420.0 420.0 50.0 iso 1.0 1.0 1000.0
fix sample all nvt temp 420.0 420.0 50.0
```

## 7. Minimal checklist before submitting to the cluster

Before spending GPU/CPU time, verify:

- The total charge of the periodic cell is zero.
- There are no missing bond, angle, dihedral, or improper coefficients.
- The initial density is not accidentally 10x too high or too low.
- The first minimization does not produce enormous forces after convergence.
- The NPT run reaches a stable density instead of box collapse or vacuum expansion.
- Temperature and pressure fluctuations are reasonable for a small all-atom cell.
- The final trajectory shows a homogeneous mixture, not phase separation or huge voids.

## 8. Expected final artifact

At the end of this minimal workflow you should have:

```text
uncured_equilibrated.data
uncured_equilibrated.restart
traj_npt.lammpstrj
traj_nvt.lammpstrj
log.lammps
```

The key file for later MC/topology-transfer work is:

```text
uncured_equilibrated.restart
```

or, if your later code prefers a data file:

```text
uncured_equilibrated.data
```

This represents the equilibrated uncured resin/hardener mixture just before any reaction attempts.

## 9. Relation to the paper

The parts of the paper used here are only the non-reactive preparation elements: BFDGE/DETDA chemistry, OPLS-AA/LigParGen molecular mechanics topologies, PACKMOL/moltemplate randomized starting configurations, 0.2 ns pre-reaction relaxation, 0.05 ns constant-volume sampling, NPT at 1 atm, curing-temperature choices between 260 and 460 K, and 0.5 fs MD time step during the topology-transfer/equilibration workflow.

