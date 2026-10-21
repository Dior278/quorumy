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
        title={p.listening ? "Pause" : "Resume the companion"}
      >
        {p.listening ? <Pause size={16} /> : <Play size={16} />}
        <span>{p.listening ? "Pause" : "Resume"}</span>
      </button>
      <details
        className="session-menu"
        onKeyDown={(e) => {
          if (e.key === "Escape") e.currentTarget.open = false;
        }}
      >
        <summary aria-label="Session options">•••</summary>
        <div className="session-menu-content">
          <label>
            Language
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
            title={!p.canCurate ? "No ideas to organize" : "Organize the board"}
          >
            <Sparkles size={17} />
            Organize the board
          </button>
          <button
            onClick={p.onToggleVoice}
            aria-pressed={p.voiceMode === "active"}
            title={p.voiceMode === "muted" ? "Turn voice on" : "Mute voice"}
          >
            {p.voiceMode === "muted" ? (
              <VolumeX size={17} />
            ) : (
              <Volume2 size={17} />
            )}
            Voice {p.voiceMode === "active" ? "on" : "off"}
          </button>
          <button
            onClick={p.onToggleSubtitles}
            aria-pressed={p.subtitlesEnabled}
            title={p.subtitlesEnabled ? "Hide subtitles" : "Show subtitles"}
          >
            {p.subtitlesEnabled ? (
              <Captions size={17} />
            ) : (
              <CaptionsOff size={17} />
            )}
            Subtitles
          </button>
          <button
            onClick={p.onTogglePromptBar}
            aria-pressed={p.promptBarVisible}
            title={p.promptBarVisible ? "Hide typing" : "Show typing"}
          >
            <MessageSquareText size={17} />
            Keyboard input
          </button>
          <button onClick={p.onRename} title="Rename the session">
            <Pencil size={17} />
            Rename
          </button>
          <button onClick={p.onExport} title="Export the session">
            <Download size={17} />
            Export the session
          </button>
          <button className="danger" onClick={p.onEnd} title="End the session">
            <Square size={16} />
            End the session
          </button>
        </div>
      </details>
    </>
  );
}
