# Tiny Moltemplate OPLS-AA Reproduction Plan 2

This document expands **Step 2: Reference Comparison Harness** from
`tiny_moltemplate_oplsaa_reproduction_plan.md`.

The goal of this step is not to implement missing OPLS-AA physics yet. The goal
is to create reusable, test-driven MD diagnostics for kUPS and LAMMPS result
folders. The tiny methane OPLS-AA case is the first fixture and acceptance
target, but the scripts should be useful for any sufficiently similar kUPS or
LAMMPS MD output: a result folder with trajectory or thermo data, optional
topology/structure files, and enough metadata to compute physical observables.

Reference source:

```text
external/lammps_oplss/moltemplate_oplsaa_tiny
```

Current kUPS starting point:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0
```

Format baseline already produced by Step 1:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1
```

Step 2 implementation target:

```text
scripts/polymerization/lammps_to_kusp/
tests/polymerization/
```

The scripts may start under the LAMMPS-to-kUPS path because this project is the
first user, but their internal design should be generic MD diagnostics. Tiny
OPLS-AA-specific defaults and fixtures should live at the CLI/default layer, not
inside the core parser, data model, plotting, or report code.

Step 2 may generate report artifacts under `results/`, but it should not create
a new kUPS example configuration. The only kUPS simulation input in scope is the
existing dirty baseline:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/methane_lj_only_nve.yaml
```

## Why This Step Exists

The `moltemplate_oplsaa_tiny_0` folder contains the first runnable kUPS-side
approximation. It is intentionally dirty: it uses the existing LJ-only MD
application, carries methane geometry and same-type LJ values, and omits the
LAMMPS OPLS-AA bonded, electrostatic, special-pair, minimization, and exact
velocity semantics.

That makes it useful as a baseline, but dangerous as a validation target. A
single total-energy or temperature curve cannot say whether a mismatch comes
from wrong parameters, missing bond terms, missing charge terms, incorrect
special-bond exclusions, the wrong LJ mixing rule, or different initialization.

Step 2 must therefore build reusable diagnostics that make every later change
visible as physical quantities:

- static energy terms;
- structural observables;
- dynamics observables;
- static topology and geometry diagnostics;
- local per-pair, per-bond, and per-angle deviations;
- generated plots and a stable `REPORT.md`.

The report should be useful even before kUPS can reproduce the full LAMMPS
simulation. Missing terms must appear as `not_implemented`, `not_available`, or
`out_of_scope`, not as silent zeros.

The same tools should also be useful after the tiny methane example. For
example, a later kUPS all-atom run or a longer LAMMPS NVE benchmark should be
diagnosable by pointing the scripts at the new result folder. The tiny fixture
should provide regression tests, not hard-coded assumptions.

## Scope

Type: **Reference**

Allowed work in this step:

- Parse LAMMPS thermo logs, with `log.tiny` as the first fixture.
- Parse LAMMPS initial and final data files when present, enough to extract
  box, coordinates, topology counts, atom types, molecule IDs, and charges.
- Read kUPS result folders containing HDF5 output and config metadata, with
  `moltemplate_oplsaa_tiny_0` as the first dirty baseline.
- Optionally run the existing `moltemplate_oplsaa_tiny_0` kUPS smoke example to
  produce its HDF5 output, without creating a new kUPS config.
- Read Step 1 resolved importer output.
- Define normalized, reusable data products for reports and plots.
- Generate a diagnostics `REPORT.md` inside the selected result folder.
- Generate plot files from normalized physical quantities.
- Add tests for parsers, report generation, status handling, and plot
  availability.

Forbidden work in this step:

- Do not change force evaluation semantics.
- Do not implement OPLS-AA bonded terms in the dynamics engine.
- Do not implement geometric LJ mixing.
- Do not implement special-pair exclusions or scaling.
- Do not tune tolerances to make dirty kUPS output appear correct.
- Do not create a new `examples/.../moltemplate_oplsaa_tiny_2` kUPS run folder.
- Do not create a new kUPS run config for Step 2.

This step is successful if it gives a clear, reproducible picture of what the
dirty kUPS approximation does wrong and gives future steps a stable way to show
what improved.

## Primary Outputs

The primary deliverable is diagnostics tooling, not a new simulation example.
The implementation should add scripts and tests that can generate reports and
figures from:

- a LAMMPS result folder with thermo logs and optional data files;
- a kUPS result folder with HDF5 output and optional config/metadata;
- optional comparison metadata such as Step 1 resolved import output;
- the tiny OPLS-AA methane fixtures as the first concrete regression case.

Suggested source files:

```text
scripts/polymerization/lammps_to_kusp/parse_lammps_md_log.py
scripts/polymerization/lammps_to_kusp/collect_md_diagnostics.py
scripts/polymerization/lammps_to_kusp/plot_md_diagnostics.py
scripts/polymerization/lammps_to_kusp/compare_md_results.py
```

Suggested tests:

```text
tests/polymerization/test_parse_lammps_md_log.py
tests/polymerization/test_md_diagnostics_output_locations.py
tests/polymerization/test_md_diagnostics_report_generation.py
tests/polymerization/test_tiny_oplsaa_geometry_diagnostics.py
tests/polymerization/test_tiny_oplsaa_pair_diagnostics.py
```

Generated artifacts should live next to the simulation result being diagnosed.
The default convention is:

```text
<result-folder>/diagnostics/
```

For a kUPS run, the user should be able to point the diagnostics script at the
kUPS result folder and receive:

```text
results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0/
  methane_lj_only_nve.h5
  methane_lj_only_nve.yaml
  diagnostics/
    REPORT.md
    data/
      kups_tiny0_observables.csv
      static_geometry.csv
      static_energy_terms.csv
      pair_diagnostics.csv
      bond_diagnostics.csv
      angle_diagnostics.csv
    plots/
      energy_timeseries.png
      temperature_timeseries.png
      pressure_timeseries.png
      energy_drift.png
      bond_lengths.png
      angle_distribution.png
      pair_distance_classes.png
      static_energy_breakdown.png
      missing_physics_matrix.png
