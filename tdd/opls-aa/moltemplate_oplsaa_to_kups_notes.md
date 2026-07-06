# Moltemplate OPLS-AA to kUPS Notes

This note explains where Moltemplate stores OPLS-AA force-field information, what
LAMMPS files Moltemplate generates, and which generated files should be translated
first for a fixed-topology kUPS prototype.

The main practical conclusion is:

Do not start by parsing Moltemplate `.lt` force-field databases. For kUPS, start
by parsing one concrete Moltemplate-generated LAMMPS system: `system.data`,
`system.in.settings`, `system.in.init`, and `system.in.charges` when present.
Those files contain the resolved numeric type IDs, topology, coordinates,
parameters, and LAMMPS style choices for a specific simulation.

## Repository Scope

The relevant checkout paths inspected here are under:

- `moltemplate/moltemplate/force_fields`
- `moltemplate/examples/all_atom/force_field_OPLSAA`
- `moltemplate/examples/all_atom/legacy_force_field_examples/force_field_OPLSAA_2008`
- `moltemplate/moltemplate/force_fields/convert_OPLSAA_to_LT`
- `moltemplate/moltemplate/force_fields/oplsaa2024_original_format`

There is also a local generated methane case at `moltemplate_oplsaa_tiny`, which
is useful as a small example of the generated LAMMPS files, but it is not part of
the Moltemplate repository.

## Generic OPLS-AA Files in Moltemplate

The generic force-field database lives in Moltemplate `.lt` files. These are
Moltemplate inputs, not final simulator inputs.

### Main OPLS-AA Databases

- `moltemplate/moltemplate/force_fields/oplsaa2024.lt`
  - Current versioned OPLS-AA database in this checkout.
  - Header says it was generated with `convert_OPLSAA_to_LT/oplsaa2lt.py` from
    the 2024 BOSS-format `.par` and `.sb` files in
    `oplsaa2024_original_format`.
  - Defines the `OPLSAA` Moltemplate object.
  - Contains atom charges, atom masses, Lennard-Jones coefficients, bonded
    coefficients, by-type rules for generating bonds/angles/dihedrals/impropers,
    and LAMMPS style declarations.

- `moltemplate/moltemplate/force_fields/oplsaa.lt`
  - Deprecated unversioned alias-style file.
  - Its content is effectively the 2024 database plus a warning section:
    `WARNING_PLEASE_USE_oplsaa2024.lt_INSTEAD.TXT`.
  - Prefer importing `oplsaa2024.lt` explicitly so atom type numbers are tied to
    a known OPLS-AA version.

- `moltemplate/moltemplate/force_fields/oplsaa2008.lt`
  - Older versioned OPLS-AA database.
  - Header says it was generated from the TINKER `oplsaa.prm` parameter file
    corresponding to "OPLS All-Atom Parameters for Organic Molecules, Ions,
    Peptides & Nucleic Acids, July 2008".
  - Still used by the legacy OPLS-AA examples, including the minimal methane
    example below.
  - Important style difference: it uses `improper_style harmonic` and
    `pair_style lj/cut/coul/long 11.0 11.0`; the 2024 file uses
    `improper_style cvff` and `pair_style lj/charmm/coul/long 9.0 11.0`.

### Related OPLS-AA Helper Files

- `moltemplate/moltemplate/force_fields/loplsaa2024.lt`
  - Adds LOPLS atom types and parameters for long hydrocarbon chains on top of
    `oplsaa2024.lt`.
  - Imports `oplsaa2024.lt`, then augments `OPLSAA` with additional charges,
    masses, LJ parameters, and dihedral coefficients.

- `moltemplate/moltemplate/force_fields/loplsaa.lt`
  - Deprecated unversioned LOPLS helper; points users to `loplsaa2024.lt`.

- `moltemplate/moltemplate/force_fields/loplsaa2008.lt`
  - LOPLS helper for the older `oplsaa2008.lt` database.

- `moltemplate/moltemplate/force_fields/spc_oplsaa2024.lt`
- `moltemplate/moltemplate/force_fields/spce_oplsaa2024.lt`
- `moltemplate/moltemplate/force_fields/tip3p_1983_oplsaa2024.lt`
- `moltemplate/moltemplate/force_fields/tip3p_2004_oplsaa2024.lt`
- `moltemplate/moltemplate/force_fields/tip5p_oplsaa2024.lt`
  - Water model helpers intended for simulations that use OPLS-AA.
  - Some import `oplsaa2024.lt` and reuse OPLS-AA water atom types and bonded
    lookup rules.
  - Some add water-specific `bond_coeff`, `angle_coeff`, `pair_coeff`, groups,
    and `fix shake` commands in `In Settings`.

