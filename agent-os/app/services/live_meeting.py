"""Agent OS Meeting Room: session lifecycle, consent, and the Gemini Live bridge.

This is an Agent OS-hosted room. Agent OS does not join Google Meet, Zoom, or any
third-party conference; the client opens a room this application serves.

Credential boundary: the browser never receives Google credentials or an access
token. Audio travels browser -> this backend over an application WebSocket, and
only this process holds Application Default Credentials when it opens the Vertex
AI Live session.

Availability: the live transport is opt-in via environment variables and is
reported honestly through `live_capability()`. When it is not configured the room
runs in a labelled fallback mode where the client types, and nothing in the UI
claims a live voice integration that is not running.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field

from app.agents.discovery_conversation import build_system_instruction
from app.contracts import ContextManifest

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


class MeetingSettings(BaseModel):
    """Meeting-room configuration, read from the environment.

    Deliberately local to this module rather than added to `app/settings.py`,
    which is shared. No model id is hardcoded: Live model availability differs by
    project and region, so an unset `GEMINI_LIVE_MODEL` means "not configured"
    and the room falls back rather than guessing a model name.
    """

    live_enabled: bool = Field(default_factory=lambda: _env_bool("GEMINI_LIVE_ENABLED", False))
    live_model: str = Field(default_factory=lambda: os.environ.get("GEMINI_LIVE_MODEL", "").strip())
    live_voice: str = Field(default_factory=lambda: os.environ.get("GEMINI_LIVE_VOICE", "").strip())
    core_model: str = Field(
        default_factory=lambda: os.environ.get("GEMINI_CORE_MODEL", "gemini-3.6-flash").strip()
    )
    project: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT", "agent-os-506220").strip()
    )
    location: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
    )
    use_vertex: bool = Field(default_factory=lambda: _env_bool("GOOGLE_GENAI_USE_VERTEXAI", True))
    input_sample_rate: int = Field(
        default_factory=lambda: _env_int("MEETING_INPUT_SAMPLE_RATE", 16000)
    )
    output_sample_rate: int = Field(
        default_factory=lambda: _env_int("MEETING_OUTPUT_SAMPLE_RATE", 24000)
    )

    # Spend guards. A Live session bills for as long as it stays open, so an
    # abandoned browser tab is a slow credit leak rather than a harmless idle
    # socket. Both caps close the upstream session, never the whole meeting:
    # the transcript survives and the client can reconnect.
    max_session_seconds: int = Field(
        default_factory=lambda: _env_int("MEETING_MAX_LIVE_SECONDS", 600)
    )
    idle_timeout_seconds: int = Field(
        default_factory=lambda: _env_int("MEETING_IDLE_TIMEOUT_SECONDS", 120)
    )

    @property
    def live_configured(self) -> bool:
        return self.live_enabled and bool(self.live_model)


def live_capability(settings: MeetingSettings | None = None) -> dict[str, Any]:
    """What the room can actually do right now, stated plainly for the UI."""
    config = settings or MeetingSettings()
    if not config.live_enabled:
        reason = "GEMINI_LIVE_ENABLED is not set; the room is running in fallback mode."
    elif not config.live_model:
        reason = "GEMINI_LIVE_MODEL is not set; no Live model has been verified for this project."
    else:
        reason = "Live voice is configured. The session opens when the client grants consent."
    return {
        "live_voice_available": config.live_configured,
        "mode": "live_voice" if config.live_configured else "fallback_text",
        "reason": reason,
        "model": config.live_model or None,
        "core_model": config.core_model,
        "input_sample_rate": config.input_sample_rate,
        "output_sample_rate": config.output_sample_rate,
        "transport": "agent_os_meeting_room_websocket",
        "max_session_seconds": config.max_session_seconds,
        "idle_timeout_seconds": config.idle_timeout_seconds,
        "note": (
            "Agent OS hosts this room. It does not join Google Meet or any "
            "third-party conference."
        ),
    }


# --------------------------------------------------------------------------- #
# Session lifecycle                                                            #
# --------------------------------------------------------------------------- #


class MeetingState(StrEnum):
    CREATED = "CREATED"
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONNECTED = "CONNECTED"
    ENDED = "ENDED"
    FAILED = "FAILED"


class ConsentRecord(BaseModel):
    granted: bool
    participant_name: str
    ai_disclosure_acknowledged: bool
    transcription_acknowledged: bool
    granted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trace_id: str = Field(default_factory=lambda: str(uuid4()))


class MeetingSession(BaseModel):
    meeting_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_id: str
    tenant_id: str
    state: MeetingState = MeetingState.CREATED
    mode: str = "fallback_text"
    consent: ConsentRecord | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    connected_at: datetime | None = None
    ended_at: datetime | None = None
    reconnect_count: int = 0
    error: str | None = None

    @property
    def consent_granted(self) -> bool:
        return self.consent is not None and self.consent.granted


class MeetingError(ValueError):
    pass


class ConsentRequired(MeetingError):
    """Raised whenever audio or transcript capture is attempted without consent."""


class MeetingNotFound(KeyError):
    pass


class InMemoryMeetingStore:
    def __init__(self) -> None:
        self._sessions: dict[str, MeetingSession] = {}
        self._lock = Lock()

    def create(self, *, workflow_id: str, tenant_id: str, mode: str) -> MeetingSession:
        session = MeetingSession(workflow_id=workflow_id, tenant_id=tenant_id, mode=mode)
        with self._lock:
            self._sessions[session.meeting_id] = session
        return session.model_copy(deep=True)

    def get(self, meeting_id: str) -> MeetingSession:
        with self._lock:
            session = self._sessions.get(meeting_id)
        if session is None:
            raise MeetingNotFound(meeting_id)
        return session.model_copy(deep=True)

    def _update(self, meeting_id: str, **changes: Any) -> MeetingSession:
        with self._lock:
            session = self._sessions.get(meeting_id)
            if session is None:
                raise MeetingNotFound(meeting_id)
            updated = session.model_copy(update=changes, deep=True)
            self._sessions[meeting_id] = updated
        return updated.model_copy(deep=True)

    def grant_consent(self, meeting_id: str, consent: ConsentRecord) -> MeetingSession:
        if not consent.granted:
            raise ConsentRequired("Consent was declined; the meeting cannot capture audio.")
        if not (consent.ai_disclosure_acknowledged and consent.transcription_acknowledged):
            raise ConsentRequired(
                "Both the AI disclosure and transcription notice must be acknowledged."
            )
        return self._update(
            meeting_id, consent=consent, state=MeetingState.CONSENT_GRANTED
        )

    def require_consent(self, meeting_id: str) -> MeetingSession:
        session = self.get(meeting_id)
        if not session.consent_granted:
            raise ConsentRequired(
                "This meeting has no recorded consent. Capture is refused."
            )
        if session.state is MeetingState.ENDED:
            raise MeetingError("This meeting has ended.")
        return session

    def mark_connected(self, meeting_id: str) -> MeetingSession:
        session = self.require_consent(meeting_id)
        changes: dict[str, Any] = {
            "state": MeetingState.CONNECTED,
            "connected_at": session.connected_at or datetime.now(UTC),
            "error": None,
        }
        if session.state is MeetingState.CONNECTED or session.connected_at is not None:
            changes["reconnect_count"] = session.reconnect_count + 1
        return self._update(meeting_id, **changes)

    def mark_failed(self, meeting_id: str, error: str) -> MeetingSession:
        return self._update(meeting_id, state=MeetingState.FAILED, error=error)

    def end(self, meeting_id: str) -> MeetingSession:
        session = self.get(meeting_id)
        if session.state is MeetingState.ENDED:
            return session
        return self._update(
            meeting_id, state=MeetingState.ENDED, ended_at=datetime.now(UTC)
        )


# --------------------------------------------------------------------------- #
# Live transport                                                               #
# --------------------------------------------------------------------------- #


class LiveEventType(StrEnum):
    AUDIO = "audio"
    INPUT_TRANSCRIPT = "input_transcript"
    OUTPUT_TRANSCRIPT = "output_transcript"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"


class LiveEvent(BaseModel):
    type: LiveEventType
    text: str = ""
    audio_b64: str = ""


class LiveTransport(Protocol):
    """Transport contract. Tests substitute a fake; nothing else changes."""

    async def start(self, *, system_instruction: str, opening: str) -> None: ...
    async def send_audio(self, pcm16: bytes) -> None: ...
    async def send_text(self, text: str) -> None: ...
    def events(self) -> AsyncIterator[LiveEvent]: ...
    async def close(self) -> None: ...


class LiveUnavailable(RuntimeError):
    """Raised when a live session is requested but the transport is not configured."""


class GeminiLiveTransport:
    """Vertex AI Gemini Live transport.

    Credentials stay in this process via Application Default Credentials. The
    browser only ever exchanges PCM frames with our own WebSocket.

    Not exercised against the live service in this branch — see the limitations
    section of the PR. Attribute access on server messages is defensive because
    the payload shape varies across google-genai releases.
    """

    def __init__(self, settings: MeetingSettings | None = None) -> None:
        self._settings = settings or MeetingSettings()
        if not self._settings.live_configured:
            raise LiveUnavailable(live_capability(self._settings)["reason"])
        self._session: Any = None
        self._context: Any = None
        self._queue: asyncio.Queue[LiveEvent] = asyncio.Queue()
        self._pump: asyncio.Task[None] | None = None

    async def start(self, *, system_instruction: str, opening: str) -> None:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=self._settings.use_vertex,
            project=self._settings.project,
            location=self._settings.location,
        )
        config: dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instruction,
            "input_audio_transcription": types.AudioTranscriptionConfig(),
            "output_audio_transcription": types.AudioTranscriptionConfig(),
        }
        if self._settings.live_voice:
            config["speech_config"] = types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._settings.live_voice
                    )
                )
            )

        self._context = client.aio.live.connect(model=self._settings.live_model, config=config)
        self._session = await self._context.__aenter__()
        self._pump = asyncio.create_task(self._drain())
        if opening:
            await self.send_text(opening)

    async def _drain(self) -> None:
        try:
            async for message in self._session.receive():
                for event in _translate_live_message(message):
                    await self._queue.put(event)
        except asyncio.CancelledError:  # pragma: no cover - task teardown
            raise
        except Exception as exc:  # pragma: no cover - network path
            await self._queue.put(LiveEvent(type=LiveEventType.ERROR, text=str(exc)))

    async def send_audio(self, pcm16: bytes) -> None:
        from google.genai import types

        await self._session.send_realtime_input(
            audio=types.Blob(
                data=pcm16,
                mime_type=f"audio/pcm;rate={self._settings.input_sample_rate}",
            )
        )

    async def send_text(self, text: str) -> None:
        await self._session.send_client_content(
            turns={"role": "user", "parts": [{"text": text}]}, turn_complete=True
        )

    async def events(self) -> AsyncIterator[LiveEvent]:  # type: ignore[override]
        while True:
            yield await self._queue.get()

    async def close(self) -> None:
        if self._pump is not None:
            self._pump.cancel()
            self._pump = None
        if self._context is not None:
            try:
                await self._context.__aexit__(None, None, None)
            finally:
                self._context = None
                self._session = None


def _translate_live_message(message: Any) -> list[LiveEvent]:
    """Map a google-genai server message onto our transport-neutral events."""
    events: list[LiveEvent] = []
    server_content = getattr(message, "server_content", None)
    if server_content is None:
        return events

    input_transcription = getattr(server_content, "input_transcription", None)
    if input_transcription is not None and getattr(input_transcription, "text", ""):
        events.append(
            LiveEvent(
                type=LiveEventType.INPUT_TRANSCRIPT, text=input_transcription.text
            )
        )

    output_transcription = getattr(server_content, "output_transcription", None)
    if output_transcription is not None and getattr(output_transcription, "text", ""):
        events.append(
            LiveEvent(
                type=LiveEventType.OUTPUT_TRANSCRIPT, text=output_transcription.text
            )
        )

    model_turn = getattr(server_content, "model_turn", None)
    for part in getattr(model_turn, "parts", None) or []:
        inline = getattr(part, "inline_data", None)
        data = getattr(inline, "data", None)
        if data:
            events.append(
                LiveEvent(
                    type=LiveEventType.AUDIO,
                    audio_b64=base64.b64encode(data).decode("ascii"),
                )
            )

    if getattr(server_content, "turn_complete", False):
        events.append(LiveEvent(type=LiveEventType.TURN_COMPLETE))
    return events


def build_live_transport(
    context: ContextManifest, settings: MeetingSettings | None = None
) -> tuple[GeminiLiveTransport, str]:
    """Create a transport and the system instruction scoped to one engagement."""
    transport = GeminiLiveTransport(settings)
    return transport, build_system_instruction(context)


# --------------------------------------------------------------------------- #
# Structured generation for the post-meeting pass                              #
# --------------------------------------------------------------------------- #


class VertexStructuredGenerator:
    """Structured JSON generation with the configured core Gemini model.

    Separate from the live session on purpose: the specification is produced by
    a deliberate second pass over the finalized transcript, never streamed out of
    the conversation.
    """

    def __init__(self, settings: MeetingSettings | None = None) -> None:
        self._settings = settings or MeetingSettings()

    def generate_json(self, *, prompt: str, instruction: str) -> dict[str, Any]:
        from google import genai
        from google.genai import types

        client = genai.Client(
            vertexai=self._settings.use_vertex,
            project=self._settings.project,
            location=self._settings.location,
        )
        response = client.models.generate_content(
            model=self._settings.core_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=instruction,
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        return _parse_json_object(getattr(response, "text", "") or "")


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Model did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Model returned JSON that is not an object.")
    return parsed
