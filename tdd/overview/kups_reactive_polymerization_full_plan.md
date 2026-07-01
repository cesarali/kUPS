# Full revised research plan: kUPS reactive polymerization via hardening-paper reproduction, ORCA data, and ML force fields

## Executive summary

The long-term goal is a SimPoly-like reactive polymer simulation framework: machine-learning force fields (MLFFs) for continuous atomistic dynamics, coupled to a learned or calibrated reaction-event model for polymerization. The immediate practical goal should not be to train a full reactive MLFF from scratch. The best first serious project is to reproduce, inside kUPS, the algorithmic core of the Meißner et al. thermoset-hardening paper: molecular dynamics relaxation, Monte Carlo selection of epoxy/amine reaction candidates, smooth topology transfer from reactant to product state, and accept/reject logic based on energetic feasibility.

This intermediate benchmark is valuable because it converts the project from a vague “simulate polymerization with ML” problem into a concrete software and scientific milestone. It also aligns naturally with kUPS: the missing general capability is a JAX-compatible topology-changing reactive-event layer. Once that layer exists, ORCA-generated quantum data can be used to calibrate or train reaction rates/barriers, and MLFFs can gradually replace classical potentials.

The plan below is therefore organized around three nested goals:

1. **Software goal:** implement dynamic topology and smooth topology transfer in kUPS.
2. **Chemistry benchmark goal:** reproduce the hardening-paper epoxy/amine curing mechanism qualitatively.
3. **ML goal:** replace fixed QM corrections and heuristic rates with ORCA-derived learned reaction models and, eventually, MLFF-driven dynamics.

---

## Scientific framing

SimPoly demonstrates that polymer bulk properties can be predicted from atomistic MD driven by ML force fields trained on first-principles data. Its main setting is non-reactive: the polymer chains are already defined, and the MLFF must model intra- and inter-chain interactions accurately enough to predict density and glass-transition behavior. Polymerization is harder because the molecular graph changes during the simulation. Bonds form, rings open, atom types and local chemical environments change, and the polymer network grows. A fixed-topology force field or standard non-reactive MLFF is therefore not sufficient by itself.

The thermoset-hardening paper provides a more direct algorithmic template for reactive polymerization. It treats local epoxy–amine bond formation with small QM-derived corrections and treats the full network by MM/MD. It then uses MC selection and smooth topology transfer to allow the network to relax during attempted bond formation. This is exactly the bridge needed for the present project: **continuous dynamics plus discrete topology-changing events**.

The revised plan therefore introduces a new central milestone: **Hardening-paper reproduction in kUPS**. This milestone sits between toy reactive models and the full MLFF/ORCA program. It gives a concrete, publishable software target: a kUPS-compatible controlled topology-transfer propagator for reactive polymerization.

---

## Revised phase overview

```text
Phase 0  kUPS baseline and reproducible simulation stack
Phase 1  Toy reactive state: A + B ⇌ AB
Phase 2  Smooth topology transfer on toy systems
Phase 3  Hardening-paper reproduction in kUPS
Phase 4  Independent ORCA/QM reaction dataset
Phase 5  Learned local barrier/rate model
Phase 6  Coupling learned rates to kUPS reactive dynamics
Phase 7  Epoxy curing benchmark and comparison to baselines
Phase 8  SimPoly-style MLFF extension for reactive polymer systems
Phase 9  Method paper / software contribution
```

The most important change relative to the first plan is Phase 3. It is now an explicit intermediate benchmark rather than being implicitly distributed across the ORCA, kUPS, and epoxy-benchmark phases.

---

# Phase 0 — kUPS baseline and reproducible simulation stack

## Goal

Establish that kUPS can run stable simple simulations, write outputs, and serve as the execution substrate for hybrid MD/MC work.

## Deliverables

- Clean environment with kUPS installed.
- Reproduced kUPS examples:
  - Lennard-Jones argon NVE.
  - Lennard-Jones argon NVT.
  - geometry relaxation.
  - short MLFF MD or MLFF relaxation example.
- Repository skeleton:

```text
reactive-kups-polymerization/
  src/reactive_kups/
  tests/
  examples/
  data/
  notebooks/
  reports/
  qm/
  configs/
```

## Tests for success

