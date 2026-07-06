# Tiny Moltemplate OPLS-AA Reproduction Plan

This plan targets faithful kUPS reproduction of:

```text
external/lammps_oplss/moltemplate_oplsaa_tiny
```

The source is a Moltemplate-generated LAMMPS `real`-units methane system using:

```lammps
atom_style full
bond_style harmonic
angle_style harmonic
dihedral_style opls
improper_style cvff
pair_style lj/charmm/coul/long 9.0 11.0
pair_modify mix geometric
special_bonds lj/coul 0.0 0.0 0.5
kspace_style pppm 0.0001
```

For this methane case there are no dihedrals or impropers, but the styles still
matter for the eventual importer contract.

## Project Overview

This mini project is a controlled path from a resolved LAMMPS/Moltemplate OPLS-AA
input deck to a kUPS simulation that can reproduce the same physical model. The
first target is intentionally tiny: one methane molecule in a periodic 30 A box.
That system is small enough to inspect by hand, but it still exercises the
important all-atom machinery: LAMMPS `atom_style full` topology, type-based
force-field parameters, partial charges, bonded interactions, nonbonded
exclusions, OPLS special-pair scaling, and long-range electrostatics.

The goal is not to make a one-off methane script. The goal is to create the
smallest reliable development ladder for adding OPLS-AA/LAMMPS-data support to
kUPS. Each rung should answer one concrete question:

- Did we copy the source data correctly?
- Did we convert units correctly?
- Did we wire existing kUPS primitives correctly?
- Did we implement a missing dynamics-engine semantic correctly?
- Did the resulting kUPS output move closer to the LAMMPS reference for the
  reason we expected?

This distinction matters because many OPLS-AA reproduction failures look similar
at the total-energy level. A wrong C-H bond coefficient, a missing charge
override, a Lorentz-Berthelot instead of geometric mixed LJ sigma, and an
incorrect 1-4 Coulomb factor can all appear as "the energy does not match
LAMMPS." The plan therefore separates format/import issues from actual
energy/force semantics, and it adds comparison tooling early so every
implementation step produces an explicit before/after report.

The intended final state for this mini project is a fixed-topology all-atom kUPS
workflow that can read the resolved LAMMPS files, evaluate the same in-scope
terms as the LAMMPS methane case, and report any remaining differences in a
structured way. Minimization and exact LAMMPS velocity initialization are kept
out of scope for now, so early validation should prioritize static
energy/force decomposition over trajectory-level agreement.

The IDE-visible path `examples/polyremization/lammps_to_kusp/REPORT.md` is not
present in this checkout. The matching report is currently:

```text
results/lammps_to_kusp/tiny_oplsaa_methane_lj_only_nve/REPORT.md
```

## First Question: What Is Missing?

### Format/import capabilities

These items copy or normalize information that LAMMPS/Moltemplate has already
resolved numerically. They should not change force evaluation semantics by
themselves.

- Parse LAMMPS `atom_style full` data files: box, masses, atoms, bonds, angles,
  dihedrals, impropers.
- Parse Moltemplate-generated input fragments: `system.in.init`,
  `system.in.settings`, and `system.in.charges`.
- Apply charge overrides from `set type ... charge ...` after reading the
  `Atoms` section, matching the LAMMPS include order.
- Preserve LAMMPS IDs: atom ID, molecule ID, atom type, bond type, angle type,
  and coefficient type IDs for diagnostics and round-trip comparisons.
- Convert LAMMPS `real` units into kUPS units:
  - kcal/mol to eV for energies and force constants.
  - Angstrom stays Angstrom.
  - fs stays fs at config level, then follows existing kUPS MD conversion.
  - charges remain elementary-charge units for Coulomb/Ewald.
- Build a resolved, explicit kUPS all-atom state from numeric files. For this
  target, do not parse generic Moltemplate `.lt` force-field databases first.

### Workflow/wiring capabilities

These items use physics primitives that mostly already exist, but are not wired
into one all-atom LAMMPS-data MD application.

