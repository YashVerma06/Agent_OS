from __future__ import annotations

import re
from uuid import uuid4

from app.contracts import (
    ActivatedWorkforce,
    ActorRole,
    OrganizationCreateRequest,
    OrganizationProfile,
    WorkforceActivationRequest,
    WorkforceTemplate,
)


class OrganizationNotFound(KeyError):
    pass


class WorkforceNotFound(KeyError):
    pass


class OnboardingError(ValueError):
    pass


class OnboardingIdempotencyConflict(OnboardingError):
    pass


SOFTWARE_DELIVERY_TEMPLATE = WorkforceTemplate(
    template_id="software_delivery_v1",
    display_name="Software Product Delivery",
    description=(
        "A governed workforce that turns client discovery into an approved specification, "
        "bounded implementation, independent review, and human-controlled staging release."
    ),
    agent_roles=[
        ActorRole.MANAGER,
        ActorRole.DISCOVERY,
        ActorRole.PLANNER,
        ActorRole.BUILDER,
        ActorRole.REVIEWER,
    ],
    human_gates=["specification_approval", "release_approval"],
)

WORKFORCE_TEMPLATES = {SOFTWARE_DELIVERY_TEMPLATE.template_id: SOFTWARE_DELIVERY_TEMPLATE}


def _workspace_slug(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
    return slug[:70] or "workspace"


class InMemoryOrganizationStore:
    """Tenant onboarding foundation with deterministic idempotency semantics."""

    def __init__(self) -> None:
        self._organizations: dict[str, OrganizationProfile] = {}
        self._workforces: dict[str, ActivatedWorkforce] = {}
        self._organization_idempotency: dict[
            str, tuple[tuple[object, ...], OrganizationProfile]
        ] = {}
        self._workforce_idempotency: dict[
            tuple[str, str], tuple[tuple[object, ...], ActivatedWorkforce]
        ] = {}

    def templates(self) -> list[WorkforceTemplate]:
        return [template.model_copy(deep=True) for template in WORKFORCE_TEMPLATES.values()]

    def create(self, request: OrganizationCreateRequest) -> OrganizationProfile:
        signature = (
            request.display_name,
            request.legal_name,
            request.owner_name,
            request.owner_email.lower(),
            request.company_size,
        )
        existing = self._organization_idempotency.get(request.idempotency_key)
        if existing is not None:
            existing_signature, organization = existing
            if existing_signature != signature:
                raise OnboardingIdempotencyConflict(
                    "The idempotency key was already used for another organization request."
                )
            return organization.model_copy(deep=True)

        organization_id = str(uuid4())
        tenant_id = f"{_workspace_slug(request.display_name)}-{organization_id[:8]}"
        organization = OrganizationProfile(
            organization_id=organization_id,
            tenant_id=tenant_id,
            display_name=request.display_name,
            legal_name=request.legal_name,
            owner_name=request.owner_name,
            owner_email=request.owner_email.lower(),
            company_size=request.company_size,
        )
        self._organizations[organization_id] = organization
        self._organization_idempotency[request.idempotency_key] = (signature, organization)
        return organization.model_copy(deep=True)

    def get(self, organization_id: str) -> OrganizationProfile:
        organization = self._organizations.get(organization_id)
        if organization is None:
            raise OrganizationNotFound(organization_id)
        return organization.model_copy(deep=True)

    def activate(
        self, organization_id: str, request: WorkforceActivationRequest
    ) -> ActivatedWorkforce:
        self.get(organization_id)
        if request.template_id not in WORKFORCE_TEMPLATES:
            raise OnboardingError("The requested workforce template does not exist.")

        signature = (
            request.template_id,
            request.display_name,
            request.meeting_mode,
            request.repository_url,
            request.base_branch,
            request.working_branch_prefix,
            request.specification_approver_email.lower(),
            request.release_approver_email.lower(),
        )
        slot = (organization_id, request.idempotency_key)
        existing = self._workforce_idempotency.get(slot)
        if existing is not None:
            existing_signature, workforce = existing
            if existing_signature != signature:
                raise OnboardingIdempotencyConflict(
                    "The idempotency key was already used for another workforce activation."
                )
            return workforce.model_copy(deep=True)

        workforce = ActivatedWorkforce(
            workforce_id=str(uuid4()),
            organization_id=organization_id,
            template_id=request.template_id,
            display_name=request.display_name,
            meeting_mode=request.meeting_mode,
            repository_url=request.repository_url.rstrip("/"),
            base_branch=request.base_branch,
            working_branch_prefix=request.working_branch_prefix,
            specification_approver_email=request.specification_approver_email.lower(),
            release_approver_email=request.release_approver_email.lower(),
        )
        self._workforces[workforce.workforce_id] = workforce
        self._workforce_idempotency[slot] = (signature, workforce)
        return workforce.model_copy(deep=True)

    def get_workforce(
        self, organization_id: str, workforce_id: str
    ) -> ActivatedWorkforce:
        self.get(organization_id)
        workforce = self._workforces.get(workforce_id)
        if workforce is None or workforce.organization_id != organization_id:
            raise WorkforceNotFound(workforce_id)
        return workforce.model_copy(deep=True)
