from __future__ import annotations

import asyncio
import os
import secrets
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import TypeAdapter, ValidationError

from quorumy.accounts import (
    AccountCredentials,
    AccountStore,
    User,
    account_database,
    user_database,
)
from quorumy.minutes import Review, calendar_export, markdown_export
from quorumy.providers import LiveBackend
from quorumy.settings import AppSettings
from quorumy.workspace.adapters.huggingface_stt import HuggingFaceSTT
from quorumy.workspace.adapters.huggingface_tts import HuggingFaceTTS
from quorumy.workspace.adapters.sqlite import SQLiteStore
from quorumy.workspace.adapters.stt_registry import STTRegistry
from quorumy.workspace.adapters.tts_registry import TTSRegistry
from quorumy.workspace.config import (
    PROJECT_ROOT,
    AppConfig,
    ProductConfig,
    account_config,
    load_config,
    load_product,
    secret,
)
from quorumy.workspace.core.coordinator import Coordinator
from quorumy.workspace.core.engine import QuorumyEngine
from quorumy.workspace.core.models import SessionStatus, now_iso
from quorumy.workspace.core.speaker import SpeakerAgent
from quorumy.workspace.core.tools import ToolRegistry, ToolSpec
from quorumy.workspace.integrations import register_research
from quorumy.workspace.llm import ChatGenerator
from quorumy.workspace.runtime import SemanticDecision, WorkspaceEngine

from .hub import WebSocketHub
from .schemas import (
    BackendHello,
    BoardCurate,
    BootstrapResponse,
    ClientHello,
    ClientMessage,
    CommitmentSettle,
    FloorChanged,
    FloorDismiss,
    FloorGrant,
    PlaybackChanged,
    ProtocolDocument,
    SessionCommand,
    SessionLanguage,
    SessionOpen,
    SessionRenameRequest,
    SessionStart,
    TaskCancel,
    TranscriptInject,
    VoiceModeCommand,
)

CLIENT_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
LOCAL_HOSTS = {"127.0.0.1", "localhost", "testserver", "::1"}


