# Research plan: reactive polymerization with kUPS + ML force fields

## Scientific motivation

The uploaded SimPoly paper demonstrates a clean and powerful direction: train a machine-learning force field (MLFF) from first-principles data and use it to run large polymer MD simulations that predict experimentally measurable bulk properties such as density and glass-transition temperature. In that setting, the polymer topology is already fixed: the chains exist, the bonds are known, and the simulation mainly needs accurate intra-chain and inter-chain forces. Polymerization is harder because the topology is not fixed. The simulation must describe continuous atomistic motion and discrete chemical events: bond formation, bond breaking, ring opening, proton transfer or local state changes, and eventually network formation.

The central research gap is therefore not simply “run MD with a better force field.” The missing layer is a **reactive event mechanism** that can be coupled to MLFF dynamics. The desirable object is a hybrid simulator of the form:

```text
MLFF molecular dynamics
+ reaction-template candidate detection
+ learned or physics-based reaction rates/barriers
+ topology-changing Monte Carlo / kinetic Monte Carlo events
+ local relaxation and continued MD
```

kUPS is a promising software substrate because it is JAX-native, composable, differentiable, and already contains MD, Monte Carlo, relaxation, classical potentials, MLFF interfaces, neighbor-list machinery, and patch-style updates. However, for polymerization the key extension is a **JAX-compatible reactive-event propagator** that can mutate molecular topology while remaining compatible with batching, JIT compilation, reproducibility, logging, and MLFF evaluation.

The project should be staged so that the chemistry, DFT, ML training, and kUPS software extension can be tested independently before being coupled. This reduces risk: the DFT phase can generate and validate local reaction data without kUPS; the ML phase can train and test a barrier/rate model without full polymer simulations; the kUPS phase can test topology-changing events on toy systems before applying them to epoxy curing.

---

## Core hypothesis

A publishable research hypothesis is:

> A generic reactive-event layer for kUPS, coupled to ML force fields and learned local reaction rates, can simulate polymerization and crosslinking more systematically than heuristic crosslinking algorithms and more transferably than system-specific reactive force fields.

The first scientifically realistic target should be **epoxy–amine curing**, especially a bisphenol-F/bisphenol-A diglycidyl ether with an aromatic diamine such as DETDA or DDS. This family has strong prior simulation literature, experimental validation data, and a clear local chemical event: amine attack on an epoxy ring followed by ring opening and formation of a C–N bond.

---

## Whole-system architecture

```text
                 ┌────────────────────────────┐
                 │  DFT / QM reference data   │
                 │  local epoxy–amine motifs  │
                 └─────────────┬──────────────┘
                               │
                               ▼
                 ┌────────────────────────────┐
                 │  learned barrier/rate model│
                 │  or calibrated rate table  │
                 └─────────────┬──────────────┘
                               │
                               ▼
┌─────────────┐    ┌────────────────────────────┐    ┌──────────────────┐
│ MLFF / FF   │───▶│ kUPS reactive propagator   │───▶│ polymer network   │
│ dynamics    │    │ MD → event → patch → relax │    │ trajectories      │
└─────────────┘    └────────────────────────────┘    └─────────┬────────┘
                                                                │
                                                                ▼
                                                ┌────────────────────────┐
                                                │ validation: cure, Tg,  │
                                                │ density, shrinkage, E  │
                                                └────────────────────────┘
```

---

## Phase 0 — kUPS baseline and reproducible simulation stack

### Goal

Establish that kUPS can run stable simple simulations, write outputs, and serve as the execution substrate for later hybrid MD/MC work.

### Deliverables

- A clean `conda` or `uv` environment with kUPS installed.
- Reproduced kUPS example simulations:
  - Lennard-Jones argon NVE.
  - Lennard-Jones argon NVT.
  - MLFF relaxation with a packaged MACE/UMA/ORB-style model.
  - Short MLFF MD example.
- A small repository structure:

