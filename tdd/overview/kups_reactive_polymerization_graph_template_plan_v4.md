# kUPS reactive polymerization plan v4

## Repository-aware graph templates, plain pre-curing MD first, and controlled topology transfer

## Executive summary

This version replaces the synthetic repository layout from v3 with the layout that is actually present in this checkout. The kUPS package lives in:

```text
src/kups/
```

There is no separate `source/` tree and the polymerization work should not create a parallel `reactive_kups` package. New kUPS source code for this project should live under one package boundary:

```text
src/kups/polymerization/
```

That folder can contain graph templates, topology tables, propagation, QM coupling, and analysis. The existing `scripts/polymerization/`, `test/polymerization/`, `docs/polymerization/`, `examples/polymerization/`, and `tdd/` folders can hold scripts, tests, docs, examples, and plans, but the kUPS extension itself should stay inside `src/kups/polymerization`.

The second important change is sequencing. The first practical milestone should not be Monte Carlo curing. It should be a minimal non-reactive MD workflow for the uncured BFDGE/DETDA mixture from the hardening paper:

```text
pack uncured BFDGE + DETDA
    -> minimize
    -> short safe NVT if needed
    -> NPT density relaxation
    -> NVT structural/RDF sampling
    -> save equilibrated uncured mixture
```

This phase has no topology mutation, no MC accept/reject step, no QM/MM correction, and no reaction event. It produces the physical starting point for the later reactive algorithm and gives an early test of the force-field/topology pipeline.

The graph-template layer from Smart Reaction Templating remains central, but it should be adapted into kUPS as an offline template compiler rather than imported directly from `external/templater-main/templater-main`. The external scripts are valuable reference code for LAMMPS `bond/react` template generation, but they are command-line scripts with global argument parsing and LAMMPS-specific outputs. kUPS needs the same core ideas converted into typed, testable modules:

```text
reactant/product topology files
    -> molecular graphs
    -> atom mapping
    -> changed local topology
    -> kUPS polymerization template
    -> runtime topology patch
    -> smooth topology-transfer propagator
```

The corrected high-level project order is therefore:

```text
Phase 0  repository-aware baseline and source boundary
Phase 1  minimal non-reactive BFDGE/DETDA pre-curing MD
Phase 2  offline graph-template compiler adapted from templater
Phase 3  kUPS dynamic topology state and patch layer
Phase 4  toy graph-derived reaction A + B -> AB
Phase 5  smooth topology transfer for graph-derived patches
Phase 6  hardening-paper reproduction with BFDGE/DETDA templates
Phase 7  ORCA-derived local reaction corrections and datasets
Phase 8  learned local barrier/rate model
Phase 9  MLFF-compatible reactive polymer simulation
Phase 10 validation, paper, and upstream-ready kUPS contribution
```

## Repository facts used in this revision

The current kUPS source tree already provides:

- `src/kups/md/`: MD integrators and observables.
- `src/kups/application/md/`: MD state construction, run loops, HDF5 output, and analysis.
- `src/kups/application/mcmc/`: generic MCMC run loop structure.
- `src/kups/core/patch.py`: generic composable state patch abstraction.
- `src/kups/core/neighborlist/`: fixed, dense, adaptive, and cell-list neighbor lists.
- `src/kups/potential/classical/`: Lennard-Jones, Coulomb, Ewald, harmonic bonds/angles, UFF-style dihedrals and impropers, Morse, and related classical terms.
- `src/kups/potential/mliap/`: ML interatomic potential interfaces.
- `src/kups/application/simulations/`: existing script entry points such as `kups_md_lj`, `kups_mcmc_rigid`, and `kups_md_mlff`.

The repository also already contains project-specific artifacts:

- `tdd/overview/basic_md_pre_curing_epoxy.md`
- `tdd/qm/orca_install_and_test_plan.md`
- `tdd/qm/epoxy_amine_cluster_workflow.md`
- `docs/polymerization/ORCA_USAGE.md`
- `docs/polymerization/environment-kups-env-qm-addons.yml`
- `scripts/polymerization/qm/*`
- `test/polymerization/fixtures/*`
- `external/templater-main/templater-main/*`

The external templater checkout includes:

- `tools/reduce_ff.py`
- `tools/create_bondreact.py`
- `tools/create_mol.py`
- `tools/lammps_files.py`
- worked examples for polyaddition, polycondensation, polycondensation with water, and chain polymerization.

The current gap is not "no MD engine exists". The gap is:

1. no kUPS-native polymerization package boundary yet;
2. no complete fixed-topology all-atom OPLS/LAMMPS-data import path for BFDGE/DETDA;
3. no dynamic topology tables with active masks;
4. no graph-derived template compiler in kUPS form;
5. no smooth mixed-topology propagator;
6. no epoxy/amine event bookkeeping inside kUPS.

## Source layout for new kUPS code

Use this as the intended source skeleton. It keeps new extension code in one package while allowing internal organization.

```text
src/kups/polymerization/
  __init__.py
  data.py
  io/
    __init__.py
    lammps_data.py
    lammps_mol.py
    template_json.py
  templates/
    __init__.py
    graph.py
    mapping.py
    diff.py
    reduce.py
    compiler.py
    validation.py
  topology/
    __init__.py
    tables.py
    patch.py
    parameters.py
    active_edges.py
  md/
    __init__.py
    precuring.py
    transfer.py
    candidates.py
  qm/
    __init__.py
    corrections.py
    features.py
  analysis/
    __init__.py
    cure.py
    network.py
    rdf.py
```

Do not create:

```text
src/reactive_kups/
reactive-kups-polymerization/
source/
```

Thin command-line scripts may live under `scripts/polymerization/` and import from `kups.polymerization`. Tests should live under `test/polymerization/`. Examples should live under `examples/polymerization/`.

## Dependency policy

The runtime topology-transfer layer should stay JAX/kUPS-native and avoid heavy graph dependencies inside jitted code.

The offline template compiler can use graph tooling:

- `networkx` for graph representation and subgraph isomorphism;
- `scipy.optimize.linear_sum_assignment` for the reactive-center assignment used by the templater paper;
- optional `rdkit` for SMILES and molecule construction;
- optional `pandas` for template reports and metadata.

These should be isolated behind the offline compiler. A reasonable packaging target is an optional extra later, for example:

```text
[project.optional-dependencies]
polymerization = ["networkx", "scipy", "rdkit", "pandas"]
```

The core MD/runtime code should consume already-compiled template arrays and should not require RDKit or NetworkX at simulation time.

---

# Phase 0 - repository-aware baseline and source boundary

## Goal

Establish a clean baseline against the real kUPS repository and define exactly where new code belongs.

## Deliverables

- A minimal `src/kups/polymerization/` package with no broad refactors outside that boundary.
- A short design note or README inside `src/kups/polymerization/` explaining:
  - offline template compilation;
  - runtime topology patches;
  - plain MD pre-curing workflow;
  - later MC/MD curing loop.
- Baseline verification of existing kUPS examples and tests relevant to this project:
  - LJ MD smoke test;
  - bonded-potential tests;
  - neighbor-list tests;
  - MCMC run-loop tests if touched.
- A decision record that `external/templater-main/templater-main` is a reference implementation, not a runtime dependency.

## Tests for success

- Existing kUPS tests still pass for the touched area.
- The new package imports as `kups.polymerization`.
- No new source package appears outside `src/kups/polymerization`.
- New optional dependencies are not imported by core kUPS modules unless explicitly needed.

## Rationale

The v3 plan invented a repository skeleton. That is now incorrect. kUPS already has a coherent package structure, typed JAX dataclasses, `Table`/`Index` containers, lens-based state access, patch abstractions, MD propagators, and classical potentials. The polymerization extension should fit those patterns.

---

# Phase 1 - minimal non-reactive BFDGE/DETDA pre-curing MD

## Goal

Produce and equilibrate an uncured epoxy/amine mixture before any reaction attempt. This is the new first scientific milestone.

The target chemistry follows the hardening paper:

- epoxy monomer: BFDGE;
- amine hardener: DETDA;
- neat mixture, no solvent;
- functional stoichiometry: 2 BFDGE : 1 DETDA;
- periodic boundary conditions;
- no cross-links initially.

## What this phase excludes

This phase intentionally excludes:

- Monte Carlo trial selection;
- Metropolis acceptance/rejection;
- bond creation;
- epoxide ring opening;
- proton transfer;
- atom-type changes;
- smooth topology transfer;
- QM/MM correction energies.

The molecules move and mix. They do not react.

## Why this phase belongs before graph templates

The MC curing algorithm needs a physically plausible uncured mixture and candidate-site RDFs. The hardening paper also chose a 5 A candidate cutoff from RDF analysis of the uncured mixture. Therefore the first practical artifact should be the equilibrated pre-curing cell and its structural diagnostics.

## Phase 1A - paper-faithful reference workflow

This is the reference path closest to the paper and to `basic_md_pre_curing_epoxy.md`.

### Inputs

- BFDGE and DETDA molecular structures.
- OPLS-AA or consistent all-atom force-field topology.
- Charges following the paper where possible: 1.14*CM1A-LBCC from LigParGen, with charge neutralization and equivalent-atom averaging.
- PACKMOL or equivalent random packing.
- LAMMPS data/restart files as the first exact reference format.

### System sizes

Use increasing sizes:

| label | BFDGE | DETDA | purpose |
|---|---:|---:|---|
| tiny debug | 8 | 4 | check topology, charge, minimization |
| small pilot | 32 | 16 | first meaningful mixture; comparable to known ReaxFF small-cell scale |
| medium pilot | 64 | 32 | better RDF and density statistics |
| production-like small cell | 128 | 64 | later curing benchmark |

### Protocol

Use the existing `basic_md_pre_curing_epoxy.md` protocol as the initial standard:

```text
0. random pack at about 0.4-0.6 g/cm3, default 0.5 g/cm3
1. energy minimization
2. optional safe NVT, 5-20 ps, 0.25-0.5 fs timestep
3. NPT density relaxation, 0.2 ns, 1 atm, target T, 0.5 fs timestep
4. NVT structural sampling, 0.05 ns, fixed final volume, 0.5 fs timestep
```

Temperature targets:

```text
300 K for room-temperature debug
380 K, 420 K, 460 K for isothermal experiment comparison
260 K, 300 K, 340 K, 380 K, 420 K, 460 K for full hardening-paper series later
```

### Deliverables

- `examples/polymerization/epoxy_amine_precuring/README.md`
- molecule input files or documented external-generation commands;
- PACKMOL input templates;
- LAMMPS input skeletons for the reference pre-curing run;
- final artifacts:

```text
uncured_equilibrated.data
uncured_equilibrated.restart
traj_npt.lammpstrj
traj_nvt.lammpstrj
log.lammps
```

- RDF analysis for epoxy/amine reactive-site distances;
- a candidate-list diagnostic using a 5 A cutoff.

### Tests for success

- Total charge is exactly zero or neutralized within a documented tolerance.
- No missing bonded or nonbonded coefficients.
- Minimization removes overlaps.
- NPT run does not collapse or expand into vacuum.
- Density stabilizes to a plausible organic-resin value.
- NVT trajectory remains stable.
- RDF and candidate counts are finite and reproducible.

## Phase 1B - kUPS-native minimal MD path

This is the kUPS integration path. It should start small and honest about current gaps.

kUPS can already construct MD state from ASE-readable structures and run MD through existing integrators. However, exact OPLS-AA reproduction requires bonded topology, exclusions, 1-4 rules, partial charges, and LAMMPS/LigParGen parameter import. The first kUPS-native MD milestone should therefore be staged:

### 1B.1 kUPS MD smoke for the uncured geometry

- Read an uncured geometry using `md_state_from_ase`.
- Run a very short NVT or NPT trajectory with an available potential path:
  - simplified LJ/Coulomb parameters for a smoke test; or
  - an available MLFF interface if appropriate for the organic chemistry.
- Validate that kUPS can move, thermostat/barostat, log, and analyze the same size of system.

This is not yet a paper-faithful force-field reproduction.

### 1B.2 kUPS fixed-topology all-atom import

Implement only the importer and state needed for the pre-curing mixture:

- LAMMPS data parser for:
  - atoms;
  - masses;
  - charges;
  - bonds;
  - angles;
  - dihedrals;
  - impropers;
  - box.