- NVE energy drift is acceptably small.
- NVT temperature stabilizes around the target value.
- Relaxation decreases energy and maximum force.
- Outputs can be read and plotted.
- Simulations are reproducible from fixed random seeds.

## Fit into whole project

This phase validates the basic computational substrate. It does not yet test chemistry.

---

# Phase 1 — toy reactive state: A + B ⇌ AB

## Goal

Create the smallest possible topology-changing system in kUPS. Two particles, `A` and `B`, can form a bonded state `AB`; the bond can optionally dissociate in the reverse direction.

## Scientific role

This phase isolates the central computational problem: topology mutation. It avoids epoxy chemistry, atom typing, proton transfer, and force-field complexity.

## Required abstractions

```python
ReactionTemplate
ReactionCandidate
ReactionEvent
ReactiveState
BondTable
TopologyPatch
ReactiveKMCMove
```

A JAX-compatible bond table should avoid dynamically appending Python objects:

```text
bond_i[max_bonds]
bond_j[max_bonds]
bond_type[max_bonds]
bond_active[max_bonds]
```

## Deliverables

- Fixed-capacity bond table with active masks.
- Candidate finder for `A-B` pairs within a distance cutoff.
- Bond creation and deletion patches.
- Simple harmonic or Morse bonded potential over active bonds.
- Unit tests for topology mutation.

## Tests for success

1. Activating a bond changes exactly one inactive slot to active.
2. Deactivating a bond reverses the state correctly.
3. Energy after patch agrees with full recomputation.
4. The system runs under `jax.jit`.
5. Batched simulations can be run with independent random seeds.
6. The reversible dimerization equilibrium matches a brute-force or analytic reference in a small box.

## Fit into whole project

This phase creates the minimal topology-changing machinery that all later polymerization simulations require.

---

# Phase 2 — smooth topology transfer on toy systems

## Goal

Implement the hardening-paper mechanism in its simplest mathematical form: do not switch instantly from reactant topology to product topology. Instead interpolate between the two over a short MD window.

## Core idea

For a reaction attempt, define a smooth switching variable `s(t)` from 0 to 1 and use an interpolated potential:

```text
E_mix(x, t) = (1 - s(t)) E_reactant(x) + s(t) E_product(x)
```

If the reaction is accepted, commit the product topology. If it is rejected, smoothly reverse back to the reactant topology.

## Deliverables

- `SmoothTopologyTransferPropagator`.
- Smooth switching function.
- Reactant and product potential wrappers.
- Commit/reverse topology logic.
- Toy demonstration with `A + B → AB`.

## Tests for success

1. Energy and forces do not show catastrophic spikes during transfer.
2. Accepted moves end in the product topology.
3. Rejected moves return to the reactant topology.
4. The same candidate can be replayed deterministically with a fixed seed.
5. The transition works under JIT for fixed-size systems.
6. Energy interpolation matches explicit reactant/product evaluations.

## Fit into whole project

This is the core algorithmic bridge between simple topology mutation and the Meißner hardening-paper reproduction. It is also the most likely useful contribution to kUPS itself.

---

# Phase 3 — hardening-paper reproduction in kUPS

## Goal

Reproduce the algorithmic structure of the Meißner et al. thermoset-hardening paper inside kUPS. The first target is not exact numerical equality with the LAMMPS implementation. The first target is qualitative reproduction of the mechanism and its validation curves.

## Why this phase is now explicit

In the original plan, hardening-paper reproduction was distributed across the toy topology phase, ORCA/QM phase, and epoxy benchmark phase. That made the plan logically correct but operationally vague. This dedicated phase turns the hardening paper into the first serious benchmark for the kUPS extension.

## Target algorithm

```text
1. Start from mixed BFDGE/DETDA or simplified epoxy/amine system.
2. Run MD relaxation.
3. Build list of nearby epoxy/amine candidates.
4. Select one candidate reaction.
5. Construct product topology.
6. Smoothly transfer reactant topology to product topology.
7. Estimate reaction energy using MM energy difference + QM correction.
8. Accept/reject by Metropolis criterion.
9. Commit product topology if accepted; reverse if rejected.
10. Repeat until curing saturates.
```

## Relation to the hardening paper

The Meißner paper uses:

