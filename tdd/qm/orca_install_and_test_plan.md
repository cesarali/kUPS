# ORCA-first QM installation and test plan

## Purpose

This document defines the first QM/DFT setup for the kUPS reactive polymerization project. The immediate goal is not to run full polymer DFT. The immediate goal is to install ORCA, verify that it runs correctly, and produce a small reproducible workflow for isolated epoxy-amine fragment calculations.

The broader QM stack from the research plan is:

- ORCA: primary DFT engine for molecular fragments, optimizations, scans, transition-state searches, and frequency checks.
- RDKit: molecule construction and conformer generation.
- xTB/GFN2-xTB: cheap pre-optimization and scan sanity checks.
- CREST: conformer search using xTB.
- ASE: workflow glue, geometry formats, constrained scans, and later NEB setup.
- Open Babel or Avogadro: molecule inspection and conversion.
- CP2K: later optional tool for periodic or condensed-phase checks, not part of the first small setup.

This first plan starts with ORCA only, then adds the Python and pre-screening tools after ORCA is validated.

## Current ORCA target

Use the current ORCA 6 series from the official FACCTs/ORCA distribution.

Official references:

- ORCA installation manual: <https://www.faccts.de/docs/orca/6.1/manual/contents/quickstartguide/installation.html>
- ORCA forum/download entry point: <https://orcaforum.kofo.mpg.de/>

ORCA requires manual download through the ORCA forum. Do not expect `conda install orca` or `pip install orca` to install the quantum chemistry program.

## Local install status

As of 2026-06-30 on this WSL machine:

- Downloaded archive:

```text
/home/cesarali/Polymerization/ORCA/orca_6_1_0_linux_x86-64_shared_openmpi418.run
```

- Archive type:

```text
Makeself 2.4.0 self-executable archive
```

- Integrity check:

```text
MD5 checksums are OK. All good.
```

- Installed ORCA path reported by the installer:

```text
/home/cesarali/orca_6_1_0
```

- Main executable:

```text
/home/cesarali/orca_6_1_0/orca
```

- Installed size:

```text
20G
```

- Water single-point smoke test:

```text
FINAL SINGLE POINT ENERGY       -76.321072287811
ORCA TERMINATED NORMALLY
```

- Repo-local Phase 3 smoke-test input:

```text
water_sp.inp created in /tmp/kups-qm-orca-smoke
```

- Repo-local Phase 3 smoke-test command:

```bash
cd /home/cesarali/Polymerization/kUPS/results/qm/orca_smoke_tests
/home/cesarali/orca_6_1_0/orca water_sp.inp > water_sp.out
```

- Repo-local Phase 3 result:

```text
FINAL SINGLE POINT ENERGY       -76.321072287811
ORCA TERMINATED NORMALLY
```

- Repo-local Phase 4 optimization input:

```text
water_opt.inp created in /tmp/kups-qm-orca-smoke
```

- Repo-local Phase 4 command:

```bash
cd /home/cesarali/Polymerization/kUPS/results/qm/orca_smoke_tests
/home/cesarali/orca_6_1_0/orca water_opt.inp > water_opt.out
```

- Repo-local Phase 4 result:

```text
THE OPTIMIZATION HAS CONVERGED
FINAL SINGLE POINT ENERGY       -76.321269043415
ORCA TERMINATED NORMALLY
```

- Repo-local Phase 5 frequency input:

```text
water_freq.inp created in /tmp/kups-qm-orca-smoke
```

- Repo-local Phase 5 command:

```bash
cd /home/cesarali/Polymerization/kUPS/results/qm/orca_smoke_tests
/home/cesarali/orca_6_1_0/orca water_freq.inp > water_freq.out
```

- Repo-local Phase 5 result:

```text
FINAL SINGLE POINT ENERGY       -76.321269925003
Total number of imaginary perturbations ...      0
ORCA TERMINATED NORMALLY
```

- Repo-local Phase 6 methylamine optimization input:

```text
methylamine_opt.inp created in /tmp/kups-qm-orca-smoke
```

