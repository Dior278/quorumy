import {
  AudioLines,
  Bot,
  BrainCircuit,
  Database,
  FileText,
  Lightbulb,
  Mic2,
  Search,
  Volume2,
  X,
} from "lucide-react";
import { useState, type ComponentType } from "react";
import type { QuorumyState } from "../protocol";
import { ResearchTasks } from "./ResearchTasks";

type AudioStatus = "idle" | "requesting" | "active" | "paused" | "error";
type NodeKey =
  | "room"
  | "stt"
  | "memory"
  | "jev"
  | "speaker"
  | "worker"
  | "notes"
  | "board"
  | "voice";

type FlowNode = {
  key: NodeKey;
  label: string;
  detail: string;
  status: string;
  icon: ComponentType<{ size?: number }>;
  active: boolean;
};

const POSITIONS: Record<NodeKey, { x: number; y: number }> = {
  room: { x: 28, y: 220 },
  stt: { x: 222, y: 220 },
  memory: { x: 440, y: 205 },
  jev: { x: 440, y: 52 },
  speaker: { x: 700, y: 42 },
  worker: { x: 700, y: 190 },
  notes: { x: 700, y: 338 },
  board: { x: 440, y: 430 },
  voice: { x: 930, y: 42 },
};

const EDGES: Array<[NodeKey, NodeKey, string]> = [
  ["room", "stt", "audio"],
  ["stt", "memory", "heard"],
  ["memory", "jev", "decision context"],
  ["jev", "speaker", "direct response"],
  ["jev", "worker", "background mission"],
  ["worker", "memory", "worker"],
  ["memory", "notes", "notes"],
  ["memory", "board", "board"],
  ["speaker", "voice", "voice"],
  ["voice", "room", "voice"],
];

