import {
  Captions,
  CaptionsOff,
  Download,
  MessageSquareText,
  Pause,
  Pencil,
  Play,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";

import type { QuorumyLanguage } from "../protocol";
import { MeetingAudioSetup } from "./MeetingAudioSetup";

type Props = {
  language: QuorumyLanguage;
  languages: Array<{ value: QuorumyLanguage; label: string }>;
  canCurate: boolean;
  curatorRunning: boolean;
  voiceMode: "active" | "muted";
  subtitlesEnabled: boolean;
  promptBarVisible: boolean;
  listening: boolean;
  onLanguage: (language: QuorumyLanguage) => void;
  onCurate: () => void;
  onToggleVoice: () => void;
  onToggleSubtitles: () => void;
  onTogglePromptBar: () => void;
  onRename: () => void;
  onExport: () => void;
  onPauseResume: () => void;
  onEnd: () => void;
};

export function SessionControls(p: Props) {
  return (
    <>
      <button
        className="control-pause"
        onClick={p.onPauseResume}
        title={p.listening ? "Mettre en pause" : "Reprendre l’assistant"}
      >
        {p.listening ? <Pause size={16} /> : <Play size={16} />}
        <span>{p.listening ? "Pause" : "Reprendre"}</span>
      </button>
      <details
        className="session-menu"
        onKeyDown={(e) => {
          if (e.key === "Escape") e.currentTarget.open = false;
        }}
      >
        <summary aria-label="Options de la session">•••</summary>
        <div className="session-menu-content">
          <label>
            Langue
            <select
              value={p.language}
              onChange={(e) => p.onLanguage(e.target.value as QuorumyLanguage)}
            >
              {p.languages.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <MeetingAudioSetup />
          <button
            disabled={!p.canCurate || p.curatorRunning || !p.listening}
            onClick={p.onCurate}
            title={
              !p.canCurate ? "Aucune idée à organiser" : "Organiser le tableau"
            }
          >
            <Sparkles size={17} />
            Organiser le tableau
          </button>
          <button
            onClick={p.onToggleVoice}
            aria-pressed={p.voiceMode === "active"}
            title={
              p.voiceMode === "muted" ? "Activer la voix" : "Couper la voix"
            }
          >
            {p.voiceMode === "muted" ? (
              <VolumeX size={17} />
            ) : (
              <Volume2 size={17} />
            )}
            Voix {p.voiceMode === "active" ? "activée" : "coupée"}
          </button>
          <button
            onClick={p.onToggleSubtitles}
            aria-pressed={p.subtitlesEnabled}
            title={
              p.subtitlesEnabled
                ? "Masquer les sous-titres"
                : "Afficher les sous-titres"
            }
          >
            {p.subtitlesEnabled ? (
              <Captions size={17} />
            ) : (
              <CaptionsOff size={17} />
            )}
            Sous-titres
          </button>
          <button
            onClick={p.onTogglePromptBar}
            aria-pressed={p.promptBarVisible}
            title={
              p.promptBarVisible ? "Masquer la saisie" : "Afficher la saisie"
            }
          >
            <MessageSquareText size={17} />
            Saisie au clavier
          </button>
          <button onClick={p.onRename} title="Renommer la session">
            <Pencil size={17} />
            Renommer
          </button>
          <button onClick={p.onExport} title="Exporter la session">
            <Download size={17} />
            Exporter la session
          </button>
          <button
            className="danger"
            onClick={p.onEnd}
            title="Terminer la session"
          >
            <Square size={16} />
            Terminer la session
          </button>
        </div>
      </details>
    </>
  );
}