- Repo-local Phase 6 command:

```bash
cd /home/cesarali/Polymerization/kUPS/results/qm/orca_smoke_tests
/home/cesarali/orca_6_1_0/orca methylamine_opt.inp > methylamine_opt.out
```

- Repo-local Phase 6 result:

```text
THE OPTIMIZATION HAS CONVERGED
FINAL SINGLE POINT ENERGY       -95.723724020751
ORCA TERMINATED NORMALLY
```

The Phase 4, Phase 5, and Phase 6 repo-local inputs are deliberately laptop-safe:

```text
%pal nprocs 1 end
%maxcore 1000
```

- Phase 7 add-on environment file:

```text
docs/polymerization/environment-kups-env-qm-addons.yml
```

- Phase 7 install command for the existing `kups-env`:

```bash
conda env update -f /home/cesarali/Polymerization/kUPS/docs/polymerization/environment-kups-env-qm-addons.yml
```

- Phase 7 verification commands:

```bash
conda activate kups-env
python -c "import rdkit; import ase; print('rdkit+ase ok')"
xtb --version
crest --version
obabel -V
/home/cesarali/orca_6_1_0/orca
```

- Phase 7 installed add-ons in `kups-env`:

```text
rdkit 2025.09.5
pandas 3.0.3
xtb 6.7.1
crest 3.0.2
openbabel 3.1.1
```

- Phase 7 post-install import and tool checks:

```text
kups imports
jax imports
ase imports
pandas imports
rdkit builds a molecule from SMILES
xtb runs
crest runs
obabel runs
ORCA runs from inside kups-env
```

- Phase 7 ORCA-in-`kups-env` water check:

```text
FINAL SINGLE POINT ENERGY       -76.321072293688
ORCA TERMINATED NORMALLY
```

- Repo-local Phase 8 ASE + ORCA input:

```text
scripts/polymerization/qm/run_ase_orca_water.py
```

- Repo-local Phase 8 command:

```bash
cd /home/cesarali/Polymerization/kUPS
ORCA_COMMAND=/home/cesarali/orca_6_1_0/orca conda run -n kups-env python scripts/polymerization/qm/run_ase_orca_water.py
```

- Repo-local Phase 8 result:

```text
BFGS step 0: energy -2076.802160 eV, fmax 0.697554 eV/A
BFGS step 1: energy -2076.806880 eV, fmax 0.174228 eV/A
BFGS step 2: energy -2076.807399 eV, fmax 0.048255 eV/A
ASE_ORCA_WATER_ENERGY_EV -2076.807398684023
ORCA TERMINATED NORMALLY
```

ASE may print a warning that ORCA geometry optimization did not converge. For this Phase 8 test, ASE is doing the geometry optimization and ORCA is only supplying energies and gradients through `EnGrad`, so the relevant convergence check is the ASE BFGS `fmax` value.

- Laptop CPU note:

`kups-env` has CUDA-enabled JAX packages installed, and JAX may print a CUDA plugin warning on a laptop without a working CUDA device. For laptop-safe CPU-only checks, run:

```bash
JAX_PLATFORMS=cpu conda run -n kups-env python -c "import kups, jax; import jax.numpy as jnp; print(jax.default_backend(), jnp.arange(5).sum())"
```

Expected result:

```text
cpu 10
```

The installer was invoked with `--target /home/cesarali/Polymerization/ORCA/orca_6_1_0`, but the ORCA setup script placed the final installation under `/home/cesarali/orca_6_1_0`. Use the reported final path unless ORCA is moved intentionally.

## Install location convention

Use one of these locations:

```text
$HOME/opt/orca
/opt/orca
```

For a normal user install, prefer:

```text
$HOME/opt/orca
```

The expected executable should then be:

```text
$HOME/opt/orca/orca
```

## Phase 1: download ORCA

1. Create or log into an ORCA forum account.
2. Download the Linux x86-64 ORCA 6 package that matches the machine.
3. Copy the downloaded archive to:

```text
$HOME/Downloads
```