export function WorkflowCanvas({
  state,
  audioStatus,
  onCancelTask,
}: {
  state: QuorumyState;
  audioStatus: AudioStatus;
  onCancelTask?: (taskId: string) => void;
}) {
  const [selected, setSelected] = useState<NodeKey | null>(null);
  const agentRuns = state.agent_runs ?? [];
  const running = agentRuns.filter((run) => run.status === "running");
  const tasks = state.tasks ?? [];
  const runningTasks = tasks.filter(
    (task) => task.status === "running" || task.status === "queued",
  );
  const lastTask = tasks.at(-1);
  const speaker = running.find((run) => run.agent === "speaker");
  const worker = running.find(
    (run) => run.agent === "worker" || run.agent === "coordinator",
  );
  const notes = running.find((run) => run.agent === "notes");
  const naming = running.find((run) => run.agent === "naming");
  const speech = state.speeches.at(-1);
  const decision = state.decisions?.at(-1);
  const decisionActive = Boolean(
    decision?.decided_at &&
      Date.now() - new Date(decision.decided_at).getTime() < 3000,
  );
  const recentBoardActivity = state.activities
    .slice()
    .reverse()
    .find((item) => item.kind.startsWith("board."));
  const recentBoardActivityAt = recentBoardActivity?.created_at;
  const boardActive = Boolean(
    worker?.agent === "coordinator" ||
      (recentBoardActivityAt &&
        Date.now() - new Date(recentBoardActivityAt).getTime() < 3000),
  );
  const pipeline = state.pipeline;
  const nodes: FlowNode[] = [
    {
      key: "room",
      label: "Conversation",
      detail:
        state.capture_mode === "text"
          ? `${state.transcript.length} interventions écrites`
          : "Audio de la conversation",
      status: audioStatus,
      icon: Mic2,
      active: audioStatus === "active",
    },
    {
      key: "stt",
      label: "Transcription",
      detail:
        state.capture_mode === "text"
          ? "Saisie au clavier"
          : `${pipeline?.stt_turns ?? 0} interventions transcrites`,
      status: pipeline?.stt_last_event || "waiting",
      icon: AudioLines,
      active:
        state.session_status === "listening" && state.capture_mode !== "text",
    },
    {
      key: "memory",
      label: "Mémoire partagée",
      detail: `${state.transcript.length} interventions, ${tasks.length} recherches`,
      status: "enregistré",
      icon: Database,
      active: running.length > 0 || runningTasks.length > 0,
    },
    {
      key: "jev",
      label: "Orientation",
      detail: decision
        ? {
            ignore: "Aucune action requise",
            capture: "Mémoriser la discussion",
            investigate: "Approfondir la question",
            respond: "Préparer une réponse",
            act: "Préparer une action",
            control: "Ajuster l’assistant",
          }[decision.result.route]
        : "Attend une intervention",
      status: decisionActive ? "deciding" : "idle",
      icon: BrainCircuit,
      active: decisionActive,
    },
    {
      key: "speaker",
      label: "Réponse",
      detail: speaker?.summary || "Prêt à vous répondre",
      status:
        speaker?.status || (state.voice_mode === "muted" ? "muted" : "idle"),
      icon: Bot,
      active: Boolean(speaker),
    },
    {
      key: "worker",
      label: "Recherches",
      detail:
        worker?.summary || lastTask?.summary || "Aucune recherche en cours",
      status: runningTasks.length
        ? `${runningTasks.length} en cours`
        : lastTask?.status || "idle",
      icon: Search,
      active: Boolean(worker || runningTasks.length),
    },
    {
      key: "notes",
      label: "Notes",
      detail:
        notes?.summary ||
        `${state.notes_cursor ?? 0}/${state.transcript.length} interventions intégrées`,
      status: notes?.status || `v${state.notes_version ?? 0}`,
      icon: FileText,
      active: Boolean(notes),
    },
    {
      key: "board",
      label: "Tableau",
      detail: `${state.cards.length} idées conservées`,
      status: boardActive ? "curating" : naming ? "naming" : "synced",
      icon: Lightbulb,
      active: boardActive,
    },
    {
      key: "voice",
      label: "Voix",
      detail: speech?.text || "Attend le bon moment",
      status: speech?.status || "idle",
      icon: Volume2,
      active: Boolean(
        speech &&
          ["waiting_gap", "authorized", "playing"].includes(speech.status),
      ),
    },
  ];
  const active = new Set<NodeKey>(
    nodes.filter((node) => node.active).map((node) => node.key),
  );

  return (
    <section className="workflow-shell">
      <header className="workflow-heading">
        <div>
          <BrainCircuit />
          <span>Les agents au travail</span>
        </div>
        <p>
          {running.length} agents et {runningTasks.length} recherches en cours
        </p>
      </header>
      <div className="workflow-viewport">
        <div className="workflow-canvas">
          <svg viewBox="0 0 1120 570" aria-hidden="true">
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>
            {EDGES.map(([from, to, channel]) => {
              const a = POSITIONS[from];
              const b = POSITIONS[to];
              const lit = active.has(from) && active.has(to);
              return (
                <g
                  key={`${from}-${to}`}
                  className={`flow-edge ${lit ? "active" : ""}`}
                >
                  <path
                    d={`M ${a.x + 75} ${a.y + 48} C ${(a.x + b.x) / 2 + 75} ${a.y + 48}, ${(a.x + b.x) / 2 + 75} ${b.y + 48}, ${b.x + 75} ${b.y + 48}`}
                  />
                  <circle r="4" filter="url(#glow)">
                    <animateMotion
                      dur="1.4s"
                      repeatCount="indefinite"
                      path={`M ${a.x + 75} ${a.y + 48} C ${(a.x + b.x) / 2 + 75} ${a.y + 48}, ${(a.x + b.x) / 2 + 75} ${b.y + 48}, ${b.x + 75} ${b.y + 48}`}
                    />
                  </circle>
                  <title>{channel}</title>
                </g>
              );
            })}
          </svg>
          {nodes.map((node) => {
            const Icon = node.icon;
            const position = POSITIONS[node.key];
            return (
              <button
                className={`flow-node ${node.active ? "active" : ""}`}
                data-node={node.key}
                key={node.key}
                style={{ left: position.x, top: position.y }}
                onClick={() => setSelected(node.key)}
              >
                <div className="node-icon">
                  <Icon size={18} />
                </div>
                <div className="node-copy">
                  <strong>{node.label}</strong>
                  <span>{node.detail}</span>
                </div>
                <small>
                  {(
                    {
                      active: "En cours",
                      idle: "Prêt",
                      waiting: "En attente",
                      synced: "Enregistré",
                      done: "Terminé",
                      failed: "À vérifier",
                      muted: "Voix coupée",
                      paused: "En pause",
                      running: "En cours",
                      curating: "Organisation",
                      deciding: "Analyse",
                      naming: "Titre",
                      finished: "Terminé",
                      suppressed: "Réponse écrite",
                      authorized: "Prêt à parler",
                      playing: "En lecture",
                      canceled: "Interrompu",
                    } as Record<string, string>
                  )[node.status] ?? node.status}
                </small>
              </button>
            );
          })}
        </div>
      </div>
      {selected && (
        <NodeInspector
          node={selected}
          state={state}
          close={() => setSelected(null)}
          onCancelTask={onCancelTask}
        />
      )}
    </section>
  );
}

