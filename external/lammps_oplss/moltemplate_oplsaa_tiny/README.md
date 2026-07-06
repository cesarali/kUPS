# Tiny Moltemplate OPLS-AA Methane Test

This directory contains a 5-atom methane system built with Moltemplate and
OPLS-AA 2024 parameters.

To regenerate the LAMMPS files:

```bash
cd moltemplate_files
moltemplate.sh system.lt
mv -f system.data system.in* ..
rm -rf output_ttree run.in.EXAMPLE
cd ..
cleanup_moltemplate.sh
```

To run the tiny LAMMPS test:

```bash
/home/cesarali/Polymerization/lammps/bin/lmp -log log.tiny -in run.in.tiny
```

The run performs a short minimization followed by 10 NVE steps.
