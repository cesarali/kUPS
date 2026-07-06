# kUPS reactive polymerization plan v3

## Graph-template-first hardening-paper reproduction, ORCA reaction data, and ML force fields

## Executive summary

The project should now be framed as a **graph-template-first reactive simulation project** rather than as a direct epoxy-specific reimplementation. The long-term target remains a SimPoly-like framework for polymer simulations with machine-learning force fields (MLFFs), but polymerization requires an additional layer that SimPoly-style fixed-topology MLFF simulations do not directly provide: dynamic molecular graphs, topology-changing events, and reaction-aware sampling.

The revised central idea is:

```text
reactant/product molecular graphs
        ↓
automated atom mapping and reaction-template extraction
        ↓
kUPS-compatible TopologyPatch objects
        ↓
smooth topology transfer during MD
        ↓
MC/kMC accept-reject or event sampling
        ↓
validation on the Meißner thermoset-hardening benchmark
        ↓
ORCA-derived learned reaction rates/barriers
        ↓
MLFF-driven reactive polymer simulation
```

The **hardening paper** remains the first serious scientific benchmark because it gives a concrete epoxy–amine curing protocol: MD relaxation, nearby epoxy/amine candidate selection, smooth transfer from reactant to product topology, QM/MM-type energetic correction, and Metropolis acceptance. The **Smart Reaction Templating** paper changes how the implementation should be designed: rather than hard-coding epoxy reactions, the software should first learn to convert reactant/product molecular graphs into reusable topology patches.

The immediate software contribution should therefore be:

> A JAX-compatible dynamic-topology and graph-derived reaction-template layer for kUPS, validated by reproducing the controlled-topology-transfer thermoset hardening algorithm.

This is stronger than “reproduce an epoxy paper in kUPS,” because the general contribution becomes reusable for other polymerization chemistries.

---

## Scientific framing

SimPoly shows that MLFFs trained on first-principles data can drive polymer MD simulations and predict bulk properties such as density and glass-transition behavior. This is a powerful non-reactive setting: the polymer chains already exist, and the simulation task is to model their interactions and thermal motion. Polymerization is harder because the molecular graph itself changes during the simulation. A curing simulation must represent bond formation, ring opening, atom-type/state changes, evolving connectivity, steric trapping, and network formation.

The Meißner thermoset-hardening paper addresses this problem with a hybrid MC/MD method. It uses MD to relax the network during attempted bond formation, smooth topology transfer to avoid violent force spikes, fixed small-molecule QM corrections for first and second epoxy–amine linking reactions, and Metropolis MC to accept or reject candidate reactions. This gives the scientific benchmark and validation target.

The Smart Reaction Templating paper addresses a different but crucial bottleneck: how to automatically construct pre- and post-reaction templates from molecular graphs. This is exactly the missing software layer that should sit before the hardening-paper algorithm. For kUPS, this means that a reaction should not be implemented as a hand-written function that changes a few epoxy-specific bonds. Instead, the software should derive a `TopologyPatch` from reactant and product graphs, then pass that patch into a smooth-transfer/MC propagator.

---

## Updated project philosophy

### Old implementation logic

```text
Hard-code epoxy/amine reaction
→ manually change atom types, bonds, angles, dihedrals, charges
→ run smooth topology transfer
→ reproduce hardening paper
```

This is risky because it produces an epoxy-only implementation.

### New implementation logic

```text
Reactant graph + product graph
→ atom mapping
→ identify changed local topology
→ generate reusable reaction template
→ compile to kUPS TopologyPatch
→ use patch in smooth topology transfer
→ reproduce hardening paper as first benchmark
```

This is better because the hardening paper becomes a validation case for a general reactive-template engine.

---

## Revised phase overview

```text
Phase 0   kUPS baseline and reproducible simulation stack
Phase 1   molecular graph and reaction-template layer
Phase 2   kUPS dynamic topology state and TopologyPatch representation
Phase 3   toy graph-derived reactions: A + B ⇌ AB
Phase 4   smooth topology transfer with graph-derived patches
Phase 5   hardening-paper reproduction in kUPS using graph templates
Phase 6   independent ORCA/QM reaction dataset
Phase 7   learned local barrier/rate model
Phase 8   coupling learned rates to kUPS reactive dynamics
Phase 9   epoxy curing benchmark and baseline comparison
Phase 10  SimPoly-style MLFF extension for reactive polymer systems
Phase 11  method paper and software contribution
```

