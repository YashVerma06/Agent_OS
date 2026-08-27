/**
 * Meeting Room API client.
 *
 * Separate from `lib/api.ts` so this feature never edits the shared control-plane
 * client. Base URL resolution matches it so both point at the same backend.
 */

import type {
  DiscoveryBoundary,
  MeetingCapability,
  MeetingSession,
  MeetingView,
  SpecificationHandoff,
  Speaker,
  Utterance,
  UtteranceSource,
} from './meeting-types';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') ?? 'http://127.0.0.1:8080';

export class MeetingApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code?: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string | { message?: string } }
      | null;
    const detail = body?.detail;
    const message =
      typeof detail === 'string'
        ? detail
        : detail?.message ?? `Meeting request failed (${response.status}).`;
    throw new MeetingApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

/** ws:// or wss:// form of the API origin, for the meeting socket. */
export function meetingSocketUrl(meetingId: string): string {
  const base = API_BASE_URL.replace(/^http/, 'ws');
  return `${base}/v1/meetings/${meetingId}/live`;
}

export const meetingApi = {
  capabilities: () => request<MeetingCapability>('/v1/meetings/capabilities'),

  boundaries: () => request<DiscoveryBoundary[]>('/v1/meetings/boundaries'),

  open: (workflowId: string, participantName: string) =>
    request<MeetingView>(`/v1/workflows/${workflowId}/meetings`, {
      method: 'POST',
      body: JSON.stringify({ participant_name: participantName }),
    }),

  get: (meetingId: string) => request<MeetingView>(`/v1/meetings/${meetingId}`),

  grantConsent: (
    meetingId: string,
    input: { participant_name: string; ai_disclosure_acknowledged: boolean; transcription_acknowledged: boolean },
  ) =>
    request<MeetingSession>(`/v1/meetings/${meetingId}/consent`, {
      method: 'POST',
      body: JSON.stringify({ granted: true, ...input }),
    }),

  transcript: (meetingId: string) =>
    request<{ meeting_id: string; finalized: boolean; utterances: Utterance[] }>(
      `/v1/meetings/${meetingId}/transcript`,
    ),

  appendUtterance: (
    meetingId: string,
    input: {
      speaker: Speaker;
      content: string;
      source?: UtteranceSource;
      dedupe_key?: string;
    },
  ) =>
    request<Utterance>(`/v1/meetings/${meetingId}/utterances`, {
      method: 'POST',
      body: JSON.stringify(input),
    }),

  finalize: (meetingId: string) =>
    request<SpecificationHandoff>(`/v1/meetings/${meetingId}/finalize`, {
      method: 'POST',
    }),
};
