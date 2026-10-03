import hashlib
import json
from enum import Enum, StrEnum

from pharma_intel.models import enums


def test_model_enums_preserve_persisted_values_and_existing_diagnostic_representation() -> None:
    classes = {
        name: cls
        for name, cls in vars(enums).items()
        if isinstance(cls, type) and issubclass(cls, Enum) and not name.startswith("_") and cls.__members__
    }
    assert len(classes) == 37
    assert all(issubclass(cls, StrEnum) for cls in classes.values())
    contract = {
        name: [
            {
                "name": member.name,
                "value": member.value,
                "str": str(member),
                "format": f"{member}",
                "repr": repr(member),
            }
            for member in cls
        ]
        for name, cls in classes.items()
    }
    digest = hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == "9999a29b0ccbebc071e6b76e69df1204e9b8dc7b4c19e8dff12b8708383287db"