The main structural change relative to the previous plan is that **graph-based reaction templating is now upstream of the hardening reproduction**. The hardening paper remains the first serious benchmark, but it should be implemented through graph-derived templates rather than hard-coded topology edits.

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
    graph_templates/
    topology/
    propagation/
    qm/
    analysis/
  tests/
  examples/
    toy_ab/
    toy_epoxy_amine/
    hardening_bfdge_detda/
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

## Fit into the whole project

This phase validates the computational substrate. No chemistry should be implemented before this is stable.

---

# Phase 1 — molecular graph and reaction-template layer

## Goal

Implement the graph-based layer inspired by Smart Reaction Templating: given reactant and product molecular graphs, automatically infer the atom mapping and the local topology changes that define a reaction.

## Scientific role

This phase separates **reaction definition** from **simulation execution**. The hardening paper tells us which epoxy–amine reactions matter, but the newer graph-template logic tells us how to define those reactions systematically.

## Core abstraction

```python
class ReactionTemplate:
    reactant_graph: MolecularGraph
    product_graph: MolecularGraph
    atom_mapping: Array  # reactant atom index -> product atom index
    created_bonds: Array
    deleted_bonds: Array
    changed_bond_types: Array
    changed_atom_types: Array
    changed_charges: Array
    changed_angles: Array
    changed_dihedrals: Array
    changed_impropers: Array
    reactive_sites: Array
    local_domain_mask: Array
```

## Inputs

Start with very small graph pairs:

```text
A + B       → AB
ethene-like + H → ethane-like toy
epoxide fragment + methylamine → amino alcohol product
primary amine + epoxy → secondary amine + alcohol
secondary amine + epoxy → tertiary amine + alcohol
```

## Deliverables

- `MolecularGraph` representation:
  - atom labels;
  - bond orders/types;
  - formal charges or partial-charge slots;
  - optional atom-type labels;
  - optional reactive-site labels.
- Graph parser from simple input formats:
  - RDKit molecule;
  - NetworkX graph;
  - simple JSON/YAML graph specification;
  - later: LAMMPS data/topology files.
- Atom-mapping function:
  - start with known mapping for toy systems;
  - then implement graph-isomorphism/subgraph-isomorphism mapping.
- Graph-difference function:
  - created bonds;
  - deleted bonds;
  - atom-state changes;
  - bond/angle/dihedral changes.
- Reduced local reaction-domain extraction.

## Tests for success

1. Atom mapping is one-to-one for toy reactions.
2. Created and deleted bonds match the known reaction.
3. Symmetric atoms are handled consistently or flagged.
4. The same reactant/product pair gives deterministic templates.
5. Local template reduction preserves all atoms affected by changed bonds, angles, dihedrals, impropers, atom types, and charges.
6. Invalid reactions are rejected because of valence or mapping inconsistencies.

## Fit into the whole project

This becomes the upstream layer for all later reactive simulation. The hardening benchmark will use templates generated here instead of manual epoxy-specific topology edits.

---

# Phase 2 — kUPS dynamic topology state and TopologyPatch representation

## Goal

Compile graph-derived reaction templates into fixed-shape, JAX-compatible topology updates that can be applied inside kUPS.

## Why this is needed

JAX prefers static array shapes, while polymerization changes the number of active bonds, angles, dihedrals, and possibly atom states. Therefore the simulation state should not append Python objects dynamically. Instead, it should contain fixed-capacity tables with masks.

## Core state design

```text
atom_type[n_atoms]
atom_charge[n_atoms]
site_state[n_sites]

bond_i[max_bonds]
bond_j[max_bonds]
bond_type[max_bonds]
bond_active[max_bonds]

angle_i[max_angles]
angle_j[max_angles]
angle_k[max_angles]
angle_type[max_angles]
angle_active[max_angles]

dihedral_i[max_dihedrals]
dihedral_j[max_dihedrals]
dihedral_k[max_dihedrals]
dihedral_l[max_dihedrals]
dihedral_type[max_dihedrals]
dihedral_active[max_dihedrals]
```

## TopologyPatch abstraction

