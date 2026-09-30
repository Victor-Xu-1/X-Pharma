from __future__ import annotations

import math
from collections import Counter
from importlib import import_module, metadata
from pathlib import Path
from typing import Any

from pharma_intel.chemistry.standardization import ChemistryStandardizer
from pharma_intel.chemistry.types import ChemistryValidationError, StandardizedStructure
from pharma_intel.ingest.parsers import DocumentParseError, ParsedDocument, TextAccumulator

# Keep native extension boundaries untyped and covered by real parser tests.
Chem: Any = import_module("rdkit.Chem")
gemmi: Any = import_module("gemmi")

MAX_CHEMICAL_RECORDS = 10_000
MAX_RECORD_PROPERTIES = 200
MAX_PROPERTY_NAME_CHARS = 200
MAX_PROPERTY_VALUE_CHARS = 10_000
MAX_STRUCTURE_MODELS = 100
MAX_STRUCTURE_CHAINS = 10_000
MAX_STRUCTURE_RESIDUES = 1_000_000
MAX_STRUCTURE_ATOMS = 2_000_000
MAX_LIGAND_TYPES = 10_000
METADATA_RECORD_PREVIEW = 100


def parse_sdf(path: Path, max_chars: int) -> ParsedDocument:
    standardizer = ChemistryStandardizer()
    output = TextAccumulator(max_chars)
    previews: list[dict[str, Any]] = []
    record_count = 0
    with path.open("rb") as source:
        supplier = Chem.ForwardSDMolSupplier(source, sanitize=True, removeHs=False, strictParsing=True)
        for record_count, molecule in enumerate(supplier, start=1):
            if record_count > MAX_CHEMICAL_RECORDS:
                raise DocumentParseError(f"SDF exceeds the {MAX_CHEMICAL_RECORDS} molecule safety limit")
            if molecule is None:
                raise DocumentParseError(f"SDF molecule {record_count} is invalid or failed strict RDKit parsing")
            standardized = _standardize_molecule(molecule, standardizer, record_count)
            name = _molecule_name(molecule, record_count)
            _write_molecule(output, record_count, name, standardized, molecule)
            if len(previews) < METADATA_RECORD_PREVIEW:
                previews.append(_structure_metadata(record_count, name, standardized))
    if record_count == 0:
        raise DocumentParseError("SDF contains no molecule records")
    return ParsedDocument(
        text=output.render(),
        metadata={
            "scientific_format": "sdf",
            "record_count": record_count,
            "record_preview": previews,
            "record_preview_truncated": record_count > len(previews),
            "standardization_version": previews[0]["standardization_version"],
        },
        parser_name="rdkit-sdf",
        parser_version=metadata.version("rdkit"),
    )


def parse_mol(path: Path, max_chars: int) -> ParsedDocument:
    molecule = Chem.MolFromMolFile(str(path), sanitize=True, removeHs=False, strictParsing=True)
    if molecule is None:
        raise DocumentParseError("MOL file is invalid or failed strict RDKit parsing")
    standardized = _standardize_molecule(molecule, ChemistryStandardizer(), 1)
    name = _molecule_name(molecule, 1)
    output = TextAccumulator(max_chars)
    _write_molecule(output, 1, name, standardized, molecule)
    preview = _structure_metadata(1, name, standardized)
    return ParsedDocument(
        text=output.render(),
        metadata={
            "scientific_format": "mol",
            "record_count": 1,
            "record_preview": [preview],
            "record_preview_truncated": False,
            "standardization_version": standardized.standardization_version,
        },
        parser_name="rdkit-mol",
        parser_version=metadata.version("rdkit"),
    )