- BFDGE + DETDA as the simplified simulation chemistry.
- Gaussian03/B3LYP/6-311+G** for two local reaction energies.
- First epoxy–amine linking correction around `-25.5 kcal/mol`.
- Second linking correction around `-15.5 kcal/mol`.
- MC/MD curing at multiple temperatures.
- A 5 Å candidate cutoff based on epoxy/amine radial distribution functions.
- Smooth topology transfer to avoid unstable immediate topology switching.
- Validation against DSC curing data and mechanical properties.

For the kUPS reproduction, only the algorithmic core is mandatory at first. Exact force-field reproduction can come later.

## Subphase 3a — minimal ORCA sanity reproduction of local reaction corrections

### Goal

Reproduce the two local reaction-energy calculations approximately, using ORCA rather than Gaussian.

### Deliverables

- ORCA input files for:
  - BFDGE or reduced epoxy fragment.
  - DETDA or reduced amine fragment.
  - first linked product.
  - second linked product.
- Energy bookkeeping script:

```text
ΔE1 = E(first_product)  - E(epoxy) - E(amine)
ΔE2 = E(second_product) - E(first_product) - E(epoxy)
```

### Tests for success

- Products are chemically valid.
- Optimized minima have no imaginary frequencies.
- Reaction energies are exothermic.
- First reaction is more exothermic than the second.
- Values are at least qualitatively comparable to the hardening-paper values.

### Fit into the whole project

This tests that ORCA structures, proton transfer, product definitions, and energy bookkeeping are correct. It is not yet the main ML dataset.

## Subphase 3b — kUPS hardening-paper toy reproduction

### Goal

Reproduce the hardening-paper algorithm on a simplified epoxy-like model, not full BFDGE/DETDA.

### Deliverables

- Simplified epoxy/amine particles or small molecules.
- Candidate finder based on reactive-site distance.
- Smooth topology transfer for one reaction event.
- Metropolis accept/reject logic with a fixed correction energy.
- Logs of accepted/rejected attempts.

### Tests for success

- Candidate list updates after every accepted reaction.
- Acceptance probability decreases as local strain increases.
- Rejected moves reverse without instability.
- Final conversion saturates below 100% if steric/geometric constraints are present.

### Fit into the whole project

This proves that the hardening-paper algorithm can live in kUPS before adding chemical complexity.

## Subphase 3c — BFDGE/DETDA kUPS reproduction

### Goal

Move from toy chemistry to the real hardening-paper chemistry.

### Deliverables

- Initial BFDGE/DETDA box generation workflow.
- Reactive-site annotation:
  - epoxy terminal carbon.
  - epoxy oxygen/ring state.
  - primary/secondary/tertiary amine state.
- Topology patch for first and second linking reactions.
- Temperature-dependent curing runs.
- Degree-of-cure analysis.
- Acceptance-ratio analysis.

### Tests for success

1. Candidate cutoff around 5 Å gives plausible candidate lists.
2. Accepted events create chemically valid C-N bonds.
3. Primary amines become secondary; secondary become tertiary.
4. No site exceeds allowed valence/functionality.
5. Acceptance ratio decreases with increasing cure.
6. Final cure lies in a plausible range, not artificially 100%.
7. Higher-temperature runs reach higher or faster conversion than low-temperature runs.
8. Network remains stable after repeated topology transfers.

### Fit into the whole project

This is the first real polymerization benchmark. It validates the kUPS extension on a known thermoset-curing algorithm before introducing learned rates or MLFF potentials.

## Subphase 3d — comparison to hardening-paper observables

### Deliverables

- Acceptance ratio vs degree of cure.
- Final degree of cure vs curing temperature.
- Heat/reaction-energy proxy vs degree of cure.
- Network statistics:
  - primary/secondary/tertiary amine fractions.
  - functionality distribution.
  - largest connected component.
  - gel fraction.

### Tests for success

- Qualitative match to paper trends.
- Simulated cure increases/saturates plausibly with temperature.
- Acceptance falls at high conversion.
- Heat/reaction-energy proxy is approximately linear with cure.

## Fit into whole project

Phase 3 becomes the central proof-of-concept. It is the first place where the work becomes recognizable as reactive polymer simulation rather than generic JAX software.

---

# Phase 4 — independent ORCA/QM reaction dataset

## Goal

Generate a modern local QM dataset for epoxy–amine reaction events. This is separate from the hardening-paper reproduction. Phase 3a is a small literature sanity check; Phase 4 is the actual dataset for your method.

