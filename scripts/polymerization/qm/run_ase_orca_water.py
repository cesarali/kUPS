import os
from pathlib import Path

from ase import Atoms
from ase.calculators.orca import ORCA, OrcaProfile
from ase.optimize import BFGS


REPO_ROOT = Path(__file__).resolve().parents[2]
workdir = REPO_ROOT / "results" / "qm" / "orca_smoke_tests" / "ase_orca_water_run"
workdir.mkdir(parents=True, exist_ok=True)

atoms = Atoms(
    "OH2",
    positions=[
        [0.000000, 0.000000, 0.000000],
        [0.000000, 0.757000, 0.586000],
        [0.000000, -0.757000, 0.586000],
    ],
)

atoms.calc = ORCA(
    profile=OrcaProfile(command=os.environ.get("ORCA_COMMAND", "orca")),
    directory=workdir,
    label="ase_water",
    orcasimpleinput="B3LYP def2-SVP TightSCF EnGrad",
    orcablocks="""
%pal
  nprocs 1
end

%maxcore 1000
""",
)

optimizer = BFGS(atoms, logfile=str(workdir / "ase_water_bfgs.log"))
optimizer.run(fmax=0.05, steps=20)

energy = atoms.get_potential_energy()
print(f"ASE_ORCA_WATER_ENERGY_EV {energy:.12f}")