- OPLS-like parameter representation sufficient for BFDGE/DETDA.
- fixed edge tables compatible with existing kUPS bonded potentials where possible.
- nonbonded exclusions and special neighbor handling, including 1-2, 1-3, and 1-4 behavior.

Place this code under:

```text
src/kups/polymerization/io/lammps_data.py
src/kups/polymerization/topology/tables.py
src/kups/polymerization/topology/parameters.py
src/kups/polymerization/md/precuring.py
```

### 1B.3 kUPS non-reactive BFDGE/DETDA run

Once the importer exists, run the same pre-curing protocol in kUPS:

- tiny debug first;
- then 32:16 pilot;
- then RDF/candidate analysis.

### Tests for success

- LAMMPS data parser round-trips atom, charge, and bonded counts.
- kUPS energy terms are finite on imported structures.
- Short NVT is stable.
- Short NPT is stable or its limitations are documented.
- RDF/candidate counts agree qualitatively with the reference trajectory.
- The output is sufficient to seed later topology-transfer tests.

## Decision point after Phase 1

If paper-faithful OPLS in kUPS is slow to implement, keep the LAMMPS reference as the scientific pre-curing source while building kUPS topology-transfer machinery on toy and reduced systems. Do not block graph-template work on perfect OPLS parity.

---

# Phase 2 - offline graph-template compiler adapted from templater

## Goal

Convert the Smart Reaction Templating idea into kUPS-native offline modules.

The external templater scripts show the core algorithm:

```text
LAMMPS data files
    -> molecular graphs with atom mass, type, charge, component
    -> conserved subgraph isomorphism
    -> similarity assignment for unmapped reactive atoms
    -> reaction-site detection from bond-connectivity changes
    -> reduced reactant/product templates
    -> atom equivalence map plus create/delete/edge/initiator IDs
```

## What to reuse conceptually

From `external/templater-main/templater-main/tools/create_bondreact.py`:

- unified reactant and product graphs;
- node attributes:
  - mass;
  - atom type;
  - pair parameters;
  - charge;
  - component ID;
- repeated subgraph-isomorphism search for conserved regions;
- similarity scoring by mass, type, and graph neighborhood;
- linear-sum assignment for unmapped nodes;
- special handling for symmetric or indistinguishable paths;
- reaction-site detection from created/deleted bonds and centrality changes;
- graph-distance cutoff for reduced templates;
- map output with equivalences, edge IDs, delete IDs, and create IDs.

## What not to reuse directly

Do not import `create_bondreact.py` as a library in kUPS. It parses CLI arguments at import time, uses global state, writes LAMMPS-specific files directly, and mixes parsing, mapping, plotting, and output generation.

Instead, port the algorithm into tested modules:

```text
src/kups/polymerization/templates/graph.py
src/kups/polymerization/templates/mapping.py
src/kups/polymerization/templates/diff.py
src/kups/polymerization/templates/reduce.py
src/kups/polymerization/templates/compiler.py
src/kups/polymerization/templates/validation.py
```

## Core data model

```python
class MolecularGraph:
    atom_id: Array
    element_or_mass: Array
    atom_type: Array
    charge: Array
    component: Array
    bonds: Array
    bond_type: Array

class ReactionTemplate:
    name: str
    reactant_graph: MolecularGraph
    product_graph: MolecularGraph
    atom_mapping: Array
    created_bonds: Array
    deleted_bonds: Array
    changed_atom_types: Array
    changed_charges: Array
    changed_bond_types: Array
    changed_angles: Array
    changed_dihedrals: Array
    changed_impropers: Array
    initiator_ids: Array
    edge_ids: Array
    create_ids: Array
    delete_ids: Array
    local_domain_mask: Array
```

For offline code, this may be plain Python plus NumPy/NetworkX. Before runtime, compile to fixed-shape JAX arrays.

## Initial template targets

Start with examples already present in `external/templater-main/templater-main`:

- polyaddition example;
- polycondensation example;
- chain polymerization example.

Then add project-specific epoxy/amine templates:

```text
primary amine + epoxide -> secondary amine + alcohol
secondary amine + epoxide -> tertiary amine + alcohol
```

## Deliverables