```

For a LAMMPS reference folder, the same tooling should be able to write:

```text
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/
  log.tiny
  log.tiny.benchmark10
  log.tiny_long_1M
  log.tiny_18M
  system.data
  tiny_oplsaa_methane_final.data
  diagnostics/
    REPORT.md
    data/
      lammps_thermo.csv
      static_geometry.csv
      static_energy_terms.csv
      pair_diagnostics.csv
      bond_diagnostics.csv
      angle_diagnostics.csv
    plots/
      energy_timeseries.png
      temperature_timeseries.png
      pressure_timeseries.png
      energy_drift.png
      bond_lengths.png
      angle_distribution.png
      pair_distance_classes.png
      static_energy_breakdown.png
      missing_physics_matrix.png
```

For comparison mode, the tool should run the same diagnostics on the LAMMPS and
kUPS result folders, then render paired figures for inspection. "Comparison"
means visual side-by-side diagnostics, not a separate physics correction layer.
Each comparison figure should use two columns:

- left column: LAMMPS;
- right column: kUPS.

The tool should also support a selected comparison output folder. The default
can be one side's `diagnostics/comparison/` subfolder, but the user should be
able to override it:

```text
<selected-result-folder>/diagnostics/comparison/
  REPORT.md
  data/
    lammps_thermo.csv
    kups_tiny0_observables.csv
    static_geometry.csv
    static_energy_terms.csv
    pair_diagnostics.csv
    bond_diagnostics.csv
    angle_diagnostics.csv
  plots/
    energy_timeseries_side_by_side.png
    temperature_timeseries_side_by_side.png
    pressure_timeseries_side_by_side.png
    energy_drift_side_by_side.png
    bond_lengths_side_by_side.png
    angle_distribution_side_by_side.png
    pair_distance_classes_side_by_side.png
    static_energy_breakdown_side_by_side.png
    missing_physics_matrix_side_by_side.png