function NodeInspector({
  node,
  state,
  close,
  onCancelTask,
}: {
  node: NodeKey;
  state: QuorumyState;
  close: () => void;
  onCancelTask?: (taskId: string) => void;
}) {
  const runs = (state.agent_runs ?? [])
    .filter((run) => {
      if (node === "speaker") return run.agent === "speaker";
      if (node === "worker")
        return run.agent === "worker" || run.agent === "coordinator";
      return run.agent === node;
    })
    .slice(-8)
    .reverse();
  const title = {
    room: "Conversation",
    stt: "Transcription",
    memory: "Mémoire partagée",
    jev: "Orientation de la conversation",
    speaker: "Réponses de Quorumy",
    worker: "Recherches",
    notes: "Notes",
    board: "Tableau",
    voice: "Voix",
  }[node];
  return (
    <aside className="node-inspector">
      <header>
        <div>
          <span>Détails</span>
          <h2>{title}</h2>
        </div>
        <button onClick={close} aria-label="Fermer les détails">
          <X size={18} />
        </button>
      </header>
      {node === "jev" && (
        <div className="inspector-stack">
          {(state.decisions ?? [])
            .slice(-6)
            .reverse()
            .map((decision) => (
              <article className="inspection-card" key={decision.id}>
                <div>
                  <b>{decision.result.route}</b>
                  <time>
                    {decision.decided_at
                      ? new Date(decision.decided_at).toLocaleTimeString()
                      : "now"}
                  </time>
                </div>
                <p>{decision.context.new_utterance as string}</p>
                <dl>
                  <dt>Addressee</dt>
                  <dd>{decision.result.addressee}</dd>
                  <dt>Initiative</dt>
                  <dd>{decision.result.initiative}</dd>
                  <dt>Memory</dt>
                  <dd>{decision.result.memory}</dd>
                  <dt>Timing</dt>
                  <dd>{decision.result.timing}</dd>
                </dl>
                <details>
                  <summary>Contexte de la décision</summary>
                  <pre>{JSON.stringify(decision.context, null, 2)}</pre>
                </details>
              </article>
            ))}
          {!state.decisions?.length && (
            <p className="muted">Aucune décision pour le moment.</p>
          )}
        </div>
      )}
      {node === "worker" && (
        <ResearchTasks tasks={state.tasks} onCancel={onCancelTask} />
      )}
      {node === "memory" && (
        <div className="memory-inspector">
          <Stat label="Transcript" value={state.transcript.length} />
          <Stat label="Cards" value={state.cards.length} />
          <Stat label="Tasks" value={state.tasks.length} />
          <Stat label="Notes version" value={state.notes_version ?? 0} />
          <Stat label="Speech turns" value={state.speeches.length} />
          <Stat label="Activities" value={state.activities.length} />
        </div>
      )}
      {node === "room" && (
        <div className="memory-inspector">
          <Stat
            label="Audio frames"
            value={state.pipeline?.audio_frames ?? 0}
          />
          <Stat label="Audio bytes" value={state.pipeline?.audio_bytes ?? 0} />
          <Stat
            label="Committed turns"
            value={state.pipeline?.stt_turns ?? 0}
          />
        </div>
      )}
      {node === "stt" && (
        <div className="memory-inspector">
          <Stat label="Messages" value={state.pipeline?.stt_messages ?? 0} />
          <Stat label="Fragments" value={state.pipeline?.stt_fragments ?? 0} />
          <Stat label="Final turns" value={state.pipeline?.stt_turns ?? 0} />
          <Stat
            label="Silence"
            value={`${Math.round((state.pipeline?.stt_inactivity_probability ?? 0) * 100)}%`}
          />
        </div>
      )}
      {node === "notes" && (
        <div className="memory-inspector">
          <Stat label="Version" value={state.notes_version ?? 0} />
          <Stat
            label="Integrated"
            value={`${state.notes_cursor ?? 0}/${state.transcript.length}`}
          />
          <Stat label="Characters" value={state.notes.length} />
        </div>
      )}
      {node === "board" && (
        <div className="inspector-stack">
          {state.activities
            .filter((item) => item.kind.startsWith("board."))
            .slice(-10)
            .reverse()
            .map((item) => (
              <article className="inspection-card" key={item.id}>
                <b>{item.kind}</b>
                <p>{item.summary}</p>
              </article>
            ))}
        </div>
      )}
      {node === "voice" && (
        <div className="inspector-stack">
          {state.speeches
            .slice(-8)
            .reverse()
            .map((speech) => (
              <article className="inspection-card" key={speech.id}>
                <div>
                  <b>{speech.reason}</b>
                  <span className={speech.status}>{speech.status}</span>
                </div>
                <p>{speech.text}</p>
              </article>
            ))}
        </div>
      )}
      {(node === "speaker" || node === "worker" || node === "notes") && (
        <details className="inspector-stack">
          <summary>Historique des agents</summary>
          {runs.map((run) => (
            <article className="inspection-card" key={run.id}>
              <div>
                <b>{run.summary}</b>
                <span className={run.status}>
                  {
                    {
                      running: "En cours",
                      done: "Terminé",
                      failed: "Échec",
                      canceled: "Annulé",
                    }[run.status]
                  }
                </span>
              </div>
              <p>
                {typeof run.duration_ms === "number"
                  ? `${(run.duration_ms / 1000).toFixed(1)} s`
                  : run.status === "running"
                    ? "En cours"
                    : "Durée indisponible"}
              </p>
              {run.error && <code>{run.error}</code>}
            </article>
          ))}
          {!runs.length && (
            <p className="muted">Aucune activité enregistrée.</p>
          )}
        </details>
      )}
    </aside>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <span>{label}</span>
      <b>{value}</b>
    </div>
  );
}