- LAMMPS data readers sufficient for templater examples.
- Graph construction unit tests.
- Atom mapping unit tests.
- Graph-difference reports.
- Reduced template JSON format independent of LAMMPS `bond/react`.
- Conversion from external `.mol`/`.map` artifacts to kUPS template JSON for comparison.
- Human-readable template reports for epoxy/amine reactions.

## Tests for success

- The compiler reproduces known created/deleted bonds for at least one external templater example.
- Atom mappings are deterministic for fixed inputs.
- Symmetric ambiguities are either resolved deterministically or reported explicitly.
- Reduced template contains all atoms needed for changed bonds, angles, dihedrals, impropers, atom types, and charges.
- Invalid mappings fail with useful diagnostics.
- The epoxy/amine primary and secondary templates are distinct.

---

# Phase 3 - kUPS dynamic topology state and runtime patch layer

## Goal

Represent topology-changing systems in fixed-shape JAX arrays and apply reaction patches using kUPS' existing patch idiom.

## Design principle

Do not dynamically append Python objects inside a simulation loop. Use fixed-capacity tables with active masks.

Example:

```text
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

The same pattern applies to impropers, atom labels/types, charges, reactive-site states, and molecule/component labels.

## Relationship to existing kUPS code

Use the existing patch machinery:

- `kups.core.patch.Patch`
- `kups.core.patch.ExplicitPatch`
- `kups.core.patch.IndexLensPatch`
- `kups.core.patch.ComposedPatch`
- `kups.core.patch.WithPatch`

The polymerization-specific topology patch should be a specialization of that system, not a disconnected parallel abstraction.

## Runtime state sketch

```python
@dataclass
class PolymerizationState:
    particles: Table[ParticleId, PolymerizationMDParticles]
    systems: Table[SystemId, PolymerizationMDSystems]
    topology: PolymerizationTopology
    templates: CompiledTemplateLibrary
    neighborlist_params: UniversalNeighborlistParameters
    step: Array
```

`PolymerizationMDParticles` should extend or mirror the existing MD particle state and add only what is needed:

```text
positions
masses
atomic_numbers
charges
labels or atom_type
system
position_gradients
momenta
exclusion
reactive_site_state
```

## Deliverables

- `PolymerizationTopology` dataclass.
- `CompiledTopologyPatch` dataclass.
- `apply_topology_patch(state, patch, accept)` function compatible with `Patch`.
- reverse-patch generation.
- capacity-overflow checks.
- active-edge views for existing fixed-edge bonded potentials.
- tests for patch application and reversal.

## Tests for success

- Patch application changes only intended entries.
- Reversal restores the previous topology exactly for toy systems.
- Active counts change as expected.
- JIT compilation succeeds for fixed-size toy states.
- Capacity overflow is detected before corrupting state.
- Existing bonded potentials can consume active edge tables or equivalent filtered views.

---

# Phase 4 - toy graph-derived reaction A + B -> AB

## Goal

Build the smallest vertical slice:

```text
toy reactant graph A + B
    -> toy product graph AB
    -> ReactionTemplate
    -> CompiledTopologyPatch
    -> kUPS state
    -> active bond appears after patch