- A fixed-topology MD state carrying particles, systems, bonds, angles, charges,
  LJ parameters, Ewald parameters, and special-pair metadata.
- A CLI or application entry point analogous to `kups_md_lj`, but consuming the
  resolved all-atom config/data.
- A summed classical potential combining:
  - harmonic bonds,
  - harmonic angles,
  - LJ nonbonded terms,
  - Ewald electrostatics,
  - later OPLS dihedrals and CVFF impropers for non-methane systems.
- HDF5 output and analysis using the existing MD application conventions.

### Dynamics-engine capabilities

These are the risky pieces because they change how energies and forces are
computed.

- Geometric LJ mixing. Current `LennardJonesParameters.from_dict` only accepts
  `lorentz_berthelot`, and sigma is arithmetic-mixed there.
- Explicit pair coefficient overrides. LAMMPS can define same-type and cross-type
  `pair_coeff` values, then generate only missing pairs by the selected mixing
  rule.
- Topology-derived 1-2, 1-3, and 1-4 pair classes. LAMMPS derives these from
  bonds before nonbonded evaluation.
- Independent LJ and Coulomb scaling factors for special pairs. The source uses
  `special_bonds lj/coul 0.0 0.0 0.5`, so 1-2 and 1-3 pairs are excluded for
  both LJ and Coulomb, while 1-4 pairs are scaled by 0.5 for both. General kUPS
  support should allow LJ and Coulomb factors to differ.
- Ewald exclusion correction with scaling, not only full exclusion. The current
  Ewald exclusion correction subtracts excluded vacuum Coulomb pairs to make
  their net interaction zero; it does not represent an arbitrary 0.5-scaled
  special pair.
- CHARMM-style LJ switching semantics for exact `lj/charmm/coul/long` matching.
  This should be delayed until we need strict LAMMPS energy matching near the
  9.0-11.0 A switching region.
- Decide whether kUPS Ewald is an acceptable reference or whether PPPM-compatible
  behavior is required. LAMMPS uses PPPM with accuracy `1.0e-4`; kUPS currently
  has Ewald, not PPPM.

Minimization and exact LAMMPS velocity initialization are intentionally out of
scope for this plan. Run comparisons should start from static energy/force
checks and short NVE checks with controlled initial momenta.

## Separation Rule

Every implementation step should label changes as one of:

- **Format**: parse, preserve, validate, or convert source data.
- **Wiring**: compose existing kUPS primitives into a new all-atom workflow.
- **Engine**: add or change energy/force semantics.
- **Reference**: generate LAMMPS/kUPS comparison outputs and tolerances.

If an experiment fails, this label tells us where to debug. For example, a wrong
C-H bond energy after importing `bond_coeff 1 340. 1.09` is likely format or
unit conversion. A wrong 1-4 Coulomb energy is engine semantics.

## Experiment Folder Sequence

Create one folder per step under:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_2
...
```

Each folder should contain:

- `README.md`: what capability is being tested and what is intentionally absent.
- `config.yaml`: kUPS run/input config for that step.
- `expected.yaml`: small reference values from LAMMPS or analytic calculation.
- `compare.yaml`: comparison settings, tolerances, and active terms.
- `run.sh`: one-command local reproduction, if the project convention permits.
- `REPORT.md`: generated result summary with pass/fail and known deviations.

Do not overwrite old folders when adding a capability. The point is to keep the
development path inspectable.

## Step 1: Numeric LAMMPS Import Skeleton

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1
```

Type: **Format**

Goal: parse the concrete generated methane files into a resolved kUPS-side
structure without running dynamics.

Inputs:

- `system.data`
- `system.in.init`
- `system.in.settings`
- `system.in.charges`

Tests:

- Counts match: 5 atoms, 4 bonds, 6 angles, 0 dihedrals, 0 impropers.
- Box matches `[-15, 15]` in x/y/z with 3D periodicity.
- Masses match atom types 1 and 2.
- Charges are taken from `system.in.charges`/`set type`, not from the zero
  charges in `system.data`.
- Bond and angle connectivity preserves LAMMPS atom IDs.
- Coefficients are stored with original units and converted kUPS units.