## Recommended software

- RDKit: molecule generation and conformers.
- CREST/xTB: conformer search and cheap pre-optimization.
- ORCA: DFT optimizations, scans, transition states, frequencies.
- ASE: workflow glue, NEB setup, file conversion.
- Open Babel / Avogadro: manual inspection and format conversion.
- Optional later: CP2K for periodic or condensed-phase checks.

## Target data

- Reactant complexes.
- Product complexes.
- Primary amine + epoxy reaction.
- Secondary amine + epoxy reaction.
- Constrained N-C distance scans.
- Possible C-O ring-opening coordinate scans.
- TS or NEB calculations for selected systems.
- Different conformers and local environments.

## Deliverables

```text
data/qm_epoxy_amine/
  raw_inputs/
  raw_outputs/
  geometries_extxyz/
  scans/
  ts_candidates/
  metadata.csv
  reaction_energy_table.csv
  barrier_table.csv
  README.md
```

`metadata.csv` should include:

```text
system_id, reaction_type, method, basis, charge, multiplicity,
geometry_type, r_NC, r_CO, energy_hartree,
relative_energy_kcal_mol, converged,
imaginary_frequencies, source_file
```

## Tests for success

1. Reactants/products optimize cleanly.
2. Minima have no imaginary frequencies.
3. TS candidates have exactly one relevant imaginary frequency.
4. Scans connect reactant-like and product-like geometries smoothly.
5. Primary and secondary amine reactions differ in reaction energy/barrier.
6. Re-running a subset gives reproducible energies.
7. Data are convertible to one ML-ready format.

## Fit into whole project

This phase supplies the quantum reference data needed for learned reaction rates/barriers. It does not require a complete kUPS implementation and can run in parallel with software development.

---

# Phase 5 — learned local barrier/rate model

## Goal

Train a local model that maps candidate reaction geometry and chemical state to a barrier, reaction energy, log-rate, or event probability.

## First target

Start with barrier or reaction-energy prediction, not a full reactive MLFF.

```text
input: local reactive fragment geometry + atom/site states
output: ΔE_rxn, ΔE‡, or log k(T)
```

A simple physical parameterization is:

```text
k(x, T) = A exp(-ΔG‡_θ(x) / k_B T)
```

## Candidate models

- Constant-barrier baseline.
- Distance-only model.
- Handcrafted features + ridge/random forest/XGBoost.
- Gaussian process for small datasets.
- Small equivariant or message-passing GNN for local fragments.

## Deliverables

- Train/validation/test splits by fragment/conformer.
- Baseline models.
- Learned model.
- Calibration curves.
- Exportable inference function for kUPS integration.

## Tests for success

1. Model improves over constant and distance-only baselines.
2. Model ranks easy vs hard reaction candidates correctly.
3. Arrhenius temperature dependence is sensible.
4. Held-out fragment/conformer performance is acceptable.
5. Model can return batched rates with fixed tensor shapes.
6. Uncertainty or ensemble disagreement increases out of domain.

## Fit into whole project

This phase upgrades the hardening-paper reproduction from fixed QM corrections to learned local chemistry.

---

# Phase 6 — coupling learned rates to kUPS reactive dynamics

## Goal

Replace fixed correction energies or heuristic acceptance rules in the kUPS hardening implementation with the learned local rate/barrier model.

## Algorithm

```text
for macro_step in simulation:
    run MD block
    find candidate epoxy/amine reactions
    extract local features/geometries
    predict barrier/rate for each candidate
    sample or select event
    smooth-transfer topology
    accept/reject or commit by kMC/MC rule
    relax and continue
```

## Deliverables

- Rate-model interface callable from kUPS.
- Feature extraction from reactive candidates.
- Batched candidate scoring.
- Event sampling based on predicted rates.
- Ablation switches:
  - fixed hardening-paper corrections.
  - constant barrier.
  - distance-only rate.
  - learned rate.

## Tests for success

1. Learned model changes event selection relative to constant-rate baseline.
2. Higher predicted barriers lead to fewer accepted events.
3. Higher temperature increases event frequency.
4. Simulations remain stable after many accepted events.
5. Learned model produces different cure curves for primary vs secondary amine reactions.

## Fit into whole project

This phase creates the first ML-enhanced reactive polymerization simulator.