```

The exact output directory and file names may change during implementation, but
the harness should keep this separation:

- machine-readable normalized data under `data/`;
- human-readable figures under `plots/`;
- summary, interpretation, pass/fail statuses, and links in `REPORT.md`.

The diagnostics scripts should not require all outputs to be placed in one
central directory. They should treat result folders as first-class inputs and
write diagnostics inside those folders unless the user explicitly passes a
custom output path.

The first concrete result folders for developing and testing this tooling are:

```text
results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal
```

The `examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0` folder
remains the only runnable kUPS example for this step. If the diagnostics command
has a `--run-dirty-baseline` option, that option should run the existing
`methane_lj_only_nve.yaml` and then analyze the resulting HDF5 file.

## Reusable Diagnostics Model

The tiny methane case should be implemented through a generic diagnostics data
model. The core code should understand these concepts, not methane-specific
file names:

- `MdResult`: a result folder, engine label, run metadata, and discovered files.
- `ThermoSeries`: step/time series for temperature, potential energy, kinetic
  energy, total energy, pressure, volume, and any available engine-specific
  columns.
- `StructureFrame`: atom IDs, atom types, molecule IDs when available, charges
  when available, positions, and box/cell.
- `Topology`: optional bonds, angles, dihedrals, impropers, and graph-distance
  pair classes.
- `ForceFieldMetadata`: optional masses, charges, LJ coefficients, bonded
  coefficients, special-pair factors, cutoffs, and long-range settings.
- `DiagnosticsReport`: normalized tables, plots, statuses, and textual
  interpretation.

Tiny-specific behavior should enter through fixtures and optional metadata:

- source defaults point at the tiny OPLS-AA paths;
- acceptance tests assert methane counts and graph classes;
- report interpretation can mention why the dirty tiny baseline is unphysical;
- generic scripts still accept other result folders with different atom counts,
  timesteps, molecule types, and available columns.

## Normalized Units

LAMMPS uses `real` units. The comparison harness should normalize values before
reporting:

| Quantity | LAMMPS source unit | Normalized report unit |
| --- | --- | --- |
| distance | Angstrom | Angstrom |
| time | fs | fs |
| energy | kcal/mol | eV |
| temperature | K | K |
| pressure | atm | atm, plus optional eV/A^3 |
| charge | elementary charge | elementary charge |
| force | kcal/mol/A | eV/A |
| mass | g/mol | amu-equivalent |

Tests must check at least the kcal/mol to eV conversion against a known value
from `log.tiny`. The LAMMPS initial minimization potential energy is:

```text
0.169805994760444 kcal/mol
```

and the final minimization potential energy is:

```text
0.168446472786458 kcal/mol
```

These values should appear in normalized data and in `REPORT.md`.

## Data Sources

The diagnostics should discover and consume common MD result files by role:

- LAMMPS thermo logs;
- LAMMPS data files or other structure/topology files when available;
- kUPS HDF5 trajectory/result files;
- kUPS run config files when available;
- optional resolved metadata files with force-field and topology information.

When a required role cannot be discovered automatically, the CLI should accept
an explicit path. When a role is absent, the corresponding diagnostics should be
marked `not_available` instead of failing unrelated diagnostics.

### Tiny LAMMPS Reference Fixture

For development and tests, read the prepared LAMMPS result folder:

```text
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/log.tiny
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/log.tiny.benchmark10
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/log.tiny_long_1M
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/log.tiny_18M
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/system.data
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/tiny_oplsaa_methane_final.data
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/tiny_oplsaa_methane_long_final.data
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/tiny_oplsaa_methane_18M_final.data
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/system.in.init
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/system.in.settings
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/system.in.charges
```

The original source deck remains:

```text
external/lammps_oplss/moltemplate_oplsaa_tiny
```

Tiny LAMMPS observable groups:

- minimization thermo block;
- minimization statistics;
- MD thermo block;
- initial data structure;
- final data structure after 10 NVE steps;
- special-bond factors printed during `read_data`;
- PPPM settings printed during initialization.

### Tiny Dirty kUPS Baseline Fixture

Read:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/README.md
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/methane_lj_only_nve.yaml
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/resolved_oplsaa_tiny.yaml
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/methane_oplsaa_tiny.cif
```

If the dirty kUPS HDF5 output exists, read it. If it does not exist, the report
must still be generated with `not_available` statuses and clear command-line
instructions for producing it from the existing `tiny_0` config. A diagnostics
script may also provide an explicit option to run that existing baseline.

