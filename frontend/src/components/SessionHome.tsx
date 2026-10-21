import {
  ArrowUpRight,
  AudioLines,
  FileCheck2,
  Layers3,
  ShieldCheck,
} from "lucide-react";
import type { CaptureMode } from "../audio";
import type { QuorumyLanguage, SessionSummary } from "../protocol";
import { MeetingAudioSetup } from "./MeetingAudioSetup";

export const LANGUAGES: Array<{ value: QuorumyLanguage; label: string }> = [
  { value: "fr", label: "Français" },
  { value: "en", label: "English" },
  { value: "es", label: "Español" },
  { value: "de", label: "Deutsch" },
  { value: "pt", label: "Português" },
];

export function Consent({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="consent">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span>
        The people involved have been told and agree to analysis by AI.
      </span>
    </label>
  );
}

type Props = {
  sessions: SessionSummary[];
  language: QuorumyLanguage;
  captureMode: CaptureMode;
  consent: boolean;
  connected: boolean;
  starting: boolean;
  error: string;
  onConsent: (value: boolean) => void;
  onLanguage: (value: QuorumyLanguage) => void;
  onCapture: (value: CaptureMode) => void;
  onStart: () => void;
  onOpen: (id: string) => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string, title: string) => void;
  onExport: (id: string) => void;
};

export function SessionHome(p: Props) {
  const systemSupported =
    typeof navigator.mediaDevices?.getDisplayMedia === "function";
  const openCommitments = p.sessions.reduce(
    (count, session) => count + (session.open_commitments ?? 0),
    0,
  );
  return (
    <section className="home-shell">
      <div className="home-hero">
        <div className="hero-copy">
          <p className="eyebrow">
            <span className="tiny-orbit" /> A STEP AHEAD, TOGETHER
          </p>
          <h1>
            The whole conversation.
            <br />
            <em>One step ahead.</em>
          </h1>
          <p className="hero-description">
            You move the ideas forward. Quorumy keeps the thread, checks what is
            said, and speaks only when given the floor.
          </p>
          <div className="hero-caption">
            <span className="caption-line" /> Beside you, without joining the
            call.
          </div>
        </div>
        <div className="launch-card">
          <div className="launch-card-heading">
            <div className="quorumy-orbit">
              <img src="/quorumy-mark.svg" alt="" />
            </div>
            <span>YOUR NEXT CONVERSATION</span>
          </div>
          <h2>Make room for Quorumy.</h2>
          <p>
            Open your usual meeting, then choose what Quorumy is allowed to
            hear.
          </p>
          <label>
            Conversation source
            <select
              value={p.captureMode}
              onChange={(e) => p.onCapture(e.target.value as CaptureMode)}
              disabled={p.starting}
            >
              <option value="text">Text · no microphone</option>
              <option value="microphone">Microphone</option>
              <option value="mixed" disabled={!systemSupported}>
                Microphone + shared audio
              </option>
              <option value="system" disabled={!systemSupported}>
                Tab or system audio
              </option>
            </select>
          </label>
          {(p.captureMode === "mixed" || p.captureMode === "system") && (
            <MeetingAudioSetup />
          )}
          <details className="launch-options">
            <summary>
              Language · {LANGUAGES.find((l) => l.value === p.language)?.label}
            </summary>
            <label>
              Session language
              <select
                value={p.language}
                onChange={(e) =>
                  p.onLanguage(e.target.value as QuorumyLanguage)
                }
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          </details>
          <Consent checked={p.consent} onChange={p.onConsent} />
          <button
            className="start launch-button"
            disabled={!p.connected || !p.consent || p.starting}
            onClick={p.onStart}
          >
            {p.starting ? "Preparing…" : "Start a session"}
            <ArrowUpRight size={18} />
          </button>
          <p className="privacy-note">
            <ShieldCheck size={14} /> Memory stays on this computer. Analysis
            uses the configured services.
          </p>
          {p.error && (
            <p className="error" role="alert">
              {p.error}
            </p>
          )}
        </div>
      </div>
      <div className="home-principles">
        <article>
          <AudioLines size={20} />
          <div>
            <span>01 / DURING</span>
            <h3>Keep the thread.</h3>
            <p>Notes that follow the discussion without interrupting ideas.</p>
          </div>
        </article>
        <article>
          <Layers3 size={20} />
          <div>
            <span>02 / FURTHER</span>
            <h3>Explore together.</h3>
            <p>Parallel research, results, and their sources.</p>
          </div>
        </article>
        <article>
          <FileCheck2 size={20} />
          <div>
            <span>03 / AFTER</span>
            <h3>Keep what matters.</h3>
            <p>Commitments to review and confirm, with the original words.</p>
          </div>
        </article>
      </div>
      {openCommitments > 0 && (
        <p className="memory-banner">
          {openCommitments > 1
            ? `${openCommitments} confirmed commitments are waiting. The next meeting will start with them.`
            : `${openCommitments} confirmed commitment is waiting. The next meeting will start with it.`}
        </p>
      )}
      <section className="session-library" aria-label="Saved sessions">
        <div className="session-library-heading">
          <div>
            <p className="eyebrow">YOUR MEMORY</p>
            <h2>Pick up the thread</h2>
          </div>
          <span>
            {p.sessions.length} session{p.sessions.length === 1 ? "" : "s"}
          </span>
        </div>
        {p.sessions.length === 0 ? (
          <p className="library-empty">
            Your conversations will appear here. You can reread and export them
            at any time.
          </p>
        ) : (
          <div className="session-list">
            {p.sessions.map((session) => (
              <article className="session-item" key={session.session_id}>
                <button
                  className="session-resume"
                  disabled={!p.connected || p.starting}
                  onClick={() => p.onOpen(session.session_id)}
                >
                  <span>
                    <strong>{session.title}</strong>
                    <small>{session.preview || "No turn recorded"}</small>
                  </span>
                  <span className="session-meta">
                    <small>
                      {session.utterance_count} turn
                      {session.utterance_count === 1 ? "" : "s"}
                    </small>
                    <time>
                      {new Date(session.updated_at).toLocaleDateString("en")}
                    </time>
                  </span>
                </button>
                <div className="session-tools">
                  <button
                    onClick={() =>
                      p.onRename(session.session_id, session.title)
                    }
                  >
                    Rename
                  </button>
                  <button onClick={() => p.onExport(session.session_id)}>
                    Export
                  </button>
                  <button
                    className="danger"
                    onClick={() =>
                      p.onDelete(session.session_id, session.title)
                    }
                  >
                    Delete
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <p className="home-credit">
        Quorumy follows the meeting and raises a hand when something is urgent.
      </p>
    </section>
  );
}
