import type { QuorumyState } from "../protocol";

type Task = QuorumyState["tasks"][number];

const tools: Record<string, string> = {
  research_web: "Recherche web",
  system_capabilities: "Outils disponibles",
  pending_selection: "Demande de recherche",
};

function statusLabel(task: Task): string {
  if (task.status === "done") return "Terminée";
  if (task.status === "canceled") return "Annulée";
  if (task.status === "failed") return "Échec";
  if (task.status === "stale") return "Périmée";
  return (
    (
      {
        queued: "En attente",
        planning: "Préparation",
        executing: "Recherche",
        synthesizing: "Synthèse",
        integrating: "Intégration",
        reporting: "Restitution",
      } as Record<string, string>
    )[task.phase ?? "queued"] ?? "En cours"
  );
}

export function ResearchTasks({
  tasks,
  onCancel,
}: {
  tasks: Task[];
  onCancel?: (taskId: string) => void;
}) {
  return (
    <div className="inspector-stack">
      {tasks
        .slice()
        .reverse()
        .map((task) => (
          <article className="inspection-card" key={task.id}>
            <div>
              <b>{tools[task.tool] ?? "Recherche"}</b>
              <span className={task.status}>{statusLabel(task)}</span>
            </div>
            <p>{task.summary}</p>
            {task.error && (
              <p className="task-error">
                {task.error === "mission_timeout"
                  ? "Le délai maximal est atteint. Vous pouvez reformuler la demande."
                  : task.error === "duplicate_in_progress"
                    ? "Une recherche identique est déjà en cours."
                    : task.status === "canceled"
                      ? "Cette recherche a été arrêtée."
                      : "La recherche n’a pas abouti. Les autres travaux restent disponibles."}
              </p>
            )}
            {typeof task.duration_ms === "number" && (
              <small>
                Durée totale : {(task.duration_ms / 1000).toFixed(1)} s
              </small>
            )}
            {task.reused_from && task.result && (
              <small>Résultat déjà obtenu dans cette session.</small>
            )}
            {onCancel &&
              task.id &&
              (task.status === "running" || task.status === "queued") && (
                <button
                  className="task-cancel"
                  onClick={() => onCancel(task.id!)}
                >
                  Arrêter cette recherche
                </button>
              )}
            {task.result && (
              <details>
                <summary>Détail du résultat</summary>
                <pre>{JSON.stringify(task.result, null, 2)}</pre>
              </details>
            )}
          </article>
        ))}
      {!tasks.length && (
        <p className="muted">Aucune recherche pour le moment.</p>
      )}
    </div>
  );
}