4. Extract it into:

```text
$HOME/opt/orca
```

Example shape after extraction:

```text
$HOME/opt/orca/orca
$HOME/opt/orca/orca_plot
$HOME/opt/orca/orca_2mkl
```

The exact extracted folder name may include the ORCA version. If so, either keep the versioned folder and point `PATH` to it, or create a stable symlink named `$HOME/opt/orca`.

## Phase 2: shell environment

Add ORCA to the shell startup file:

```bash
export ORCA_DIR="$HOME/opt/orca"
export PATH="$ORCA_DIR:$PATH"
```

Then reload the shell:

```bash
source ~/.bashrc
```

Verify:

```bash
which orca
orca --version
```

Expected result:

- `which orca` points to `$HOME/opt/orca/orca` or the selected versioned ORCA directory.
- `orca --version` prints an ORCA 6 version.

## Phase 3: minimal ORCA smoke test

Create a temporary working directory outside the source tree:

```bash
mkdir -p /tmp/kups-qm-orca-smoke
cd /tmp/kups-qm-orca-smoke
```

Create `water_sp.inp`:

```text
! B3LYP def2-SVP TightSCF

* xyz 0 1
O   0.000000   0.000000   0.000000
H   0.000000   0.757000   0.586000
H   0.000000  -0.757000   0.586000
*
```

Run:

```bash
orca water_sp.inp > water_sp.out
```

Check:

```bash
grep "ORCA TERMINATED NORMALLY" water_sp.out
grep "FINAL SINGLE POINT ENERGY" water_sp.out
```

Success criteria:

- The output contains `ORCA TERMINATED NORMALLY`.
- The output contains a final single-point energy.
- No missing shared-library errors appear.

## Phase 4: minimal geometry optimization test

Create `water_opt.inp`:

```text
! B3LYP def2-SVP TightSCF Opt

* xyz 0 1
O   0.000000   0.000000   0.000000
H   0.000000   0.757000   0.586000
H   0.000000  -0.757000   0.586000
*
```

Run:

```bash
orca water_opt.inp > water_opt.out
```

Check:

```bash
grep "ORCA TERMINATED NORMALLY" water_opt.out
grep "THE OPTIMIZATION HAS CONVERGED" water_opt.out
ls water_opt.xyz
```

Success criteria:

- ORCA terminates normally.
- The geometry optimization converges.
- ORCA writes an optimized geometry file such as `water_opt.xyz`.

## Phase 5: minimal frequency test

Create `water_freq.inp` from the optimized structure:

```text
! B3LYP def2-SVP TightSCF Freq

* xyzfile 0 1 water_opt.xyz
```

Run:

```bash
orca water_freq.inp > water_freq.out
```

Check:

```bash
grep "ORCA TERMINATED NORMALLY" water_freq.out
grep -i "imaginary" water_freq.out
```

Success criteria:

- ORCA terminates normally.
- The optimized water minimum should not have imaginary frequencies.

## Phase 6: first chemically relevant ORCA test

After the water smoke tests pass, run one small organic molecule optimization before attempting epoxy-amine reactions.

Recommended first molecule:

```text
methylamine
```

Input `methylamine_opt.inp`:

```text
! B3LYP def2-SVP D3BJ TightSCF Opt

* xyz 0 1
C   0.000000   0.000000   0.000000
N   1.450000   0.000000   0.000000
H  -0.360000   1.020000   0.000000
H  -0.360000  -0.510000   0.883000
H  -0.360000  -0.510000  -0.883000
H   1.800000   0.480000   0.820000
H   1.800000   0.480000  -0.820000
*
```

Run:

```bash
orca methylamine_opt.inp > methylamine_opt.out
```

Check:

```bash
grep "ORCA TERMINATED NORMALLY" methylamine_opt.out
grep "THE OPTIMIZATION HAS CONVERGED" methylamine_opt.out
```

Success criteria:

- ORCA can optimize a small organic fragment.
- This confirms the method/basis syntax used for later amine and epoxy fragments.

