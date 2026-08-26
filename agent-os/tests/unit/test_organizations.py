import pytest

from app.contracts import OrganizationCreateRequest, WorkforceActivationRequest
from app.platform.organizations import (
    InMemoryOrganizationStore,
    OnboardingIdempotencyConflict,
)


def organization_request() -> OrganizationCreateRequest:
    return OrganizationCreateRequest(
        display_name="Acme Software",
        legal_name="Acme Software Private Limited",
        owner_name="Asha Rao",
        owner_email="asha@example.com",
        company_size="11-50",
        idempotency_key="acme-registration-v1",
    )


def test_organization_registration_is_idempotent() -> None:
    store = InMemoryOrganizationStore()

    first = store.create(organization_request())
    replay = store.create(organization_request())

    assert replay.organization_id == first.organization_id
    assert replay.tenant_id == first.tenant_id
    assert replay.identity_status == "UNVERIFIED_FOUNDATION"


def test_registration_key_cannot_be_reused_for_another_organization() -> None:
    store = InMemoryOrganizationStore()
    store.create(organization_request())
    changed = organization_request().model_copy(update={"display_name": "Another Company"})

    with pytest.raises(OnboardingIdempotencyConflict):
        store.create(changed)


def test_workforce_activation_records_boundaries_without_claiming_connections() -> None:
    store = InMemoryOrganizationStore()
    organization = store.create(organization_request())
    request = WorkforceActivationRequest(
        template_id="software_delivery_v1",
        display_name="Delivery Workforce",
        meeting_mode="agent_os_room",
        repository_url="https://github.com/acme/product",
        base_branch="main",
        working_branch_prefix="agentos/",
        specification_approver_email="specs@example.com",
        release_approver_email="release@example.com",
        idempotency_key="delivery-workforce-v1",
    )

    workforce = store.activate(organization.organization_id, request)
    replay = store.activate(organization.organization_id, request)

    assert replay.workforce_id == workforce.workforce_id
    assert workforce.integration_status["github"] == "boundary_saved_not_connected"
    assert workforce.integration_status["calendar"] == "not_connected"