def parse_macromolecular_structure(path: Path, max_chars: int) -> ParsedDocument:
    try:
        structure = gemmi.read_structure(str(path), merge_chain_parts=True)
        structure.setup_entities()
    except Exception as exc:
        raise DocumentParseError(f"Macromolecular structure failed strict Gemmi parsing: {exc}") from exc
    model_count = len(structure)
    if model_count == 0:
        raise DocumentParseError("Macromolecular structure contains no models")
    if model_count > MAX_STRUCTURE_MODELS:
        raise DocumentParseError(f"Structure exceeds the {MAX_STRUCTURE_MODELS} model safety limit")

    chain_ids: set[str] = set()
    ligand_counts: Counter[str] = Counter()
    chain_count = 0
    residue_count = 0
    atom_count = 0
    for model_index, model in enumerate(structure, start=1):
        for chain in model:
            chain_count += 1
            if chain_count > MAX_STRUCTURE_CHAINS:
                raise DocumentParseError(f"Structure exceeds the {MAX_STRUCTURE_CHAINS} chain safety limit")
            chain_ids.add(str(chain.name) or f"unnamed-{model_index}-{chain_count}")
            for residue in chain:
                residue_count += 1
                if residue_count > MAX_STRUCTURE_RESIDUES:
                    raise DocumentParseError(f"Structure exceeds the {MAX_STRUCTURE_RESIDUES} residue safety limit")
                atom_count += len(residue)
                if atom_count > MAX_STRUCTURE_ATOMS:
                    raise DocumentParseError(f"Structure exceeds the {MAX_STRUCTURE_ATOMS} atom safety limit")
                if not residue.is_water() and str(residue.het_flag) != "A":
                    ligand_counts[_clean_scalar(str(residue.name), "ligand name", 80)] += 1
                    if len(ligand_counts) > MAX_LIGAND_TYPES:
                        raise DocumentParseError(f"Structure exceeds the {MAX_LIGAND_TYPES} ligand-type safety limit")
    if atom_count == 0:
        raise DocumentParseError("Macromolecular structure contains no atoms")

    source_format = _structure_format(path, structure)
    resolution = float(structure.resolution)
    resolution_value = resolution if math.isfinite(resolution) and resolution > 0 else None
    ligand_summary = [
        {"component_id": component_id, "instance_count": count} for component_id, count in sorted(ligand_counts.items())
    ]
    chain_list = sorted(chain_ids)
    metadata_payload: dict[str, Any] = {
        "scientific_format": source_format,
        "structure_name": _clean_scalar(str(structure.name or path.stem), "structure name", 500),
        "model_count": model_count,
        "chain_count": chain_count,
        "chain_ids": chain_list,
        "residue_count": residue_count,
        "atom_count": atom_count,
        "ligands": ligand_summary,
        "resolution_angstrom": resolution_value,
        "space_group": _optional_scalar(str(structure.spacegroup_hm), 120),
    }
    output = TextAccumulator(max_chars)
    output.add("[[structure]]")
    for field in (
        "scientific_format",
        "structure_name",
        "model_count",
        "chain_count",
        "residue_count",
        "atom_count",
        "resolution_angstrom",
        "space_group",
    ):
        value = metadata_payload[field]
        if value is not None:
            output.add(f"{field}: {value}")
    output.add(f"chain_ids: {','.join(chain_list)}")
    for ligand in ligand_summary:
        output.add(f"ligand: {ligand['component_id']} instances={ligand['instance_count']}")
    return ParsedDocument(
        text=output.render(),
        metadata=metadata_payload,
        parser_name=f"gemmi-{source_format}",
        parser_version=metadata.version("gemmi"),
    )


def _standardize_molecule(
    molecule: Any,
    standardizer: ChemistryStandardizer,
    record_number: int,
) -> StandardizedStructure:
    try:
        source_smiles = str(Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True))
        return standardizer.standardize_smiles(source_smiles)
    except ChemistryValidationError as exc:
        raise DocumentParseError(f"Molecule {record_number} failed RDKit authority validation: {exc}") from exc
    except Exception as exc:
        raise DocumentParseError(f"Molecule {record_number} could not be standardized by RDKit: {exc}") from exc


def _molecule_name(molecule: Any, record_number: int) -> str:
    raw_name = str(molecule.GetProp("_Name")) if molecule.HasProp("_Name") else ""
    return _clean_scalar(raw_name.strip() or f"molecule-{record_number}", "molecule name", 500)


def _write_molecule(
    output: TextAccumulator,
    record_number: int,
    name: str,
    structure: StandardizedStructure,
    molecule: Any,
) -> None:
    output.add(f"[[molecule:{record_number}]]")
    output.add(f"name: {name}")
    for field, value in _structure_metadata(record_number, name, structure).items():
        if field not in {"record_number", "name", "standardization_version"}:
            output.add(f"{field}: {value}")
    output.add(f"standardization_version: {structure.standardization_version}")
    property_names = sorted(str(value) for value in molecule.GetPropNames(includePrivate=False, includeComputed=False))
    if len(property_names) > MAX_RECORD_PROPERTIES:
        raise DocumentParseError(f"Molecule {record_number} exceeds the {MAX_RECORD_PROPERTIES} property safety limit")
    for property_name in property_names:
        safe_name = _clean_scalar(property_name, "property name", MAX_PROPERTY_NAME_CHARS)
        safe_value = _clean_scalar(str(molecule.GetProp(property_name)), "property value", MAX_PROPERTY_VALUE_CHARS)
        output.add(f"property.{safe_name}: {safe_value}")


def _structure_metadata(record_number: int, name: str, structure: StandardizedStructure) -> dict[str, Any]:
    return {
        "record_number": record_number,
        "name": name,
        "canonical_smiles": structure.canonical_smiles,
        "isomeric_smiles": structure.isomeric_smiles,
        "standard_inchi": structure.standard_inchi,
        "standard_inchi_key": structure.standard_inchi_key,
        "molecular_formula": structure.molecular_formula,
        "molecular_weight": structure.molecular_weight,
        "exact_mass": structure.exact_mass,
        "atom_count": structure.atom_count,
        "heavy_atom_count": structure.heavy_atom_count,
        "standardization_version": structure.standardization_version,
    }


def _structure_format(path: Path, structure: Any) -> str:
    if path.suffix.casefold() in {".cif", ".mmcif"}:
        return "mmcif"
    reported = str(structure.input_format).casefold()
    return "mmcif" if "mmcif" in reported or "cif" in reported else "pdb"


def _clean_scalar(value: str, label: str, maximum: int) -> str:
    normalized = " ".join(value.replace("\x00", " ").split())
    if not normalized:
        raise DocumentParseError(f"Scientific {label} is empty")
    if len(normalized) > maximum:
        raise DocumentParseError(f"Scientific {label} exceeds the {maximum} character safety limit")
    return normalized


def _optional_scalar(value: str, maximum: int) -> str | None:
    normalized = " ".join(value.replace("\x00", " ").split())
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise DocumentParseError(f"Scientific metadata exceeds the {maximum} character safety limit")
    return normalized
