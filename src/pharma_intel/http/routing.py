from fastapi import FastAPI

from pharma_intel.http.agent_chemistry import router as agent_chemistry_router
from pharma_intel.http.agent_deals import router as agent_deals_router
from pharma_intel.http.agent_entities import router as agent_entities_router
from pharma_intel.http.agent_epidemiology import router as agent_epidemiology_router
from pharma_intel.http.agent_knowledge import router as agent_knowledge_router
from pharma_intel.http.agent_news import router as agent_news_router
from pharma_intel.http.agent_patents import router as agent_patents_router
from pharma_intel.http.agent_pipeline import router as agent_pipeline_router
from pharma_intel.http.agent_regulatory import router as agent_regulatory_router
from pharma_intel.http.agent_trials import router as agent_trials_router
from pharma_intel.http.authentication import router as authentication_router
from pharma_intel.http.chemistry import router as chemistry_router
from pharma_intel.http.commercial_accounting import router as commercial_accounting_router
from pharma_intel.http.commercial_billing import router as commercial_billing_router
from pharma_intel.http.commercial_exports import router as commercial_exports_router
from pharma_intel.http.commercial_risk import router as commercial_risk_router
from pharma_intel.http.commercial_usage import router as commercial_usage_router
from pharma_intel.http.comparison import router as comparison_router
from pharma_intel.http.data_lifecycle import router as data_lifecycle_router
from pharma_intel.http.deals import router as deals_router
from pharma_intel.http.dossiers import router as dossiers_router
from pharma_intel.http.enterprise import router as enterprise_router
from pharma_intel.http.enterprise_keys import router as enterprise_keys_router
from pharma_intel.http.enterprise_models import router as enterprise_models_router
from pharma_intel.http.entities import router as entities_router
from pharma_intel.http.environment import router as environment_router
from pharma_intel.http.epidemiology import router as epidemiology_router
from pharma_intel.http.evidence import router as evidence_router
from pharma_intel.http.governance_review import router as governance_review_router
from pharma_intel.http.health import router as health_router
from pharma_intel.http.identity import router as identity_router
from pharma_intel.http.ingestion_runs import router as ingestion_runs_router
from pharma_intel.http.ingestion_sources import router as ingestion_sources_router
from pharma_intel.http.knowledge import router as knowledge_router
from pharma_intel.http.monitoring import router as monitoring_router
from pharma_intel.http.news import router as news_router
from pharma_intel.http.organizations import router as organization_router
from pharma_intel.http.patents import router as patents_router
from pharma_intel.http.pipeline import router as pipeline_router
from pharma_intel.http.projection_maintenance import router as projection_maintenance_router
from pharma_intel.http.public_research import router as public_research_router
from pharma_intel.http.publication import router as publication_router
from pharma_intel.http.quality import router as quality_router
from pharma_intel.http.quarantine import router as quarantine_router
from pharma_intel.http.registration import router as account_registration_router
from pharma_intel.http.regulatory import router as regulatory_router
from pharma_intel.http.search_projection import router as search_projection_router
from pharma_intel.http.source_assets import router as source_assets_router
from pharma_intel.http.source_versions import router as source_versions_router
from pharma_intel.http.trials import router as trials_router
from pharma_intel.http.workspace import router as workspace_router


def install_feature_routes(app: FastAPI) -> None:
    app.include_router(account_registration_router)
    app.include_router(authentication_router)
    app.include_router(organization_router)
    app.include_router(enterprise_router)
    app.include_router(environment_router)
    app.include_router(enterprise_keys_router)
    app.include_router(enterprise_models_router)
    app.include_router(trials_router)
    app.include_router(pipeline_router)
    app.include_router(patents_router)
    app.include_router(deals_router)
    app.include_router(regulatory_router)
    app.include_router(epidemiology_router)
    app.include_router(news_router)
    app.include_router(entities_router)
    app.include_router(public_research_router)
    app.include_router(dossiers_router)
    app.include_router(workspace_router)
    app.include_router(governance_review_router)
    app.include_router(identity_router)
    app.include_router(publication_router)
    app.include_router(projection_maintenance_router)
    app.include_router(quality_router)
    app.include_router(knowledge_router)
    app.include_router(health_router)
    app.include_router(search_projection_router)
    app.include_router(comparison_router)
    app.include_router(monitoring_router)
    app.include_router(evidence_router)
    app.include_router(ingestion_sources_router)
    app.include_router(ingestion_runs_router)
    app.include_router(source_assets_router)
    app.include_router(quarantine_router)
    app.include_router(source_versions_router)
    app.include_router(agent_entities_router)
    app.include_router(agent_pipeline_router)
    app.include_router(agent_trials_router)
    app.include_router(agent_patents_router)
    app.include_router(agent_deals_router)
    app.include_router(agent_regulatory_router)
    app.include_router(agent_epidemiology_router)
    app.include_router(agent_news_router)
    app.include_router(agent_knowledge_router)
    app.include_router(agent_chemistry_router)
    app.include_router(chemistry_router)
    app.include_router(commercial_usage_router)
    app.include_router(commercial_accounting_router)
    app.include_router(commercial_exports_router)
    app.include_router(commercial_billing_router)
    app.include_router(commercial_risk_router)
    app.include_router(data_lifecycle_router)