## Phase 7: add QM helpers to the existing kUPS environment

The working development environment is:

```text
kups-env
```

Do not create a separate QM environment unless dependency conflicts become a real problem. The current `kups-env` already has:

```text
ase
numpy
scipy
matplotlib
```

The missing QM helper packages are:

```text
rdkit
pandas
xtb
crest
openbabel
```

Install or update these packages with:

```bash
conda env update -f /home/cesarali/Polymerization/kUPS/docs/polymerization/environment-kups-env-qm-addons.yml
```

or directly:

```bash
conda install -n kups-env -c conda-forge rdkit pandas xtb crest openbabel
```

Activate:

```bash
conda activate kups-env
```

Verify:

```bash
python -c "import rdkit; import ase; print('rdkit+ase ok')"
xtb --version
crest --version
obabel -V
/home/cesarali/orca_6_1_0/orca
```

For CPU-only laptop checks with JAX:

```bash
JAX_PLATFORMS=cpu conda run -n kups-env python -c "import kups, jax; import jax.numpy as jnp; print('kups+jax cpu ok', jax.default_backend(), jnp.arange(5).sum())"
```

Success criteria:

- RDKit imports.
- ASE imports.
- xTB runs.
- CREST runs.
- Open Babel runs.
- ORCA remains callable from inside `kups-env`.

## Phase 8: ORCA plus ASE smoke test

ASE should call the external ORCA executable. In this local setup, pass an explicit ORCA path through `ORCA_COMMAND` instead of relying on shell `PATH`.

Use the repo-local ASE smoke script:

```text
scripts/polymerization/qm/run_ase_orca_water.py
```

Run:

```bash
ORCA_COMMAND=/home/cesarali/orca_6_1_0/orca conda run -n kups-env python scripts/polymerization/qm/run_ase_orca_water.py
```

Success criteria:

- ASE launches ORCA.
- ORCA terminates normally.
- The script prints a potential energy.

## Phase 9: first epoxy-amine mini target

Only after all previous phases pass, start a tiny fragment workflow:

1. Build one epoxy fragment and one amine fragment with RDKit.
2. Generate several conformers.
3. Pre-optimize each fragment with xTB.
4. Create a reactant complex with the amine nitrogen near the epoxy carbon.
5. Run ORCA optimization at a small level:

```text
! B3LYP def2-SVP D3BJ TightSCF Opt
```

6. Run a constrained scan over the forming N-C distance:

```text
r_NC = 3.0, 2.8, 2.6, ..., 1.5 Angstrom
```

7. Store all inputs and outputs under:

```text
test/polymerization/fixtures/epoxy_amine_orca/
  manifest.csv
  r2_near_attack_svp_engrad/
    r2_near_attack_svp_engrad.inp
    r2_near_attack_svp_engrad.xyz
```

## Troubleshooting notes

### `orca: command not found`

`PATH` does not include the ORCA directory. Check:

```bash
echo "$PATH"
ls "$HOME/opt/orca/orca"
```

### Missing shared libraries

Use the official ORCA Linux package and check the ORCA manual for system requirements. If the binary was copied from another machine, reinstall from the official archive on the target machine.

### ORCA runs outside conda but not inside conda

The conda activation may be changing `PATH`. Re-run:

```bash
export ORCA_DIR="$HOME/opt/orca"
export PATH="$ORCA_DIR:$PATH"
which orca
```

### ASE cannot launch ORCA

First confirm that plain ORCA works:

```bash
orca --version
```

Then confirm Python can see the same shell environment:

```bash
python -c "import shutil; print(shutil.which('orca'))"
```

## Definition of done for ORCA setup

ORCA setup is complete when all of the following are true:

- `orca --version` works from a fresh terminal.
- ORCA is callable inside `kups-env`.
- Water single-point calculation terminates normally.
- Water geometry optimization converges.
- Water frequency calculation terminates normally.
- Methylamine geometry optimization converges.
- ASE can launch ORCA and return an energy.

After that, we can start writing reusable scripts for epoxy-amine fragment generation and scan metadata.