```python
class TopologyPatch:
    atom_type_updates: Array
    charge_updates: Array
    site_state_updates: Array
    activate_bonds: Array
    deactivate_bonds: Array
    update_bond_types: Array
    activate_angles: Array
    deactivate_angles: Array
    update_angle_types: Array
    activate_dihedrals: Array
    deactivate_dihedrals: Array
    update_dihedral_types: Array
    reverse_patch: Optional[TopologyPatch]
```

## Deliverables

- `ReactiveState` dataclass extending the kUPS state.
- Fixed-capacity topology tables.
- Patch compiler:

```text
ReactionTemplate + candidate atom indices → TopologyPatch
```

- Patch application:

```text
state_new = apply_patch(state_old, patch)
```

- Patch reversal:

```text
state_old = apply_patch(state_new, patch.reverse)
```

## Tests for success

1. Patch application changes only intended entries.
2. Patch reversal exactly restores the previous topology state.
3. Active-mask counts change as expected.
4. Energy recomputation after patch is consistent with the updated topology.
5. The patch works under `jax.jit`.
6. The patch works for batched systems or repeated independent replicas.
7. Capacity overflow is detected gracefully.

## Fit into the whole project

This phase is the core kUPS software contribution. It connects the graph-template layer to the actual simulation state.

---

# Phase 3 — toy graph-derived reactions: A + B ⇌ AB

## Goal

Create the smallest possible end-to-end reactive simulation: a graph-derived template creates a topology patch; the patch is applied to a simple kUPS system; the system forms and optionally breaks a bond.

## Scientific role

This isolates topology mutation from epoxy chemistry. It verifies that the architecture works before introducing atom types, ring opening, charge redistribution, or real force fields.

## Required workflow

```text
Toy reactant graph: A + B
Toy product graph: AB
        ↓
ReactionTemplate
        ↓
TopologyPatch
        ↓
A/B particles in kUPS
        ↓
apply patch when particles are close
        ↓
active AB bond appears
```

## Deliverables

- Toy `A+B→AB` reactant/product graph files.
- Automatic template extraction.
- Candidate finder for A/B pairs within a cutoff.
- Bond-creation patch.
- Optional reverse reaction patch.
- Simple harmonic or Morse bonded potential over active bonds.
- Unit tests and one notebook demo.

## Tests for success

1. The extracted graph template contains exactly one created bond.
2. The kUPS patch activates exactly one bond slot.
3. The bonded potential becomes active only after patch application.
4. The system runs under `jax.jit`.
5. A reversible version reaches a plausible bound/unbound equilibrium in a small box.
6. The event log records candidate, patch, acceptance decision, and topology state.

## Fit into the whole project

This is the first complete vertical slice of the project: graph template → topology patch → reactive kUPS state → simulation.

---

# Phase 4 — smooth topology transfer with graph-derived patches

## Goal

Implement the Meißner-style smooth topology transfer, but with the reactant and product topologies generated by the graph-template/patch layer.

## Core idea

For a reaction attempt, define a smooth switching variable `s(t)` from 0 to 1 and use an interpolated potential:

```text
E_mix(x, t) = (1 - s(t)) E_reactant(x) + s(t) E_product(x)
```

The force is the corresponding mixture of reactant and product forces. If the reaction is accepted, commit the product topology. If it is rejected, smoothly reverse the transfer back to the reactant topology.

## Deliverables

- `SmoothTopologyTransferPropagator`.
- Smooth switching function.
- Reactant/product potential wrappers.
- Patch-aware potential evaluation:

```text
E_reactant = potential(state)
E_product  = potential(apply_patch(state, patch))
E_mix      = (1 - s) E_reactant + s E_product
```

- Commit/reverse topology logic.
- Energy and force logging.
- Toy demonstration with graph-derived `A+B→AB` patch.

## Tests for success

1. Energy and forces do not show catastrophic spikes during transfer.
2. Accepted moves end in the product topology.
3. Rejected moves return to the reactant topology.
4. Energy interpolation matches explicit reactant/product evaluations.
5. The same candidate can be replayed deterministically with a fixed seed.
6. The transition works under JIT for fixed-size systems.
7. Force traces are smooth enough for stable short MD trajectories.

## Fit into the whole project

This is the direct bridge from graph-derived topology patches to the hardening-paper algorithm. It is also one of the most important potential contributions to kUPS.

---

# Phase 5 — hardening-paper reproduction in kUPS using graph templates

