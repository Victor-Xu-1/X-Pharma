from dataclasses import dataclass


@dataclass(frozen=True)
class ExportInput:
    tenant_id: str
    job_id: str


@dataclass(frozen=True)
class ExportFailureInput:
    tenant_id: str
    job_id: str
    code: str
    message: str
