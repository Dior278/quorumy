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
  decision: "Décision",
  action: "Action",
  question: "Question",
  risk: "Vigilance",
  proposed: "À relire",
  confirmed: "Validé",
  rejected: "Écarté",
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
          <p className="eyebrow">DE LA DISCUSSION À L’ENGAGEMENT</p>
          <h1>Ce que vous retenez</h1>
          <p>
            L’IA propose. Vous relisez les paroles et confirmez ce qui a
            réellement été convenu.
          </p>
        </div>
        <button
          className="start"
          disabled={busy || !state.transcript.length || !state.consent_at}
          onClick={() => void request("POST")}
        >
          {busy
            ? "Préparation…"
            : board
              ? "Actualiser les propositions"
              : "Préparer les propositions"}
        </button>
      </div>
      {!state.consent_at && (
        <p className="notice">
          Reprenez la session pour préparer de nouvelles propositions. La
          relecture reste disponible.
        </p>
      )}
      {board?.stale && (
        <p className="notice">
          La discussion a évolué. Actualisez le carnet avant de valider d’autres
          engagements.
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
                "quorumy-engagements.md",
              ).catch((e) => setError(String(e)))
            }
          >
            Exporter les engagements
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
              Rappels calendrier
            </button>
          )}
          <span>
            {board.discarded > 0
              ? `${board.discarded} proposition(s) sans citation exacte écartée(s).`
              : "Les extraits sont contrôlés dans la transcription."}
          </span>
        </div>
      )}
      {!board?.notes.length && (
        <div className="empty">
          <h2>
            {board
              ? "Aucun engagement suffisamment étayé."
              : "Chaque engagement mérite une preuve."}
          </h2>
          <p>
            Les suggestions et les hypothèses ne deviennent pas automatiquement
            des décisions.
          </p>
        </div>
      )}
      <div className="minutes-grid">
        {board?.notes.map((note) => (
          <NoteCard
            key={`${board.version}-${note.id}`}
            note={note}
            people={[
              { id: "renard", name: "Renard", connected: true },
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
        Une citation exacte ne garantit pas l’interprétation. La relecture porte
        le nom de son auteur. Les voix d’un appel externe partagé ne sont pas
        identifiées automatiquement. Les fichiers calendrier sont des rappels,
        sans invitation envoyée.
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
          <p>« {e.quote} »</p>
          <cite>{e.speaker}</cite>
        </blockquote>
      ))}
      {note.kind === "action" && (
        <div className="commitment-fields">
          <label>
            Responsable
            <select
              value={owner}
              disabled={disabled}
              onChange={(e) => setOwner(e.target.value)}
            >
              <option value="">Non attribué</option>
              {people.map((p) => (
                <option value={p.id} key={p.id}>
                  {p.name}
                  {p.connected ? "" : " · absent"}
                </option>
              ))}
              {owner && !people.some((p) => p.id === owner) && (
                <option value={owner}>
                  {note.owner_name || "Ancien participant"}
                </option>
              )}
            </select>
          </label>
          <label>
            Échéance confirmée
            <input
              type="date"
              value={due}
              disabled={disabled}
              onChange={(e) => setDue(e.target.value)}
            />
          </label>
          {note.due_quote && <small>Entendu : {note.due_quote}</small>}
        </div>
      )}
      <div className="commitment-actions">
        <button
          disabled={disabled}
          onClick={() => void review("confirmed", owner, due)}
        >
          Confirmer
        </button>
        <button
          disabled={disabled}
          onClick={() => void review("rejected", owner, due)}
        >
          Écarter
        </button>
        {note.status !== "proposed" && (
          <button
            disabled={disabled}
            onClick={() => void review("proposed", owner, due)}
          >
            À relire
          </button>
        )}
      </div>
    </article>
  );
}
