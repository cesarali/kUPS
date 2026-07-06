# Step 1: Generic Numeric LAMMPS Import Skeleton

This step builds the format handoff needed before any OPLS-AA energy matching
work can be trusted. Moltemplate has already resolved the force-field database
and molecule definitions into concrete LAMMPS files, so the first kUPS task is
to read those numeric files directly. The importer should preserve the original
LAMMPS IDs, topology, style declarations, coefficient tables, charge overrides,
and unit choices, then write a stable resolved representation for later steps.

The result of this step is a reusable translator plus a checker protocol, not a
dynamics application. The translator creates `resolved.yaml`; the checker proves
that the imported deck is internally consistent and ready for later milestones.
If a later energy comparison fails, this report should make it clear whether the
input handoff was correct or whether the bug is in a later wiring or engine
step.

## Implemented Shape

- Public API: `kups.polymerization.lammps.load_lammps_deck(...)`.
- Directory helper: `kups.polymerization.lammps.load_lammps_deck_directory(...)`.
- CLI: `kups_lammps_import --source <deck-dir> --out <resolved.yaml>`.
- Checker: `kups.polymerization.lammps.check_lammps_deck(...)`.
- First generated example:
  `examples/polyremization/lammps_to_kusp/moltemplate_oplsaa_tiny_1/resolved.yaml`.

The importer supports resolved LAMMPS `atom_style full` data files with
`Masses`, `Atoms`, `Bonds`, `Angles`, `Dihedrals`, and `Impropers` sections. It
also parses Moltemplate/LAMMPS fragments containing `units`, force-field styles,
`pair_style`, `pair_modify`, `special_bonds`, `kspace_style`, coefficient rows,
and `set type ... charge ...` overrides.

## Generic Contract

The translator is considered correct for a compatible resolved deck when it can
represent:

- source file provenance and include order;
- box bounds and periodicity;
- atom IDs, molecule IDs, atom types, charges, and Cartesian coordinates;
- mass and coefficient tables by LAMMPS type ID;
- bond, angle, dihedral, and improper topology with original LAMMPS IDs;
- original LAMMPS `real` units plus converted kUPS-side units;
- pair style, mixing rule, special-bond factors, and kspace settings;
- unsupported or not-yet-used syntax explicitly instead of silently dropping it.

Unsupported syntax should either fail clearly or appear in the `unsupported`
section of the resolved representation. Required syntax that blocks faithful
import should make the checker fail.

## Checker Protocol

The checker runs on every imported deck and validates:

- every topology item references existing atoms;
- every used topology type has a matching coefficient;
- every used atom type has a mass;
- charge overrides are applied after `system.data`;
- total charge is reported;
- unit conversions are present for parsed coefficients;
- 1-2, 1-3, and 1-4 special-pair classes can be generated from bonds;
- missing explicit pair coefficients are marked as future mixing work;
- later-step readiness is reported as `ready_input`, `not_implemented`, or
  `blocked_by_import_error`.

This checker is intentionally generic. The methane fixture has extra known-value
checks, but those checks are not the boundary of the importer.

## Tiny Fixture Acceptance Criteria

For `external/lammps_oplss/moltemplate_oplsaa_tiny`, the importer should produce:

- 5 atoms, 4 bonds, 6 angles, 0 dihedrals, and 0 impropers;
- 2 atom types, 1 bond type, and 1 angle type;
- a periodic box from `-15.0` to `15.0` in x/y/z;
- charges from `system.in.charges`: type 1 `-0.24`, type 2 `0.06`;
- LJ coefficients `pair_coeff 1 1 0.060 3.570` and
  `pair_coeff 2 2 0.030 2.500`;
- bonded coefficients `bond_coeff 1 340. 1.09` and
  `angle_coeff 1 33. 107.8`;
- topology-derived special-pair counts: 4 one-two, 6 one-three, 0 one-four;
- preserved semantics: `units real`, `atom_style full`,
  `pair_modify mix geometric`, `special_bonds lj/coul 0.0 0.0 0.5`, and
  `kspace_style pppm 0.0001`.

## Test Plan

- Unit-test generic section parsing with small synthetic data snippets.
- Unit-test charge override order independently from methane.
- Unit-test kcal/mol to eV conversion.
- Unit-test topology graph classification for 1-2, 1-3, and 1-4 pairs.
- Add fixture coverage for the tiny methane deck.
- Add smoke coverage for `external/lammps_oplss/alkane_chain_single_lammps_ready`
  to prove the importer is not methane-specific.
- Add negative coverage for missing atom references and missing coefficient
  types.

## Current Scope

Step 1 remains format-only. It does not evaluate energies, create forces, run
MD, implement LJ geometric mixing, apply special-pair scaling in an engine, wire
Ewald, or compare LAMMPS trajectories. Those are later steps, and the checker is
the protocol that keeps this import step measurable against them.
