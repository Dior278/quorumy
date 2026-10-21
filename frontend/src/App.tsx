import {
  Columns3,
  CheckCheck,
  ArrowLeft,
  FileText,
  Hand,
  MessageSquareText,
  Send,
  Workflow,
} from "lucide-react";
import { send } from "./api";
import { AccountGate } from "./components/AccountGate";
import { SessionHome, Consent, LANGUAGES } from "./components/SessionHome";
import { MinutesView } from "./components/MinutesView";
import { QuorumySubtitles } from "./components/QuorumySubtitles";
import { NotesView } from "./components/NotesView";
import { SessionControls } from "./components/SessionControls";
import {
  WorkspaceNavigation,
  type WorkspaceView,
} from "./components/WorkspaceNavigation";
import { WorkflowCanvas } from "./components/WorkflowCanvas";
import { Board, Transcript, ActivityStrip } from "./components/WorkspaceViews";
import { useQuorumy } from "./hooks/useQuorumy";
export function App() {
  const {
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
  } = useQuorumy();
  if (needsAccount)
    return <AccountGate error={error} onSubmit={authenticate} />;
  if (!state)
    return (
      <main className="loading">
        {error || `Connecting to ${displayName}…`}
      </main>
    );
  const listening = state.session_status === "listening";
  const capturing = audioStatus === "active" || audioStatus === "requesting";
  const navigation: Array<{
    view: WorkspaceView;
    label: string;
    icon: typeof Workflow;
  }> = [
    { view: "notes", label: "Notes", icon: FileText },
    { view: "board", label: "Board", icon: Columns3 },
    { view: "minutes", label: "Commitments", icon: CheckCheck },
    { view: "transcript", label: "Conversation", icon: MessageSquareText },
    { view: "flow", label: "Agents", icon: Workflow },
  ];

  const inSession =
    state.session_status !== "idle" && state.session_status !== "closed";
  return (
    <main>
      <header className={listening ? "session-header live" : "session-header"}>
        <div className="brand">
          {inSession && (
            <button
              className="icon-button back-button"
              title="End and return home"
              onClick={() => void command("stop")}
            >
              <ArrowLeft size={18} />
            </button>
          )}
          <img src="/quorumy-mark.svg" alt="" />
          <div>
            <strong>{inSession ? state.title : displayName}</strong>
            <small>
              {inSession
                ? `Quorumy · ${listening ? "Live" : "Paused"}`
                : "Your meeting companion"}
            </small>
          </div>
        </div>
        {inSession && (
          <WorkspaceNavigation
            active={view}
            items={navigation}
            onSelect={setView}
          />
        )}
        <div className="header-actions">
          {(state.hand?.level === "raised" ||
            state.hand?.level === "urgent") && (
            <div className="hand-wrap">
              <button
                type="button"
                className={
                  state.hand.level === "urgent"
                    ? "hand-signal urgent"
                    : "hand-signal"
                }
                title={state.hand.summary || "Quorumy is asking for the floor"}
                onClick={() => {
                  const socket = socketRef.current;
                  if (socket) send(socket, { type: "floor.grant" });
                }}
              >
                <Hand size={18} />
                {state.hand.level === "urgent" ? "Urgent" : "Floor"}
              </button>
              <button
                type="button"
                className="text-button"
                onClick={() => {
                  const socket = socketRef.current;
                  if (socket) send(socket, { type: "floor.dismiss" });
                }}
              >
                Not now
              </button>
            </div>
          )}
          {state.session_status !== "idle" &&
            state.session_status !== "closed" && (
              <>
                <SessionControls
                  language={language}
                  languages={LANGUAGES}
                  canCurate={
                    state.cards.length > 0 ||
                    (state.notes_document?.topics?.length ?? 0) > 0
                  }
                  curatorRunning={state.agent_runs.some(
                    (run) =>
                      run.agent === "coordinator" && run.status === "running",
                  )}
                  voiceMode={state.voice_mode}
                  subtitlesEnabled={subtitlesEnabled}
                  promptBarVisible={promptBarVisible}
                  listening={listening}
                  onLanguage={changeLanguage}
                  onCurate={() =>
                    socketRef.current &&
                    send(socketRef.current, { type: "board.curate" })
                  }
                  onToggleVoice={() =>
                    socketRef.current &&
                    send(socketRef.current, {
                      type: "voice.mode",
                      mode: state.voice_mode === "muted" ? "active" : "muted",
                    })
                  }
                  onToggleSubtitles={toggleSubtitles}
                  onTogglePromptBar={togglePromptBar}
                  onRename={() =>
                    state.session_id &&
                    void renameSession(state.session_id, state.title)
                  }
                  onExport={() =>
                    state.session_id && void exportSession(state.session_id)
                  }
                  onPauseResume={() =>
                    void command(listening && capturing ? "pause" : "resume")
                  }
                  onEnd={() => void command("stop")}
                />
              </>
            )}
          <div className={`connection ${connected ? "online" : ""}`}>
            <i />
            {connected
              ? "Connected"
              : reconnecting
                ? "Reconnecting…"
                : "Offline"}
          </div>
        </div>
      </header>

      {state.session_status === "idle" || state.session_status === "closed" ? (
        <SessionHome
          sessions={sessions}
          language={language}
          captureMode={captureMode}
          consent={consent}
          connected={connected}
          starting={starting}
          error={error}
          onConsent={setConsent}
          onLanguage={changeLanguage}
          onCapture={setCaptureMode}
          onStart={() => void start()}
          onOpen={(id) => void resumeSession(id)}
          onRename={(id, title) => void renameSession(id, title)}
          onDelete={(id, title) => void deleteSession(id, title)}
          onExport={(id) => void exportSession(id)}
        />
      ) : (
        <>
          {(state.carried ?? []).some((item) => item.status === "open") && (
            <section className="memory-strip" aria-label="Open commitments">
              {(state.carried ?? [])
                .filter((item) => item.status === "open")
                .map((item) => (
                  <article
                    className="memory-card"
                    key={`${item.session_id}-${item.id}`}
                  >
                    <div>
                      <small>
                        {item.session_title}
                        {item.owner_name ? ` · ${item.owner_name}` : ""}
                      </small>
                      <p>{item.text}</p>
                    </div>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => {
                        const socket = socketRef.current;
                        if (socket)
                          send(socket, {
                            type: "commitment.settle",
                            session_id: item.session_id,
                            note_id: item.id,
                          });
                      }}
                    >
                      Done
                    </button>
                  </article>
                ))}
            </section>
          )}
          {!connected && (
            <div className="session-notice" role="status">
              {reconnecting
                ? "Reconnecting. Listening stays off until you resume."
                : "Connection lost. Listening is off."}{" "}
              <button onClick={reconnect}>Try again now</button>
            </div>
          )}
          {!listening && connected && (
            <div className="session-notice">
              Session paused · You can review and export your work.{" "}
              <button
                onClick={() => {
                  setConsent(false);
                  setResumePrompt(true);
                }}
              >
                Resume
              </button>
            </div>
          )}
          {resumePrompt && (
            <div className="dialog-backdrop">
              <section
                className="resume-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="resume-title"
              >
                <h2 id="resume-title">Resume with Quorumy</h2>
                <p>
                  The source stays the one from this session. Analysis resumes
                  after you confirm.
                </p>
                <Consent checked={consent} onChange={setConsent} />
                <div>
                  <button onClick={() => setResumePrompt(false)}>Cancel</button>
                  <button
                    className="start"
                    disabled={!consent || !connected}
                    onClick={() => void command("resume")}
                  >
                    Resume the session
                  </button>
                </div>
              </section>
            </div>
          )}
          <section className="view-stage">
            {view === "flow" && (
              <WorkflowCanvas
                state={state}
                audioStatus={audioStatus}
                onCancelTask={
                  connected
                    ? (taskId) =>
                        socketRef.current &&
                        send(socketRef.current, {
                          type: "task.cancel",
                          task_id: taskId,
                        })
                    : undefined
                }
              />
            )}
            {view === "board" && <Board state={state} />}
            {view === "notes" && <NotesView state={state} />}
            {view === "minutes" && <MinutesView state={state} />}
            {view === "transcript" && (
              <Transcript state={state} partial={partial} />
            )}
          </section>
          {(promptBarVisible || captureMode === "text") && (
            <section className="manual command-bar">
              <input
                aria-label="Message to Quorumy"
                disabled={!listening || !connected}
                maxLength={12000}
                value={manual}
                onChange={(event) => setManual(event.target.value)}
                onKeyDown={(event) => event.key === "Enter" && inject()}
                placeholder={
                  listening
                    ? "An idea, a question… Address Quorumy."
                    : "Resume the session to write to Quorumy"
                }
              />
              <button
                disabled={!listening || !connected || !manual.trim()}
                onClick={inject}
                title="Send"
                aria-label="Send"
              >
                <Send size={17} />
              </button>
            </section>
          )}
          {error && (
            <div className="error global-error" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          <ActivityStrip
            state={state}
            partial={partial}
            audioStatus={audioStatus}
            audioLevel={audioLevel}
          />
          <QuorumySubtitles
            enabled={subtitlesEnabled}
            text={subtitle}
            companionName={state.identity_name}
          />
        </>
      )}
    </main>
  );
}
