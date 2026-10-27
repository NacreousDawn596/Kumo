"""Chemistry: parse, verify, and generate 3D structures via RDKit."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/chemistry", tags=["chemistry"])

# CPK colors (Jmol convention) for common elements.
CPK = {
    "H": "#ffffff",
    "C": "#909090",
    "N": "#3050f8",
    "O": "#ff0d0d",
    "F": "#90e050",
    "Cl": "#1ff01f",
    "Br": "#a62929",
    "I": "#940094",
    "S": "#ffff30",
    "P": "#ff8000",
    "Na": "#ab5cf2",
    "K": "#8f40d4",
    "Ca": "#3dff00",
    "Mg": "#8aff00",
    "Fe": "#e06633",
    "Zn": "#7d80b0",
    "Cu": "#c88033",
}


class MoleculeIn(BaseModel):
    smiles: str


def _cpk(symbol: str) -> str:
    return CPK.get(symbol, "#ff1493")


def _structure(smiles: str) -> dict:
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, rdMolDescriptors

    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return {"valid": False, "error": "Could not parse this SMILES string."}

    # Sanitization already validated valences/connectivity. Add explicit H for a
    # physically sensible 3D embedding; heavy atoms keep their original indices.
    mol3d = Chem.AddHs(mol)
    try:
        AllChem.EmbedMolecule(mol3d, randomSeed=42)
        AllChem.MMFFOptimizeMolecule(mol3d, maxIters=200)
    except Exception:  # noqa: BLE001 — fall back to a flat layout
        mol3d = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol3d)

    conf = mol3d.GetConformer()

    heavy = []  # display index -> mol3d atom index
    atoms = []
    for atom in mol3d.GetAtoms():
        if atom.GetAtomicNum() == 1:
            continue  # implicit hydrogens are not drawn
        idx = atom.GetIdx()
        pos = conf.GetAtomPosition(idx)
        atoms.append({
            "symbol": atom.GetSymbol(),
            "x": round(pos.x, 4),
            "y": round(pos.y, 4),
            "z": round(pos.z, 4),
            "charge": int(atom.GetFormalCharge()),
            "color": _cpk(atom.GetSymbol()),
        })
        heavy.append(idx)

    heavy_to_display = {idx: i for i, idx in enumerate(heavy)}
    bonds = []
    for bond in mol.GetBonds():
        a = bond.GetBeginAtomIdx()
        b = bond.GetEndAtomIdx()
        if a in heavy_to_display and b in heavy_to_display:
            bonds.append({
                "a": heavy_to_display[a],
                "b": heavy_to_display[b],
                "order": int(bond.GetBondTypeAsDouble()),
            })

    return {
        "valid": True,
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "molecular_weight": round(Descriptors.MolWt(mol), 2),
        "num_atoms": len(atoms),
        "num_bonds": len(bonds),
        "total_charge": int(Chem.GetFormalCharge(mol)),
        "atoms": atoms,
        "bonds": bonds,
    }


@router.post("/molecule")
def analyze_molecule(body: MoleculeIn):
    if not body.smiles or not body.smiles.strip():
        raise HTTPException(status_code=400, detail="SMILES is required")
    if len(body.smiles) > 500:
        raise HTTPException(status_code=400, detail="SMILES too long")
    return _structure(body.smiles)
