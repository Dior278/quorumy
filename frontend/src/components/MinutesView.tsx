import { useState } from "react";
import type { QuorumyState } from "../protocol";
import { request as apiRequest, download } from "../api";

type Note = {
  id: string;
  kind: string;
  text: string;
  status: string;
  owner_id: string;
  owner_name: string;
  due_date: string | null;
  due_quote: string | null;
  evidence: Array<{ utterance_id: string; quote: string; speaker: string }>;
};
type Board = {
  version: string;
  stale: boolean;
  discarded: number;
  notes: Note[];
};
const labels: Record<string, string> = {
  decision: "Decision",
  action: "Action",
  question: "Question",
  risk: "Risk",
  proposed: "To review",
  confirmed: "Confirmed",
  rejected: "Set aside",
};

export function MinutesView({ state }: { state: QuorumyState }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const board = state.minutes as Board | null;
  async function request(method: string, body?: object) {
    setBusy(true);
    setError("");
    try {
      await apiRequest("/v1/minutes", method, body);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="minutes-shell">
      <div className="minutes-heading">
        <div>
          <p className="eyebrow">FROM DISCUSSION TO COMMITMENT</p>
          <h1>What you keep</h1>
          <p>
            The model proposes. You reread the words and confirm what was
            actually agreed.
          </p>
        </div>
        <button
          className="start"
          disabled={busy || !state.transcript.length || !state.consent_at}
          onClick={() => void request("POST")}
        >
          {busy
            ? "Preparing…"
            : board
              ? "Refresh proposals"
              : "Prepare proposals"}
        </button>
      </div>
      {!state.consent_at && (
        <p className="notice">
          Resume the session to prepare new proposals. Review stays available.
        </p>
      )}
      {board?.stale && (
        <p className="notice">
          The discussion has moved on. Refresh the record before confirming more
          commitments.
        </p>
      )}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {board && (
        <div className="minutes-exports">
          <button
            onClick={() =>
              void download(
                `/v1/sessions/${state.session_id}/minutes/md`,
                "quorumy-commitments.md",
              ).catch((e) => setError(String(e)))
            }
          >
            Export commitments
          </button>
          {!board.stale && (
            <button
              onClick={() =>
                void download(
                  `/v1/sessions/${state.session_id}/minutes/ics`,
                  "quorumy-actions.ics",
                ).catch((e) => setError(String(e)))
              }
            >
              Calendar reminders
            </button>
          )}
          <span>
            {board.discarded > 0
              ? `${board.discarded} proposal(s) without an exact quote were set aside.`
              : "Quotes are checked against the transcript."}
          </span>
        </div>
      )}
      {!board?.notes.length && (
        <div className="empty">
          <h2>
            {board
              ? "No commitment is supported well enough."
              : "Every commitment deserves evidence."}
          </h2>
          <p>
            Suggestions and hypotheses do not become decisions on their own.
          </p>
        </div>
      )}
      <div className="minutes-grid">
        {board?.notes.map((note) => (
          <NoteCard
            key={`${board.version}-${note.id}`}
            note={note}
            people={[
              { id: "renard", name: "You", connected: true },
              ...(state.participants || []).filter((p) => p.id !== "renard"),
            ]}
            disabled={busy || board.stale}
            review={(status, owner, due) =>
              request("PATCH", {
                type: "minutes_review",
                version: board.version,
                note_id: note.id,
                status,
                owner_id: owner,
                due_date: due || null,
              })
            }
          />
        ))}
      </div>
      <p className="fine-print">
        An exact quote does not guarantee the interpretation. A review carries
        the reviewer’s name. Voices from a shared external call are not
        identified automatically. Calendar files are reminders, not invitations.
      </p>
    </section>
  );
}

function NoteCard({
  note,
  disabled,
  review,
  people,
}: {
  note: Note;
  people: Array<{ id: string; name: string; connected?: boolean }>;
  disabled: boolean;
  review: (status: string, owner: string, due: string) => Promise<void>;
}) {
  const [owner, setOwner] = useState(note.owner_id || "");
  const [due, setDue] = useState(note.due_date || "");
  return (
    <article className={`commitment ${note.status}`}>
      <div className="commitment-label">
        <span>{labels[note.kind]}</span>
        <b>{labels[note.status]}</b>
      </div>
      <h2>{note.text}</h2>
      {note.evidence.map((e) => (
        <blockquote key={e.utterance_id}>
          <p>“{e.quote}”</p>
          <cite>{e.speaker}</cite>
        </blockquote>
      ))}
      {note.kind === "action" && (
        <div className="commitment-fields">
          <label>
            Owner
            <select
              value={owner}
              disabled={disabled}
              onChange={(e) => setOwner(e.target.value)}
            >
              <option value="">Unassigned</option>
              {people.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                  {p.connected ? "" : " · away"}
                </option>
              ))}
              {owner && !people.some((p) => p.id === owner) && (
                <option value={owner}>
                  {note.owner_name || "Former participant"}
                </option>
              )}
            </select>
          </label>
          <label>
            Confirmed due date
            <input
              type="date"
              value={due}
              disabled={disabled}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
          {note.due_quote && <small>Heard: {note.due_quote}</small>}
        </div>
      )}
      <div className="commitment-actions">
        <button
          disabled={disabled}
          onClick={() => void review("confirmed", owner, due)}
        >
          Confirm
        </button>
        <button
          disabled={disabled}
          onClick={() => void review("rejected", owner, due)}
        >
          Set aside
        </button>
        {note.status !== "proposed" && (
          <button
            disabled={disabled}
            onClick={() => void review("proposed", owner, due)}
          >
            To review
          </button>
        )}
      </div>
    </article>
  );
}
