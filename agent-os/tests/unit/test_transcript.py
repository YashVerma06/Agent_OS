from __future__ import annotations

import json

import pytest

from app.services.transcript import (
    InMemoryTranscriptStore,
    Speaker,
    TranscriptFinalized,
    UtteranceSource,
    transcript_as_dialogue,
)

MEETING = "meeting-1"
WORKFLOW = "workflow-1"


def append(store: InMemoryTranscriptStore, content: str, **kwargs):
    params = {
        "meeting_id": MEETING,
        "workflow_id": WORKFLOW,
        "speaker": Speaker.CLIENT,
        "content": content,
        "source": UtteranceSource.LIVE_VOICE,
    }
    params.update(kwargs)
    return store.append(**params)


def test_backend_assigns_sequence_numbers_from_one() -> None:
    store = InMemoryTranscriptStore()
    first = append(store, "We manage rental properties.")
    second = append(store, "Tenants submit maintenance issues.", speaker=Speaker.AGENT)
    third = append(store, "Managers update the status.")

    assert [first.sequence_number, second.sequence_number, third.sequence_number] == [1, 2, 3]
    assert [item.sequence_number for item in store.list(MEETING)] == [1, 2, 3]


def test_every_utterance_carries_the_required_fields() -> None:
    store = InMemoryTranscriptStore()
    utterance = append(store, "Tenants need a form.")

    for field in (
        "utterance_id",
        "workflow_id",
        "meeting_id",
        "sequence_number",
        "speaker",
        "timestamp",
        "content",
        "source",
        "trace_id",
    ):
        assert getattr(utterance, field) is not None, field


def test_explicit_dedupe_key_collapses_a_reconnect_replay() -> None:
    """A client that replays after reconnecting must not duplicate the transcript."""
    store = InMemoryTranscriptStore()
    first = append(store, "Severity levels matter.", dedupe_key="client-turn-7")
    replay = append(store, "Severity levels matter.", dedupe_key="client-turn-7")

    assert replay.utterance_id == first.utterance_id
    assert replay.sequence_number == first.sequence_number
    assert len(store.list(MEETING)) == 1


def test_identical_content_is_collapsed_without_an_explicit_key() -> None:
    store = InMemoryTranscriptStore()
    append(store, "Please repeat that.")
    append(store, "Please repeat that.")
    assert len(store.list(MEETING)) == 1


def test_same_text_from_a_different_speaker_is_a_distinct_utterance() -> None:
    store = InMemoryTranscriptStore()
    append(store, "Confirmed.", speaker=Speaker.CLIENT)
    append(store, "Confirmed.", speaker=Speaker.AGENT)
    assert len(store.list(MEETING)) == 2


def test_meetings_do_not_share_a_sequence_space() -> None:
    store = InMemoryTranscriptStore()
    append(store, "First meeting line.")
    other = store.append(
        meeting_id="meeting-2",
        workflow_id="workflow-2",
        speaker=Speaker.CLIENT,
        content="Second meeting line.",
        source=UtteranceSource.LIVE_VOICE,
    )
    assert other.sequence_number == 1
    assert len(store.list(MEETING)) == 1


def test_empty_content_is_rejected() -> None:
    store = InMemoryTranscriptStore()
    with pytest.raises(ValueError):
        append(store, "   ")


def test_finalize_freezes_the_transcript() -> None:
    store = InMemoryTranscriptStore()
    append(store, "We need a portal.")
    document = store.finalize(MEETING, WORKFLOW)

    assert document.utterance_count == 1
    assert store.is_finalized(MEETING)
    with pytest.raises(TranscriptFinalized):
        append(store, "One more thought.")


def test_finalize_is_idempotent() -> None:
    store = InMemoryTranscriptStore()
    append(store, "We need a portal.")
    first = store.finalize(MEETING, WORKFLOW)
    second = store.finalize(MEETING, WORKFLOW)
    assert first.content == second.content
    assert first.ended_at == second.ended_at


def test_finalized_content_is_valid_json_with_every_field() -> None:
    store = InMemoryTranscriptStore()
    append(store, "Tenants report issues.")
    append(store, "Understood.", speaker=Speaker.AGENT)
    document = store.finalize(MEETING, WORKFLOW)

    payload = json.loads(document.content)
    assert payload["artifact"] == "MEETING_TRANSCRIPT"
    assert payload["utterance_count"] == 2
    for entry in payload["utterances"]:
        assert set(entry) == {
            "utterance_id",
            "workflow_id",
            "meeting_id",
            "sequence_number",
            "speaker",
            "timestamp",
            "content",
            "source",
            "trace_id",
        }


def test_empty_meeting_still_finalizes() -> None:
    store = InMemoryTranscriptStore()
    document = store.finalize(MEETING, WORKFLOW)
    assert document.utterance_count == 0
    assert document.started_at is None


def test_dialogue_rendering_omits_system_events() -> None:
    store = InMemoryTranscriptStore()
    append(store, "Client speaking.")
    append(store, "Connection restored.", speaker=Speaker.SYSTEM,
           source=UtteranceSource.SYSTEM_EVENT)
    append(store, "Agent replying.", speaker=Speaker.AGENT)

    dialogue = transcript_as_dialogue(store.list(MEETING))
    assert "Connection restored." not in dialogue
    assert "Client: Client speaking." in dialogue
    assert "Discovery Agent: Agent replying." in dialogue