No engine changes are allowed in this step.

## Step 2: Reference Comparison Harness

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_2
```

Type: **Reference**

Goal: create the scripts and report format used by every later experiment to
compare LAMMPS and kUPS outputs.

This should be early because otherwise each milestone will invent its own
comparison method. The harness does not need all kUPS physics to exist yet. It
can start by parsing LAMMPS reference files, reading any available kUPS outputs,
and marking unavailable kUPS terms as `not_implemented`.

Expected implementation:

- Parse LAMMPS `log.tiny` thermo output into normalized units.
- Parse LAMMPS initial and final data files for box, coordinates, atom types,
  charges, and topology counts.
- Read kUPS output formats that exist at each stage:
  - resolved YAML for importer-only stages,
  - static energy JSON/YAML for energy-evaluation stages,
  - HDF5 trajectory output for MD stages.
- Generate a per-folder `REPORT.md` with a stable table:
  - format checks,
  - active energy terms,
  - inactive or not-yet-implemented terms,
  - LAMMPS value,
  - kUPS value,
  - absolute and relative difference,
  - tolerance,
  - pass/fail/status.
- Keep comparison scripts separate from engine code. They should report
  differences, not silently correct them.

Suggested script locations:

```text
scripts/polymerization/lammps_to_kusp/parse_lammps_log.py
scripts/polymerization/lammps_to_kusp/compare_tiny_oplsaa.py
```

Tests:

- The parser extracts the LAMMPS initial minimization energy and MD thermo
  series from `log.tiny`.
- LAMMPS `real` energy values are converted from kcal/mol to eV.
- A comparison run can produce a report even when kUPS has only imported data
  and no matching energy terms yet.

The important design point is progressive comparison. Early reports should not
pretend to pass full OPLS-AA reproduction; they should say exactly which terms
are absent and whether the newly added capability moved in the expected
direction.

## Step 3: Fixed-Topology State and Bond/Angle Energy

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_3
```

Type: **Wiring**

Goal: build a kUPS state that can evaluate harmonic bond and harmonic angle
energies using explicit fixed edges.

Expected implementation:

- Reuse current harmonic bond and angle primitives.
- Convert LAMMPS harmonic bond `K` directly to eV/A^2 because LAMMPS harmonic
  bond uses `E = K * (r - r0)^2`.
- Convert LAMMPS harmonic angle `K` carefully. Current kUPS harmonic angle
  computes angle deviations in degrees, so either convert `K` to eV/degree^2
  for current behavior or update the engine to a radian-native angle potential
  in a separate, explicit engine step.

Tests:

- Static bond energy for the imported coordinates matches an analytic
  calculation.
- Static angle energy for the imported coordinates matches an analytic
  calculation.
- Total bonded energy is independent of atom ordering after remapping IDs.

No nonbonded terms are active yet.

## Step 4: Geometric LJ Mixing

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_4
```

Type: **Engine**

Goal: support `pair_modify mix geometric` for LJ sigma and epsilon.

Expected implementation:

- Extend LJ parameter creation with a `geometric` mixing rule:
  - `sigma_ij = sqrt(sigma_i * sigma_j)`
  - `epsilon_ij = sqrt(epsilon_i * epsilon_j)`
- Keep `lorentz_berthelot` behavior unchanged.

Tests:

- Unit test the 2-type methane matrix:
  - C-C from `pair_coeff 1 1`.
  - H-H from `pair_coeff 2 2`.
  - C-H generated geometrically.
- Existing LJ tests for Lorentz-Berthelot continue to pass.

This step only changes pair parameter generation. It should still not try to
match LAMMPS methane energies because bonded intramolecular exclusions are not
active yet.

## Step 5: Explicit Pair Coefficient Overrides

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_5
```

Type: **Format + Engine**

Goal: represent LAMMPS `pair_coeff i j epsilon sigma` as an explicit matrix
where provided cross terms override generated mixed terms.

Expected implementation:

- Import same-type and cross-type `pair_coeff` rows into a type-pair table.
- Generate missing pairs by the selected mixing rule.
- Preserve which pairs were explicit versus generated for diagnostics.

Tests:

- Same methane behavior as Step 4 because only 1-1 and 2-2 are explicit.
- Add a small synthetic two-type fixture with an explicit 1-2 override and prove
  it beats the mixing rule.

This is both format and engine work because it requires parsed coefficient
provenance and force evaluation must use the final pair matrix.

## Step 6: Topology-Derived 1-2 and 1-3 LJ Masks

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_6
```

Type: **Engine**

Goal: derive special-pair classes from bonds and exclude 1-2 and 1-3 LJ pairs.

For methane:

- 1-2 pairs: C-H bonded pairs, excluded.
- 1-3 pairs: H-H pairs through H-C-H angles, excluded.
- 1-4 pairs: none.

Expected implementation:

- Build topology graph distances from bonds.
- Produce pair classifications for graph distance 1, 2, and 3.
- Apply LJ scale factors from `special_bonds lj`.
- Start with factors `[0.0, 0.0, 1.0]` if easier, then set `[0.0, 0.0, 0.5]`
  in Step 7.

Tests:

- Methane intramolecular LJ energy becomes zero because all pairs are 1-2 or
  1-3.
- An added butane-like synthetic topology includes at least one 1-4 pair.

This cannot be represented by only copying force-field values. It changes which
neighbor-list edges contribute to the LJ energy.

## Step 7: Independent LJ Special-Pair Scaling

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_7
```

Type: **Engine**

Goal: support arbitrary LJ special factors for 1-2, 1-3, and 1-4 pairs.

Expected implementation:

- Store per-pair or per-edge LJ scale factors.
- Multiply LJ edge energies by the scale factor before summation.
- Do not couple these factors to Coulomb factors.

Tests:

- Methane remains zero LJ because it has only 1-2 and 1-3 pairs.
- A synthetic 4-atom chain has a 1-4 LJ energy exactly equal to 0.5 times the
  normal LJ pair energy under `special_bonds lj 0.0 0.0 0.5`.

This step is required even though methane has no 1-4 pairs, because faithful
OPLS-AA support needs it for the next molecule larger than methane.

## Step 8: Configure Ewald From Imported Charges

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_8
```

Type: **Format + Wiring**

Goal: wire kUPS Ewald using charges imported from the LAMMPS/Moltemplate files.

Expected implementation:

- Build Ewald parameters from imported charges and periodic box.
- Let the config choose:
  - target accuracy, defaulting from `kspace_style pppm 0.0001`;
  - real-space cutoff, defaulting from the Coulomb cutoff in
    `pair_style lj/charmm/coul/long 9.0 11.0`.
- Document that this is Ewald, not PPPM.

Tests:

- Net charge is zero for methane.
- Ewald can evaluate finite energy and forces for the charged state.
- Energy changes if charge overrides are disabled, proving the charge include
  path matters.

This step wires existing Ewald behavior. It does not yet claim LAMMPS PPPM
numerical equivalence.

## Step 9: Coulomb Exclusion Correction for `special_bonds 0 0 0.5`

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_9
```

Type: **Engine**

Goal: match LAMMPS Coulomb special-pair semantics independently from LJ.

For methane, all intramolecular charged pairs are 1-2 or 1-3, so they should be
fully excluded from Coulomb.

Expected implementation:

- Derive Coulomb special-pair classes from the same topology graph as LJ.
- Apply Coulomb factors from `special_bonds coul`.
- Extend current Ewald exclusion correction beyond full exclusion so it can also
  represent a retained fraction, especially 0.5 for 1-4 pairs.

Tests:

- Methane Coulomb special-pair correction removes all intramolecular 1-2 and
  1-3 Coulomb interactions.
- Synthetic 4-atom chain retains exactly 0.5 of the 1-4 Coulomb interaction.
- LJ and Coulomb factors can differ in a synthetic fixture.

This is the most important engine-risk step. Current Ewald exclusion correction
is designed around zeroing excluded pairs, not arbitrary LAMMPS special scaling.