```text
reactive-kups-polymerization/
  env/
  examples_reproduced/
  notebooks/
  src/
  tests/
  data/
  reports/
```

### How to test success

- NVE energy drift is small over a short trajectory.
- NVT temperature distribution stabilizes around target temperature.
- MLFF relaxation reduces maximum force and energy.
- HDF5 or trajectory outputs can be read and plotted.
- Simulations are reproducible from fixed PRNG seeds.

### Fit into the whole project

This phase verifies the computational substrate. If this fails, the reactive project should not start. The goal is not chemical insight yet; the goal is software trust.

---

## Phase 1 — toy reactive-event layer: A + B ⇌ AB

### Goal

Implement the smallest possible topology-changing move in kUPS: two particles can form or break a bond. This isolates the central software problem from polymer chemistry.

### Scientific content

The toy system should have particles of type `A` and `B`. When an `A` and `B` particle are within a reactive cutoff, the simulator proposes bond creation. The reverse reaction deletes an active bond with a prescribed rate. This is enough to test whether a kUPS state can contain a dynamic bond table and whether a propagator can update topology while remaining compatible with JAX.

### Required software extension

A first version of:

```python
ReactionTemplate
RateModel
ReactionEvent
ReactiveKMCPropagator
BondTable / ActiveBondMask
TopologyPatch
```

The bond table should probably be fixed-capacity, e.g.

```text
bond_i:          int[max_bonds]
bond_j:          int[max_bonds]
bond_type:       int[max_bonds]
bond_active:     bool[max_bonds]
```

This avoids dynamic Python lists inside JIT-compiled code.

### Deliverables

- A `ReactiveState` dataclass extending the usual kUPS state with a fixed-capacity bond table.
- A candidate finder for `A–B` pairs within a cutoff.
- A constant-rate or Metropolis-style reaction proposal.
- A topology patch that activates/deactivates bonds.
- A simple bonded potential term that depends on the active bond table.
- Unit tests for bond creation, bond deletion, masking, and energy changes.

### How to test success

1. **Topology test**: after one accepted event, exactly one inactive bond slot becomes active.
2. **Energy test**: the energy after a bond-creation patch matches full recomputation.
3. **Equilibrium test**: for reversible `A + B ⇌ AB`, the equilibrium bound fraction should match a known analytic or brute-force reference in a small box.
4. **JAX test**: the propagator works under `jax.jit`.
5. **Batching test**: many independent systems can run under `vmap` or batched state layout.
6. **Reproducibility test**: same seed gives same event sequence.

### Fit into the whole project

This is the minimal prototype of polymerization. If this phase works, the project has its central software abstraction: topology-changing stochastic events coupled to dynamics.

---

## Phase 2 — polymerization-like toy model: step-growth network formation

### Goal

Extend the toy event layer from single dimerization to many-functional monomers forming chains or networks.

### Scientific content

Use coarse atomistic or particle-level monomers with functionality 2, 3, or 4. For example:

```text
A2 + B2 → linear chains
A2 + B3 → branched polymers
A2 + B4 → crosslinked network / gelation toy model
```

This gives a bridge between the toy event layer and epoxy thermosets, without yet requiring real chemistry.

### Deliverables

- General reaction templates with functional-site states:
  - unreacted site
  - reacted site
  - exhausted site
- Monomer identity tracking.
- Chain/network analysis code:
  - molecular weight distribution
  - number-average and weight-average molecular weight
  - gel fraction
  - largest connected component
  - conversion / degree of cure
- Event statistics logging:
  - event type
  - time or step
  - candidate distance
  - rate
  - acceptance decision

### How to test success

1. **Conversion test**: degree of reaction increases monotonically in irreversible simulations.
2. **Valence test**: no site reacts more times than chemically allowed.
3. **Graph test**: connected components and gel fraction are correct for hand-built small systems.
4. **Kinetic test**: for well-mixed systems, conversion approximately follows simple mass-action kinetics.
5. **Finite-size test**: gel fraction changes systematically with system size and functionality.

