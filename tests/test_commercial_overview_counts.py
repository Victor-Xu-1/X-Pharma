from sqlalchemy.orm import Session

from pharma_intel.commercial.query import commercial_overview
from pharma_intel.models import AgentClient, Tenant


def test_commercial_counts_cover_the_complete_organization_not_a_bounded_list(session: Session, tenant: Tenant) -> None:
    other = Tenant(slug="other-commercial-counts", name="Other organization")
    session.add(other)
    session.flush()
    session.add_all(
        [
            AgentClient(
                tenant_id=tenant.id,
                client_key=f"client-{index}",
                oauth_client_id=f"oauth-{index}",
                display_name=f"Client {index}",
                active=index < 501,
            )
            for index in range(502)
        ]
    )
    session.add(
        AgentClient(tenant_id=other.id, client_key="foreign", oauth_client_id="foreign", display_name="Foreign")
    )
    session.commit()
    overview = commercial_overview(session, tenant.id)
    assert overview["active_client_count"] == 501
    assert (
        overview["pending_export_count"]
        == overview["dead_billing_delivery_count"]
        == overview["open_dispute_count"]
        == 0
    )
