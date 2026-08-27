"""Timestamped meeting transcript capture.

The backend is authoritative for ordering. Clients never choose a sequence
number: they submit an utterance and the store assigns the next slot under a
lock. A reconnecting client that replays utterances it already sent must not
create duplicates, so every append carries a dedupe key scoped to the meeting.

Finalizing a transcript freezes it. The frozen document is what becomes the
MEETING_TRANSCRIPT artifact, and it is the only input the downstream structured
generation is allowed to read.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from threading import Lock
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class Speaker(StrEnum):
    CLIENT = "client"
    AGENT = "agent"
    SYSTEM = "system"


class UtteranceSource(StrEnum):
    """Where the text came from. Never label a fallback as live voice."""

    LIVE_VOICE = "live_voice"
    UPLOADED_TRANSCRIPT = "uploaded_transcript"
    WRITTEN_BRIEF = "written_brief"
    SYSTEM_EVENT = "system_event"


class Utterance(BaseModel):
    utterance_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    meeting_id: str
    sequence_number: int
    speaker: Speaker
    timestamp: datetime = Field(default_factory=utc_now)
    content: str
    source: UtteranceSource
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class TranscriptDocument(BaseModel):
    """Frozen transcript. `content` is what gets hashed into the artifact."""

    meeting_id: str
    workflow_id: str
    utterance_count: int
    started_at: datetime | None
    ended_at: datetime
    utterances: list[Utterance]
    content: str


class TranscriptError(ValueError):
    pass


class TranscriptFinalized(TranscriptError):
    pass


def _default_dedupe_key(speaker: Speaker, content: str, source: UtteranceSource) -> str:
    """Deterministic fallback key for clients that do not supply one.

    Two identical utterances from the same speaker are collapsed. That is the
    right trade for a reconnect replay, where the alternative is a duplicated
    transcript line that a human then has to reconcile.
    """
    digest = sha256(f"{speaker.value}|{source.value}|{content.strip()}".encode()).hexdigest()
    return f"auto:{digest}"


class InMemoryTranscriptStore:
    """Reference transcript store. Persistence adapters must preserve ordering."""

    def __init__(self) -> None:
        self._utterances: dict[str, list[Utterance]] = {}
        self._dedupe: dict[str, dict[str, str]] = {}
        self._finalized: dict[str, TranscriptDocument] = {}
        self._lock = Lock()

    def append(
        self,
        *,
        meeting_id: str,
        workflow_id: str,
        speaker: Speaker,
        content: str,
        source: UtteranceSource,
        trace_id: str | None = None,
        dedupe_key: str | None = None,
    ) -> Utterance:
        text = content.strip()
        if not text:
            raise TranscriptError("An utterance must carry non-empty content.")

        with self._lock:
            if meeting_id in self._finalized:
                raise TranscriptFinalized(
                    "The transcript for this meeting is finalized and cannot be extended."
                )

            entries = self._utterances.setdefault(meeting_id, [])
            seen = self._dedupe.setdefault(meeting_id, {})
            key = dedupe_key or _default_dedupe_key(speaker, text, source)

            existing_id = seen.get(key)
            if existing_id is not None:
                for entry in entries:
                    if entry.utterance_id == existing_id:
                        return entry.model_copy(deep=True)

            utterance = Utterance(
                workflow_id=workflow_id,
                meeting_id=meeting_id,
                sequence_number=len(entries) + 1,
                speaker=speaker,
                content=text,
                source=source,
                trace_id=trace_id or str(uuid4()),
            )
            entries.append(utterance)
            seen[key] = utterance.utterance_id
            return utterance.model_copy(deep=True)

    def list(self, meeting_id: str) -> list[Utterance]:
        with self._lock:
            entries = self._utterances.get(meeting_id, [])
            return [entry.model_copy(deep=True) for entry in entries]

    def is_finalized(self, meeting_id: str) -> bool:
        return meeting_id in self._finalized

    def finalized_document(self, meeting_id: str) -> TranscriptDocument | None:
        document = self._finalized.get(meeting_id)
        return document.model_copy(deep=True) if document else None

    def finalize(self, meeting_id: str, workflow_id: str) -> TranscriptDocument:
        """Freeze the transcript. Idempotent: a second call returns the same document."""
        with self._lock:
            existing = self._finalized.get(meeting_id)
            if existing is not None:
                return existing.model_copy(deep=True)

            entries = list(self._utterances.get(meeting_id, []))
            document = TranscriptDocument(
                meeting_id=meeting_id,
                workflow_id=workflow_id,
                utterance_count=len(entries),
                started_at=entries[0].timestamp if entries else None,
                ended_at=utc_now(),
                utterances=entries,
                content=render_transcript(meeting_id, workflow_id, entries),
            )
            self._finalized[meeting_id] = document
            return document.model_copy(deep=True)


def render_transcript(
    meeting_id: str, workflow_id: str, utterances: list[Utterance]
) -> str:
    """Serialize the transcript as the JSON that becomes MEETING_TRANSCRIPT.

    Every field the permission matrix asks for is present on every line, so the
    artifact is self-describing without the store that produced it.
    """
    payload = {
        "artifact": "MEETING_TRANSCRIPT",
        "meeting_id": meeting_id,
        "workflow_id": workflow_id,
        "utterance_count": len(utterances),
        "utterances": [
            {
                "utterance_id": item.utterance_id,
                "workflow_id": item.workflow_id,
                "meeting_id": item.meeting_id,
                "sequence_number": item.sequence_number,
                "speaker": item.speaker.value,
                "timestamp": item.timestamp.isoformat(),
                "content": item.content,
                "source": item.source.value,
                "trace_id": item.trace_id,
            }
            for item in utterances
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def transcript_as_dialogue(utterances: list[Utterance]) -> str:
    """Plain readable dialogue, used as the prompt input for generation."""
    lines = []
    for item in utterances:
        if item.speaker is Speaker.SYSTEM:
            continue
        who = "Client" if item.speaker is Speaker.CLIENT else "Discovery Agent"
        lines.append(f"[{item.sequence_number:03d}] {who}: {item.content}")
    return "\n".join(lines)