## Goal

Reproduce the algorithmic structure of the Meißner thermoset-hardening paper inside kUPS, but with reaction topology changes generated through the graph-template/TopologyPatch layer.

## Why this phase is now central

The previous plan already included hardening-paper reproduction as the first serious benchmark. The new version makes the implementation more general: the hardening reaction is no longer a hand-coded epoxy case, but a validation case for a graph-derived reactive topology system.

## Target algorithm

```text
1. Start from mixed BFDGE/DETDA or simplified epoxy/amine system.
2. Run MD relaxation.
3. Build list of nearby epoxy/amine candidates.
4. Select one candidate reaction.
5. Select the relevant ReactionTemplate:
     primary amine + epoxy → secondary amine + alcohol
     secondary amine + epoxy → tertiary amine + alcohol
6. Compile candidate-specific TopologyPatch from the template.
7. Smoothly transfer reactant topology to product topology.
8. Estimate reaction energy using MM energy difference + QM correction.
9. Accept/reject by Metropolis criterion.
10. Commit product topology if accepted; reverse if rejected.
11. Repeat until curing saturates.
```

## Relation to the hardening paper

The hardening paper provides the benchmark details:

- BFDGE + DETDA as the simplified simulation chemistry.
- Gaussian03/B3LYP/6-311+G\*\* for the two local reaction energies.
- First epoxy–amine linking correction around `-25.5 kcal/mol`.
- Second linking correction around `-15.5 kcal/mol`.
- MC/MD curing at multiple temperatures.
- NpT curing at 1 atm.
- A 5 Å candidate cutoff based on epoxy/amine radial distribution functions.
- Smooth topology transfer to avoid unstable immediate topology switching.
- Validation against DSC curing data and mechanical properties.

For the kUPS reproduction, the first target is **algorithmic and qualitative reproduction**, not exact numerical identity with their LAMMPS implementation.

---

## Subphase 5a — minimal ORCA sanity reproduction of local reaction corrections

### Goal

Reproduce the two local reaction-energy calculations approximately, using ORCA rather than Gaussian.

### Deliverables

- ORCA input files for:
  - BFDGE or reduced epoxy fragment;
  - DETDA or reduced amine fragment;
  - first linked product;
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
- Values are qualitatively comparable to the hardening-paper values.

### Fit into the whole project

This checks product structures, proton transfer, charge/multiplicity, ORCA settings, and energy bookkeeping. It is a small sanity step, not yet the main ML dataset.

---

## Subphase 5b — graph templates for epoxy–amine reactions

### Goal

Generate reaction templates for the two epoxy–amine additions from reactant/product graphs.

### Templates

```text
Template I:
primary amine + epoxy → secondary amine + alcohol

Template II:
secondary amine + epoxy → tertiary amine + alcohol
```

### Deliverables

- Reactant and product graph files for both templates.
- Atom mapping for each template.
- Created/deleted bond tables.
- Atom-type/state-change tables.
- Angle/dihedral/improper-change tables, initially simplified if necessary.
- Template reduction to the local reactive domain.
- Human-readable template report:

```text
created bonds: C_epoxy_terminal -- N_amine
broken bonds:  C_epoxy -- O_epoxy_ring  [if explicit ring opening is represented]
changed states: amine primary → secondary, epoxy unreacted → opened alcohol
changed local topology: angles/dihedrals around C, N, O
```

### Tests for success

1. The graph difference identifies the C–N bond formation.
2. The epoxide ring-opening change is represented consistently.
3. The amine state changes correctly.
4. Primary and secondary amine templates are distinct.
5. The patch can be applied and reversed on an isolated fragment.
6. Valence and site-state constraints are satisfied.

### Fit into the whole project

This is where Smart Reaction Templating logic directly enters the hardening reproduction. It prevents an epoxy-only hard-coded implementation.

---

## Subphase 5c — kUPS hardening-paper toy reproduction

### Goal

Run the hardening-paper algorithm on a simplified epoxy-like system, not full BFDGE/DETDA.

### Deliverables

- Simplified epoxy/amine particles or small molecules.
- Candidate finder based on reactive-site distance.
- Graph-derived template and TopologyPatch.
- Smooth topology transfer for one reaction event.
- Metropolis accept/reject logic with fixed correction energy.
- Logs of accepted/rejected attempts.