The dirty baseline should be labeled explicitly as:

```text
kups_tiny0_lj_only_dirty_baseline
```

This prevents later readers from mistaking it for a faithful OPLS-AA attempt.

### Tiny Step 1 Import Baseline Fixture

Read:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/resolved.yaml
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/REPORT.md
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/expected.yaml
```

Use this as the format truth for counts, charge override application,
coefficient availability, and topology-derived special-pair counts.

## Report Status Vocabulary

Every comparison row should have one of these statuses:

| Status | Meaning |
| --- | --- |
| `pass` | Value is available and within tolerance. |
| `fail` | Value is available and outside tolerance. |
| `not_implemented` | kUPS cannot compute this physical term yet. |
| `not_available` | The data source was not produced or could not be read. |
| `out_of_scope` | The quantity is intentionally excluded from this step. |
| `diagnostic_only` | No pass/fail tolerance is assigned yet. |
| `expected_mismatch` | The mismatch is expected from known missing physics. |

The dirty `tiny_0` run should mostly produce `expected_mismatch` and
`not_implemented` rows. That is correct for Step 2.

## Physical Diagnostics

### 1. Static Energy Diagnostics

The report should separate energy into available physical terms:

| Term | LAMMPS reference | Dirty kUPS baseline | Expected Step 2 status |
| --- | --- | --- | --- |
| potential total | from `log.tiny` | from kUPS HDF5 if available | `expected_mismatch` |
| kinetic | from thermo, derived if needed | from kUPS HDF5 if available | `diagnostic_only` |
| total energy | from thermo | from kUPS HDF5 if available | `expected_mismatch` |
| harmonic bond | not decomposed in current LAMMPS log | not implemented in dirty kUPS | `not_implemented` |
| harmonic angle | not decomposed in current LAMMPS log | not implemented in dirty kUPS | `not_implemented` |
| LJ nonbonded | not decomposed in current LAMMPS log | dirty kUPS LJ-only | `expected_mismatch` |
| Coulomb/PPPM | not decomposed in current LAMMPS log | not implemented in dirty kUPS | `not_implemented` |
| special-pair correction | implied by topology and LAMMPS settings | missing in dirty kUPS | `not_implemented` |

Required static plots:

- `static_energy_breakdown.png`: stacked or grouped bar chart with available
  terms and missing-term annotations.
- `missing_physics_matrix.png`: matrix showing which force-field semantics are
  present in LAMMPS, Step 1 resolved data, dirty kUPS, and future kUPS stages.

TDD tests:

- Given `log.tiny`, parser extracts minimization initial and final potential
  energy.
- Given a missing kUPS HDF5 file, report generation still succeeds.
- Missing physical terms are not converted to numeric zero.
- Total-energy comparison row for dirty kUPS is marked `expected_mismatch` or
  `not_available`, not `pass`.

### 2. Structural Observables

For methane, structural diagnostics are more informative than global RDF alone
because the system is a single molecule in a large periodic box. The harness
should therefore report both local internal geometry and pair-distance classes.

Required structural quantities:

- C-H bond lengths for all four bonds;
- H-C-H angles for all six angles;
- pair distances grouped by topology class:
  - 1-2 bonded C-H pairs;
  - 1-3 H-H pairs through the central carbon;
  - 1-4 pairs, expected count zero for methane;
  - non-special intermolecular pairs, expected count zero for single methane;
- center of mass;
- radius of gyration for the molecule;
- minimum image sanity checks in the 30 A periodic box;
- optional all-atom RDF only as `diagnostic_only`, because one molecule is too
  sparse for a meaningful bulk RDF.

Required structural plots:

- `bond_lengths.png`: C-H bond length bars with the imported equilibrium
  `r0 = 1.09 A` as a reference line.
- `angle_distribution.png`: H-C-H angle bars or histogram with
  `theta0 = 107.8 deg` as a reference line.
- `pair_distance_classes.png`: grouped pair distances by topology class.

TDD tests:

- Static geometry computed from the initial LAMMPS data has 4 C-H bond lengths,
  6 H-C-H angles, 4 one-two pairs, 6 one-three pairs, and 0 one-four pairs.
- The report includes the fact that methane has no 1-4 special pairs, so
  `special_bonds 0.0 0.0 0.5` cannot be fully validated by methane alone.
- The dirty kUPS baseline is flagged as structurally comparable only if the
  loaded coordinates preserve atom identities and molecule membership.

Physical interpretation required in `REPORT.md`:

- Bond-length deviations primarily exercise bond parameter import and harmonic
  bond wiring in later steps.
- Angle deviations primarily exercise angle parameter import and degree/radian
  convention handling.
- Pair-distance class diagnostics reveal whether later LJ and Coulomb
  exclusions are applied to the correct graph-distance pairs.
- Center of mass and radius of gyration give a quick global check that the
  molecule is not drifting, wrapping incorrectly, or changing internal geometry
  unexpectedly.

### 3. Dynamics Observables

LAMMPS performs minimization, then creates velocities at 50 K with
`mom yes rot yes`, then runs 10 NVE steps at 0.25 fs. The dirty kUPS baseline
does not reproduce this initialization exactly. Step 2 should compare dynamics
as diagnostics, not as trajectory-level pass/fail.

Required time-series quantities:

- step;
- time in fs;
- temperature;
- potential energy;
- kinetic energy if available or derivable;
- total energy;
- total-energy drift relative to the first MD frame;
- pressure;
- optional center-of-mass position and velocity;
- optional molecule radius of gyration over time;
- optional maximum bond-length deviation over time if trajectory data exists.

Required dynamics plots:

- `energy_timeseries.png`: potential and total energy vs time.
- `temperature_timeseries.png`: temperature vs time.
- `pressure_timeseries.png`: pressure vs time.
- `energy_drift.png`: total-energy drift vs time.

TDD tests:

- Parser identifies the LAMMPS MD block beginning at step 2 after minimization
  and ending at step 12 after 10 NVE steps.
- The report distinguishes minimization thermo rows from MD thermo rows.
- Energy drift is computed from MD rows only, not from minimization rows.
- Dirty kUPS trajectory comparison is marked `diagnostic_only` or
  `expected_mismatch` until minimization and velocity initialization are in
  scope.

Physical interpretation required in `REPORT.md`:

- Potential-energy trends indicate whether force-field terms are too stiff,
  missing, or applied to wrong pairs.
- Temperature trends are sensitive to initialization, constraints on total
  momentum/rotation, and energy transfer between kinetic and potential modes.
- Total-energy drift is an integration and force-consistency diagnostic, but it
  should not be interpreted before the static force field is correct.
- Pressure is expected to be noisy and physically weak for one methane molecule
  in a 30 A box, but it is still useful for catching severe virial or unit
  mistakes.

### 4. Pair-Level and Local Energy Diagnostics

Step 2 should define pair-level diagnostics even if kUPS cannot compute all
local terms yet. This is the bridge from report plotting to engine development.

Required local tables:

- `bond_diagnostics.csv`:
  - bond ID;
  - atom IDs;
  - atom types;
  - length;
  - equilibrium length;
  - deviation;
  - coefficient;
  - energy if available.
- `angle_diagnostics.csv`:
  - angle ID;
  - atom IDs;
  - angle in degrees;
  - equilibrium angle;
  - deviation;
  - coefficient;
  - energy if available.
- `pair_diagnostics.csv`:
  - atom IDs;
  - atom types;
  - topology class: `1-2`, `1-3`, `1-4`, `normal`;
  - distance;
  - LJ scale factor from LAMMPS special bonds;
  - Coulomb scale factor from LAMMPS special bonds;
  - LJ epsilon/sigma after mixing or explicit override if available;
  - charge product;
  - status for each possible term.

TDD tests:

- Pair diagnostics contain exactly 10 unique atom pairs for methane.
- The 4 C-H pairs are classified as `1-2`.
- The 6 H-H pairs are classified as `1-3`.
- No pair is classified as `normal` for the one-molecule methane system.
- LJ and Coulomb special scales are represented independently.

Physical interpretation required in `REPORT.md`:

- Wrong local classifications will corrupt both LJ and Coulomb even if global
  energy looks close by accident.
- Missing 1-2 and 1-3 exclusions explain why the dirty LJ-only baseline can
  produce unphysical intramolecular nonbonded energy.
- Methane cannot test 1-4 scaling; the report should recommend a later
  butane-like synthetic fixture for that.

## Diagnostics CLI Contract

The main user-facing output of Step 2 should be a script command that builds the
diagnostic report and plots. The script should be result-folder-oriented:

- point it at a kUPS result folder to write `<kups-result-dir>/diagnostics/`;
- point it at a LAMMPS result folder to write `<lammps-result-dir>/diagnostics/`;
- point it at both folders to write comparison diagnostics into a selected
  diagnostics location.

It should expose paths explicitly, but its defaults should point at the current
tiny methane fixtures.

Suggested kUPS-only command:

```bash
python scripts/polymerization/lammps_to_kusp/compare_md_results.py \
  --mode kups \
  --dirty-kups-root examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0 \
  --kups-result-dir results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0
