import type { QuorumyState } from "../protocol";
type AudioStatus = "idle" | "requesting" | "active" | "paused" | "error";
const WAVE_SHAPE = [
  0.45, 0.7, 1, 0.6, 0.85, 0.5, 0.95, 0.65, 0.8, 0.4, 0.75, 0.55,
];

export function Board({ state }: { state: QuorumyState }) {
  if (!state.cards.length)
    return (
      <div className="empty">
        <span>01</span>
        <h2>Les idées prennent place ici.</h2>
        <p>
          Quorumy rassemble les idées, les décisions et les résultats de
          recherche au fil de la discussion.
        </p>
      </div>
    );
  const labels: Record<string, string> = {
    idea: "Idée",
    question: "Question",
    decision: "Décision évoquée",
    suggestion: "Suggestion",
    finding: "Résultat",
  };
  return (
    <div className="board">
      {state.cards
        .slice()
        .reverse()
        .map((card, index) => (
          <article className={`card c${index % 4}`} key={card.id}>
            <small>{labels[card.kind]}</small>
            <h2>{card.title}</h2>
            <p>{card.body}</p>
            <Sources state={state} ids={card.source_ids ?? []} />
          </article>
        ))}
    </div>
  );
}

export function Transcript({
  state,
  partial,
}: {
  state: QuorumyState;
  partial: string;
}) {
  const entries = [
    ...state.transcript.map((u) => ({
      id: u.id,
      at: u.committed_at,
      speaker: u.speaker === "unknown" ? "Voix non identifiée" : u.speaker,
      text: u.text,
      assistant: false,
      delivery: "",
      sourceIds: [] as string[],
    })),
    ...state.speeches
      .filter(
        (s) =>
          s.text &&
          (["playing", "finished", "interrupted"].includes(s.status) ||
            (s.status === "suppressed" && s.error === "voice_muted")),
      )
      .map((s) => ({
        id: s.id,
        at: s.playback_started_at ?? s.created_at,
        speaker: "Quorumy",
        text: s.text,
        assistant: true,
        sourceIds: s.source_ids ?? [],
        delivery:
          s.status === "interrupted"
            ? "Interrompue · texte préparé"
            : s.status === "suppressed"
              ? "Réponse écrite · voix coupée"
              : s.status === "playing"
                ? "En cours de lecture"
                : "",
      })),
  ].sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));
  if (!entries.length && !partial)
    return (
      <div className="empty">
        <h2>La conversation commence ici.</h2>
        <p>
          Les paroles transcrites et les réponses de Quorumy restent
          consultables pendant la session.
        </p>
      </div>
    );
  return (
    <div className="transcript">
      {partial && (
        <div className="line partial">
          <time>En cours</time>
          <p>{partial}</p>
        </div>
      )}
      {entries.map((item) => (
        <div
          className={`line ${item.assistant ? "assistant" : ""}`}
          key={item.id}
        >
          <time>
            {item.at
              ? new Date(item.at).toLocaleTimeString("fr-FR", {
                  hour: "2-digit",
                  minute: "2-digit",
                })
              : ""}
          </time>
          <div>
            <strong className="line-author">{item.speaker}</strong>
            {item.delivery && (
              <small className="delivery-status">{item.delivery}</small>
            )}
            <p>{item.text}</p>
            {item.assistant && (
              <Sources
                state={state}
                ids={item.sourceIds}
                className="answer-sources"
              />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function Sources({
  state,
  ids,
  className = "card-sources",
}: {
  state: QuorumyState;
  ids: string[];
  className?: string;
}) {
  const tasks = state.tasks.filter((t) => ids.includes(t.id ?? ""));
  const originIds = [...ids, ...tasks.map((t) => t.source_utterance_id)];
  const utterances = state.transcript.filter((u) =>
    originIds.includes(u.id ?? ""),
  );
  const links = new Map<string, { url: string; title: string }>();
  for (const task of tasks) {
    const result = task.result as Record<string, unknown> | null;
    for (const list of [result?.sources, result?.results]) {
      if (!Array.isArray(list)) continue;
      for (const source of list) {
        if (!source || typeof source.url !== "string") continue;
        try {
          const url = new URL(source.url);
          if (
            !["http:", "https:"].includes(url.protocol) ||
            url.username ||
            url.password
          )
            continue;
          if (!links.has(url.href))
            links.set(url.href, {
              url: url.href,
              title:
                typeof source.title === "string" && source.title.trim()
                  ? source.title
                  : url.hostname,
            });
        } catch {
          /* An invalid provider URL is not a usable citation. */
        }
      }
    }
  }
  if (!utterances.length && !links.size) return null;
  return (
    <details className={className}>
      <summary>
        {className === "answer-sources"
          ? "Origine de cette réponse"
          : "Voir les sources"}
      </summary>
      {utterances.length > 0 && <span>Dans la conversation</span>}
      {utterances.map((u) => (
        <blockquote key={u.id}>{u.text}</blockquote>
      ))}
      {links.size > 0 && <span>Sources consultées · {links.size}</span>}
      {Array.from(links.values()).map((s) => (
        <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer">
          {s.title || s.url}
        </a>
      ))}
      {links.size > 0 && (
        <small>
          Ces références permettent de contrôler la réponse ; leur présence ne
          valide pas chaque affirmation.
        </small>
      )}
    </details>
  );
}

export function ActivityStrip({
  state,
  partial,
  audioStatus,
  audioLevel,
}: {
  state: QuorumyState;
  partial: string;
  audioStatus: AudioStatus;
  audioLevel: number;
}) {
  const latest = state.activities.at(-1);
  const latestTask = state.tasks.at(-1);
  const labels: Record<string, string> = {
    task:
      latestTask?.status === "failed"
        ? "Une recherche n’a pas abouti. Consultez les détails dans Agents."
        : latestTask?.status === "canceled"
          ? "Recherche arrêtée. La conversation peut continuer."
          : latestTask?.status === "done"
            ? "Le résultat de recherche est disponible."
            : "Recherche en cours. Vous pouvez la suivre dans Agents.",
    notes: "Les notes sont à jour.",
    heard: "Intervention enregistrée.",
    "board.curated": "Le tableau est à jour.",
    "board.create": "Une idée a rejoint le tableau.",
    "board.update": "Une idée a été précisée.",
    "session.renamed": "Le titre de la session est à jour.",
    "minutes.generated": "Les engagements sont prêts à être relus.",
    "minutes.reviewed": "Votre relecture est enregistrée.",
    "voice.muted": "La voix est coupée. Les réponses restent écrites.",
    "voice.active": "La voix de Quorumy est activée.",
  };
  const activity = latest
    ? (labels[latest.kind] ?? latest.summary)
    : "Quorumy est prêt. La conversation peut commencer.";
  return (
    <footer>
      <div className="audio-monitor" aria-label={`Microphone ${audioStatus}`}>
        <span>
          {state.capture_mode === "text"
            ? "Session texte"
            : audioStatus === "active"
              ? "Écoute en cours"
              : "Écoute arrêtée"}
        </span>
        <div className="wave" aria-hidden="true">
          {WAVE_SHAPE.map((shape, index) => (
            <i
              key={index}
              style={{ height: `${4 + audioLevel * shape * 24}px` }}
            />
          ))}
        </div>
      </div>
      <p>{partial || activity}</p>
    </footer>
  );
}
