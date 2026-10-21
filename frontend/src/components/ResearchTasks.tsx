import type { QuorumyState } from "../protocol";

type Task = QuorumyState["tasks"][number];

const tools: Record<string, string> = {
  research_web: "Web research",
  system_capabilities: "Available tools",
  pending_selection: "Research request",
};

function statusLabel(task: Task): string {
  if (task.status === "done") return "Done";
  if (task.status === "canceled") return "Canceled";
  if (task.status === "failed") return "Failed";
  if (task.status === "stale") return "Outdated";
  return (
    (
      {
        queued: "Waiting",
        planning: "Preparing",
        executing: "Researching",
        synthesizing: "Synthesizing",
        integrating: "Integrating",
        reporting: "Reporting",
      } as Record<string, string>
    )[task.phase ?? "queued"] ?? "In progress"
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
              <b>{tools[task.tool] ?? "Research"}</b>
              <span className={task.status}>{statusLabel(task)}</span>
            </div>
            <p>{task.summary}</p>
            {task.error && (
              <p className="task-error">
                {task.error === "mission_timeout"
                  ? "The time limit was reached. You can rephrase the request."
                  : task.error === "duplicate_in_progress"
                    ? "The same research is already running."
                    : task.status === "canceled"
                      ? "This research was stopped."
                      : "The research did not finish. Other work is still available."}
              </p>
            )}
            {typeof task.duration_ms === "number" && (
              <small>
                Total time: {(task.duration_ms / 1000).toFixed(1)} s
              </small>
            )}
            {task.reused_from && task.result && (
              <small>This result was already found in this session.</small>
            )}
            {onCancel &&
              task.id &&
              (task.status === "running" || task.status === "queued") && (
                <button
                  className="task-cancel"
                  onClick={() => onCancel(task.id!)}
                >
                  Stop this research
                </button>
              )}
            {task.result && (
              <details>
                <summary>Result detail</summary>
                <pre>{JSON.stringify(task.result, null, 2)}</pre>
              </details>
            )}
          </article>
        ))}
      {!tasks.length && <p className="muted">No research yet.</p>}
    </div>
  );
}