### Tests for success

- Candidate list updates after every accepted reaction.
- Acceptance probability decreases as local strain increases.
- Rejected moves reverse without instability.
- Final conversion saturates below 100% if steric/geometric constraints are present.
- Event log includes selected template, candidate atoms, patch ID, energy difference, and MC decision.

### Fit into the whole project

This proves that the hardening-paper algorithm can live in kUPS before full chemical complexity.

---

## Subphase 5d — BFDGE/DETDA kUPS reproduction

### Goal

Move from toy chemistry to the real hardening-paper chemistry.

### Deliverables

- Initial BFDGE/DETDA box generation workflow.
- Reactive-site annotation:
  - epoxy terminal carbon;
  - epoxy oxygen/ring state;
  - primary/secondary/tertiary amine state.
- Graph-derived topology patches for first and second linking reactions.
- Temperature-dependent curing runs.
- Degree-of-cure analysis.
- Acceptance-ratio analysis.

### Tests for success

1. Candidate cutoff around 5 Å gives plausible candidate lists.
2. Accepted events create chemically valid C–N bonds.
3. Primary amines become secondary; secondary become tertiary.
4. No site exceeds allowed valence/functionality.
5. Acceptance ratio decreases with increasing cure.
6. Final cure lies in a plausible range, not artificially 100%.
7. Higher-temperature runs reach higher or faster conversion than low-temperature runs.
8. Network remains stable after repeated topology transfers.

### Fit into the whole project

This is the first real polymerization benchmark. It validates the general graph-patch/smooth-transfer machinery on known epoxy curing.

---

## Subphase 5e — comparison to hardening-paper observables

### Deliverables

- Acceptance ratio vs degree of cure.
- Final degree of cure vs curing temperature.
- Heat/reaction-energy proxy vs degree of cure.
- Network statistics:
  - primary/secondary/tertiary amine fractions;
  - functionality distribution;
  - largest connected component;
  - gel fraction.

### Tests for success

- Qualitative match to paper trends.
- Simulated cure increases/saturates plausibly with temperature.
- Acceptance falls at high conversion.
- Heat/reaction-energy proxy is approximately linear with cure.
- Differences from the paper can be attributed to force-field simplifications, not broken topology logic.

### Fit into the whole project

Phase 5 is the central proof-of-concept. It is the first point where the work becomes recognizable as reactive polymer simulation rather than generic JAX software.

---

# Phase 6 — independent ORCA/QM reaction dataset

## Goal

Generate a modern local QM dataset for epoxy–amine reaction events. This is separate from the hardening-paper reproduction. Phase 5a is a small literature sanity check; Phase 6 is the actual dataset for the new method.

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
- Constrained N–C distance scans.
- Possible C–O ring-opening coordinate scans.
- TS or NEB calculations for selected systems.
- Different conformers and local environments.
- Optional catalyst/promoter variants later:
  - noncatalyzed;
  - self-promoted;
  - water/alcohol-assisted.

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
8. The dataset can be joined to graph-template IDs.

## Fit into the whole project

This phase supplies the quantum reference data needed for learned reaction rates/barriers. It does not require a complete kUPS implementation and can run in parallel with software development.

---

# Phase 7 — learned local barrier/rate model

## Goal

Train a local model that maps candidate reaction geometry and chemical state to a barrier, reaction energy, log-rate, or event probability.

## First target

Start with barrier or reaction-energy prediction, not a full reactive MLFF.

```text
input: local reactive fragment geometry + atom/site states + template ID
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
- Template-conditioned model:

```text
features = geometry + atom states + ReactionTemplate embedding
```

## Deliverables

- Train/validation/test splits by fragment/conformer/template.
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
7. Template-conditioned model distinguishes primary and secondary amine chemistry.

## Fit into the whole project

This phase upgrades the hardening-paper reproduction from fixed QM corrections to learned local chemistry.

---

# Phase 8 — coupling learned rates to kUPS reactive dynamics

## Goal

Replace fixed correction energies or heuristic acceptance rules in the kUPS hardening implementation with the learned local rate/barrier model.

## Algorithm

```text
for macro_step in simulation:
    run MD block
    find candidate epoxy/amine reactions
    assign ReactionTemplate to each candidate
    compile candidate-specific TopologyPatch
    extract local features/geometries
    predict barrier/rate for each candidate
    sample or select event
    smooth-transfer topology
    accept/reject or commit by MC/kMC rule
    relax and continue