## Step 10: Ewald-vs-PPPM Reference Decision

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_10
```

Type: **Reference**

Goal: decide what "faithful reproduction" means for long-range electrostatics.

Options:

- Accept kUPS Ewald as the reference-compatible method and compare within
  method/tolerance differences against LAMMPS PPPM.
- Add a LAMMPS reference variant using Ewald, if available in the local LAMMPS
  build, to compare Ewald to Ewald.
- Treat PPPM compatibility as a future engine project if exact LAMMPS PPPM
  behavior is required.

Tests:

- Static energy decomposition report includes bond, angle, LJ, Coulomb/Ewald,
  and total potential energy.
- Compare against LAMMPS `log.tiny` initial potential energy
  `0.169805994760444` kcal/mol converted to kUPS eV, with an explicit tolerance
  and explanation for any Ewald/PPPM mismatch.

This step should end with a written decision in `REPORT.md`; it should not hide
PPPM/Ewald differences inside loose tolerances.

## Step 11: CHARMM-Style LJ Switching

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_11
```

Type: **Engine**

Goal: implement `lj/charmm/coul/long 9.0 11.0` LJ switching if exact LAMMPS
matching requires it.

Expected implementation:

- Add a switch-aware LJ variant or a switch mode on the existing LJ potential.
- Preserve the current sharp-cutoff and tail-correction LJ behavior.
- Confirm the exact LAMMPS formula and whether only LJ is switched while Coulomb
  uses the long-range split.

Tests:

- Pairwise energy/force fixture at distances:
  - below 9.0 A,
  - between 9.0 and 11.0 A,
  - at and beyond 11.0 A.
- A static methane-box test where an added nonbonded probe atom sits inside the
  switching region.

For the current one-methane 30 A box, this may not affect intramolecular terms
after exclusions, but it matters for exact intermolecular OPLS-AA comparisons.

## Step 12: Full All-Atom NVE Smoke Test

Folder:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_12
```

Type: **Wiring + Reference**

Goal: run the imported fixed-topology methane case with all in-scope terms:
bond, angle, LJ with OPLS mixing and special scaling, and Ewald electrostatics.

Inputs intentionally excluded:

- LAMMPS-style minimization.
- Exact LAMMPS velocity initialization with `mom yes rot yes`.

Tests:

- Static energy/force check before MD.
- 10-step NVE smoke test with deterministic kUPS momenta.
- Energy drift is reasonable for the 0.25 fs timestep.
- Report clearly states whether comparison is:
  - static energy only,
  - statistical MD behavior,
  - or trajectory-level matching.

Trajectory-level matching is not expected until minimization and velocity
initialization are brought into scope.

## Development Checklist

- [ ] Add LAMMPS full-data parser tests before importer implementation.
- [ ] Add comparison scripts and stable `REPORT.md` output before engine work.
- [ ] Add numeric unit-conversion tests for every imported coefficient kind.
- [ ] Add LJ geometric mixing without changing Lorentz-Berthelot behavior.
- [ ] Add explicit pair coefficient override tests.
- [ ] Add topology graph-distance tests for 1-2, 1-3, and 1-4 classifications.
- [ ] Add LJ special scaling tests.
- [ ] Add Coulomb/Ewald special scaling tests.
- [ ] Add one experiment folder per milestone.
- [ ] Generate a `REPORT.md` per experiment with actual kUPS command, result,
  and remaining mismatch.

## Practical Priority

The fastest useful path is:

1. Import numeric LAMMPS files.
2. Build the comparison harness and report format.
3. Evaluate static bond and angle energies.
4. Implement geometric LJ and pair overrides.
5. Implement special-pair topology and LJ scaling.
6. Wire charged Ewald.
7. Extend Ewald correction for special-pair scaling.
8. Decide Ewald versus PPPM reference policy.
9. Add CHARMM switching only if comparison demands it.

This ordering keeps parameter-copying and engine-semantics changes separate, so
failures can be assigned to the right layer instead of being hidden inside a
large "OPLS importer" change.