### Fit into the whole project

This phase tests the polymerization logic independently from epoxy chemistry and DFT. It produces figures that already look like polymer science: conversion curves, network growth, molecular-weight distributions, and gelation.

---

## Phase 3 — independent DFT/QM data generation for epoxy–amine local reactions

### Goal

Generate a small but scientifically defensible dataset for the local epoxy–amine reaction event. This phase can and should be done mostly independently of kUPS.

### Why it is separate

The reactive-event model needs local reaction energetics or barriers. These can be computed on small fragments before there is any full polymer simulator. The DFT dataset can then later be used in two ways:

1. To calibrate a simple Arrhenius/rate table.
2. To train a learned local barrier/rate model.

This phase should not wait for the kUPS implementation. It can run in parallel.

### Target chemistry

Start with fragments representing:

- epoxy group from DGEBF/DGEBA/BFDGE-like resin;
- primary aromatic amine, e.g. DETDA/DDS-like fragment;
- secondary amine after first addition;
- product alcohol/amine local environment.

The first local reaction templates are:

```text
primary amine + epoxy → secondary amine + alcohol
secondary amine + epoxy → tertiary amine + alcohol
```

### Recommended software

#### Molecule construction and conformers

- **RDKit**: build molecules, generate conformers, initial 3D geometries.
- **CREST + xTB**: conformer search and cheap pre-optimization.
- **ASE**: workflow glue for geometry manipulation, trajectory formats, calculators, NEB setup.
- **Open Babel / Avogadro**: manual inspection and format conversion.

#### Fast pre-screening

- **GFN2-xTB** using the `xtb` program.
- Optional: **ORCA** can also run semi-empirical and DFT calculations.

#### DFT single points and optimizations

- **ORCA** for molecular fragments in vacuum or implicit solvent.
  - Good for organic reaction fragments.
  - Practical for B3LYP, ωB97X-D/ωB97X-V-like, def2-SVP/def2-TZVP style calculations.
  - Convenient for transition-state searches and frequency analysis.
- **CP2K** for periodic condensed-phase fragments or later QM/MM/periodic checks.
  - More aligned with SimPoly-style periodic polymer data.
  - Useful later if the reaction environment must include periodic packing.

#### Transition paths and barriers

- **ORCA TS search + frequency analysis** for isolated molecular reaction barriers.
- **ASE NEB** with ORCA, xTB, or CP2K calculators for approximate minimum-energy paths.
- **CP2K NEB** for periodic/condensed-phase reaction path checks.

### Dataset design

Create a dataset with the following levels:

#### Level 0: reactant/product sanity dataset

```text
reactant_complex.xyz
product_complex.xyz
optimized_reactant.out
optimized_product.out
reaction_energy.csv
```

Target values:

- optimized reactant energy;
- optimized product energy;
- reaction energy;
- relevant bond distances;
- imaginary frequency check only for TS, not for minima.

#### Level 1: constrained reaction-coordinate scans

Scan the forming N–C distance and possibly the breaking C–O epoxy bond distance:

```text
r_NC = 3.0, 2.8, 2.6, ..., 1.4 Å
```

For each point:

- constrain one or two reaction coordinates;
- optimize remaining coordinates;
- record energy and geometry.

#### Level 2: transition-state or NEB dataset

For selected fragment pairs:

- run NEB or TS search;
- identify approximate barrier;
- validate transition state by one imaginary frequency;
- connect TS to reactant/product with IRC where possible.

#### Level 3: environment perturbation dataset

Add local environment variation:

- different substituents around epoxy;
- primary vs secondary amine;
- different conformers;
- nearby hydrogen-bond donor/acceptor;
- optional implicit solvent or dielectric;
- optional small cluster with one or two neighboring resin molecules.

### Deliverables

- A structured dataset:

```text
data/qm_epoxy_amine/
  raw_inputs/
  raw_outputs/
  geometries_extxyz/
  scans/
  ts_candidates/
  metadata.csv
  README.md
```

