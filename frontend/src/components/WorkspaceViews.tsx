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
        <h2>Ideas land here.</h2>
        <p>
          Quorumy gathers ideas, decisions, and research results as the
          discussion moves.
        </p>
      </div>
    );
  const labels: Record<string, string> = {
    idea: "Idea",
    question: "Question",
    decision: "Decision mentioned",
    suggestion: "Suggestion",
    finding: "Finding",
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
      speaker: u.speaker === "unknown" ? "Unidentified voice" : u.speaker,
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
            ? "Interrupted · prepared text"
            : s.status === "suppressed"
              ? "Written answer · voice off"
              : s.status === "playing"
                ? "Playing"
                : "",
      })),
  ].sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));
  if (!entries.length && !partial)
    return (
      <div className="empty">
        <h2>The conversation starts here.</h2>
        <p>
          Transcribed words and Quorumy’s answers stay available during the
          session.
        </p>
      </div>
    );
  return (
    <div className="transcript">
      {partial && (
        <div className="line partial">
          <time>Live</time>
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
              ? new Date(item.at).toLocaleTimeString("en", {
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
          ? "Where this answer came from"
          : "View sources"}
      </summary>
      {utterances.length > 0 && <span>In the conversation</span>}
      {utterances.map((u) => (
        <blockquote key={u.id}>{u.text}</blockquote>
      ))}
      {links.size > 0 && <span>Sources checked · {links.size}</span>}
      {Array.from(links.values()).map((s) => (
        <a key={s.url} href={s.url} target="_blank" rel="noopener noreferrer">
          {s.title || s.url}
        </a>
      ))}
      {links.size > 0 && (
        <small>
          These references let you check the answer; listing them does not
          confirm every claim.
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
        ? "A search did not finish. See the details in Agents."
        : latestTask?.status === "canceled"
          ? "Research stopped. The conversation can continue."
          : latestTask?.status === "done"
            ? "The research result is ready."
            : "Research is running. You can follow it in Agents.",
    notes: "Notes are up to date.",
    heard: "Turn recorded.",
    "board.curated": "The board is up to date.",
    "board.create": "An idea joined the board.",
    "board.update": "An idea was refined.",
    "session.renamed": "The session title is up to date.",
    "minutes.generated": "Commitments are ready to review.",
    "minutes.reviewed": "Your review is saved.",
    "voice.muted": "Voice is off. Answers stay written.",
    "voice.active": "Quorumy’s voice is on.",
    "commitment.done": "Commitment closed.",
  };
  const activity = latest
    ? (labels[latest.kind] ?? latest.summary)
    : "Quorumy is ready. The conversation can start.";
  return (
    <footer>
      <div className="audio-monitor" aria-label={`Microphone ${audioStatus}`}>
        <span>
          {state.capture_mode === "text"
            ? "Text session"
            : audioStatus === "active"
              ? "Listening"
              : "Listening off"}
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
