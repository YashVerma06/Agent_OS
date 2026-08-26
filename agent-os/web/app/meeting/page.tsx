'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Icon } from '../components/icon';
import { MeetingRoom } from '../components/meeting-room';

/**
 * Client-facing Agent OS Meeting Room.
 *
 * Deliberately its own route rather than a panel inside the control room: a
 * client following this link sees consent, voice and transcript, and never the
 * operator's workflow, policy or audit surfaces.
 *
 * Usage: /meeting?workflow=<workflow_id>&project=…&client=…&approver=…
 */

function Room() {
  const search = useSearchParams();
  const workflowId = search.get('workflow');

  if (!workflowId) {
    return (
      <main className="mr-shell mr-center">
        <div className="mr-brand-mark"><Icon name="shield" size={22} /></div>
        <p className="mr-eyebrow">Agent OS Meeting Room</p>
        <h1>This meeting link is incomplete.</h1>
        <p className="mr-lead">
          A meeting room is scoped to one engagement. Ask your Agent OS operator
          for the link that includes the engagement reference.
        </p>
      </main>
    );
  }

  return (
    <MeetingRoom
      workflowId={workflowId}
      projectName={search.get('project') ?? undefined}
      clientName={search.get('client') ?? undefined}
      approverEmail={search.get('approver') ?? undefined}
      onExit={() => window.close()}
    />
  );
}

function Opening() {
  return (
    <main className="mr-shell mr-center" role="status">
      <div className="mr-brand-mark"><Icon name="spark" size={22} /></div>
      <p className="mr-eyebrow">Agent OS Meeting Room</p>
      <h1>Opening the room…</h1>
    </main>
  );
}

export default function MeetingPage() {
  // useSearchParams suspends during static rendering, so the boundary is
  // required rather than decorative.
  return (
    <Suspense fallback={<Opening />}>
      <Room />
    </Suspense>
  );
}