```

This should write:

```text
results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0/diagnostics/
```

Suggested LAMMPS-only command:

```bash
python scripts/polymerization/lammps_to_kusp/compare_md_results.py \
  --mode lammps \
  --lammps-result-dir results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal
```

This should write:

```text
results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal/diagnostics/
```

Suggested comparison command:

```bash
python scripts/polymerization/lammps_to_kusp/compare_md_results.py \
  --mode compare \
  --lammps-result-dir results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal \
  --dirty-kups-root examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0 \
  --kups-result-dir results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0 \
  --import-step1-root examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1 \
  --comparison-out results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0/diagnostics/comparison
```

The `--comparison-out` argument should be optional. If it is omitted, the tool
should choose a deterministic default such as:

```text
<kups-result-dir>/diagnostics/comparison/
```

if a kUPS result directory is present, otherwise:

```text
<lammps-result-dir>/diagnostics/comparison/
```

Comparison mode should build each paired figure from the same normalized
diagnostic tables used by the individual LAMMPS-only and kUPS-only reports. For
example, the energy time-series comparison should place the LAMMPS energy plot
in column 1 and the kUPS energy plot in column 2. It should not use a different
analysis path for comparison.

Optional dirty-baseline run command:

```bash
python scripts/polymerization/lammps_to_kusp/compare_md_results.py \
  --mode kups \
  --run-dirty-baseline \
  --dirty-kups-root examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0 \
  --kups-result-dir results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0
