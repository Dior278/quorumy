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
        <Volume2 size={16} /> Faire entendre Quorumy dans l’appel
      </summary>
      <div className="meeting-audio-body">
        <p>
          Vous entendez Quorumy sur cet ordinateur. Pour le faire entendre aux
          participants, activez aussi le partage de son dans la réunion.
          Utilisez un casque.
        </p>
        <ol>
          <li>
            <strong>L’appel → Quorumy.</strong> Choisissez « Microphone + audio
            partagé ». Au démarrage, sélectionnez l’onglet de la réunion avec
            son audio.
          </li>
          <li>
            <strong>Quorumy → l’appel.</strong> Dans Teams sur le web : Partager
            → Écran, fenêtre ou onglet → Onglet. Sélectionnez Quorumy et activez
            « Partager aussi l’audio de l’onglet ». Dans Meet : Présenter → Un
            onglet, avec son audio.
          </li>
          <li>
            <strong>Vérifiez ensemble.</strong> Jouez le son ci-dessous et
            faites confirmer sa réception par un participant. Gardez la voix de
            Quorumy activée.
          </li>
        </ol>
        <button type="button" onClick={testSound} disabled={testing}>
          <Volume2 size={16} /> {testing ? "Lecture…" : "Jouer le son de test"}
        </button>
        {result === "played" && (
          <p role="status">
            Deux notes jouées dans cet onglet. Un participant doit confirmer les
            avoir entendues.
          </p>
        )}
        {result === "error" && (
          <p role="alert">
            Le son n’a pas pu être joué. Vérifiez la sortie audio du navigateur,
            puis réessayez.
          </p>
        )}
        <p className="meeting-audio-help">
          Choisissez l’onglet de la réunion pour l’écoute, pas tout le son de
          l’ordinateur : Quorumy risquerait de s’entendre. Le partage vers
          l’appel se règle dans votre plateforme.
        </p>
        <p className="meeting-audio-links">
          Guides audio :{" "}
          <a
            href="https://support.google.com/meet/answer/9308856?hl=fr"
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
          . Sur Zoom installé, utilisez « Partager le son » ; vérifiez aussi
          l’absence d’écho.
        </p>
      </div>
    </details>
  );
}
