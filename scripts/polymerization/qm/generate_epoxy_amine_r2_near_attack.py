from pathlib import Path

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem


REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = REPO_ROOT / "test" / "polymerization" / "fixtures"
PRE_ORCA_ROOT = FIXTURE_ROOT / "epoxy_amine_pre_orca"

TARGET_NC_DISTANCE_A = 2.4


def embed_and_optimize(smiles: str, seed: int) -> Chem.Mol:
    mol = Chem.AddHs(Chem.MolFromSmiles(smiles))
    status = AllChem.EmbedMolecule(mol, randomSeed=seed)
    if status != 0:
        raise RuntimeError(f"RDKit embedding failed for {smiles}")
    AllChem.UFFOptimizeMolecule(mol, maxIters=500)
    return mol


def coordinates(mol: Chem.Mol) -> np.ndarray:
    conf = mol.GetConformer()
    return np.array([list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())])


def epoxide_atoms(mol: Chem.Mol) -> tuple[int, int, int]:
    ring_info = mol.GetRingInfo()
    for ring in ring_info.AtomRings():
        if len(ring) != 3:
            continue
        symbols = [mol.GetAtomWithIdx(i).GetSymbol() for i in ring]
        if symbols.count("O") == 1 and symbols.count("C") == 2:
            oxygen = next(i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "O")
            carbons = [i for i in ring if mol.GetAtomWithIdx(i).GetSymbol() == "C"]
            return carbons[0], carbons[1], oxygen
    raise RuntimeError("Could not find a three-membered C-C-O epoxide ring")


def methylamine_nitrogen(mol: Chem.Mol) -> int:
    for atom in mol.GetAtoms():
        if atom.GetSymbol() == "N":
            return atom.GetIdx()
    raise RuntimeError("Could not find methylamine nitrogen")


def unit(vector: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(vector)
    if norm < 1e-12:
        raise ValueError("Cannot normalize a near-zero vector")
    return vector / norm


def write_xyz(path: Path, symbols: list[str], coords: np.ndarray, comment: str) -> None:
    lines = [str(len(symbols)), comment]
    for symbol, xyz in zip(symbols, coords):
        lines.append(f"{symbol:2s} {xyz[0]: .8f} {xyz[1]: .8f} {xyz[2]: .8f}")
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    PRE_ORCA_ROOT.mkdir(parents=True, exist_ok=True)

    epoxy = embed_and_optimize("COCC1CO1", seed=17)
    amine = embed_and_optimize("CN", seed=23)

    epoxy_coords = coordinates(epoxy)
    amine_coords = coordinates(amine)

    attacked_c, other_c, epoxide_o = epoxide_atoms(epoxy)
    nitrogen = methylamine_nitrogen(amine)

    c_pos = epoxy_coords[attacked_c]
    o_pos = epoxy_coords[epoxide_o]
    other_c_pos = epoxy_coords[other_c]

    attack_axis = unit(c_pos - 0.5 * (o_pos + other_c_pos))
    target_n_pos = c_pos + TARGET_NC_DISTANCE_A * attack_axis

    shifted_amine_coords = amine_coords + (target_n_pos - amine_coords[nitrogen])

    symbols = [atom.GetSymbol() for atom in epoxy.GetAtoms()]
    symbols.extend(atom.GetSymbol() for atom in amine.GetAtoms())
    combined_coords = np.vstack([epoxy_coords, shifted_amine_coords])

    n_global = epoxy.GetNumAtoms() + nitrogen
    nc_distance = float(np.linalg.norm(combined_coords[n_global] - combined_coords[attacked_c]))

    xyz_name = "r2_near_attack.xyz"
    comment = (
        "R2 near-attack glycidyl methyl ether + methylamine; "
        f"attacked_c_index={attacked_c}; nitrogen_index={n_global}; "
        f"N_C_distance_A={nc_distance:.4f}"
    )
    write_xyz(PRE_ORCA_ROOT / xyz_name, symbols, combined_coords, comment)

    metadata = "\n".join(
        [
            "geometry_id,smiles_epoxy,smiles_amine,attacked_c_index,nitrogen_index,n_c_distance_a",
            f"R2,COCC1CO1,CN,{attacked_c},{n_global},{nc_distance:.6f}",
            "",
        ]
    )
    smiles = "\n".join(
        [
            "glycidyl_methyl_ether COCC1CO1",
            "methylamine CN",
            "ring_opened_product COCC(O)CNC",
            "",
        ]
    )
    (PRE_ORCA_ROOT / "smiles.txt").write_text(smiles)
    (PRE_ORCA_ROOT / "r2_near_attack_metadata.csv").write_text(metadata)

    print(f"Wrote {PRE_ORCA_ROOT / xyz_name}")
    print(f"N...C distance: {nc_distance:.4f} A")


if __name__ == "__main__":
    main()
