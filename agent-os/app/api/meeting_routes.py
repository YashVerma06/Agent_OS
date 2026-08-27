"""Agent OS Meeting Room API.

Exposes an `APIRouter`. It is NOT mounted by `app/fast_api_app.py`, which is a
shared file this branch deliberately leaves untouched; Arpit mounts it during
integration.

Store access goes through FastAPI dependencies so tests can inject fresh
in-memory engines without importing the process-wide singletons.

Specification completion is expressed with the shared `AgentRunResult` and
`HandoffEnvelope` contracts and validated by `app.orchestration.handoff`, so the
meeting room proposes on exactly the same terms as every other specialist and
has no private route past the approval gate.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.agents.discovery_conversation import (
    AI_DISCLOSURE,
    CONVERSATION_INSTRUCTION,
    DISCOVERY_TOPICS,
    build_discovery_context,
    build_system_instruction,
    discovery_boundary_report,
    opening_utterance,
)
from app.contracts import (
    ActorRole,
    AgentRunResult,
    AgentRunStatus,
    ArtifactCreateRequest,
    HandoffEnvelope,
    HandoffGate,
    TransitionRequest,
    WorkflowState,
)
from app.orchestration.context import ContextAssembler, ContextBuildError
from app.orchestration.handoff import HandoffDenied, validate_handoff
from app.platform.artifacts import ArtifactError
from app.platform.workflow import TransitionDenied, WorkflowNotFound
from app.services.live_meeting import (
    ConsentRecord,
    ConsentRequired,
    GeminiLiveTransport,
    InMemoryMeetingStore,
    LiveEventType,
    MeetingError,
    MeetingNotFound,
    MeetingSession,
    MeetingSettings,
    VertexStructuredGenerator,
    live_capability,
)
from app.services.specification import (
    REQUIRED_SECTIONS,
    build_discovery_record,
    build_specification_draft,
    render_specification,
    validate_specification,
)
from app.services.transcript import (
    InMemoryTranscriptStore,
    Speaker,
    TranscriptFinalized,
    UtteranceSource,
)

router = APIRouter(tags=["meeting"])

# Meeting-scoped stores. These belong to this feature, unlike the workflow and
# artifact stores which are owned by the control plane.
meetings = InMemoryMeetingStore()
transcripts = InMemoryTranscriptStore()


# --------------------------------------------------------------------------- #
# Dependencies                                                                 #
# --------------------------------------------------------------------------- #


def get_workflow_engine() -> Any:
    from app.fast_api_app import workflows

    return workflows


def get_artifact_store() -> Any:
    from app.fast_api_app import artifacts

    return artifacts


def get_meeting_store() -> InMemoryMeetingStore:
    return meetings


def get_transcript_store() -> InMemoryTranscriptStore:
    return transcripts


def get_settings() -> MeetingSettings:
    return MeetingSettings()


def get_structured_generator() -> Any:
    return VertexStructuredGenerator()


def get_context_assembler() -> ContextAssembler:
    from app.fast_api_app import contexts

    return contexts


WorkflowEngine = Annotated[Any, Depends(get_workflow_engine)]
ArtifactStore = Annotated[Any, Depends(get_artifact_store)]
MeetingStore = Annotated[InMemoryMeetingStore, Depends(get_meeting_store)]
TranscriptStore = Annotated[InMemoryTranscriptStore, Depends(get_transcript_store)]
Settings = Annotated[MeetingSettings, Depends(get_settings)]
Generator = Annotated[Any, Depends(get_structured_generator)]
Contexts = Annotated[ContextAssembler, Depends(get_context_assembler)]


# --------------------------------------------------------------------------- #
# Request/response models                                                      #
# --------------------------------------------------------------------------- #


class MeetingCreateRequest(BaseModel):
    participant_name: str = Field(default="Client representative", max_length=120)


class ConsentRequest(BaseModel):
    granted: bool
    participant_name: str = Field(min_length=1, max_length=120)
    ai_disclosure_acknowledged: bool = False
    transcription_acknowledged: bool = False


class UtteranceRequest(BaseModel):
    speaker: Speaker
    content: str = Field(min_length=1, max_length=10_000)
    source: UtteranceSource = UtteranceSource.WRITTEN_BRIEF
    dedupe_key: str | None = Field(default=None, max_length=200)
    trace_id: str | None = Field(default=None, max_length=100)


class MeetingView(BaseModel):
    session: MeetingSession
    disclosure: str
    capability: dict[str, Any]
    topics: list[str]


class SpecificationHandoff(BaseModel):
    """Meeting-room view of specification completion.

    `run` is the shared agent-run contract and carries the actual proposal;
    everything below it is meeting evidence the room's panels render.

    Execution stops here. Nothing in this response approves anything: the
    envelope requests the specification approval gate, names no next agent, and
    reports WAITING_FOR_HUMAN, so the next transition requires an authenticated
    human actor.
    """

    run: AgentRunResult
    meeting_id: str
    workflow_state: WorkflowState
    transcript_artifact_id: str
    discovery_record_artifact_id: str
    specification_artifact_id: str
    specification_sha256: str
    lineage: dict[str, list[str]]
    validation_problems: list[str]
    required_sections: list[str]
    utterance_count: int
    # Surfaced so the room's post-meeting panels show generated evidence rather
    # than a client-side keyword guess.
    topics_covered: list[str] = Field(default_factory=list)
    topics_not_covered: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    confirmed_decisions: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    specification_markdown: str = ""


# --------------------------------------------------------------------------- #
# REST                                                                         #
# --------------------------------------------------------------------------- #


@router.get("/v1/meetings/capabilities")
def get_capabilities(settings: Settings) -> dict[str, Any]:
    """Declared before the `{meeting_id}` routes so the literal path wins."""
    return live_capability(settings)


@router.get("/v1/meetings/boundaries")
def get_boundaries() -> list[dict[str, object]]:
    return discovery_boundary_report(WorkflowState.DISCOVERY.value)


@router.post(
    "/v1/workflows/{workflow_id}/meetings",
    response_model=MeetingView,
    status_code=status.HTTP_201_CREATED,
)
def create_meeting(
    workflow_id: str,
    request: MeetingCreateRequest,
    workflows: WorkflowEngine,
    store: MeetingStore,
    settings: Settings,
) -> MeetingView:
    del request  # participant name is captured with consent, not before it
    try:
        workflow = workflows.get(workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc

    capability = live_capability(settings)
    session = store.create(
        workflow_id=workflow_id,
        tenant_id=workflow.tenant_id,
        mode=str(capability["mode"]),
    )
    return MeetingView(
        session=session,
        disclosure=AI_DISCLOSURE,
        capability=capability,
        topics=list(DISCOVERY_TOPICS),
    )


@router.get("/v1/meetings/{meeting_id}", response_model=MeetingView)
def get_meeting(meeting_id: str, store: MeetingStore, settings: Settings) -> MeetingView:
    session = _session_or_404(store, meeting_id)
    return MeetingView(
        session=session,
        disclosure=AI_DISCLOSURE,
        capability=live_capability(settings),
        topics=list(DISCOVERY_TOPICS),
    )


@router.post("/v1/meetings/{meeting_id}/consent", response_model=MeetingSession)
def grant_consent(
    meeting_id: str, request: ConsentRequest, store: MeetingStore
) -> MeetingSession:
    _session_or_404(store, meeting_id)
    try:
        return store.grant_consent(
            meeting_id,
            ConsentRecord(
                granted=request.granted,
                participant_name=request.participant_name,
                ai_disclosure_acknowledged=request.ai_disclosure_acknowledged,
                transcription_acknowledged=request.transcription_acknowledged,
            ),
        )
    except ConsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/v1/meetings/{meeting_id}/transcript")
def get_transcript(
    meeting_id: str, store: MeetingStore, transcript_store: TranscriptStore
) -> dict[str, Any]:
    _session_or_404(store, meeting_id)
    return {
        "meeting_id": meeting_id,
        "finalized": transcript_store.is_finalized(meeting_id),
        "utterances": [
            item.model_dump(mode="json") for item in transcript_store.list(meeting_id)
        ],
    }


@router.post(
    "/v1/meetings/{meeting_id}/utterances", status_code=status.HTTP_201_CREATED
)
def append_utterance(
    meeting_id: str,
    request: UtteranceRequest,
    store: MeetingStore,
    transcript_store: TranscriptStore,
) -> dict[str, Any]:
    session = _session_or_404(store, meeting_id)
    try:
        store.require_consent(meeting_id)
    except ConsentRequired as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except MeetingError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        utterance = transcript_store.append(
            meeting_id=meeting_id,
            workflow_id=session.workflow_id,
            speaker=request.speaker,
            content=request.content,
            source=request.source,
            trace_id=request.trace_id,
            dedupe_key=request.dedupe_key,
        )
    except TranscriptFinalized as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return utterance.model_dump(mode="json")


@router.post("/v1/meetings/{meeting_id}/finalize", response_model=SpecificationHandoff)
def finalize_meeting(
    meeting_id: str,
    store: MeetingStore,
    transcript_store: TranscriptStore,
    workflows: WorkflowEngine,
    artifacts: ArtifactStore,
    generator: Generator,
    contexts: Contexts,
) -> SpecificationHandoff:
    """Finalize the transcript and run the separate structured generation pass.

    The live conversation does not become the specification. This endpoint
    freezes the transcript, then generates the discovery record and the
    specification in a distinct pass over that frozen evidence.
    """
    session = _session_or_404(store, meeting_id)
    if not session.consent_granted:
        raise HTTPException(
            status_code=403,
            detail="This meeting has no recorded consent, so no artifact may be produced.",
        )

    try:
        workflow = workflows.get(session.workflow_id)
    except WorkflowNotFound as exc:
        raise HTTPException(status_code=404, detail="Workflow not found.") from exc

    if workflow.state is not WorkflowState.DISCOVERY:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Specification submission requires the workflow in DISCOVERY; "
                f"it is in {workflow.state.value}."
            ),
        )

    store.end(meeting_id)
    document = transcript_store.finalize(meeting_id, session.workflow_id)

    # The shared assembler is the authority on what Discovery may read. It also
    # re-runs `validate_delegation`, so a workflow that drifted out of a
    # delegable state fails here rather than after the artifacts are written.
    try:
        context = contexts.build(session.workflow_id, ActorRole.DISCOVERY)
    except (ContextBuildError, HandoffDenied) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        transcript_artifact = artifacts.create(
            session.workflow_id,
            ArtifactCreateRequest(
                logical_name="MEETING_TRANSCRIPT",
                kind="application/json",
                content=document.content,
                actor=ActorRole.DISCOVERY,
                idempotency_key=f"{meeting_id}-transcript-v1",
            ),
        )
    except ArtifactError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        record = build_discovery_record(
            context=context, transcript=document, generator=generator
        )
        draft = build_specification_draft(
            context=context, record=record, generator=generator
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Structured generation failed: {exc}",
        ) from exc

    markdown = render_specification(context=context, record=record, draft=draft)
    problems = validate_specification(markdown)

    try:
        record_artifact = artifacts.create(
            session.workflow_id,
            ArtifactCreateRequest(
                logical_name="DISCOVERY_RECORD",
                kind="application/json",
                content=record.as_json(),
                actor=ActorRole.DISCOVERY,
                source_artifact_ids=[transcript_artifact.artifact_id],
                idempotency_key=f"{meeting_id}-discovery-record-v1",
            ),
        )
        specification_artifact = artifacts.create(
            session.workflow_id,
            ArtifactCreateRequest(
                logical_name="SPECIFICATIONS",
                kind="text/markdown",
                content=markdown,
                actor=ActorRole.DISCOVERY,
                source_artifact_ids=[
                    transcript_artifact.artifact_id,
                    record_artifact.artifact_id,
                ],
                idempotency_key=f"{meeting_id}-specifications-v1",
            ),
        )
    except ArtifactError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    # The agent proposes; the deterministic validator decides. Building the
    # envelope before the transition means an illegal proposal - one naming a
    # next agent, or claiming completion instead of waiting - is rejected while
    # the workflow is still in DISCOVERY.
    envelope = HandoffEnvelope(
        workflow_id=session.workflow_id,
        from_agent=ActorRole.DISCOVERY,
        requested_next_agent=None,
        output_artifact_ids=[
            transcript_artifact.artifact_id,
            record_artifact.artifact_id,
            specification_artifact.artifact_id,
        ],
        required_gate=HandoffGate.SPECIFICATION_APPROVAL,
        status=AgentRunStatus.WAITING_FOR_HUMAN,
        trace_id=context.trace_id,
        idempotency_key=f"{meeting_id}-specification-handoff",
    )
    try:
        validate_handoff(workflow, envelope)
    except HandoffDenied as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        result = workflows.transition(
            session.workflow_id,
            TransitionRequest(
                action="submit_specification",
                actor=ActorRole.DISCOVERY,
                idempotency_key=f"{meeting_id}-submit-specification",
                metadata={
                    "meeting_id": meeting_id,
                    "source": "agent_os_meeting_room",
                    "utterance_count": document.utterance_count,
                    "specification_sha256": specification_artifact.sha256,
                    "validation_problems": problems,
                },
            ),
        )
    except TransitionDenied as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "audit_event": exc.audit_event.model_dump(mode="json"),
            },
        ) from exc

    return SpecificationHandoff(
        run=AgentRunResult(
            workflow_id=session.workflow_id,
            agent=ActorRole.DISCOVERY,
            status=AgentRunStatus.WAITING_FOR_HUMAN,
            output_artifact_ids=list(envelope.output_artifact_ids),
            summary=(
                f"Discovery produced SPECIFICATIONS v{specification_artifact.version} from "
                f"{document.utterance_count} recorded utterances. Awaiting human "
                f"specification approval."
            ),
            handoff=envelope,
            trace_id=context.trace_id,
        ),
        meeting_id=meeting_id,
        workflow_state=result.workflow.state,
        transcript_artifact_id=transcript_artifact.artifact_id,
        discovery_record_artifact_id=record_artifact.artifact_id,
        specification_artifact_id=specification_artifact.artifact_id,
        specification_sha256=specification_artifact.sha256,
        lineage={
            "MEETING_TRANSCRIPT": [],
            "DISCOVERY_RECORD": [transcript_artifact.artifact_id],
            "SPECIFICATIONS": [
                transcript_artifact.artifact_id,
                record_artifact.artifact_id,
            ],
        },
        validation_problems=problems,
        required_sections=list(REQUIRED_SECTIONS),
        utterance_count=document.utterance_count,
        topics_covered=record.topics_covered,
        topics_not_covered=record.topics_not_covered,
        unresolved_questions=record.unresolved_questions,
        confirmed_decisions=record.confirmed_decisions,
        assumptions=record.assumptions,
        specification_markdown=markdown,
    )


# --------------------------------------------------------------------------- #
# WebSocket bridge                                                             #
# --------------------------------------------------------------------------- #


TURN_INSTRUCTION = (
    CONVERSATION_INSTRUCTION
    + "\n\nReturn JSON only: {\"question\": str, \"topic\": str}. "
    "Exactly one question."
)


@router.websocket("/v1/meetings/{meeting_id}/live")
async def meeting_live(
    websocket: WebSocket,
    meeting_id: str,
    store: MeetingStore,
    transcript_store: TranscriptStore,
    workflows: WorkflowEngine,
    settings: Settings,
) -> None:
    """Bidirectional meeting channel.

    Client frames: {"type":"audio","data":<b64 pcm16>} | {"type":"text","content":str}
    Server frames: ready | utterance | audio | turn_complete | error

    Consent is enforced before any capture. Google credentials never cross this
    boundary; only PCM and text do.
    """
    await websocket.accept()

    try:
        session = store.get(meeting_id)
    except MeetingNotFound:
        await websocket.send_json({"type": "error", "message": "Unknown meeting."})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if not session.consent_granted:
        await websocket.send_json(
            {
                "type": "error",
                "message": "Consent is required before this meeting can capture audio.",
                "code": "consent_required",
            }
        )
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    capability = live_capability(settings)
    workflow_id = session.workflow_id

    try:
        context = build_discovery_context(workflows.get(workflow_id))
    except Exception:  # pragma: no cover - control plane unavailable
        await websocket.send_json(
            {"type": "error", "message": "Engagement context unavailable."}
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    session = store.mark_connected(meeting_id)
    await websocket.send_json(
        {
            "type": "ready",
            "mode": capability["mode"],
            "capability": capability,
            "reconnect_count": session.reconnect_count,
            "meeting_id": meeting_id,
        }
    )

    # Live session state lives in a dict so the watchdog and the receive loop
    # agree on whether an upstream (billable) session is still open.
    live: dict[str, Any] = {"transport": None, "pump": None, "watchdog": None}
    loop = asyncio.get_running_loop()
    started_at = loop.time()
    activity = {"t": started_at}

    async def emit_utterance(speaker: Speaker, text: str, source: UtteranceSource) -> None:
        utterance = transcript_store.append(
            meeting_id=meeting_id,
            workflow_id=workflow_id,
            speaker=speaker,
            content=text,
            source=source,
        )
        await websocket.send_json(
            {"type": "utterance", "utterance": utterance.model_dump(mode="json")}
        )

    async def release_live(code: str, message: str) -> None:
        """Close the upstream Live session without ending the meeting.

        The transcript stays intact and the client may reconnect. This is what
        keeps an abandoned tab from billing indefinitely.
        """
        transport = live.get("transport")
        if transport is None:
            return
        live["transport"] = None
        pump = live.get("pump")
        live["pump"] = None
        if pump is not None:
            pump.cancel()
        with contextlib.suppress(Exception):
            await transport.close()
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "live_released", "code": code, "message": message}
            )

    async def watchdog() -> None:
        while live.get("transport") is not None:
            await asyncio.sleep(5)
            now = loop.time()
            if now - started_at >= settings.max_session_seconds:
                await release_live(
                    "live_session_cap",
                    f"Live voice stopped at the {settings.max_session_seconds}s "
                    "session cap. The transcript is intact; reconnect to continue.",
                )
                return
            if now - activity["t"] >= settings.idle_timeout_seconds:
                await release_live(
                    "live_idle_timeout",
                    f"Live voice released after {settings.idle_timeout_seconds}s "
                    "idle to protect Google Cloud credits. Reconnect to resume.",
                )
                return

    if capability["live_voice_available"]:
        try:
            transport = GeminiLiveTransport(settings)
            await transport.start(
                system_instruction=build_system_instruction(context),
                opening=opening_utterance(context),
            )
            live["transport"] = transport
        except Exception as exc:  # LiveUnavailable or any transport start failure
            store.mark_failed(meeting_id, str(exc))
            await websocket.send_json(
                {
                    "type": "error",
                    "message": f"Live voice failed to start: {exc}",
                    "code": "live_start_failed",
                }
            )
            live["transport"] = None

    if live.get("transport") is not None:

        async def forward_live() -> None:
            transport = live.get("transport")
            if transport is None:
                return
            async for event in transport.events():
                if event.type is LiveEventType.AUDIO:
                    await websocket.send_json(
                        {
                            "type": "audio",
                            "data": event.audio_b64,
                            "sample_rate": settings.output_sample_rate,
                        }
                    )
                elif event.type is LiveEventType.INPUT_TRANSCRIPT:
                    await emit_utterance(
                        Speaker.CLIENT, event.text, UtteranceSource.LIVE_VOICE
                    )
                elif event.type is LiveEventType.OUTPUT_TRANSCRIPT:
                    await emit_utterance(
                        Speaker.AGENT, event.text, UtteranceSource.LIVE_VOICE
                    )
                elif event.type is LiveEventType.TURN_COMPLETE:
                    await websocket.send_json({"type": "turn_complete"})
                elif event.type is LiveEventType.ERROR:
                    await websocket.send_json({"type": "error", "message": event.text})

        live["pump"] = asyncio.create_task(forward_live())
        live["watchdog"] = asyncio.create_task(watchdog())

    try:
        while True:
            frame = await websocket.receive_json()
            activity["t"] = loop.time()
            kind = frame.get("type")
            transport = live.get("transport")

            if kind == "ping":
                await websocket.send_json({"type": "pong"})
            elif kind == "audio":
                if transport is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "This room is in text fallback mode; audio is not "
                                "being processed."
                            ),
                            "code": "fallback_mode",
                        }
                    )
                    continue
                await transport.send_audio(base64.b64decode(frame.get("data", "")))
            elif kind == "text":
                content = str(frame.get("content", "")).strip()
                if not content:
                    continue
                source = (
                    UtteranceSource.LIVE_VOICE
                    if transport is not None
                    else UtteranceSource.WRITTEN_BRIEF
                )
                await emit_utterance(Speaker.CLIENT, content, source)
                if transport is not None:
                    await transport.send_text(content)
            elif kind == "end":
                break
    except WebSocketDisconnect:
        pass
    except TranscriptFinalized:
        with contextlib.suppress(Exception):
            await websocket.send_json(
                {"type": "error", "message": "This transcript is finalized."}
            )
    finally:
        watchdog_task = live.get("watchdog")
        if watchdog_task is not None:
            watchdog_task.cancel()
        await release_live("session_closed", "Live session closed.")
        with contextlib.suppress(Exception):
            await websocket.close()


def _session_or_404(store: InMemoryMeetingStore, meeting_id: str) -> MeetingSession:
    try:
        return store.get(meeting_id)
    except MeetingNotFound as exc:
        raise HTTPException(status_code=404, detail="Meeting not found.") from exc
