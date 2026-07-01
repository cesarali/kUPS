# Epoxy-amine smoke-test workspace

This page describes the first reduced epoxy-amine Phase 9A smoke-test files.

The first target is the R2 near-attack geometry:

```text
glycidyl methyl ether + methylamine
```

The first ORCA job should be a laptop-safe single-core `EnGrad` label, not an optimization.

For cluster execution, see:

```text
tdd/qm/epoxy_amine_cluster_workflow.md
scripts/polymerization/qm/prepare_epoxy_amine_orca_smoke.py
scripts/polymerization/qm/run_orca_smoke_job.sh
scripts/polymerization/qm/slurm_orca_smoke_array.sh
scripts/polymerization/qm/parse_orca_smoke_results.py
scripts/Potsdam/orca_epoxy_amine_smoke.job
test/polymerization/fixtures/epoxy_amine_orca/
```
