import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpenText } from "lucide-react";
import type { QuorumyState } from "../protocol";

export function NotesView({ state }: { state: QuorumyState }) {
  if (!state.notes) {
    return (
      <div className="empty notes-empty">
        <BookOpenText />
        <h2>Un espace pour vos idées.</h2>
        <p>
          Parlez ou écrivez. Quorumy organise vos notes dès qu’une idée se
          précise.
        </p>
      </div>
    );
  }
  const readableNotes = state.notes.replace(/\s*\[(utt_[^\]]+)]/g, "");
  return (
    <section className="notes-shell">
      <header className="notes-meta">
        <div>
          <BookOpenText />
          <span>Notes vivantes</span>
        </div>
        <div>
          <b>v{state.notes_version ?? 0}</b>
          <span>
            {state.notes_cursor ?? 0}/{state.transcript.length} interventions
            intégrées
          </span>
        </div>
      </header>
      <article className="notes-document">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {readableNotes}
        </ReactMarkdown>
      </article>
    </section>
  );
}