```

## Deliverables

- Toy graph files in `examples/polymerization/toy_ab/`.
- Template extraction for one created bond.
- Candidate finder for A/B pairs within a cutoff.
- Runtime patch that activates one bond slot.
- Simple harmonic or Morse bond active only after reaction.
- Event log structure:

```text
step
template_id
candidate_atom_ids
distance
patch_id
accepted
energy_before
energy_after
```

## Tests for success

- Extracted template contains exactly one created bond.
- Runtime patch activates exactly one inactive bond slot.
- Bonded potential is inactive before patch and active after patch.
- JIT works.
- Reversible toy mode can deactivate the same bond.
- Event logging records enough information to replay the event.

---

# Phase 5 - smooth topology transfer with graph-derived patches

## Goal

Implement the controlled topology-transfer mechanism from the hardening paper using graph-derived patches.

## Core idea

For a candidate reaction, evaluate both topologies during a short MD window:

```text
E_mix(x, t) = (1 - s(t)) E_reactant(x) + s(t) E_product(x)
F_mix(x, t) = (1 - s(t)) F_reactant(x) + s(t) F_product(x)
```

If the event is accepted, commit the product topology. If it is rejected, reverse the transfer to the reactant topology.

The hardening paper used a continuous switching function. kUPS can start with a simple smooth ramp for tests, then match the paper's ramp when validating.

## Deliverables

- `SmoothTopologyTransferPropagator` under `src/kups/polymerization/md/transfer.py`.
- Mixed-potential wrapper that evaluates reactant and product topology states.
- Switching schedule with deterministic replay.
- Commit/reverse logic using `Patch`.
- Energy and force trace logging.
- Toy `A+B->AB` smooth-transfer example.

## Tests for success

- Energy and forces remain finite during transfer.
- Accepted moves end in product topology.
- Rejected moves restore reactant topology.
- Mixed energy equals explicit weighted reactant/product energies.
- Fixed seed gives replayable transfer.
- Transfer works under JIT for fixed-size states.

## Important implementation note

Smooth transfer usually costs about two force evaluations per MD step because both reactant and product topologies are evaluated. This is acceptable for the first benchmark because the purpose is stable relaxation during event attempts.

---

# Phase 6 - hardening-paper reproduction with BFDGE/DETDA templates

## Goal

Reproduce the algorithmic structure of the controlled-topology-transfer hardening paper inside kUPS, using graph-derived templates rather than hand-coded epoxy-specific topology edits.

## Target algorithm

```text
1. Start from equilibrated uncured BFDGE/DETDA mixture from Phase 1.
2. Run an MD block.
3. Identify nearby epoxy/amine candidates.
4. Select a candidate event.
5. Select template:
   - primary amine + epoxide -> secondary amine + alcohol
   - secondary amine + epoxide -> tertiary amine + alcohol
6. Compile candidate-specific topology patch.
7. Smoothly transfer reactant topology to product topology.
8. Estimate reaction energy:
      delta_E = <E_product_mm> - <E_reactant_mm> + correction
