# Tiny Moltemplate OPLS-AA Methane to kUPS

This folder contains only the files needed to run a best-effort kUPS
translation of:

```text
external/lammps_oplss/moltemplate_oplsaa_tiny
```

The source is a Moltemplate-generated LAMMPS `real`-units methane system using
OPLS-AA 2024 parameters. The LAMMPS run does:

1. read `system.in.init`
2. read `system.data`
3. include `system.in.settings`
4. include `system.in.charges`
5. minimize
6. create 50 K velocities
7. run 10 NVE steps at 0.25 fs

Current kUPS can run the approximation in `methane_lj_only_nve.yaml` through the
existing LJ MD application:

```bash
JAX_PLATFORMS=cpu conda run -n kups-env kups_md_lj examples/polyremization/lammps_to_kusp/methane_lj_only_nve.yaml
```

That approximation is not an OPLS-AA reproduction. It keeps the methane geometry
and same-type LJ epsilon/sigma values, but it omits bonded terms, Coulomb/PPPM,
LAMMPS `special_bonds` scaling, geometric LJ mixing, minimization, and exact
LAMMPS velocity initialization.

The smoke test is expected to produce unphysical energies/temperatures because
the generic LJ application applies nonbonded LJ to bonded intramolecular pairs
that the LAMMPS OPLS-AA setup excludes or scales.

Use `resolved_oplsaa_tiny.yaml` as the closer target representation for a future
kUPS all-atom/LAMMPS-data importer.

Run outputs and analysis notes live outside `examples`, under:

```text
results/lammps_to_kusp/tiny_oplsaa_methane_lj_only_nve
```