- A `metadata.csv` with at least:

```text
system_id, reaction_type, method, basis, charge, multiplicity,
geometry_type, r_NC, r_CO, energy_hartree, relative_energy_kcal_mol,
converged, imaginary_frequencies, source_file
```

- A first barrier table:

```text
reaction_type, fragment, delta_E_rxn, delta_E_barrier, method, confidence
```

### How to test this phase separately

1. **Geometry sanity**: optimized reactants/products have no imaginary frequencies.
2. **TS sanity**: transition states have exactly one relevant imaginary frequency.
3. **Path sanity**: NEB or scan connects reactant to product without discontinuous geometry jumps.
4. **Chemical sanity**: primary amine first addition and secondary amine second addition have different energetics.
5. **Reproducibility**: rerunning a small subset gives energies within tolerance.
6. **Method sensitivity**: compare cheap xTB scan shape with DFT scan shape; xTB does not need exact barriers, but should give roughly sensible geometry.
7. **Data usability**: all outputs are converted to one ML-ready format such as `.extxyz` plus metadata.

### Fit into the whole project

This phase supplies the physics for the rate model. It does not need kUPS. It can be executed by a chemistry collaborator or on an HPC cluster while the kUPS software layer is being developed.

---

## Phase 4 — learned local barrier/rate model

### Goal

Train a model that maps local molecular geometry and chemical state to a reaction barrier or log-rate.

### Possible model targets

Start simple. Do not train a full reactive MLFF first.

Possible supervised targets:

```text
ΔE_rxn       reaction energy
ΔE‡          barrier energy
log k        log Arrhenius rate
p_event      event probability over a coarse time interval
```

A physically interpretable first model is:

```text
k(x, T) = A exp(-ΔG‡_θ(x) / k_B T)
```

where the neural network predicts `ΔG‡_θ(x)` or `ΔE‡_θ(x)` from local features.

### Candidate model classes

- Hand-crafted local features + Gaussian process / random forest / XGBoost.
- Small equivariant GNN on the local reacting fragment.
- Message-passing graph network over atom types, distances, and candidate reactive atoms.
- Energy-difference model using MLFF embeddings if accessible.

For the first implementation, use a simple model first. The hard part is the simulator coupling, not winning a barrier-prediction benchmark.

### Deliverables

- Train/validation/test split by fragment/conformer, not just random frames.
- Baseline models:
  - constant barrier;
  - distance-only model;
  - hand-crafted features + ridge/random forest;
  - small GNN.
- Metrics:
  - MAE in kcal/mol for barrier energy;
  - rank correlation of candidate reaction rates;
  - calibration of event probabilities;
  - uncertainty or ensemble disagreement.
- Exportable rate model callable from kUPS.

### How to test success independently

1. **Barrier MAE**: learned model improves over constant and distance-only baselines.
2. **Ranking test**: model ranks easy vs hard reaction candidates correctly.
3. **Temperature test**: rates change correctly with temperature through Arrhenius scaling.
4. **Out-of-domain test**: hold out one fragment family or substituent.
5. **Uncertainty test**: model is uncertain on geometries far from the training distribution.
6. **Interface test**: given a batch of candidate local geometries, the model returns rates with fixed shapes.

### Fit into the whole project

This phase replaces heuristic reaction probabilities with chemically informed rates. It is the ML component that makes the method more than a hand-coded crosslinking algorithm.

---

## Phase 5 — integrate learned reaction events with kUPS dynamics

### Goal

Couple the event layer from Phases 1–2 with the barrier/rate model from Phase 4 and with classical or MLFF dynamics.

### Algorithmic loop

```text
for macro_step in simulation:
    run n MD steps with current topology
    detect candidate reactions from neighbor list + functional-site states
    compute local features for each candidate
    predict barrier/rate for each candidate
    sample event with Gillespie/kMC or Metropolis rule
    apply topology patch if event accepted
    locally relax or anneal
    log event and continue
```

### Deliverables

