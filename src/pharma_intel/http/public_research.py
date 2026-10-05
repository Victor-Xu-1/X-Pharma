from fastapi import APIRouter, HTTPException

from pharma_intel.http.dependencies import PrincipalDep, SessionDep
from pharma_intel.public_research.coverage import local_coverage
from pharma_intel.public_research.service import PublicResearchBusy, PublicResearchService
from pharma_intel.schemas.public_research import PublicResearchCoverage, PublicResearchQuery, PublicResearchResponse
from pharma_intel.security import Principal

router = APIRouter()


def _require_human(principal: Principal) -> None:
    principal.require("entities:read")
    if principal.actor_type != "user":
        raise HTTPException(status_code=403, detail="Public online research requires a human workbench session")


@router.post("/api/v1/public-research/search", response_model=PublicResearchResponse, tags=["public-research"])
def public_research(query: PublicResearchQuery, principal: PrincipalDep) -> PublicResearchResponse:
    _require_human(principal)
    try:
        return PublicResearchService().search(query)
    except PublicResearchBusy as error:
        raise HTTPException(
            status_code=429, detail="Public research is busy; retry explicitly", headers={"Retry-After": "2"}
        ) from error


@router.get("/api/v1/public-research/coverage", response_model=PublicResearchCoverage, tags=["public-research"])
def public_coverage(principal: PrincipalDep, session: SessionDep) -> PublicResearchCoverage:
    _require_human(principal)
    return local_coverage(session, principal.tenant_id)