```

## Deliverables

- Rate-model interface callable from kUPS.
- Feature extraction from reactive candidates.
- Batched candidate scoring.
- Event sampling based on predicted rates.
- Ablation switches:
  - fixed hardening-paper corrections;
  - constant barrier;
  - distance-only rate;
  - graph-template-conditioned learned rate.

## Tests for success

1. Learned model changes event selection relative to constant-rate baseline.
2. Higher predicted barriers lead to fewer accepted events.
3. Higher temperature increases event frequency.
4. Simulations remain stable after many accepted events.
5. Learned model produces different cure curves for primary vs secondary amine reactions.
6. Event selection remains compatible with graph-template constraints and valence rules.

## Fit into the whole project

This phase creates the first ML-enhanced reactive polymerization simulator.

---

# Phase 9 — epoxy curing benchmark and baseline comparison

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
- Constant-rate MC/kMC.
- Accelerated ReaxFF literature numbers, where comparable.
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
8. Graph-template layer produces reusable reaction definitions across at least two epoxy/amine variants.

## Fit into the whole project

This phase turns the software contribution into a polymer-science result.

---

# Phase 10 — SimPoly-style MLFF extension for reactive polymer systems

## Goal

Move from classical or semi-classical dynamics toward a SimPoly-inspired MLFF workflow for reactive polymer systems.

## Important distinction

This does not mean immediately training a full universal reactive MLFF. Instead, build toward it gradually:

```text
existing MLFF for non-reactive dynamics
+ graph-derived topology-changing event layer
+ learned ORCA-derived reaction model
+ targeted active-learning data near problematic configurations
```

## Possible directions

### Direction A — MLFF for post-cure networks

Use kUPS/MACE/UMA/Vivace-style MLFFs to simulate cured networks after topology has been generated by the reactive event layer.

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
6. MLFF integration does not bypass the graph-template valence constraints.

## Fit into the whole project

This phase connects the hardening-paper reproduction to the long-term SimPoly-like goal.

---

# Phase 11 — method paper and software contribution

## Goal

Convert the project into a method paper and, ideally, a kUPS contribution.

## Possible paper title

**Graph-derived reactive topology transfer for ML force-field simulations of polymerization**

## Main claims

1. kUPS can be extended with a JAX-compatible dynamic topology representation.
2. Reactant/product molecular graphs can be compiled into reversible topology patches.
3. Smooth topology transfer enables stable reactive event attempts.
4. The Meißner thermoset-hardening algorithm can be reproduced algorithmically in kUPS.
5. ORCA-derived local reaction data can replace fixed literature corrections.
6. Learned local rates/barriers improve reactive event selection.
7. The framework provides a route from fixed-topology SimPoly-style MLFFs to reactive polymerization simulations.

## Minimum figures

1. Method schematic: graph pair → reaction template → topology patch → smooth transfer → MC/kMC decision.
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
| 2 | graph-template layer | A+B→AB graph mapping and diff | correct atom mapping and created bond |
| 3 | dynamic topology state | fixed-capacity topology tables and patches | topology tests pass under JIT |
| 4 | toy smooth transfer | graph-derived A+B→AB smooth transfer | accepted/rejected events stable |
| 5 | epoxy graph templates | primary/secondary epoxy–amine templates | valid graph-derived patches |
| 6 | hardening toy model | epoxy-like candidate + topology patch | valid reaction events in kUPS |
| 7 | ORCA sanity check | first/second linking energies | exothermic, correct ordering |
| 8 | BFDGE/DETDA reproduction | kUPS curing runs | acceptance decreases with cure |
| 9 | hardening validation | cure vs temperature and network stats | qualitative match to paper |
| 10 | modern ORCA dataset | scans/TS/barrier table | ML-ready metadata and geometries |
| 11 | learned-rate integration | kUPS + learned event selection | stable reactive simulations |
| 12 | paper/repo | draft + figures + software package | workshop/preprint-ready |

---

# Immediate four-week plan

## Week 1 — kUPS and graph-template setup

- Install kUPS.
- Run simple MD and relaxation examples.
- Create project repository.
- Implement a minimal `MolecularGraph` object.
- Implement a hand-specified atom mapping for `A+B→AB`.

## Week 2 — graph difference and topology patch

- Implement graph-difference logic.
- Implement fixed-capacity bond table.
- Implement `TopologyPatch` for creating/deleting one bond.
- Write unit tests.
- Test JIT compatibility.

## Week 3 — smooth topology transfer toy example

- Implement reactant/product potential interpolation.
- Use the graph-derived patch for `A+B→AB`.
- Plot energy and force traces.
- Implement accepted and rejected moves.

## Week 4 — epoxy/amine minimal prototype

- Define simplified epoxy/amine reactant and product graphs.
- Generate the first epoxy–amine `ReactionTemplate`.
- Compile it to a kUPS `TopologyPatch`.
- Implement candidate detection by distance cutoff.
- Run one irreversible reaction event and log candidate counts, accepted events, conversion, and topology state.

At the end of four weeks, the project should have a real prototype: **graph-derived topology-changing smooth transfer for reactive events in kUPS**.

---

# Risk register

| Risk | Severity | Mitigation |
|---|---:|---|
| Dynamic topology in JAX is difficult | high | fixed-size tables and masks |
| Graph matching is ambiguous for symmetric molecules | high | start with explicit atom mapping, then add graph-isomorphism scoring |
| Exact Meißner reproduction is force-field-specific | high | target algorithmic/qualitative reproduction first |
| OPLS/LigParGen import is painful | medium | start with simplified bonded potentials and later import full topology |
| Epoxy ring opening/proton transfer is ambiguous | medium/high | validate isolated templates with ORCA and manual inspection |
| ORCA structures/products are ambiguous | medium | first reproduce small hardening-paper correction energies |
| MLFF fails near reactive geometries | high | keep topology change explicit; use MLFF first for relaxation/post-cure dynamics |
| DFT barriers are expensive | medium | xTB pre-screening + small ORCA subset |
| Validation data are sparse | medium | use hardening paper, accelerated ReaxFF paper, and thermoset literature as benchmarks |
| Project scope explodes | high | keep graph-derived hardening reproduction as the central first deliverable |

---

# How to explain the project to kUPS/Cusp developers

A concise framing would be:

> I am working on reactive polymerization simulations in kUPS. The first concrete benchmark is a kUPS reimplementation of the Meißner thermoset-hardening algorithm: MD relaxation, epoxy/amine candidate selection, smooth topology transfer, and MC accept/reject. The general software contribution is not epoxy-specific: I want to generate reaction topology patches from reactant/product molecular graphs, then apply these patches through a JAX-compatible dynamic-topology and smooth-transfer propagator. The chemistry benchmark is BFDGE/DETDA curing, and the longer-term goal is to couple this reactive-event layer to ORCA-derived learned rate models and ML force fields.

This is stronger than saying “I want to simulate epoxy polymerization,” because it identifies the exact missing abstraction in kUPS: **graph-derived topology patches plus reactive propagation**.

---

# Relationship between the three key papers

## SimPoly

SimPoly motivates the long-term MLFF direction: first-principles-labeled polymer configurations, ML force fields, large-scale MD, and validation against bulk properties. It is primarily a non-reactive fixed-topology framework.

## Meißner hardening paper

The hardening paper motivates the first reactive benchmark: MC/MD curing, smooth topology transfer, fixed QM corrections, and validation against degree of cure, DSC heat, and mechanical properties.

## Smart Reaction Templating

Smart Reaction Templating motivates the software architecture for reaction definition: use molecular graphs, atom mapping, reaction-site identification, and reduced pre/post templates rather than hand-written topology edits.

## Combined project identity

```text
SimPoly gives the MLFF endpoint.
The hardening paper gives the reactive simulation benchmark.
Smart Reaction Templating gives the graph-template software layer.

Your project combines them into:

graph-derived reactive topology transfer for MLFF-compatible polymerization simulations.
```

---

# Final recommendation

The revised plan is stronger than the previous version. The previous plan correctly centered the hardening-paper reproduction, but it still risked becoming an epoxy-specific implementation. The new plan makes the **graph-template layer** explicit and upstream. That gives the project a more general method contribution:

> Build graph-derived topology patches, execute them through smooth topology transfer in kUPS, validate on thermoset hardening, then replace fixed reaction corrections with ORCA-derived learned rates and eventually MLFF dynamics.