9. Accept/reject with Metropolis probability.
10. Commit product topology if accepted; reverse if rejected.
11. Repeat until curing saturates.
```

## Paper details to preserve

The hardening paper used:

- BFDGE + DETDA simplified chemistry;
- OPLS-AA topologies from LigParGen;
- 1.14*CM1A-LBCC charges;
- charge neutralization and equivalent-atom charge averaging;
- randomized starting configurations from PACKMOL/moltemplate;
- 0.2 ns pre-reaction relaxation;
- 0.05 ns constant-volume RDF sampling;
- NpT curing at 1 atm;
- temperatures 260, 300, 340, 380, 420, and 460 K;
- 0.5 fs timestep during topology transfer and equilibration;
- 5 A candidate cutoff from epoxy/amine RDFs;
- two isolated reaction-energy corrections:
  - first linking: QM reaction energy about -25.5 kcal/mol, with the paper's isolated-MM offset about +38.8 kcal/mol;
  - second linking: QM reaction energy about -15.5 kcal/mol, with the paper's isolated-MM offset about +42.1 kcal/mol;
- MC acceptance using a Metropolis probability.

The visible table in the local paper text reports simulated final curing degrees of roughly:

| T cure (K) | simulated cure (%) |
|---:|---:|
| 260 | 78 |
| 300 | 83 |
| 340 | 86 |
| 380 | 88 |
| 420 | 93 |
| 460 | 93 |

The first kUPS target is qualitative and algorithmic reproduction, not exact numeric equality.

## Subphase 6A - simplified epoxy/amine prototype

Before full BFDGE/DETDA:

- reduced epoxide/amine fragments;
- graph-derived primary-amine template;
- one accepted event;
- one rejected event;
- fixed correction energy;
- event log and topology validation.

### Tests for success

- Candidate list updates after accepted reactions.
- Primary amine site state becomes secondary.
- Epoxide site becomes opened alcohol state.
- Rejected events reverse without topology drift.
- No reactive site exceeds allowed functionality.

## Subphase 6B - BFDGE/DETDA full topology templates

Deliver:

- BFDGE and DETDA reactant graphs;
- singly linked product graph;
- doubly linked product graph;
- primary and secondary epoxy/amine templates;
- local reduced template reports;
- topology patches for:
  - C-N bond formation;
  - epoxide ring opening;
  - N-H to O-H proton transfer representation;
  - atom-type changes;
  - charge changes;
  - affected bonds, angles, dihedrals, and impropers.

### Tests for success

- C-N bond formation is detected.
- Epoxide ring opening is represented consistently.
- Primary and secondary amine states are distinct.
- Product graph passes valence/site-state checks.
- Patch application on isolated fragments is reversible.

## Subphase 6C - kUPS curing loop

Deliver:

- candidate finder using reactive-site distances;
- MC/MD outer loop;
- smooth-transfer attempts;
- correction-energy selection for first vs second linking;
- degree-of-cure tracker;
- acceptance-ratio tracker;
- network statistics:
  - primary/secondary/tertiary amine fractions;
  - BFDGE/DETDA component connectivity;
  - largest connected component;
  - gel fraction;
  - functionality distribution.

### Tests for success

- Candidate cutoff around 5 A produces plausible candidate counts.
- Accepted events create chemically valid links.
- Acceptance ratio decreases with cure.
- Cure saturates below 100% for constrained systems.
- Higher-temperature runs reach higher or faster conversion than lower-temperature runs.
- Network remains stable after repeated topology transfers.

---

# Phase 7 - ORCA-derived local reaction corrections and datasets

## Goal

Use ORCA to replace or validate fixed literature correction energies and then build a local reaction dataset for later learned rates.

This phase should build on existing local work:

- `tdd/qm/orca_install_and_test_plan.md`
- `tdd/qm/epoxy_amine_cluster_workflow.md`
- `scripts/polymerization/qm/*`
- `test/polymerization/fixtures/epoxy_amine_orca/*`

## First target

Keep the first ORCA target small:

```text
reduced epoxy-amine near-attack geometry
    -> ORCA energy + gradient
    -> parse result
    -> metadata table
```

The existing workflow already includes a reduced epoxy/amine near-attack smoke test.

## Deliverables

- ORCA structures for:
  - reduced epoxide fragment;
  - reduced primary amine fragment;
  - first linked product;
  - second linked product or secondary-amine analog.
- Energy bookkeeping script:

```text
delta_E_1 = E(first_product)  - E(epoxide) - E(primary_amine)
delta_E_2 = E(second_product) - E(first_product) - E(epoxide)
```

- metadata CSV with geometry, method, basis, charge, multiplicity, convergence, energy, gradients, and source files.
- comparison to hardening-paper correction values.

## Tests for success

- ORCA jobs terminate normally.
- Minima have no imaginary frequencies where frequency jobs are run.
- Products are chemically valid.
- First reaction is more exothermic than second reaction.
- Result parser is deterministic and catches failed jobs.

---

# Phase 8 - learned local barrier/rate model

## Goal

Train a local model for candidate reaction ranking or event probabilities.

The first ML target should be local and discrete, not a full reactive MLFF:

```text
input: local reactive fragment geometry + site states
output: reaction energy, barrier proxy, log rate, or event probability
```

## Baselines

- fixed correction from hardening paper;
- constant barrier;
- distance-only model;
- handcrafted geometry features plus ridge/random forest/XGBoost;
- small message-passing model only after enough data exists.

## Deliverables

- feature extractor under `src/kups/polymerization/qm/features.py`;
- dataset table;
- train/validation/test split by fragment and conformer;
- baseline model reports;
- exportable inference function for kUPS event scoring.

## Tests for success

- Model beats constant and distance-only baselines.
- Higher barrier means lower event probability.
- Temperature dependence is physically sensible.
- Inference can be batched over candidates.
- Out-of-domain cases are flagged or assigned uncertainty.

---

# Phase 9 - MLFF-compatible reactive polymer simulation

## Goal

Couple the topology-event layer to MLFF-driven dynamics where appropriate.

The safe architecture remains explicit topology events:

```text
MD/MLFF relaxation
    -> candidate detection
    -> local event scoring
    -> smooth topology transfer or local relaxation
    -> commit/reject topology patch
```

This avoids pretending that a fixed-topology MLFF alone can perform polymerization.

## Deliverables

- potential wrapper compatible with existing `kups.potential.mliap` paths;
- ablation modes:
  - classical-only;
  - MLFF relaxation with fixed correction;
  - MLFF relaxation with learned event model;
  - classical reference.
- comparison of cure curves and structural statistics.

## Tests for success

- MLFF mode is stable on uncured and partially cured structures.
- Event selection differs meaningfully from constant-rate baselines.
- Cure trends remain plausible.
- The explicit topology state remains the source of truth.

---

# Phase 10 - validation, paper, and upstream-ready contribution

## Goal

Turn the work into a coherent kUPS contribution and scientific result.

## Validation targets

- Phase 1 pre-curing:
  - density;
  - RDF;
  - candidate counts.
- Phase 6 curing:
  - acceptance ratio vs cure;
  - final cure vs temperature;
  - reaction heat proxy vs cure;
  - network statistics.
- Later mechanical validation:
  - density of cured network;
  - gel fraction;
  - optional elastic moduli if long trajectories are feasible.

## Software contribution

The upstream-facing contribution is:

```text
graph-derived topology patches + smooth topology transfer for reactive polymerization in kUPS
```

This is broader than an epoxy script and narrower than a full reactive force field.

---

# Immediate implementation sequence

## Week 1 - Phase 0 and Phase 1 scaffolding

- Create `src/kups/polymerization/`.
- Add package README/design note.
- Add pre-curing example folder.
- Implement or document the reference LAMMPS/PACKMOL pre-curing workflow.
- Add a charge/topology sanity checker for generated BFDGE/DETDA inputs.

## Week 2 - minimal non-reactive MD diagnostics

- Run tiny debug pre-curing reference.
- Produce RDF/candidate-count diagnostics.
- Start kUPS-native MD smoke on the same geometry.
- Decide whether exact OPLS import is needed immediately or can follow the graph-template toy path.

## Week 3 - external templater adaptation

- Implement graph parsing for one external templater example.
- Reproduce mapping or changed-bond report for that example.
- Emit kUPS template JSON.
- Add tests around graph mapping and reduced template content.

## Week 4 - toy runtime patch

- Add fixed-capacity topology tables.
- Apply a graph-derived `A+B->AB` patch.
- Run a tiny kUPS MD example with bond activation.
- Log one accepted and one rejected toy event.

At the end of four weeks, the project should have:

```text
1. an equilibrated uncured-mixture reference workflow;
2. a repository-correct polymerization package boundary;
3. a first graph-template compiler slice;
4. a toy runtime topology patch in kUPS.
```

---

# Risk register

| Risk | Severity | Mitigation |
|---|---:|---|
| Exact OPLS/LigParGen parity in kUPS takes longer than expected | high | keep LAMMPS reference workflow while building kUPS topology-transfer on toy/reduced systems |
| Dynamic topology conflicts with JAX static shapes | high | fixed-capacity tables and active masks |
| Graph matching is ambiguous for symmetric molecules | high | deterministic tie-breaking, manual mapping overrides, and explicit ambiguity reports |
| External templater scripts are not library-ready | medium | port algorithms into small modules; keep external as reference |
| Epoxy proton transfer and ring opening are hard to encode | high | validate isolated template products with ORCA and manual inspection |
| Full BFDGE/DETDA topology import is large | medium/high | start with reduced fragments and isolated template tests |
| Smooth transfer doubles force evaluations | medium | acceptable for benchmark; optimize only after correctness |
| Learned model scope expands too early | high | keep fixed correction baseline until hardening loop works |
| MLFF fails near reactive geometries | high | keep explicit topology changes; use MLFF first for relaxation/scoring support |

---

# Key correction to v3

The v3 plan had the right scientific direction but the wrong software boundary and an overly early jump into reaction templates. The corrected plan is:

```text
respect kUPS source layout
    -> put new source under src/kups/polymerization
    -> first build plain uncured BFDGE/DETDA MD
    -> then adapt graph templating offline
    -> then build JAX-safe topology patches
    -> then run smooth topology transfer and MC curing
```

Monte Carlo requires discrete trial steps and accept/reject decisions. That should come after the pure MD pre-curing workflow is reproducible.