- `moltemplate/moltemplate/force_fields/spc_oplsaa.lt`
- `moltemplate/moltemplate/force_fields/spce_oplsaa.lt`
- `moltemplate/moltemplate/force_fields/tip3p_1983_oplsaa.lt`
- `moltemplate/moltemplate/force_fields/tip3p_2004_oplsaa.lt`
- `moltemplate/moltemplate/force_fields/tip5p_oplsaa.lt`
  - Deprecated unversioned helpers that point toward the 2024-named files.

- `moltemplate/moltemplate/force_fields/spc_oplsaa2008.lt`
- `moltemplate/moltemplate/force_fields/tip3p_1983_oplsaa2008.lt`
- `moltemplate/moltemplate/force_fields/tip5p_oplsaa2008.lt`
  - Water helpers for the older 2008 OPLS-AA database.

- `moltemplate/moltemplate/force_fields/build_your_own_force_field/oplsaa_simple.lt`
  - A small teaching file, not the production OPLS-AA database.
  - Useful for understanding the file structure because it contains compact
    examples of charges, masses, LJ coefficients, bonded coefficients, by-type
    topology rules, and `In Init` style declarations.

- `moltemplate/moltemplate/force_fields/convert_OPLSAA_to_LT/oplsaa2lt.py`
- `moltemplate/moltemplate/force_fields/convert_OPLSAA_to_LT/oplsaa2lt_classes.py`
- `moltemplate/moltemplate/force_fields/convert_OPLSAA_to_LT/oplsaa2lt_utils.py`
- `moltemplate/moltemplate/force_fields/convert_OPLSAA_to_LT/README.md`
  - Converter used to build OPLS-AA `.lt` files from BOSS `.par` and `.sb`
    inputs.
  - The README says `.par` contains atom definitions, dihedral, and improper
    parameters; `.sb` contains bond and angle parameters.

- `moltemplate/moltemplate/force_fields/oplsaa2024_original_format/Jorgensen_et_al-2024-The_Journal_of_Physical_Chemistry_B.sup-2.par`
- `moltemplate/moltemplate/force_fields/oplsaa2024_original_format/Jorgensen_et_al-2024-The_Journal_of_Physical_Chemistry_B.sup-3.sb`
  - Original BOSS-format inputs distributed with this checkout for the 2024
    conversion.

- `moltemplate/moltemplate/force_fields/oplsaa2008_original_format/README.txt`
- `moltemplate/moltemplate/force_fields/oplsaa2008_original_format/AUTHOR.txt`
  - Provenance notes for the older TINKER-derived conversion. The original
    TINKER parameter file is not distributed there.

- `moltemplate/moltemplate/depreciated/oplsaa_moltemplate.py`
  - Old deprecated conversion script for generating an `oplsaa.lt` file from a
    TINKER-style parameter file. It is not the implementation to use today.

## What Is Stored in the OPLS-AA `.lt` Files?

The main production files are large, but their organization is regular.
For `oplsaa2024.lt` and `oplsaa.lt`, the important section boundaries are:

- `write_once("In Charges")`: starts near line 67.
- `write_once("Data Masses")`: starts near line 1098.
- LJ `pair_coeff` block in `write_once("In Settings")`: starts near line 3100.
- `bond_coeff` block in `write_once("In Settings")`: starts near line 4108.
- `write_once("Data Bonds By Type")`: starts near line 4578.
- `angle_coeff` block in `write_once("In Settings")`: starts near line 5055.
- `write_once("Data Angles By Type")`: starts near line 6488.
- `dihedral_coeff` block in `write_once("In Settings")`: starts near line 7928.
- `write_once("Data Dihedrals By Type")`: starts near line 9126.
- `improper_coeff` block in `write_once("In Settings")`: starts near line 10333.
- `write_once("Data Impropers By Type (...)")`: starts near line 10344.
- `write_once("In Init")`: starts near line 10361.

For `oplsaa2008.lt`, the same information exists, but the line numbers and some
styles differ:

