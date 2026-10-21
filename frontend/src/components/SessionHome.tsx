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
        Les personnes concernées sont informées et d’accord pour l’analyse par
        l’IA.
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
            <span className="tiny-orbit" /> UN PEU PLUS LOIN, ENSEMBLE
          </p>
          <h1>
            Toute la conversation.
            <br />
            <em>Une longueur d’avance.</em>
          </h1>
          <p className="hero-description">
            Vous faites avancer les idées. Quorumy garde le fil, vérifie ce qui
            se dit et ne parle que lorsque la parole lui est donnée.
          </p>
          <div className="hero-caption">
            <span className="caption-line" /> À vos côtés, sans rejoindre
            l’appel.
          </div>
        </div>
        <div className="launch-card">
          <div className="launch-card-heading">
            <div className="quorumy-orbit">
              <img src="/quorumy-mark.svg" alt="" />
            </div>
            <span>VOTRE PROCHAINE CONVERSATION</span>
          </div>
          <h2>Faites une place à Quorumy.</h2>
          <p>
            Ouvrez votre réunion habituelle, puis choisissez ce que Quorumy peut
            écouter.
          </p>
          <label>
            Source de la conversation
            <select
              value={p.captureMode}
              onChange={(e) => p.onCapture(e.target.value as CaptureMode)}
              disabled={p.starting}
            >
              <option value="text">Texte · sans microphone</option>
              <option value="microphone">Microphone</option>
              <option value="mixed" disabled={!systemSupported}>
                Microphone + audio partagé
              </option>
              <option value="system" disabled={!systemSupported}>
                Audio d’un onglet ou du système
              </option>
            </select>
          </label>
          {(p.captureMode === "mixed" || p.captureMode === "system") && (
            <MeetingAudioSetup />
          )}
          <details className="launch-options">
            <summary>
              Langue · {LANGUAGES.find((l) => l.value === p.language)?.label}
            </summary>
            <label>
              Langue de la session
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
            {p.starting ? "Préparation…" : "Démarrer une session"}
            <ArrowUpRight size={18} />
          </button>
          <p className="privacy-note">
            <ShieldCheck size={14} /> Mémoire sur cet ordinateur. Analyse via
            les services configurés.
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
            <span>01 / PENDANT</span>
            <h3>Gardez le fil.</h3>
            <p>
              Des notes qui suivent la discussion, sans interrompre vos idées.
            </p>
          </div>
        </article>
        <article>
          <Layers3 size={20} />
          <div>
            <span>02 / PLUS LOIN</span>
            <h3>Explorez ensemble.</h3>
            <p>Des recherches en parallèle, des résultats et leurs sources.</p>
          </div>
        </article>
        <article>
          <FileCheck2 size={20} />
          <div>
            <span>03 / ENSUITE</span>
            <h3>Retenez l’essentiel.</h3>
            <p>
              Des engagements à relire et confirmer, avec les paroles d’origine.
            </p>
          </div>
        </article>
      </div>
      {openCommitments > 0 && (
        <p className="memory-banner">
          {openCommitments > 1
            ? `${openCommitments} engagements confirmés vous attendent. La prochaine réunion commencera avec eux.`
            : `${openCommitments} engagement confirmé vous attend. La prochaine réunion commencera avec eux.`}
        </p>
      )}
      <section className="session-library" aria-label="Sessions enregistrées">
        <div className="session-library-heading">
          <div>
            <p className="eyebrow">VOTRE MÉMOIRE</p>
            <h2>Reprendre le fil</h2>
          </div>
          <span>
            {p.sessions.length} session{p.sessions.length > 1 ? "s" : ""}
          </span>
        </div>
        {p.sessions.length === 0 ? (
          <p className="library-empty">
            Vos conversations apparaîtront ici. Vous pourrez les relire et les
            exporter à tout moment.
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
                    <small>
                      {session.preview || "Aucune intervention enregistrée"}
                    </small>
                  </span>
                  <span className="session-meta">
                    <small>{session.utterance_count} interventions</small>
                    <time>
                      {new Date(session.updated_at).toLocaleDateString("fr-FR")}
                    </time>
                  </span>
                </button>
                <div className="session-tools">
                  <button
                    onClick={() =>
                      p.onRename(session.session_id, session.title)
                    }
                  >
                    Renommer
                  </button>
                  <button onClick={() => p.onExport(session.session_id)}>
                    Exporter
                  </button>
                  <button
                    className="danger"
                    onClick={() =>
                      p.onDelete(session.session_id, session.title)
                    }
                  >
                    Supprimer
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
      <p className="home-credit">
        Quorumy suit la réunion et lève la main quand quelque chose urge.
      </p>
    </section>
  );
}
