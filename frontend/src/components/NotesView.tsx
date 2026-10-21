import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { BookOpenText } from "lucide-react";
import type { QuorumyState } from "../protocol";

export function NotesView({ state }: { state: QuorumyState }) {
  if (!state.notes) {
    return (
      <div className="empty notes-empty">
        <BookOpenText />
        <h2>A place for your ideas.</h2>
        <p>
          Speak or type. Quorumy organizes your notes as an idea takes shape.
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
          <span>Living notes</span>
        </div>
        <div>
          <b>v{state.notes_version ?? 0}</b>
          <span>
            {state.notes_cursor ?? 0}/{state.transcript.length} turns integrated
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
