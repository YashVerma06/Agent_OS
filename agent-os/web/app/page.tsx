'use client';

import { useEffect, useRef, useState } from 'react';
import { ControlRoom } from './components/control-room';
import { Icon } from './components/icon';
import { Onboarding, type OnboardingDraft } from './components/onboarding';
import { controlPlane } from './lib/api';
import type {
  ActivatedWorkforce,
  AgentDefinition,
  OrganizationProfile,
  PlatformHealth,
  WorkforceTemplate,
  WorkflowSnapshot,
} from './lib/types';

const SESSION_KEY = 'agent-os-active-workspace';

interface SessionPointer {
  organizationId: string;
  workforceId: string;
  workflowId: string;
}

function newActivationKeys() {
  return {
    organization: `organization-${crypto.randomUUID()}`,
    workforce: `workforce-${crypto.randomUUID()}`,
    engagement: `engagement-${crypto.randomUUID()}`,
  };
}

export default function Home() {
  const [health, setHealth] = useState<PlatformHealth | null>(null);
  const [templates, setTemplates] = useState<WorkforceTemplate[]>([]);
  const [fleet, setFleet] = useState<AgentDefinition[]>([]);
  const [organization, setOrganization] = useState<OrganizationProfile | null>(null);
  const [workforce, setWorkforce] = useState<ActivatedWorkforce | null>(null);
  const [workflow, setWorkflow] = useState<WorkflowSnapshot | null>(null);
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activationKeys = useRef(newActivationKeys());

  useEffect(() => {
    async function boot() {
      try {
        const [platform, workforceTemplates, registeredFleet] = await Promise.all([
          controlPlane.health(),
          controlPlane.workforceTemplates(),
          controlPlane.workforce(),
        ]);
        setHealth(platform);
        setTemplates(workforceTemplates);
        setFleet(registeredFleet);

        const saved = sessionStorage.getItem(SESSION_KEY);
        if (!saved) return;
        try {
          const pointer = JSON.parse(saved) as SessionPointer;
          const [savedOrganization, savedWorkforce, savedWorkflow] = await Promise.all([
            controlPlane.organization(pointer.organizationId),
            controlPlane.activatedWorkforce(pointer.organizationId, pointer.workforceId),
            controlPlane.workflow(pointer.workflowId),
          ]);
          setOrganization(savedOrganization);
          setWorkforce(savedWorkforce);
          setWorkflow(savedWorkflow);
        } catch {
          sessionStorage.removeItem(SESSION_KEY);
        }
      } catch {
        setError('The Agent OS control plane is offline. Start the FastAPI service on port 8080.');
      } finally {
        setBooting(false);
      }
    }

    void boot();
  }, []);

  function completeOnboarding(draft: OnboardingDraft) {
    setBusy(true);
    setError(null);
    void (async () => {
      try {
        const createdOrganization = await controlPlane.createOrganization({
          display_name: draft.organizationName.trim(),
          legal_name: draft.legalName.trim() || undefined,
          owner_name: draft.ownerName.trim(),
          owner_email: draft.ownerEmail.trim(),
          company_size: draft.companySize,
          idempotency_key: activationKeys.current.organization,
        });
        const activatedWorkforce = await controlPlane.activateWorkforce(
          createdOrganization.organization_id,
          {
            template_id: draft.templateId,
            display_name: draft.workforceName.trim(),
            meeting_mode: draft.meetingMode,
            repository_url: draft.repositoryUrl.trim(),
            base_branch: draft.baseBranch.trim(),
            working_branch_prefix: draft.workingBranchPrefix.trim(),
            specification_approver_email: draft.specificationApproverEmail.trim(),
            release_approver_email: draft.releaseApproverEmail.trim(),
            idempotency_key: activationKeys.current.workforce,
          },
        );
        const createdEngagement = await controlPlane.createEngagement(
          createdOrganization.organization_id,
          {
            workforce_id: activatedWorkforce.workforce_id,
            client_name: draft.clientName.trim(),
            project_name: draft.projectName.trim(),
            client_contact_name: draft.clientContactName.trim() || undefined,
            client_contact_email: draft.clientContactEmail.trim() || undefined,
            client_request: draft.clientRequest.trim(),
            idempotency_key: activationKeys.current.engagement,
          },
        );

        sessionStorage.setItem(
          SESSION_KEY,
          JSON.stringify({
            organizationId: createdOrganization.organization_id,
            workforceId: activatedWorkforce.workforce_id,
            workflowId: createdEngagement.workflow_id,
          } satisfies SessionPointer),
        );
        setOrganization(createdOrganization);
        setWorkforce(activatedWorkforce);
        setWorkflow(createdEngagement);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Workspace activation failed.');
      } finally {
        setBusy(false);
      }
    })();
  }

  function exitWorkspace() {
    sessionStorage.removeItem(SESSION_KEY);
    activationKeys.current = newActivationKeys();
    setOrganization(null);
    setWorkforce(null);
    setWorkflow(null);
    setError(null);
  }

  if (booting) {
    return (
      <main className="loading-screen" role="status">
        <div className="loading-mark"><Icon name="spark" size={25} /></div>
        <p className="eyebrow">Agent OS</p>
        <h1>Preparing your workforce infrastructure</h1>
        <span className="loading-line"><i /></span>
      </main>
    );
  }

  if (health && organization && workforce && workflow) {
    return (
      <ControlRoom
        health={health}
        organization={organization}
        workforce={workforce}
        initialWorkflow={workflow}
        fleet={fleet}
        onExit={exitWorkspace}
      />
    );
  }

  return (
    <Onboarding
      health={health}
      templates={templates}
      fleet={fleet}
      busy={busy}
      error={error}
      onSubmit={completeOnboarding}
    />
  );
}