---

# Phase 7 — epoxy curing benchmark and baseline comparison

## Goal

Demonstrate that the kUPS reactive simulator produces meaningful thermoset-curing observables and compares favorably to existing baselines.

## Systems

Start with one:

```text
BFDGE/DGEBF/DGEBA + DETDA
```

Later extend to:

```text
DGEBA + DDS
other amine hardeners
other epoxy resins
```

## Baselines

- Hardening-paper style fixed correction model.
- Distance-only crosslinking heuristic.
- Constant-rate kMC/MC.
- ReaxFF/accelerated ReaxFF literature numbers, where comparable.
- Classical force field post-cure MD.
- MLFF post-cure MD.

## Observables

- Degree of cure vs temperature.
- Acceptance ratio vs degree of cure.
- Network statistics.
- Density and shrinkage.
- Heat/reaction-energy proxy.
- Tg if computationally feasible.
- Elastic modulus if computationally feasible.

## Tests for success

1. Final networks are chemically valid.
2. Degree of cure falls in realistic literature ranges.
3. Acceptance decreases at high conversion.
4. Heat/reaction-energy proxy is approximately linear with conversion.
5. Density/shrinkage are plausible.
6. Learned-rate model improves at least one validation metric over heuristic models.
7. Results are robust across random seeds.

## Fit into whole project

This phase turns the software contribution into a polymer-science result.

---

# Phase 8 — SimPoly-style MLFF extension for reactive polymer systems

## Goal

Move from classical or semi-classical dynamics toward a SimPoly-inspired MLFF workflow for reactive polymer systems.

## Important distinction

This does not mean immediately training a full universal reactive MLFF. Instead, build toward it gradually:

```text
existing MLFF for non-reactive dynamics
+ topology-changing event layer
+ learned ORCA-derived reaction model
+ targeted active-learning data near problematic configurations
```

## Possible directions

### Direction A — MLFF for post-cure networks

Use kUPS/Vivace/MACE/UMA-style MLFFs to simulate cured networks after topology has been generated by the reactive event layer.

### Direction B — MLFF for local relaxation during topology transfer

Use an MLFF for local relaxation after reaction events, while still using template-based topology changes.

### Direction C — targeted MLFF fine-tuning

Generate ORCA/CP2K labels for configurations where generic MLFFs fail:

- close epoxy/amine contacts;
- partially transferred topologies;
- strained post-reaction local motifs;
- dense crosslinked environments;
- inter-chain dissociation or packing curves.

### Direction D — active learning

Use uncertainty or disagreement between MLFFs to select new QM calculations.

## Deliverables

- Dataset of reactive/polymerization-relevant configurations.
- MLFF evaluation against ORCA/CP2K labels.
- Stability tests in MD.
- Comparison of classical vs MLFF relaxation after reaction events.
- Active-learning loop prototype.

## Tests for success

1. MLFF reproduces QM energies/forces on held-out local reactive motifs.
2. MLFF relaxation does not break chemically valid product structures.
3. MD stability improves or remains acceptable relative to classical potential.
4. Density/post-cure property predictions improve over classical baseline.
5. Active learning identifies high-error/high-uncertainty regions.

## Fit into whole project

This phase connects the hardening-paper reproduction to the long-term SimPoly-like goal.

---

# Phase 9 — method paper and software contribution

## Goal

Convert the project into a method paper and, ideally, a kUPS contribution.

## Possible paper title

**Reactive topology transfer for ML force-field simulations of polymerization**

## Main claims

1. kUPS can be extended with a JAX-compatible dynamic topology representation.
2. Smooth topology transfer enables stable reactive event attempts.
3. The Meißner thermoset-hardening algorithm can be reproduced algorithmically in kUPS.
4. ORCA-derived local reaction data can replace fixed literature corrections.
5. Learned local rates/barriers improve reactive event selection.
6. The framework provides a route from fixed-topology SimPoly-style MLFFs to reactive polymerization simulations.

## Minimum figures

1. Method schematic: MD → candidate detection → smooth topology transfer → MC/kMC decision → topology commit/reversal.
2. Toy A+B⇌AB validation.
3. Smooth topology transfer energy trace for accepted and rejected attempts.
4. Hardening-paper reproduction: acceptance ratio vs cure.
5. Hardening-paper reproduction: final cure vs temperature.
6. ORCA reaction scan/barrier dataset.
7. Learned rate model vs baselines.
8. Epoxy network snapshot and network statistics.

