# Using ORCA 6.1.0 From Other Repositories

ORCA is installed in this project at:

```bash
/work/ojedamarin/Projects/Polymerization/orca_6_1_0_linux_x86-64_shared_openmpi418
```

The main executable is:

```bash
/work/ojedamarin/Projects/Polymerization/orca_6_1_0_linux_x86-64_shared_openmpi418/orca
```

## Recommended Setup

Before running ORCA from any folder or repo, source the setup script from this project:

```bash
source /work/ojedamarin/Projects/Polymerization/setup_orca.sh
```

Then run ORCA normally from your working repo:

```bash
orca my_input.inp > my_output.out
```

This setup script:

- sets `ORCA_DIR`
- adds ORCA to `PATH`
- adds ORCA libraries to `LD_LIBRARY_PATH`
- loads `mpi/OpenMPI/4.1.6-GCC-13.2.0` if the `module` command is available
- defines an `orca` shell function that calls the full ORCA path, which ORCA requires for parallel `PAL` jobs

## Example From Another Repo

```bash
cd /path/to/your/other/repo
source /work/ojedamarin/Projects/Polymerization/setup_orca.sh
orca calculation.inp > calculation.out
```

## Optional: Make It Available In Every New Shell

If you want ORCA available automatically in future terminal sessions, add this line to `~/.bashrc`:

```bash
source /work/ojedamarin/Projects/Polymerization/setup_orca.sh
```

After editing `~/.bashrc`, either open a new terminal or run:

```bash
source ~/.bashrc
```

## Quick Check

Run:

```bash
source /work/ojedamarin/Projects/Polymerization/setup_orca.sh
type orca
```

Expected result: `orca` should be reported as a shell function pointing to the ORCA installation path above.