```

The optional `--run-dirty-baseline` mode should run the existing config:

```text
examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0/methane_lj_only_nve.yaml
```

It must not synthesize a new kUPS configuration. If running kUPS is unavailable
in the local environment, the diagnostics should still produce LAMMPS-only and
static import diagnostics with the dirty kUPS trajectory marked
`not_available`.

The tiny fixture command should make these inputs explicit in the generated
`REPORT.md`:

| Input | Default |
| --- | --- |
| LAMMPS result directory | `results/lammps_to_kusp/lammps_tiny_moltemplate_source_minimal` |
| Dirty kUPS root | `examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_0` |
| Dirty kUPS config | `methane_lj_only_nve.yaml` |
| kUPS result directory | `results/lammps_to_kusp/kUPS_moltemplate_oplss_tiny_0` |
| Dirty kUPS HDF5 | `<kups-result-dir>/methane_lj_only_nve.h5` |
| Step 1 import root | `examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1` |
| kUPS diagnostics output | `<kups-result-dir>/diagnostics` |
| LAMMPS diagnostics output | `<lammps-result-dir>/diagnostics` |
| Comparison diagnostics output | `<selected-result-dir>/diagnostics/comparison` or explicit `--comparison-out` |

The command should use fixed report units:

| Quantity | Unit |
| --- | --- |
| energy | eV |
| distance | Angstrom |
| time | fs |
| pressure | atm, with optional eV/A^3 |
| temperature | K |

The command should always try to produce:

- static energy diagnostics;
- structural diagnostics;
- dynamics diagnostics when trajectory data exists;
- pair, bond, and angle diagnostics;
- plot files;
- a single `REPORT.md`.

For other similar MD runs, the same command should degrade gracefully according
to available inputs:

- if only thermo data exists, generate time-series energy, temperature,
  pressure, and drift diagnostics;
- if topology/structure files exist, also generate local geometry and
  pair-class diagnostics;
- if term-resolved energies exist, include static and time-series energy
  decomposition;
- if a quantity is unavailable, mark it `not_available` instead of failing the
  whole report.

## `REPORT.md` Contract

The report should have stable sections:

1. Summary
2. Source Files
3. Capability Matrix
4. Static Energy
5. Structural Observables
6. Dynamics
7. Local Pair/Bond/Angle Diagnostics
8. Plots
9. Known Missing Physics
10. Next Implementation Targets

Required summary language:

- State that LAMMPS is the current reference.
- State that `moltemplate_oplsaa_tiny_0` is a dirty LJ-only kUPS baseline.
- State that Step 2 does not claim reproduction.
- State whether all data files and plots were generated.

Required capability matrix rows:

| Capability | LAMMPS | Step 1 import | Dirty kUPS tiny_0 | Step 2 harness |
| --- | --- | --- | --- | --- |
| atom_style full topology | yes | yes | partial | reads |
| harmonic bonds | yes | parameters only | no | reports missing |
| harmonic angles | yes | parameters only | no | reports missing |
| LJ pair coeffs | yes | parameters only | partial | reports |
| geometric mixing | yes | recorded | no | reports missing |
| special_bonds LJ | yes | recorded | no | reports missing |
| charges | yes | yes | no active Coulomb | reports |
| PPPM Coulomb | yes | settings only | no | reports missing |
| minimization | yes | protocol only | no | out of scope |
| exact velocity create | yes | protocol only | no | out of scope |
| NVE smoke test | yes | protocol only | dirty approximation | diagnostic |

## Plotting Requirements

Implementation should use a non-interactive plotting backend so reports can be
generated in CI or headless development environments.

Plot files should be deterministic:

- fixed figure size;
- fixed labels and units;
- no timestamps inside images;
- missing data represented by annotations or omitted series with a clear legend;
- no dependency on interactive display.

Comparison plot files should be deterministic paired views:

- two columns exactly: LAMMPS on the left, kUPS on the right;
- same diagnostic quantity in both columns;
- same units in both columns;
- shared y-axis limits for direct visual comparison when the quantity is
  comparable;
- shared x-axis units, with independent x ranges only when run lengths differ;
- each column title should name the engine and result folder label;
- missing data in one engine should render an annotated empty panel, not remove
  the column.

TDD tests should not compare entire PNG binary contents. Instead they should
assert:

- expected plot files are created;
- files are non-empty;
- plotting functions accept missing optional data;
- source data tables used for plots match expected numeric values.
- comparison plotting receives the same normalized LAMMPS and kUPS tables used
  for the individual reports.

## Implementation Boundary

Comparison and plotting code should live outside engine code. The exact module
names may change to fit the repository, but this step should remain
reference/report tooling. It should not silently patch kUPS inputs or engine
behavior.

The scripts should be reusable by later OPLS-AA steps: later work should be able
to point the same diagnostics command at a newer kUPS output and receive the
same tables, plots, and report sections with additional implemented terms.

Avoid hard-coded assumptions in reusable modules:

- do not assume exactly 5 atoms;
- do not assume methane-specific atom names;
- do not assume one molecule;
- do not assume the only log file is named `log.tiny`;
- do not assume all LAMMPS runs have both minimization and MD blocks;
- do not assume all kUPS outputs use the dirty LJ-only config.

Those assumptions are allowed only in tiny-fixture tests and tiny-specific
default arguments.

## Acceptance Tests

### Parser Tests

- Parse a LAMMPS thermo log from an arbitrary file path, not only `log.tiny`.
- Extract both thermo tables from the tiny `log.tiny` fixture.
- Classify the first tiny thermo table as minimization.
- Classify the second tiny thermo table as MD.
- Extract tiny minimization initial, next-to-last, and final energies.
- Extract the tiny 10-step NVE trajectory rows from steps 2 through 12.
- Parse a thermo-only fixture that has no minimization block.
- Preserve source LAMMPS units and expose normalized units.

### Geometry Tests

- Read initial methane coordinates.
- Compute four C-H distances.
- Compute six H-C-H angles.
- Compute one center of mass.
- Compute one molecular radius of gyration.
- Confirm 30 A cubic periodic box.

### Topology Class Tests

- Build graph-distance pair classes from the imported bonds.
- Confirm 4 one-two pairs.
- Confirm 6 one-three pairs.
- Confirm 0 one-four pairs.
- Confirm 0 normal intramolecular pairs for methane.
- Store independent LJ and Coulomb special scales.

### Dirty Baseline Tests

- Read `methane_lj_only_nve.yaml`.
- Confirm it uses `mixing_rule: lorentz_berthelot`.
- Confirm it has no active bond, angle, Coulomb, PPPM, or special-bond
  semantics.
- Report those absences as known missing physics.

### CLI and Output-Location Tests

- Given `--mode kups --kups-result-dir <dir>`, write diagnostics to
  `<dir>/diagnostics/`.
- Given `--mode lammps --lammps-result-dir <dir>`, write diagnostics to
  `<dir>/diagnostics/`.
- Given `--mode compare` with both result directories and no explicit
  `--comparison-out`, write comparison diagnostics to a deterministic default
  under one result directory, preferably `<kups-result-dir>/diagnostics/comparison/`.
- Given `--mode compare --comparison-out <dir>`, write comparison diagnostics
  exactly to `<dir>`.
- In comparison mode, generate paired plot files where column 1 is LAMMPS and
  column 2 is kUPS.
- In comparison mode, reuse the LAMMPS-only and kUPS-only normalized diagnostic
  tables rather than recomputing a different comparison-specific analysis.
- Do not require copying kUPS outputs into the LAMMPS folder or LAMMPS outputs
  into the kUPS folder.
- Do not create a new kUPS run config when `--run-dirty-baseline` is used.

### Report Tests

- Generate `REPORT.md` without requiring kUPS HDF5 output.
- Generate `REPORT.md` with dirty kUPS HDF5 output if present.
- Generate kUPS-only, LAMMPS-only, and comparison reports from the same scripts.
- Generate a report from a generic MD thermo fixture with no methane topology.
- Include links or relative paths to every generated plot.
- Include a table row for each expected physical term, even if missing.
- Do not mark full reproduction as pass in Step 2.

### Plot Tests

- Generate all required plot files from fixture data.
- Generate plots when optional kUPS trajectory data is missing.
- Ensure static geometry plots include reference values from imported force
  field parameters.
- Ensure time-series plots do not mix minimization rows with MD rows.
- Ensure comparison plots keep a two-column layout even when one side lacks a
  diagnostic quantity.

## Expected Step 2 Outcome

At the end of this step, the report should make these points obvious:

- The LAMMPS methane reference is parsed and normalized.
- The dirty kUPS `tiny_0` baseline is measurable, but not physically faithful.
- The largest known gaps are bonded terms, electrostatics, special-pair
  semantics, geometric LJ mixing, minimization, and exact velocity
  initialization.
- Methane is excellent for checking 1-2 and 1-3 exclusions, but insufficient for
  validating 1-4 scaling.
- Future engine steps can be judged by changes in concrete plots and tables,
  not only by a final total-energy number.

## How This Feeds Later Steps

Step 3 should add harmonic bond and angle energy values into the same
`static_energy_terms.csv` and `REPORT.md` sections.

Step 4 and Step 5 should update pair diagnostics with geometric mixing and
explicit pair coefficient provenance.

Step 6 and Step 7 should change pair diagnostics and LJ energy reports by
applying special-pair topology classes and LJ scaling.

Step 8 and Step 9 should add Coulomb/Ewald energy diagnostics and independent
Coulomb special scaling.

Step 10 should use the existing static energy and dynamics report format to
write the Ewald-versus-PPPM decision.

Step 12 should use the same plots and tables for the first full all-atom NVE
smoke test.

The main rule is that later steps add columns, rows, and plots to this harness.
They should not invent a new reporting path unless Step 2 proves inadequate.