- `write_once("In Charges")`: line 46.
- `write_once("Data Masses")`: line 966.
- LJ `pair_coeff` block: line 2802.
- `bond_coeff` block: line 3718.
- `write_once("Data Bonds By Type")`: line 4104.
- `angle_coeff` block: line 4494.
- `write_once("Data Angles By Type")`: line 5518.
- `dihedral_coeff` block: line 6546.
- `write_once("Data Dihedrals By Type")`: line 7353.
- `improper_coeff` block: line 8164.
- `write_once("Data Impropers By Type (...)")`: line 8210.
- `write_once("In Init")`: line 9030.

### Atom Type Definitions

Atom types appear as Moltemplate `@atom:` symbols throughout the file. In the
2024 file, the user-facing short types look like `@atom:138`, while Moltemplate
also creates longer internal names such as names containing `_b..._a..._d..._i...`.
Those suffixes are equivalence categories for bond, angle, dihedral, and
improper lookup.

The `replace{ ... }` commands connect short atom names to the longer internal
names used by the by-type rules.

### Atom Masses

Atom masses are in:

```lt
write_once("Data Masses") {
  @atom:... mass
}
```

After Moltemplate runs, these become the `Masses` section of `system.data`,
with numeric LAMMPS atom type IDs.

### Partial Charges

OPLS-AA charges are generally assigned by atom type in:

```lt
write_once("In Charges") {
  set type @atom:... charge ...
}
```

After Moltemplate runs, these become `system.in.charges`, for example:

```lammps
set type 1 charge -0.24
set type 2 charge 0.06
```

OPLS-AA examples usually include `system.in.charges` after `read_data`, so these
commands override the charge column that was written in the `Atoms` section of
`system.data`.

### Lennard-Jones Pair Coefficients

LJ parameters are stored as `pair_coeff` commands in `In Settings`, for example:

```lt
write_once("In Settings") {
  pair_coeff @atom:... @atom:... epsilon sigma
}
```

In generated files these become numeric type IDs in `system.in.settings`:

```lammps
pair_coeff 1 1 0.060 3.570
```

The OPLS-AA files also set `pair_modify mix geometric`, so missing unlike-pair
coefficients are generated by LAMMPS using geometric mixing unless explicit
cross coefficients are present.

### Bond Coefficients

Bond parameters are in `bond_coeff` commands in `In Settings`. OPLS-AA uses
`bond_style harmonic` in the inspected files.

LAMMPS harmonic bond coefficients are `K r0`, and LAMMPS uses:

```text
E = K * (r - r0)^2
```

There is no extra `1/2` factor in the LAMMPS coefficient convention.

### Angle Coefficients

Angle parameters are in `angle_coeff` commands in `In Settings`. OPLS-AA uses
`angle_style harmonic`.

LAMMPS harmonic angle coefficients are `K theta0`, where `theta0` is written in
degrees in the input file. LAMMPS uses:

```text
E = K * (theta - theta0)^2
```

Again, there is no extra `1/2` factor in the LAMMPS coefficient convention.

### Dihedral Coefficients

Dihedral parameters are in `dihedral_coeff` commands in `In Settings`.
The inspected OPLS-AA files use:

```lammps
dihedral_style opls
```

LAMMPS `dihedral_style opls` uses four coefficients, commonly written
`K1 K2 K3 K4`, with the OPLS form:

```text
E = 0.5*K1*(1 + cos(phi))
  + 0.5*K2*(1 - cos(2*phi))
  + 0.5*K3*(1 + cos(3*phi))
  + 0.5*K4*(1 - cos(4*phi))
```

### Improper Coefficients

Improper parameters are in `improper_coeff` commands in `In Settings`.
The style must be read from `system.in.init`, because it differs by database:

- `oplsaa2024.lt` and `oplsaa.lt`: `improper_style cvff`.
- `oplsaa2008.lt`: `improper_style harmonic`.

Do not assume one improper formula for all OPLS-AA generated systems.

### By-Type Topology Rules

The generic `.lt` files contain Moltemplate rules for creating concrete bonded
topology from atom types:

- `Data Bonds By Type`
- `Data Angles By Type`
- `Data Dihedrals By Type`
- `Data Impropers By Type (...)`

These rules are part of Moltemplate's job. kUPS should not reimplement them for
the first milestone. Let Moltemplate generate the final `Bonds`, `Angles`,
`Dihedrals`, and `Impropers` sections in `system.data`, then parse those.

