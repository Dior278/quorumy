import { useState } from "react";
import { Volume2 } from "lucide-react";

import { playMeetingTestSound } from "../meetingAudio";

export function MeetingAudioSetup() {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<"played" | "error" | null>(null);

  async function testSound() {
    if (testing) return;
    setTesting(true);
    setResult(null);
    try {
      await playMeetingTestSound();
      setResult("played");
    } catch {
      setResult("error");
    } finally {
      setTesting(false);
    }
  }

  return (
    <details className="meeting-audio">
      <summary>
        <Volume2 size={16} /> Let the call hear Quorumy
      </summary>
      <div className="meeting-audio-body">
        <p>
          You hear Quorumy on this computer. To let other participants hear it,
          also share sound in the meeting. Use headphones.
        </p>
        <ol>
          <li>
            <strong>Call → Quorumy.</strong> Choose “Microphone + shared audio”.
            When you start, select the meeting tab with its audio.
          </li>
          <li>
            <strong>Quorumy → call.</strong> In Teams on the web: Share →
            Screen, window, or tab → Tab. Select Quorumy and turn on “Also share
            tab audio”. In Meet: Present → A tab, with its audio.
          </li>
          <li>
            <strong>Check together.</strong> Play the sound below and ask a
            participant to confirm they heard it. Keep Quorumy’s voice on.
          </li>
        </ol>
        <button type="button" onClick={testSound} disabled={testing}>
          <Volume2 size={16} /> {testing ? "Playing…" : "Play the test sound"}
        </button>
        {result === "played" && (
          <p role="status">
            Two notes played in this tab. A participant must confirm they heard
            them.
          </p>
        )}
        {result === "error" && (
          <p role="alert">
            The sound could not be played. Check the browser audio output, then
            try again.
          </p>
        )}
        <p className="meeting-audio-help">
          Choose the meeting tab for listening, not all computer sound: Quorumy
          could hear itself. Sharing into the call is set in your meeting app.
        </p>
        <p className="meeting-audio-links">
          Audio guides:{" "}
          <a
            href="https://support.google.com/meet/answer/9308856?hl=en"
            target="_blank"
            rel="noreferrer"
          >
            Meet
          </a>
          {" · "}
          <a
            href="https://support.microsoft.com/en-us/teams/meetings/share-sound-from-your-computer-in-microsoft-teams-meetings-or-live-events"
            target="_blank"
            rel="noreferrer"
          >
            Teams
          </a>
          {" · "}
          <a
            href="https://support.zoom.com/hc/en/article?id=zm_kb&sysparm_article=KB0063608"
            target="_blank"
            rel="noreferrer"
          >
            Zoom
          </a>
          . On the Zoom app, use “Share sound”; also check that there is no
          echo.
        </p>
      </div>
    </details>
  );
}