- `EpoxyAmineReactionTemplate`.
- Candidate detector for amine N and epoxy carbon pairs.
- Site-state tracker:
  - epoxy unreacted/reacted;
  - amine primary/secondary/tertiary;
  - ring-opened product.
- Rate model interface.
- Local relaxation after accepted events.
- Event logger.
- Example simulation of a small epoxy/amine box.

### How to test success

1. **Candidate correctness**: all candidates correspond to chemically valid N/epoxy pairs.
2. **Valence correctness**: no nitrogen or epoxy reacts beyond allowed functionality.
3. **Patch correctness**: after reaction, the topology and site states are consistent.
4. **Stability**: local relaxation removes bad contacts after bond creation.
5. **Small-box validation**: manually inspect a few events in molecular visualization software.
6. **Rate sensitivity**: higher temperature or lower barrier gives faster conversion.
7. **Ablation**: constant-rate model vs learned-rate model produces measurable differences.

### Fit into the whole project

This is the first real hybrid polymerization simulator. It connects software contribution, quantum data, ML modeling, and polymer science.

---

## Phase 6 — epoxy curing benchmark and comparison to baselines

### Goal

Demonstrate that the method produces meaningful polymerization observables and can beat or complement existing baselines.

### Suggested benchmark system

Start with one family:

```text
DGEBF/BFDGE/DGEBA + DETDA or DDS
```

Prioritize a system for which the literature reports:

- degree of cure;
- density;
- shrinkage;
- glass-transition temperature;
- elastic modulus;
- DSC heat or cure kinetics.

### Baselines

- Heuristic distance-based crosslinking algorithm.
- Classical MD after imposed crosslinking.
- Reactive force field such as ReaxFF or IFF-R if available.
- Constant-rate kMC model.
- Your learned-rate hybrid MLFF/kMC model.

### Deliverables

- Cure curves: conversion vs simulation macro-time or event count.
- Network statistics:
  - gel fraction;
  - largest component;
  - crosslink density;
  - molecular weight distribution before gelation.
- Post-cure properties:
  - density;
  - shrinkage;
  - Tg estimate if feasible;
  - elastic modulus if feasible.
- Comparison table against literature.
- Ablation study:
  - no learned rates;
  - no local relaxation;
  - classical potential vs MLFF;
  - different DFT data levels.

### How to test success

1. **Network validity**: final network has plausible valence and connectivity.
2. **Conversion range**: final degree of cure is in the range reported for comparable simulations/experiments.
3. **Density/shrinkage**: post-cure density and shrinkage are physically plausible.
4. **Robustness**: results are stable across random seeds.
5. **Baseline improvement**: learned-rate model improves at least one of:
   - cure kinetics;
   - final conversion;
   - property prediction;
   - transfer across temperatures or resin variants.
6. **Compute feasibility**: one benchmark simulation can be run repeatedly on available hardware.

### Fit into the whole project

This is the validation phase. It turns the software and ML method into a polymer-science result.

---

## Phase 7 — publishable method paper

### Goal

Convert the project into a paper whose core contribution is methodological, not merely a case study.

### Possible paper framing

**Title sketch:**

> Reactive event propagation for ML force-field simulations of polymerization

### Main claims

1. kUPS can be extended with a generic topology-changing reactive propagator.
2. The method separates continuous dynamics from rare chemical events.
3. Learned local reaction rates from DFT improve over heuristic distance-based curing.
4. Epoxy–amine curing provides a realistic benchmark for hybrid MLFF/kMC polymerization.

### Minimum figures

1. Method schematic: MD → candidate detection → rate model → topology patch → relaxation.
2. Toy A+B⇌AB validation against analytic equilibrium.
3. Step-growth toy polymerization: conversion and gelation.
4. DFT reaction scan / barrier dataset.
5. Epoxy curing benchmark: conversion, network statistics, density/shrinkage.
6. Ablation: constant rate vs learned rate, classical FF vs MLFF.

### Likely venues

