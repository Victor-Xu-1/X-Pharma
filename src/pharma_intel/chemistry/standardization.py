from __future__ import annotations

import threading
from importlib import import_module
from typing import Any

from pharma_intel.chemistry.types import ChemistryValidationError, StandardizedStructure

# RDKit 2026.03.3 ships malformed generated type stubs. Keep the untyped C++
# boundary inside this adapter and verify its behavior with real RDKit tests.
Chem: Any = import_module("rdkit.Chem")
rdBase: Any = import_module("rdkit.rdBase")
Descriptors: Any = import_module("rdkit.Chem.Descriptors")
inchi: Any = import_module("rdkit.Chem.inchi")
rdMolDescriptors: Any = import_module("rdkit.Chem.rdMolDescriptors")
rdMolStandardize: Any = import_module("rdkit.Chem.MolStandardize.rdMolStandardize")

STANDARDIZATION_VERSION = "rdkit-2026.03.3/cleanup-fragment-uncharger-tautomer-v1"
MAX_STRUCTURE_CHARS = 20_000
MAX_STRUCTURE_ATOMS = 2_000
MAX_SMARTS_CHARS = 4_000
MAX_SMARTS_ATOMS = 512

_RDKIT_PARSE_LOCK = threading.RLock()


class ChemistryStandardizer:
    def __init__(self) -> None:
        self._uncharger = rdMolStandardize.Uncharger()
        self._tautomer_enumerator = rdMolStandardize.TautomerEnumerator()
        self._tautomer_enumerator.SetMaxTautomers(256)
        self._tautomer_enumerator.SetMaxTransforms(1_000)

    def standardize_smiles(self, smiles: str) -> StandardizedStructure:
        normalized_input = self._validate_text(smiles, MAX_STRUCTURE_CHARS, "structure_too_large")
        with _RDKIT_PARSE_LOCK, rdBase.BlockLogs():
            molecule = Chem.MolFromSmiles(normalized_input, sanitize=True)
            if molecule is None:
                raise ChemistryValidationError("invalid_smiles", "The supplied structure is not valid SMILES")
            self._validate_molecule(molecule, MAX_STRUCTURE_ATOMS)
            molecule = rdMolStandardize.Cleanup(molecule)
            molecule = rdMolStandardize.FragmentParent(molecule)
            molecule = self._uncharger.uncharge(molecule)
            molecule = self._tautomer_enumerator.Canonicalize(molecule)
            Chem.SanitizeMol(molecule)
            Chem.AssignStereochemistry(molecule, cleanIt=True, force=True)
            self._validate_molecule(molecule, MAX_STRUCTURE_ATOMS)

            canonical_smiles = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            standard_inchi = inchi.MolToInchi(molecule)
            standard_inchi_key = inchi.MolToInchiKey(molecule)
            if not canonical_smiles or not standard_inchi or not standard_inchi_key:
                raise ChemistryValidationError(
                    "standardization_failed",
                    "RDKit could not produce canonical structure identifiers",
                )
            return StandardizedStructure(
                input_structure=normalized_input,
                input_format="smiles",
                canonical_smiles=canonical_smiles,
                isomeric_smiles=canonical_smiles,
                standard_inchi=standard_inchi,
                standard_inchi_key=standard_inchi_key,
                molecular_formula=rdMolDescriptors.CalcMolFormula(molecule),
                molecular_weight=round(float(Descriptors.MolWt(molecule)), 6),
                exact_mass=round(float(rdMolDescriptors.CalcExactMolWt(molecule)), 6),
                atom_count=int(molecule.GetNumAtoms()),
                heavy_atom_count=int(molecule.GetNumHeavyAtoms()),
                standardization_version=STANDARDIZATION_VERSION,
            )

    def normalize_smarts(self, smarts: str) -> str:
        normalized_input = self._validate_text(smarts, MAX_SMARTS_CHARS, "smarts_too_large")
        with _RDKIT_PARSE_LOCK, rdBase.BlockLogs():
            query = Chem.MolFromSmarts(normalized_input)
            if query is None:
                raise ChemistryValidationError("invalid_smarts", "The supplied substructure query is not valid SMARTS")
            if query.GetNumAtoms() == 0 or query.GetNumAtoms() > MAX_SMARTS_ATOMS:
                raise ChemistryValidationError(
                    "smarts_atom_limit",
                    f"SMARTS queries must contain between 1 and {MAX_SMARTS_ATOMS} atoms",
                )
            return str(Chem.MolToSmarts(query))

    @staticmethod
    def _validate_text(value: str, maximum: int, too_large_code: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ChemistryValidationError("structure_required", "A chemical structure query is required")
        if "\x00" in normalized:
            raise ChemistryValidationError("invalid_structure_text", "Chemical structure text contains a null byte")
        if len(normalized) > maximum:
            raise ChemistryValidationError(too_large_code, f"Chemical structure text exceeds {maximum} characters")
        return normalized

    @staticmethod
    def _validate_molecule(molecule: Any, maximum_atoms: int) -> None:
        atom_count = int(molecule.GetNumAtoms())
        if atom_count == 0 or atom_count > maximum_atoms:
            raise ChemistryValidationError(
                "structure_atom_limit",
                f"Chemical structures must contain between 1 and {maximum_atoms} atoms",
            )
        if any(int(atom.GetAtomicNum()) == 0 for atom in molecule.GetAtoms()):
            raise ChemistryValidationError(
                "unsupported_query_atom",
                "Canonical chemical structures cannot contain wildcard or query atoms",
            )
