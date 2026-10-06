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
    # Reviewed additive stages; migration a3d7f2b9c641 preserves all prior values.
    assert enums.DevelopmentPhase.EARLY_PHASE_1.value == "early_phase_1"
    assert enums.DevelopmentPhase.UNKNOWN.value == "unknown"
    assert digest == "96b0513ff894831d93c917af02a8e6fdfb20cf8f0033741a13758b2e63475157"