## Fit into whole project

This phase packages the work as a coherent scientific-computing and ML-for-materials contribution.

---

# Revised 12-month roadmap

| Month | Objective | Main deliverable | Success criterion |
|---:|---|---|---|
| 1 | kUPS baseline | reproduced MD/MC/relaxation examples | stable runs and plots |
| 2 | reactive state | fixed-capacity bond table | topology tests pass under JIT |
| 3 | toy topology transfer | smooth transfer for A+B→AB | accepted/rejected events stable |
| 4 | hardening toy model | epoxy-like candidate + topology patch | valid reaction events in kUPS |
| 5 | ORCA sanity check | first/second linking energies | exothermic, correct ordering |
| 6 | BFDGE/DETDA reproduction | kUPS curing runs | acceptance decreases with cure |
| 7 | hardening validation | cure vs temperature and network stats | qualitative match to paper |
| 8 | modern ORCA dataset | scans/TS/barrier table | ML-ready metadata and geometries |
| 9 | rate model | learned barrier/rate predictor | improves over constant/distance-only |
| 10 | learned-rate integration | kUPS + learned event selection | stable reactive simulations |
| 11 | baseline comparison | heuristic vs learned vs literature | clear improvement or insight |
| 12 | paper/repo | draft + figures + software package | workshop/preprint-ready |

---

# Immediate four-week plan

## Week 1 — kUPS and repo setup

- Install kUPS.
- Run simple MD and relaxation examples.
- Create project repository.
- Write a short internal note on kUPS state, potentials, propagators, patches, and MC moves.

## Week 2 — dynamic bond table

- Implement fixed-capacity bond table.
- Implement topology patch for creating/deleting one bond.
- Write unit tests.
- Test JIT compatibility.

## Week 3 — smooth topology transfer toy example

- Implement reactant/product potential interpolation.
- Run A+B→AB transfer.
- Plot energy and force traces.
- Implement accepted and rejected moves.

## Week 4 — hardening-paper minimal prototype

- Define simplified epoxy/amine reactive sites.
- Implement candidate detection by distance cutoff.
- Implement one irreversible reaction event.
- Log candidate counts, accepted events, and conversion.

At the end of four weeks, the project should already have a real kUPS extension prototype: topology-changing smooth transfer for reactive events.

---

# Risk register

| Risk | Severity | Mitigation |
|---|---:|---|
| Dynamic topology in JAX is difficult | high | fixed-size tables and masks |
| Exact Meißner reproduction is too force-field-specific | high | target algorithmic/qualitative reproduction first |
| OPLS/LigParGen import is painful | medium | start with simplified bonded potentials |
| ORCA structures/products are ambiguous | medium | first reproduce small hardening-paper correction energies |
| MLFF fails near reactive geometries | high | keep topology change explicit; use MLFF first for relaxation/post-cure dynamics |
| DFT barriers are expensive | medium | xTB pre-screening + small ORCA subset |
| Validation data are sparse | medium | use hardening paper, ReaxFF paper, and thermoset literature as benchmarks |
| Project scope explodes | high | keep Phase 3 as the central first deliverable |

---

# How to explain the project to kUPS/Cusp developers

A concise framing would be:

> I am working on reactive polymerization simulations in kUPS. The first concrete benchmark is a kUPS reimplementation of the Meißner thermoset-hardening algorithm: MD relaxation, candidate epoxy/amine reaction selection, smooth topology transfer, and MC accept/reject. The general software contribution is a JAX-compatible dynamic topology and controlled topology-transfer propagator. The chemistry benchmark is BFDGE/DETDA curing, and the longer-term goal is to couple this reactive-event layer to ORCA-derived learned rate models and ML force fields.

This is stronger than saying “I want to simulate epoxy polymerization,” because it identifies the exact missing abstraction in kUPS.

---

# Final recommendation

The revised plan is better than the original because it adds a concrete intermediate benchmark. The original plan jumped from toy topology changes to ORCA datasets and eventually epoxy validation. The new plan inserts the hardening-paper reproduction as the first serious kUPS milestone. This makes the project more realistic, easier to communicate, and more likely to produce a useful software contribution even before the full MLFF program is complete.

