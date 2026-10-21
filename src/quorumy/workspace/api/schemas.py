from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from quorumy.workspace.core.models import QuorumyState, SessionSummary
from quorumy.workspace.languages import QuorumyLanguage


class WireModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientHello(WireModel):
    type: Literal["client.hello"]
    protocol_version: int
    client_id: str
    access_token: str = ""
    capabilities: dict[str, bool] = Field(default_factory=dict)


class SessionStart(WireModel):
    type: Literal["session.start"]
    language: QuorumyLanguage = "en"
    capture_mode: Literal["text", "microphone", "system", "mixed"] = "text"
    output_mode: Literal["local_only"] = "local_only"
    consent: StrictBool = False


class SessionCommand(WireModel):
    type: Literal["session.command"]
    command: Literal["pause", "resume", "stop"]
    consent: StrictBool = False


class SessionOpen(WireModel):
    type: Literal["session.open"]
    session_id: str


class SessionLanguage(WireModel):
    type: Literal["session.language"]
    language: QuorumyLanguage


class VoiceModeCommand(WireModel):
    type: Literal["voice.mode"]
    mode: Literal["active", "muted"]


class BoardCurate(WireModel):
    type: Literal["board.curate"]


class TaskCancel(WireModel):
    type: Literal["task.cancel"]
    task_id: str = Field(min_length=1, max_length=100)


class FloorChanged(WireModel):
    type: Literal["floor.changed"]
    busy: bool


class FloorGrant(WireModel):
    type: Literal["floor.grant"]


class FloorDismiss(WireModel):
    type: Literal["floor.dismiss"]


class CommitmentSettle(WireModel):
    type: Literal["commitment.settle"]
    session_id: str
    note_id: str


class CaptureChanged(WireModel):
    type: Literal["capture.changed"]
    source: Literal["microphone", "system"]
    status: Literal["active", "denied", "ended", "unavailable"]


class TranscriptInject(WireModel):
    type: Literal["transcript.inject"]
    text: str = Field(min_length=1, max_length=12000)


class PlaybackChanged(WireModel):
    type: Literal["playback.started", "playback.finished", "playback.interrupted"]
    speech_id: str


ClientMessage = Annotated[
    ClientHello
    | BoardCurate
    | TaskCancel
    | SessionStart
    | SessionOpen
    | SessionLanguage
    | VoiceModeCommand
    | SessionCommand
    | FloorChanged
    | FloorGrant
    | FloorDismiss
    | CommitmentSettle
    | CaptureChanged
    | TranscriptInject
    | PlaybackChanged,
    Field(discriminator="type"),
]


class BootstrapResponse(WireModel):
    access_token: str
    project_id: str
    display_name: str
    companion_name: str
    protocol_version: int
    active_model: str
    models: list[str]
    account_name: str = ""
    hf_ready: bool = False
    state: QuorumyState
    sessions: list[SessionSummary]


class SessionRenameRequest(WireModel):
    title: str = Field(min_length=1, max_length=80)


class BackendHello(WireModel):
    type: Literal["backend.hello"]
    project_id: str
    protocol_version: int


class StateSnapshot(WireModel):
    type: Literal["state.snapshot"]
    state: QuorumyState
    sessions: list[SessionSummary]


class TranscriptPartial(WireModel):
    type: Literal["transcript.partial"]
    text: str


class SpeechAudio(WireModel):
    data_base64: str
    format: str
    sample_rate: int


class SpeechAuthorized(WireModel):
    type: Literal["speech.authorized"]
    speech_id: str
    text: str
    reason: str
    audio: SpeechAudio | None = None
    playback: Literal["server", "browser"] = "server"


class SpeechStop(WireModel):
    type: Literal["speech.stop"]
    speech_id: str
    reason: str


class SpeechAudioChunk(WireModel):
    type: Literal["speech.audio.chunk"]
    speech_id: str
    sequence: int
    data_base64: str
    format: str
    sample_rate: int


class SpeechAudioEnd(WireModel):
    type: Literal["speech.audio.end"]
    speech_id: str


class SpeechSubtitle(WireModel):
    type: Literal["speech.subtitle"]
    speech_id: str
    text: str
    segment_index: int = 0
    start_s: float = 0
    stop_s: float = 0
    final: bool = False


class PresenceCue(WireModel):
    type: Literal["presence.cue"]
    cue: Literal["thinking", "progress"]
    label: str
    audio: SpeechAudio | None = None


class ProtocolError(WireModel):
    type: Literal["protocol.error"]
    code: str
    message: str


ServerMessage = Annotated[
    BackendHello
    | StateSnapshot
    | TranscriptPartial
    | SpeechAuthorized
    | SpeechStop
    | SpeechAudioChunk
    | SpeechAudioEnd
    | SpeechSubtitle
    | PresenceCue
    | ProtocolError,
    Field(discriminator="type"),
]


class ProtocolDocument(WireModel):
    client: ClientMessage
    server: ServerMessage