- Machine learning/scientific computing: NeurIPS AI4Science workshop, ICLR AI4Science workshop, ICML AI for Science workshop.
- Mainstream ML if algorithmic contribution is strong: NeurIPS / ICLR / ICML, but only if the method is general and validated beyond one chemistry.
- Computational chemistry/materials: Journal of Chemical Theory and Computation, npj Computational Materials, Digital Discovery, Nature Computational Science if the result is strong.

---

## 12-month roadmap

| Month | Main objective | Deliverable | Success criterion |
|---:|---|---|---|
| 1 | kUPS baseline | Reproduce MD, MC, relaxation, MLFF examples | stable runs, plots, reproducible seed behavior |
| 2 | Toy reactive state | Fixed-capacity bond table and topology patch | unit tests pass under JIT |
| 3 | A+B⇌AB simulator | Reversible reaction propagator | equilibrium bound fraction matches reference |
| 4 | Step-growth toy polymer | Functional-site model and network analysis | conversion/gelation curves generated |
| 5 | DFT workflow setup | RDKit/xTB/ORCA or CP2K pipeline | reactant/product optimizations reproducible |
| 6 | DFT scans | constrained scans and first TS/NEB paths | barrier table with metadata |
| 7 | Rate model | baseline + learned barrier/rate predictor | improves over constant/distance-only baseline |
| 8 | kUPS integration | rate model callable in reactive propagator | small reactive simulation with learned rates |
| 9 | Epoxy template | epoxy–amine event template and site states | chemically valid accepted events |
| 10 | Small epoxy box | first curing simulations | plausible conversion and stable trajectories |
| 11 | Baselines/ablations | compare heuristic, constant-rate, learned-rate | at least one clear improvement metric |
| 12 | Paper prototype | method paper draft + figures + repo | coherent preprint/workshop submission |

---

## Risk register

| Risk | Severity | Mitigation |
|---|---:|---|
| JAX dynamic topology is hard | high | fixed-capacity bond tables and masks |
| kUPS MLFF does not support topology-aware bonded terms easily | medium/high | start with classical bonded potentials; only later combine with MLFF |
| DFT barriers are expensive | medium | fragments first, xTB pre-screening, small subset at DFT level |
| MLFF fails near reactive geometries | high | do not rely on fully reactive MLFF initially; use event model and local relaxation |
| Epoxy chemistry too complex | medium | primary/secondary amine epoxy additions only; defer side reactions |
| Validation data sparse | medium | start with literature-rich DGEBF/BFDGE/DGEBA + DETDA/DDS systems |
| Project becomes too chemical | medium | keep ML contribution centered on generic event propagation + learned rates |

---

## First two-week action plan

### Week 1

- Install kUPS.
- Run LJ NVE/NVT examples.
- Run MLFF relaxation example.
- Read kUPS propagator, patch, potential, and MC-move abstractions.
- Create minimal local repository and test suite.

### Week 2

- Implement `BondTable` and `ReactiveState`.
- Implement hand-coded topology patch for one bond creation.
- Implement simple harmonic bond potential over active bonds.
- Write tests:
  - activate one bond;
  - deactivate one bond;
  - energy changes after patch;
  - JIT compatibility.

At the end of week 2, the project should have a concrete software artifact that could already be discussed with the kUPS developers: a minimal proposal for topology-changing reactive events.

---

## What to communicate to the kUPS/Cusp developers

A concise technical message could be:

> I am exploring polymerization simulations with kUPS. The key missing abstraction appears to be a generic topology-changing reactive-event propagator: MD steps generate candidate local chemical events, a rate model samples an event, and a patch updates a fixed-capacity bond/state table. I am prototyping this first on A+B⇌AB and then on epoxy–amine curing. Does this direction align with the intended patch/propagator design of kUPS, and would you be open to discussing the right way to represent dynamic bonded topology in a JAX-compatible state?

This frames the work as a natural extension of their architecture, not as a request for them to implement domain-specific chemistry.

