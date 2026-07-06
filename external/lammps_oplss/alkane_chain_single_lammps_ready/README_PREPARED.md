# Alkane Chain LAMMPS Folder Prepared from Moltemplate

This folder was prepared from:

`moltemplate/examples/all_atom/force_field_OPLSAA/alkane_chain_single`

LAMMPS was not run. Only Moltemplate was run to convert the `.lt` source files
into the files that LAMMPS needs.

## What Moltemplate Generated

These files are produced from `moltemplate_files/system.lt`:

- `system.data`: atom coordinates, box, masses, and molecular topology.
- `system.in.init`: LAMMPS initialization commands such as units, atom style,
  bonded styles, pair style, and kspace style.
- `system.in.settings`: force-field coefficients generated from LOPLSAA/OPLSAA.
- `system.in.charges`: charge assignments generated from the force field.

The source files used by Moltemplate are kept in `moltemplate_files/`:

- `system.lt`: top-level system definition and simulation box.
- `alkane50.lt`: the 50-carbon alkane chain definition.
- `ch2.lt` and `ch3.lt`: monomer/end-cap definitions.

## Files LAMMPS Reads First

For the minimization script:

```bash
lmp_mpi -i run.in.min
```

LAMMPS reads:

- `run.in.min`
- `system.in.init`
- `system.data`
- `system.in.settings`
- `system.in.charges`

`run.in.min` would create `system_after_min.data` if LAMMPS were run.

For the NVT script:

```bash
lmp_mpi -i run.in.nvt
```

LAMMPS reads:

- `run.in.nvt`
- `system.in.init`
- `system_after_min.data`
- `system.in.settings`
- `system.in.charges`

Because `system_after_min.data` is produced by `run.in.min`, run minimization
first if you want to follow the original example workflow.

## How This Folder Was Prepared

From inside this folder:

```bash
cd moltemplate_files
moltemplate.sh system.lt
mv -f system.data system.in* ../
rm -rf output_ttree
rm -f run.in.EXAMPLE
mv -f warning*.txt ../ 2>/dev/null || true
mv -f log.* ../ 2>/dev/null || true
cd ..
```

The same steps are available in `prepare_from_moltemplate.sh`.

Moltemplate printed a warning that `atom_style` was unspecified while parsing
the `.lt` files and assumed `atom_style full`. The generated `system.in.init`
does explicitly contain `atom_style full`, which is what this example uses.

## Optional Cleanup

The generated OPLSAA settings include many unused force-field types. That is
normal for this example and is harmless. To remove unused types later, run:

```bash
cleanup_moltemplate.sh
```

Do that only after checking that the uncleaned files work for your LAMMPS build.