### Special Bonds and 1-4 Scaling

The inspected OPLS-AA init blocks use:

```lammps
special_bonds lj/coul 0.0 0.0 0.5
```

This means:

- 1-2 bonded pairs: LJ and Coulomb scaled by 0.
- 1-3 pairs connected through an angle: LJ and Coulomb scaled by 0.
- 1-4 pairs connected through a dihedral: LJ and Coulomb scaled by 0.5.

This scaling is essential for reproducing LAMMPS nonbonded energies.

### LAMMPS Style Declarations

The style declarations are in `write_once("In Init")`.

For `oplsaa2024.lt`:

```lammps
units real
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

For `oplsaa2008.lt`:

```lammps
units real
atom_style full
bond_style harmonic
angle_style harmonic
dihedral_style opls
improper_style harmonic
pair_style lj/cut/coul/long 11.0 11.0
pair_modify mix geometric
special_bonds lj/coul 0.0 0.0 0.5
kspace_style pppm 0.0001
```

## What Moltemplate Generates

The common workflow is:

```bash
cd moltemplate_files
moltemplate.sh system.lt
mv -f system.data system.in* ..
```

Moltemplate maps LT section names to generated files. In
`moltemplate/moltemplate/lttree_styles.py`, `Data ...` sections correspond to
the LAMMPS data file, while `In ...` sections correspond to LAMMPS input-script
fragments whose names begin with `system.in.`.

### `system.data`

This is the LAMMPS data file read by:

```lammps
read_data "system.data"
```

It contains the concrete simulation box, atom records, masses, and topology.
Typical relevant sections are:

- Header counts: number of atoms, bonds, angles, dihedrals, impropers, and type
  counts.
- Box bounds: `xlo xhi`, `ylo yhi`, `zlo zhi`; possibly triclinic tilt factors
  in other systems.
- `Masses`
- `Atoms`
- `Velocities`, if present.
- `Bonds`
- `Angles`
- `Dihedrals`
- `Impropers`

For `atom_style full`, the `Atoms` lines have:

```text
atom-id molecule-id atom-type charge x y z
```

For OPLS-AA, the charge values in `Atoms` may be placeholders if
`system.in.charges` is later included.

### `system.in.init`

This file is read before `read_data`. It declares LAMMPS units, atom style, and
force-field styles:

- `units`
- `atom_style`
- `pair_style`
- `pair_modify`
- `bond_style`
- `angle_style`
- `dihedral_style`
- `improper_style`
- `special_bonds`
- `kspace_style`

For kUPS, this file defines the semantics of the coefficients in the other
files. Do not interpret `bond_coeff`, `angle_coeff`, `dihedral_coeff`, or
`improper_coeff` without first reading the corresponding styles.

### `system.in.settings`

This file is read after `read_data`. It contains concrete force-field settings
for the numeric LAMMPS type IDs in `system.data`:

- `pair_coeff`
- `bond_coeff`
- `angle_coeff`
- `dihedral_coeff`
- `improper_coeff`

It can also contain other LAMMPS commands emitted by helper `.lt` files, such as
`group` and `fix shake` for water models.

### `system.in.charges`

This file exists when an `In Charges` section was emitted. OPLS-AA uses it for
atom-type charge assignment:

```lammps
set type N charge q
```

LAMMPS input scripts in the OPLS-AA examples include it after `read_data`, so it
overrides charges in `system.data`. A kUPS importer should apply the same order:
read `system.data`, then apply type charges from `system.in.charges` if the
LAMMPS run script includes that file.

### `system.in`

Some Moltemplate systems can generate a `system.in` file, usually from an
`In Run` or literal output section. The OPLS-AA examples inspected here normally
do not rely on a generated single `system.in`; instead they provide separate
run scripts such as:

- `run.in.min`
- `run.in.npt`
- `run.in.nvt`

Those scripts include `system.in.init`, call `read_data`, then include
`system.in.settings` and often `system.in.charges`.

### Other Generated or Optional Files

- `output_ttree/`
  - Temporary/debug output from Moltemplate.
  - Useful for debugging generation, not needed by kUPS.

- `ttree_assignments.txt`
  - Internal mapping/debug file used by Moltemplate tooling.
  - Not needed for a first kUPS importer.

- `log.cite*`
  - Citation/provenance output.
  - Not needed for energy evaluation.

- `warning_duplicate_angles.txt`, `warning_duplicate_dihedrals.txt`, etc.
  - Can appear when using duplicate-reporting modes.
  - Useful for improving Moltemplate input quality, but not part of a final
    generated topology parser.

- Additional `system.in.*` files
  - Moltemplate can emit arbitrary extra files. For example, other examples use
    `system.in.sw` for a Stillinger-Weber parameter file.
  - For OPLS-AA fixed-topology support, start with init, settings, charges, and
    data.

## Files to Translate into kUPS First

The first implementation should parse the concrete generated LAMMPS files, not
the generic `.lt` OPLS-AA database. Moltemplate already resolved atom types,
bonded topology, and coefficient type IDs for one system.

### `system.data`

Parse:

- box bounds
- `Masses`
- `Atoms`
- `Bonds`
- `Angles`
- `Dihedrals`
- `Impropers`

This gives kUPS the fixed molecular graph, coordinates, atom type IDs, molecule
IDs, masses, and initial charges before any `system.in.charges` override.

### `system.in.settings`

Parse:

- `pair_coeff`
- `bond_coeff`
- `angle_coeff`
- `dihedral_coeff`
- `improper_coeff`

These are concrete numeric LAMMPS type coefficients. The importer should map
each bond, angle, dihedral, and improper in `system.data` to the coefficient for
its type ID.

### `system.in.init`

Parse:

- `units`
- `atom_style`
- `pair_style`
- `pair_modify`
- `bond_style`
- `angle_style`
- `dihedral_style`
- `improper_style`
- `special_bonds`
- `kspace_style`

These commands define the meaning of the coefficients. For OPLS-AA, pay special
attention to `units real`, `dihedral_style opls`, `special_bonds lj/coul 0.0 0.0
0.5`, and whether the pair style is `lj/charmm/coul/long` or
`lj/cut/coul/long`.

### `system.in.charges`

If present and included by the LAMMPS run script, apply it after parsing
`system.data`:

- `set type <type-id> charge <charge>`

For OPLS-AA examples this is usually required, because charges in the molecule
definitions are often placeholders.

## Minimal OPLS-AA Example

The smallest OPLS-AA example found in the Moltemplate repository is:

```text
moltemplate/examples/all_atom/legacy_force_field_examples/force_field_OPLSAA_2008/methane
```

It uses:

- `moltemplate_files/system.lt`
- `moltemplate_files/methane.lt`
- `run.in.npt`
- `run.in.nvt`

The methane molecule imports the older database:

```lt
import "oplsaa2008.lt"
Methane inherits OPLSAA {
  ...
}
```

To generate the LAMMPS files:

```bash
cd moltemplate/examples/all_atom/legacy_force_field_examples/force_field_OPLSAA_2008/methane/moltemplate_files
moltemplate.sh system.lt
mv -f system.data system.in* ..
cd ..
```

To run LAMMPS, use one of the provided run scripts:

```bash
lmp -in run.in.npt
# or, depending on local LAMMPS executable name:
lmp_mpi -i run.in.npt
```

This example does not provide or require a generated `system.in` as the main
entry point. The run scripts are the LAMMPS input files. They include
`system.in.init`, read `system.data`, then include `system.in.settings` and
`system.in.charges`.

A small current-version example is:

```text
moltemplate/examples/all_atom/force_field_OPLSAA/butane
```

It uses `oplsaa2024.lt` and is a better current-version test after methane:

```bash
cd moltemplate/examples/all_atom/force_field_OPLSAA/butane/moltemplate_files
moltemplate.sh system.lt
mv -f system.data system.in* ..
cd ..
lmp -in run.in.npt
```

## Search Commands

Useful repository-wide searches:

```bash
find . -iname "*opls*"
```

Targeted force-field searches:

```bash
grep -R "write_once.*In Settings" -n moltemplate/moltemplate/force_fields
grep -R "pair_coeff" -n moltemplate/moltemplate/force_fields/opls*
grep -R "bond_coeff" -n moltemplate/moltemplate/force_fields/opls*
grep -R "angle_coeff" -n moltemplate/moltemplate/force_fields/opls*
grep -R "dihedral_coeff" -n moltemplate/moltemplate/force_fields/opls*
grep -R "improper_coeff" -n moltemplate/moltemplate/force_fields/opls*
grep -R "special_bonds" -n moltemplate/moltemplate/force_fields/opls*
```

The same searches with `rg` are faster:

```bash
rg -n "write_once.*In Settings" moltemplate/moltemplate/force_fields
rg -n "pair_coeff" moltemplate/moltemplate/force_fields/opls*
rg -n "bond_coeff" moltemplate/moltemplate/force_fields/opls*
rg -n "angle_coeff" moltemplate/moltemplate/force_fields/opls*
rg -n "dihedral_coeff" moltemplate/moltemplate/force_fields/opls*
rg -n "improper_coeff" moltemplate/moltemplate/force_fields/opls*
rg -n "special_bonds|pair_style|bond_style|angle_style|dihedral_style|improper_style|kspace_style" moltemplate/moltemplate/force_fields/opls*
```

Find generated-file references in examples:

```bash
rg -n "system\\.data|system\\.in\\.init|system\\.in\\.settings|system\\.in\\.charges" moltemplate/examples
```

Find OPLS-AA examples:

```bash
find moltemplate/examples/all_atom -path "*OPLSAA*" -type f | sort
```

## Implications for kUPS

To reproduce a Moltemplate/LAMMPS OPLS-AA simulation, kUPS needs:

- A LAMMPS data/settings/init parser.
- A `MolecularTopology` or similar internal structure storing atoms, molecule
  IDs, masses, charges, atom types, bonds, angles, dihedrals, impropers, and
  simulation cell.
- Harmonic bond energy matching LAMMPS `bond_style harmonic`.
- Harmonic angle energy matching LAMMPS `angle_style harmonic`.
- OPLS dihedral energy matching LAMMPS `dihedral_style opls`.
- Improper energy matching the generated `improper_style`, which can be `cvff`
  for `oplsaa2024.lt` or `harmonic` for `oplsaa2008.lt`.
- Lennard-Jones nonbonded energy matching the generated `pair_style` and
  `pair_modify` settings.
- Coulomb energy using charges after applying `system.in.charges`.
- Exclusions and 1-4 scaling from `special_bonds`.
- Periodic boundary conditions from `system.data`.
- Optional later: long-range electrostatics matching `kspace_style pppm` or an
  Ewald/PPPM approximation close enough for the validation target.

Existing kUPS classical potentials cover some building blocks, but OPLS-AA
support should be validated against LAMMPS style-by-style. In particular,
OPLS dihedrals, CVFF impropers, LAMMPS nonbonded switching/cutoff behavior, and
`special_bonds` scaling should be treated as exact compatibility work, not as
generic force-field parsing.

## Recommended First Milestone

1. Parse one Moltemplate-generated OPLS-AA LAMMPS system.
2. Reproduce LAMMPS `run 0` bonded energies in kUPS:
   - `ebond`
   - `eangle`
   - `edihed`
   - `eimp`, if present
3. Only after bonded terms match, add nonbonded LJ/Coulomb.
4. Only after static energies match, try short MD.

The first milestone should ignore the generic `.lt` database except as
documentation. kUPS should consume the resolved generated files.

## Validation Against LAMMPS

Make a small validation LAMMPS input that uses the generated files and performs
`run 0`:

```lammps
include "system.in.init"

read_data "system.data"

include "system.in.settings"
include "system.in.charges"

thermo 1
thermo_style custom step pe ebond eangle edihed eimp evdwl ecoul elong etotal
run 0
```

If `system.in.charges` does not exist or the original run script does not
include it, omit that include. For OPLS-AA examples, it is usually present and
important.

Use the same coordinates, box, topology, type IDs, coefficients, styles, and
charges in kUPS. First reproduce the bonded components (`ebond`, `eangle`,
`edihed`, `eimp`) independently. Then add nonbonded validation (`evdwl`,
`ecoul`, and later `elong`). Do not try to reproduce a trajectory until static
energy components agree for the same configuration.

## What Not to Do First

- Do not manually transcribe every OPLS-AA parameter.
- Do not reimplement Moltemplate's atom typing or by-type topology generation.
- Do not start with long-range electrostatics or MD trajectory matching.
- Do not assume `oplsaa2008.lt`, `oplsaa.lt`, and `oplsaa2024.lt` have identical
  atom type numbering or identical LAMMPS styles.
