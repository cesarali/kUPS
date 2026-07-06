# LAMMPS Deck Import Report

## Summary

Status: `pass`

This report validates the resolved LAMMPS/Moltemplate deck as a format handoff.
It checks source completeness, topology references, coefficient availability,
charge override application, unit-conversion presence, and topology-derived
special-pair classes. It does not evaluate kUPS energies or run dynamics.

## Counts

- atoms: 5
- bonds: 4
- angles: 6
- dihedrals: 0
- impropers: 0

## Checker

- total charge e: 0
- one-two pairs: 4
- one-three pairs: 6
- one-four pairs: 0
- missing explicit pair coeffs: 1

## Readiness

| Contract | Status |
| --- | --- |
| format_import | ready_input |
| bonded_terms | ready_input |
| lj_pair_matrix | not_implemented |
| special_pair_scaling | ready_input |
| electrostatics | ready_input |
| dynamics | not_implemented |

## Errors

- None

## Warnings

- None