def create_app() -> FastAPI:
    config, product = load_config(), load_product()
    hub = WebSocketHub()
    accounts = AccountStore(account_database(PROJECT_ROOT))
    auth_required = os.environ.get("QUORUMY_AUTH", "required") != "off"
    allowed_hosts = (
        [
            item.strip()
            for item in os.environ.get("QUORUMY_ALLOWED_HOSTS", "*").split(",")
        ]
        if auth_required
        else list(LOCAL_HOSTS)
    )
    shared_room: Room | None = None
    rooms: dict[str, Room] = {}
    rooms_guard = asyncio.Lock()

    async def close_room(room: Room) -> None:
        await room.resources.engine.stop()
        await room.resources.engine.backend.close()

    async def ensure_room(user: User) -> Room:
        signature = (user.hf_token, user.model)
        async with rooms_guard:
            current = rooms.get(user.id)
            if current is not None and current.signature == signature:
                current.user = user
                return current
            if current is not None:
                await close_room(current)
            user_hub = WebSocketHub()
            user_config = account_config(
                config,
                model=user.model,
                database_path=user_database(PROJECT_ROOT, user.id),
            )
            user_resources = compose(
                product,
                user_config,
                user_hub,
                secrets={"HF_TOKEN": user.hf_token},
            )
            await user_resources.engine.start()
            room = Room(
                user_resources,
                user_hub,
                secrets.token_urlsafe(32),
                user=user,
                signature=signature,
            )
            rooms[user.id] = room
            return room

    async def room_for_host(host: str, session_cookie: str) -> Room:
        if shared_room is None:
            raise HTTPException(503, "The server is still starting.")
        if session_cookie:
            user = await accounts.user_for_session(session_cookie)
            if user is not None:
                return await ensure_room(user)
        if auth_required and host != "testclient":
            raise HTTPException(401, "Sign in.")
        if host in {"127.0.0.1", "::1", "testclient"}:
            return shared_room
        raise HTTPException(403, "Open Quorumy on this computer.")

    def open_paths() -> set[str]:
        return {"/v1/bootstrap", "/v1/protocol", "/v1/register", "/v1/login"}

    @asynccontextmanager
    async def lifespan(application):
        nonlocal shared_room
        await accounts.open()
        resources = compose(product, config, hub)
        shared_room = Room(resources, hub, secrets.token_urlsafe(32))
        application.state.resources = resources
        await resources.engine.start()
        try:
            yield
        finally:
            if shared_room is not None:
                await close_room(shared_room)
            for room in list(rooms.values()):
                await close_room(room)
            rooms.clear()
            await accounts.close()

    app = FastAPI(title=product.display_name, version="0.4.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["*"])

    @app.middleware("http")
    async def authorize(request: Request, call_next):
        origin = request.headers.get("origin")
        if (
            origin and urlsplit(origin).netloc != request.headers.get("host")
        ) or request.headers.get("sec-fetch-site") == "cross-site":
            return Response(status_code=403)
        if request.url.path.startswith("/v1/") and request.url.path not in open_paths():
            try:
                room = await room_for_host(
                    request.client.host if request.client else "",
                    request.cookies.get("quorumy_session", ""),
                )
            except HTTPException as error:
                return Response(status_code=error.status_code)
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
            if not _same_secret(supplied, room.token):
                return Response(status_code=403)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
            }
        )
        return response

    def remember(response: Response, request: Request, token: str) -> None:
        response.set_cookie(
            "quorumy_session",
            token,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https",
            max_age=60 * 60 * 24 * 30,
            path="/",
        )

    @app.post("/v1/register")
    async def register(body: AccountCredentials, request: Request, response: Response):
        try:
            user, session = await accounts.register(body)
            await ensure_room(user)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        remember(response, request, session)
        return {"ok": True, "name": user.name}

    @app.post("/v1/login")
    async def login(body: AccountCredentials, request: Request, response: Response):
        try:
            user, session = await accounts.login(body)
            await ensure_room(user)
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        remember(response, request, session)
        return {"ok": True, "name": user.name}

    @app.get("/health")
    async def health():
        if shared_room is None:
            return {"status": "starting"}
        return {
            "status": "ok",
            "process": shared_room.resources.engine.state.process_status,
        }

    @app.get("/v1/bootstrap", response_model=BootstrapResponse)
    async def bootstrap(request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        engine = room.resources.engine
        return BootstrapResponse(
            **product.model_dump(),
            active_model=engine.config.llm.active_model,
            models=[item.id for item in engine.config.llm.models],
            access_token=room.token,
            account_name=room.user.name if room.user else "",
            hf_ready=bool(room.user and room.user.hf_token),
            state=engine.client_state(),
            sessions=await engine.list_sessions(),
        )

    @app.get("/v1/protocol", response_model=ProtocolDocument)
    async def protocol_document():
        return ProtocolDocument(
            client=ClientHello(
                type="client.hello",
                protocol_version=product.protocol_version,
                client_id="example",
            ),
            server=BackendHello(
                type="backend.hello",
                project_id=product.project_id,
                protocol_version=product.protocol_version,
            ),
        )

    @app.patch("/v1/sessions/{session_id}")
    async def rename(session_id: str, body: SessionRenameRequest, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        if not await room.resources.engine.rename_session(session_id, body.title):
            raise HTTPException(404, "Session not found.")
        return {"updated": True}

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    async def delete(session_id: str, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        async with room.lock:
            if not await room.resources.engine.delete_session(session_id):
                raise HTTPException(404, "Session not found.")
        return Response(status_code=204)

    @app.get("/v1/sessions/{session_id}/export")
    async def export_session(session_id: str, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        content = await room.resources.engine.export_session(session_id)
        if content is None:
            raise HTTPException(404, "Session not found.")
        return Response(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="{session_id}.md"'},
        )

    @app.get("/v1/sessions/{session_id}/journal")
    async def journal(session_id: str, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        if await room.resources.engine.store.load(session_id) is None:
            raise HTTPException(404, "Session not found.")
        return await room.resources.engine.store.journal(session_id)

    @app.post("/v1/minutes")
    async def generate_minutes(request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        task = room.resources.engine._spawn(room.resources.engine.generate_minutes())
        try:
            return await task
        except asyncio.CancelledError:
            raise HTTPException(409, "Analysis stopped because the session was paused.")
        except ValueError as error:
            raise HTTPException(409, str(error)) from error
        except Exception as error:
            raise HTTPException(502, "Preparation failed. Try again.") from error

    @app.patch("/v1/minutes")
    async def review_minutes(body: Review, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        try:
            return await room.resources.engine.review_minutes(body)
        except ValueError as error:
            raise HTTPException(409, str(error)) from error

    @app.get("/v1/sessions/{session_id}/minutes/{format}")
    async def export_minutes(session_id: str, format: str, request: Request):
        room = await room_for_host(
            request.client.host if request.client else "",
            request.cookies.get("quorumy_session", ""),
        )
        state = await room.resources.engine.store.load(session_id)
        if state is None or not state.minutes or format not in {"md", "ics"}:
            raise HTTPException(404, "Commitments not found.")
        if format == "ics" and state.minutes.get("stale"):
            raise HTTPException(
                409, "Actualisez les engagements avant l’export calendrier."
            )
        content = (
            calendar_export(state.minutes, session_id)
            if format == "ics"
            else markdown_export(state.minutes, state.title)
        )
        return Response(
            content,
            media_type="text/calendar" if format == "ics" else "text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="{session_id}.{format}"'
            },
        )

    @app.websocket("/v1/live")
    async def live(websocket: WebSocket):
        origin = urlsplit(websocket.headers.get("origin", ""))
        if origin.scheme not in {
            "http",
            "https",
        } or origin.netloc != websocket.headers.get("host"):
            await websocket.close(code=1008)
            return
        await websocket.accept()
        joined = False
        room: Room | None = None
        try:
            room = await room_for_host(
                websocket.client.host if websocket.client else "",
                websocket.cookies.get("quorumy_session", ""),
            )
            hello = CLIENT_ADAPTER.validate_python(
                await asyncio.wait_for(websocket.receive_json(), 10)
            )
            if not isinstance(hello, ClientHello) or not _same_secret(
                hello.access_token, room.token
            ):
                await websocket.close(code=1008)
                return
            if hello.protocol_version != product.protocol_version:
                raise ValueError("Reload the page to use the new version.")
            async with room.lock:
                if (
                    room.controller is not None
                    and room.controller_id != hello.client_id
                ):
                    raise ValueError(
                        "Quorumy is already open in another tab. Close it and try again."
                    )
                if room.controller is not None:
                    # A reconnect from the same tab can replace a half-open socket.
                    # The old handler must never pause or command its replacement.
                    room.hub.disconnect(room.controller)
                    with suppress(Exception):
                        await asyncio.wait_for(
                            room.controller.close(code=4000), timeout=1
                        )
                    await room.resources.engine.client_disconnected()
                room.controller, room.controller_id = websocket, hello.client_id
                room.hub.attach(websocket)
                joined = True
                await websocket.send_json(
                    {
                        "type": "backend.hello",
                        "project_id": product.project_id,
                        "protocol_version": product.protocol_version,
                    }
                )
                await room.resources.engine._broadcast_state()
            while True:
                frame = await websocket.receive()
                if (
                    frame["type"] == "websocket.disconnect"
                    or room.controller is not websocket
                ):
                    break
                try:
                    if frame.get("bytes") is not None:
                        await room.resources.engine.ingest_audio(frame["bytes"])
                        continue
                    raw = frame.get("text", "")
                    if len(raw) > 64000:
                        raise ValueError("Message is too large.")
                    message = CLIENT_ADAPTER.validate_json(raw)
                    if isinstance(message, BoardCurate):
                        if not room.resources.engine.state.consent_at:
                            raise ValueError(
                                "Resume the session before organizing the board."
                            )
                        room.resources.engine._spawn(
                            room.resources.engine.curate_board()
                        )
                    else:
                        async with room.lock:
                            if room.controller is not websocket:
                                break
                            await dispatch_client_message(
                                room.resources.engine, message
                            )
                except (ValueError, ValidationError) as error:
                    await websocket.send_json(
                        {
                            "type": "protocol.error",
                            "code": "COMMAND_REJECTED",
                            "message": "Check the fields that were sent."
                            if isinstance(error, ValidationError)
                            else str(error),
                        }
                    )
                except Exception:
                    await websocket.send_json(
                        {
                            "type": "protocol.error",
                            "code": "COMMAND_FAILED",
                            "message": "This action failed. Your data is still available.",
                        }
                    )
        except (WebSocketDisconnect, RuntimeError, TimeoutError):
            pass
        except HTTPException as error:
            with suppress(Exception):
                await websocket.send_json(
                    {
                        "type": "protocol.error",
                        "code": "CONNECTION_REJECTED",
                        "message": error.detail
                        if isinstance(error.detail, str)
                        else "Connection refused.",
                    }
                )
            await websocket.close(code=1008)
        except (ValueError, ValidationError) as error:
            await websocket.send_json(
                {
                    "type": "protocol.error",
                    "code": "CONNECTION_REJECTED",
                    "message": str(error)
                    if not isinstance(error, ValidationError)
                    else "Connexion invalide.",
                }
            )
            await websocket.close(code=1008)
        finally:
            if joined and room is not None:
                async with room.lock:
                    room.hub.disconnect(websocket)
                    if room.controller is websocket:
                        try:
                            await room.resources.engine.client_disconnected()
                        finally:
                            room.controller = room.controller_id = None

    frontend = Path(
        os.environ.get(
            "QUORUMY_FRONTEND_DIR",
            Path(__file__).resolve().parents[4] / "frontend" / "dist",
        )
    )
    if (frontend / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="interface")
    return app


class Room:
    def __init__(
        self,
        resources: Resources,
        hub: WebSocketHub,
        token: str,
        user: User | None = None,
        signature: tuple[str, str] = ("", ""),
    ) -> None:
        self.resources = resources
        self.hub = hub
        self.token = token
        self.user = user
        self.signature = signature
        self.lock = asyncio.Lock()
        self.controller: WebSocket | None = None
        self.controller_id: str | None = None


def _same_secret(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)


class Resources:
    def __init__(self, engine: QuorumyEngine) -> None:
        self.engine = engine


def _stt_adapter(provider, secrets_map: dict[str, str]):
    return HuggingFaceSTT(
        provider,
        secrets_map.get(provider.secret_env) or secret(provider.secret_env),
    )


def _tts_adapter(provider, secrets_map: dict[str, str]):
    return HuggingFaceTTS(
        provider,
        secrets_map.get(provider.secret_env) or secret(provider.secret_env),
    )


def compose(
    product: ProductConfig,
    config: AppConfig,
    hub: WebSocketHub,
    secrets: dict[str, str] | None = None,
) -> Resources:
    secrets_map = secrets or {}
    generator = ChatGenerator(config.llm, secrets=secrets_map)
    decision = SemanticDecision(generator)
    backend = LiveBackend(AppSettings(), generator=generator)
    stt_providers = {
        provider.id: _stt_adapter(provider, secrets_map)
        for provider in config.voice.stt.providers
    }
    stt = STTRegistry(config.voice.stt, stt_providers)
    tts = TTSRegistry(
        config.voice.tts,
        {
            provider.id: _tts_adapter(provider, secrets_map)
            for provider in config.voice.tts.providers
        },
    )
    tools = ToolRegistry(config.policy.research_max_concurrency)

    async def list_capabilities(_arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ok",
            "capabilities": tools.prompt_catalog(),
            "message": (
                "These are the capabilities currently registered and available to Quorumy."
            ),
        }

    tools.register(
        ToolSpec(
            name="system_capabilities",
            description=(
                "List Quorumy's currently registered tools and their effects. Use this when the room asks "
                "what Quorumy can do, which tools are available, or whether a capability exists."
            ),
            effect="read",
            input_schema={"type": "object", "properties": {}},
            handler=list_capabilities,
        )
    )
    research_health = register_research(tools, backend)
    coordinator = Coordinator(generator, tools, config.policy, config.llm.roles)
    speaker = SpeakerAgent(generator, config.llm.roles.speaker)
    store = SQLiteStore(config.storage.resolved_path())
    engine = WorkspaceEngine(
        backend=backend,
        product=product,
        config=config,
        store=store,
        decision=decision,
        speaker=speaker,
        coordinator=coordinator,
        stt=stt,
        tts=tts,
        publish=hub.broadcast,
        tool_health=research_health,
    )
    return Resources(engine)


async def dispatch_client_message(
    engine: QuorumyEngine, message: ClientMessage
) -> None:
    if isinstance(message, SessionStart):
        await engine.start_session(message.model_dump(mode="json", exclude={"type"}))
    elif isinstance(message, SessionOpen):
        if not await engine.open_session(message.session_id):
            raise ValueError("Session not found.")
    elif isinstance(message, SessionLanguage):
        await engine.set_language(message.language)
    elif isinstance(message, VoiceModeCommand):
        await engine.set_voice_mode(message.mode)
    elif isinstance(message, BoardCurate):
        await engine.curate_board()
    elif isinstance(message, TaskCancel):
        await engine.cancel_mission(message.task_id)
    elif isinstance(message, SessionCommand):
        if message.command == "resume":
            if message.consent is not True:
                raise ValueError("Confirm agreement before resuming.")
            engine.state.consent_at = now_iso()
        await engine.session_command(message.command)
    elif isinstance(message, FloorChanged):
        await engine.floor_changed(message.busy)
    elif isinstance(message, FloorGrant):
        await engine.grant_floor()
    elif isinstance(message, FloorDismiss):
        await engine.dismiss_hand()
    elif isinstance(message, CommitmentSettle):
        await engine.settle_commitment(message.session_id, message.note_id)
    elif isinstance(message, TranscriptInject):
        if engine.state.session_status != SessionStatus.LISTENING:
            raise ValueError("Resume the session before sending a message.")
        await engine.commit_utterance(message.text, source="manual")
    elif isinstance(message, PlaybackChanged):
        await engine.playback_changed(message.speech_id, message.type.split(".", 1)[1])
    else:
        return
