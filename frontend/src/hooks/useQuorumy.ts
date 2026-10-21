import { useEffect, useRef, useState } from "react";
import {
  AuthRequired,
  bootstrap,
  deleteQuorumySession,
  exportQuorumySession,
  liveSocket,
  loginAccount,
  registerAccount,
  renameQuorumySession,
  send,
  type AccountBody,
} from "../api";
import { AudioBridge, type CaptureMode } from "../audio";
import {
  promptBarVisibleByDefault,
  savePromptBarVisibility,
} from "../preferences";
import { CLIENT_PROTOCOL_VERSION } from "../protocol";
import type {
  QuorumyLanguage,
  QuorumyState,
  ServerMessage,
  SessionSummary,
  SpeechAuthorized,
} from "../protocol";
import type { WorkspaceView } from "../components/WorkspaceNavigation";
type AudioStatus = "idle" | "requesting" | "active" | "paused" | "error";
export function useQuorumy() {
  const [state, setState] = useState<QuorumyState>();
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [partial, setPartial] = useState("");
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [connectionAttempt, setConnectionAttempt] = useState(0);
  const retryCountRef = useRef(0);
  const clientIdRef = useRef(crypto.randomUUID());
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(
    undefined,
  );
  const [view, setView] = useState<WorkspaceView>("notes");
  const [displayName, setDisplayName] = useState("Quorumy");
  const [captureMode, setCaptureMode] = useState<CaptureMode>("text");
  const [language, setLanguage] = useState<QuorumyLanguage>("fr");
  const [manual, setManual] = useState("");
  const [error, setError] = useState("");
  const [audioStatus, setAudioStatus] = useState<AudioStatus>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
  const [promptBarVisible, setPromptBarVisible] = useState(
    promptBarVisibleByDefault,
  );
  const [consent, setConsent] = useState(false);
  const [resumePrompt, setResumePrompt] = useState(false);
  const [starting, setStarting] = useState(false);
  const [needsAccount, setNeedsAccount] = useState(false);
  const needsAccountRef = useRef(false);
  const languageRef = useRef(language);
  languageRef.current = language;
  const captureReadyRef = useRef(false);
  const [subtitle, setSubtitle] = useState("");
  const socketRef = useRef<WebSocket | undefined>(undefined);
  const audioRef = useRef<AudioBridge | undefined>(undefined);
  const activeSpeechRef = useRef<string | null>(null);
  const streamStartedRef = useRef(false);
  const subtitlesEnabledRef = useRef(true);

  useEffect(() => {
    let active = true;
    setConnected(false);
    const bootstrapRequest = bootstrap();
    void bootstrapRequest
      .then((payload) => {
        if (!active) return;
        if (payload.protocol_version !== CLIENT_PROTOCOL_VERSION) {
          throw new Error(
            `Frontend protocol ${CLIENT_PROTOCOL_VERSION} does not match backend protocol ${payload.protocol_version}. Restart the backend and reload.`,
          );
        }
        document.title = payload.display_name;
        setDisplayName(payload.display_name);
        setState(payload.state);
        setSessions(payload.sessions);
        const initialLanguage = payload.state.language ?? "en";
        setLanguage(initialLanguage);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        if (reason instanceof AuthRequired) {
          needsAccountRef.current = true;
          setNeedsAccount(true);
          setError("");
          return;
        }
        setError(String(reason));
      });
    const socket = liveSocket();
    socketRef.current = socket;
    const audio = new AudioBridge(
      (chunk) => {
        if (captureReadyRef.current && socket.readyState === WebSocket.OPEN)
          socket.send(chunk);
      },
      (busy) => {
        send(socket, { type: "floor.changed", busy });
        if (busy) audio.stopCue();
      },
      setAudioLevel,
      () => {
        const speechId = activeSpeechRef.current;
        activeSpeechRef.current = null;
        streamStartedRef.current = false;
        if (speechId && socket.readyState === WebSocket.OPEN) {
          send(socket, { type: "playback.interrupted", speech_id: speechId });
        }
      },
      () => {
        captureReadyRef.current = false;
        setAudioStatus("paused");
        setConsent(false);
        send(socket, {
          type: "session.command",
          command: "pause",
          consent: false,
        });
      },
    );
    audioRef.current = audio;
    const speechStartedAt = new Map<string, number>();
    const pendingSubtitles = new Map<
      string,
      Array<{ text: string; start: number }>
    >();
    const subtitleTimers = new Set<ReturnType<typeof setTimeout>>();
    const scheduleSubtitle = (
      speechId: string,
      text: string,
      startSeconds: number,
    ) => {
      const startedAt = speechStartedAt.get(speechId);
      if (startedAt === undefined) {
        const pending = pendingSubtitles.get(speechId) ?? [];
        pending.push({ text, start: startSeconds });
        pendingSubtitles.set(speechId, pending);
        return;
      }
      const elapsed = performance.now() - startedAt;
      const delay = Math.max(0, startSeconds * 1000 - elapsed);
      const timer = setTimeout(() => {
        subtitleTimers.delete(timer);
        if (activeSpeechRef.current === speechId) setSubtitle(text);
      }, delay);
      subtitleTimers.add(timer);
    };
    socket.onopen = async () => {
      try {
        const payload = await bootstrapRequest;
        if (payload.protocol_version !== CLIENT_PROTOCOL_VERSION) {
          socket.close(1008, "Protocol mismatch");
          throw new Error("Quorumy was updated. Reload this page.");
        }
        if (!active || socket.readyState !== WebSocket.OPEN) return;
        send(socket, {
          type: "client.hello",
          protocol_version: CLIENT_PROTOCOL_VERSION,
          client_id: clientIdRef.current,
          access_token: payload.access_token,
          capabilities: { audio_capture: true, audio_playback: true },
        });
      } catch (reason) {
        if (reason instanceof AuthRequired) {
          needsAccountRef.current = true;
          setNeedsAccount(true);
          setError("");
          socket.close(1008);
          return;
        }
        setError(reason instanceof Error ? reason.message : String(reason));
        socket.close();
      }
    };
    socket.onclose = (event) => {
      if (!active) return;
      setConnected(false);
      setStarting(false);
      setConsent(false);
      captureReadyRef.current = false;
      audio.stopPlayback();
      activeSpeechRef.current = null;
      streamStartedRef.current = false;
      setSubtitle("");
      setPartial("");
      void audio.stopCapture();
      setAudioStatus("paused");
      const canRetry = event.code !== 1008 && !needsAccountRef.current;
      setReconnecting(canRetry);
      if (canRetry) {
        const delay = Math.min(
          10000,
          500 * 2 ** Math.min(retryCountRef.current++, 5),
        );
        retryTimerRef.current = setTimeout(() => {
          if (active) setConnectionAttempt((attempt) => attempt + 1);
        }, delay);
      }
    };
    socket.onmessage = (event) => {
      const message = JSON.parse(String(event.data)) as ServerMessage;
      if (!active) return;
      if (message.type === "backend.hello") {
        setConnected(true);
        setReconnecting(false);
        retryCountRef.current = 0;
        setError("");
      }
      if (message.type === "state.snapshot") {
        const listening = message.state.session_status === "listening";
        captureReadyRef.current = listening;
        if (!listening) {
          void audio.stopCapture();
          setAudioStatus("paused");
          setConsent(false);
        }
        setStarting(false);
        setCaptureMode(
          message.state.session_id
            ? (message.state.capture_mode ?? "text")
            : "text",
        );
        setPartial(message.state.partial ?? "");
        setState(message.state);
        setSessions(message.sessions);
        const currentLanguage = message.state.language ?? "en";
        setLanguage(currentLanguage);
      } else if (message.type === "transcript.partial")
        setPartial(message.text);
      else if (message.type === "speech.stop") {
        if (activeSpeechRef.current === message.speech_id) {
          audio.stopPlayback();
          setSubtitle("");
          streamStartedRef.current = false;
          activeSpeechRef.current = null;
        }
        speechStartedAt.delete(message.speech_id);
        pendingSubtitles.delete(message.speech_id);
      } else if (message.type === "speech.authorized") {
        if (message.playback === "browser") {
          speakLocally(
            socket,
            message.speech_id,
            message.text,
            languageRef.current,
            setSubtitle,
            activeSpeechRef,
          );
          return;
        }
        if (activeSpeechRef.current !== message.speech_id) {
          audio.stopPlayback();
          streamStartedRef.current = false;
        }
        void playSpeech(socket, audio, message, activeSpeechRef, () =>
          setSubtitle(""),
        );
      } else if (message.type === "speech.subtitle") {
        if (!message.final && message.text) {
          scheduleSubtitle(
            message.speech_id,
            message.text,
            message.start_s ?? 0,
          );
        }
      } else if (message.type === "speech.audio.chunk") {
        if (activeSpeechRef.current === message.speech_id) {
          if (audio.participantSpeaking) {
            interruptPlayback();
            return;
          }
          if (!streamStartedRef.current) {
            streamStartedRef.current = true;
            void audio.beginPcmStream();
            speechStartedAt.set(message.speech_id, performance.now());
            for (const pending of pendingSubtitles.get(message.speech_id) ??
              []) {
              scheduleSubtitle(message.speech_id, pending.text, pending.start);
            }
            pendingSubtitles.delete(message.speech_id);
            send(socket, {
              type: "playback.started",
              speech_id: message.speech_id,
            });
          }
          audio.pushPcmChunk(message.data_base64, message.sample_rate);
        }
      } else if (message.type === "speech.audio.end") {
        if (activeSpeechRef.current === message.speech_id) {
          void audio.endPcmStream().then(() => {
            if (activeSpeechRef.current !== message.speech_id) return;
            activeSpeechRef.current = null;
            streamStartedRef.current = false;
            setSubtitle("");
            speechStartedAt.delete(message.speech_id);
            pendingSubtitles.delete(message.speech_id);
            send(socket, {
              type: "playback.finished",
              speech_id: message.speech_id,
            });
          });
        }
      } else if (message.type === "presence.cue")
        void audio.playCue(message.audio ?? undefined);
      else if (message.type === "protocol.error") {
        setError(message.message);
        setStarting(false);
        if (message.code === "COMMAND_FAILED") {
          captureReadyRef.current = false;
          void audio.stopCapture();
          setAudioStatus("error");
        }
      }
    };
    return () => {
      active = false;
      clearTimeout(retryTimerRef.current);
      socket.close();
      audio.stopPlayback();
      for (const timer of subtitleTimers) clearTimeout(timer);
      void audio.stopCapture();
    };
  }, [connectionAttempt]);

  async function authenticate(
    mode: "register" | "login",
    body: AccountBody,
  ): Promise<void> {
    setError("");
    if (mode === "register") await registerAccount(body);
    else await loginAccount(body);
    needsAccountRef.current = false;
    setNeedsAccount(false);
    setConnectionAttempt((attempt) => attempt + 1);
  }

  function reconnect(): void {
    clearTimeout(retryTimerRef.current);
    retryCountRef.current = 0;
    setError("");
    setReconnecting(true);
    setConnectionAttempt((attempt) => attempt + 1);
  }

  async function start(): Promise<void> {
    if (!consent || starting) return;
    setStarting(true);
    setError("");
    try {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN)
        throw new Error("The connection to Quorumy is not ready.");
      interruptPlayback();
      await startCapture();
      send(socket, {
        type: "session.start",
        language,
        capture_mode: captureMode,
        output_mode: "local_only",
        consent,
      });
    } catch (reason) {
      setStarting(false);
      setAudioStatus("error");
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function command(value: "pause" | "resume" | "stop"): Promise<void> {
    setError("");
    try {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN)
        throw new Error("The connection to Quorumy is not ready.");
      if (value === "pause" || value === "stop") interruptPlayback();
      if (value === "resume") {
        if (!consent) {
          setResumePrompt(true);
          return;
        }
        setResumePrompt(false);
        await startCapture();
      }
      if (value === "pause" || value === "stop") {
        captureReadyRef.current = false;
        setConsent(false);
        await audioRef.current?.stopCapture();
        setAudioStatus(value === "pause" ? "paused" : "idle");
      }
      send(socket, {
        type: "session.command",
        command: value,
        consent: value === "resume" && consent,
      });
    } catch (reason) {
      setStarting(false);
      setAudioStatus("error");
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function startCapture(): Promise<void> {
    setAudioStatus("requesting");
    await audioRef.current?.start(captureMode);
    setAudioStatus("active");
  }

  async function resumeSession(sessionId: string): Promise<void> {
    setError("");
    try {
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN)
        throw new Error("The connection to Quorumy is not ready.");
      interruptPlayback();
      captureReadyRef.current = false;
      await audioRef.current?.stopCapture();
      setConsent(false);
      setView("notes");
      send(socket, { type: "session.open", session_id: sessionId });
    } catch (reason) {
      setStarting(false);
      setAudioStatus("error");
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  function changeLanguage(value: QuorumyLanguage): void {
    setLanguage(value);
    if (state?.session_id && socketRef.current) {
      send(socketRef.current, { type: "session.language", language: value });
    }
  }

  function interruptPlayback(): void {
    audioRef.current?.stopPlayback();
    setSubtitle("");
    const speechId = activeSpeechRef.current;
    activeSpeechRef.current = null;
    const socket = socketRef.current;
    if (speechId && socket?.readyState === WebSocket.OPEN) {
      send(socket, { type: "playback.interrupted", speech_id: speechId });
    }
  }

  async function renameSession(
    sessionId: string,
    currentTitle: string,
  ): Promise<void> {
    const title = window.prompt("Session title", currentTitle)?.trim();
    if (!title || title === currentTitle) return;
    try {
      await renameQuorumySession(sessionId, title);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function deleteSession(
    sessionId: string,
    title: string,
  ): Promise<void> {
    if (!window.confirm(`Permanently delete “${title}” from this computer?`))
      return;
    try {
      await deleteQuorumySession(sessionId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    }
  }

  async function exportSession(id: string): Promise<void> {
    try {
      await exportQuorumySession(id);
    } catch (reason) {
      setError(String(reason));
    }
  }

  function inject(): void {
    const text = manual.trim();
    if (
      !text ||
      !socketRef.current ||
      !connected ||
      state?.session_status !== "listening"
    )
      return;
    send(socketRef.current, { type: "transcript.inject", text });
    setView("transcript");
    setManual("");
  }

  function toggleSubtitles(): void {
    const next = !subtitlesEnabledRef.current;
    subtitlesEnabledRef.current = next;
    setSubtitlesEnabled(next);
  }

  function togglePromptBar(): void {
    setPromptBarVisible((current) => {
      const next = !current;
      savePromptBarVisibility(next);
      return next;
    });
  }

  return {
    state,
    sessions,
    partial,
    connected,
    reconnecting,
    reconnect,
    view,
    setView,
    displayName,
    captureMode,
    setCaptureMode,
    language,
    manual,
    setManual,
    error,
    setError,
    audioStatus,
    audioLevel,
    subtitlesEnabled,
    promptBarVisible,
    subtitle,
    consent,
    setConsent,
    resumePrompt,
    setResumePrompt,
    starting,
    needsAccount,
    authenticate,
    socketRef,
    start,
    command,
    resumeSession,
    changeLanguage,
    renameSession,
    deleteSession,
    exportSession,
    inject,
    toggleSubtitles,
    togglePromptBar,
  };
}

function speakLocally(
  socket: WebSocket,
  speechId: string,
  text: string,
  language: string,
  setSubtitle: (value: string) => void,
  activeSpeech: { current: string | null },
): void {
  activeSpeech.current = speechId;
  setSubtitle(text);
  const synth = window.speechSynthesis;
  const finish = (type: "playback.finished" | "playback.interrupted") => {
    if (activeSpeech.current !== speechId) return;
    activeSpeech.current = null;
    setSubtitle("");
    send(socket, { type, speech_id: speechId });
  };
  if (!synth) {
    send(socket, { type: "playback.started", speech_id: speechId });
    finish("playback.finished");
    return;
  }
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang =
    language === "en"
      ? "en-US"
      : language === "de"
        ? "de-DE"
        : language === "es"
          ? "es-ES"
          : language === "pt"
            ? "pt-PT"
            : "fr-FR";
  utterance.onend = () => finish("playback.finished");
  utterance.onerror = () => finish("playback.interrupted");
  send(socket, { type: "playback.started", speech_id: speechId });
  synth.cancel();
  synth.speak(utterance);
}

async function playSpeech(
  socket: WebSocket,
  audio: AudioBridge,
  message: SpeechAuthorized,
  activeSpeech: { current: string | null },
  onFinished: () => void,
): Promise<void> {
  if (audio.participantSpeaking) {
    send(socket, {
      type: "playback.interrupted",
      speech_id: message.speech_id,
    });
    return;
  }
  activeSpeech.current = message.speech_id;
  try {
    if (message.audio) {
      send(socket, { type: "playback.started", speech_id: message.speech_id });
      await audio.playAudio(
        message.audio.data_base64,
        message.audio.format,
        message.audio.sample_rate,
      );
      if (activeSpeech.current === message.speech_id) {
        activeSpeech.current = null;
        onFinished();
        send(socket, {
          type: "playback.finished",
          speech_id: message.speech_id,
        });
      }
    }
  } catch {
    if (activeSpeech.current !== message.speech_id) return;
    activeSpeech.current = null;
    onFinished();
    send(socket, {
      type: "playback.interrupted",
      speech_id: message.speech_id,
    });
  }
}
