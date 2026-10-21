import { useState } from "react";
import type { AccountBody } from "../api";

const DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct:cheapest";

type Props = {
  error: string;
  onSubmit: (mode: "register" | "login", body: AccountBody) => Promise<void>;
};

export function AccountGate({ error, onSubmit }: Props) {
  const [mode, setMode] = useState<"register" | "login">("register");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [hfToken, setHfToken] = useState("");
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [modelEdited, setModelEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState("");

  async function submit() {
    setLocalError("");
    setBusy(true);
    try {
      await onSubmit(mode, {
        name: name.trim(),
        password,
        hf_token: hfToken.trim(),
        model: mode === "login" && !modelEdited ? "" : model.trim(),
      });
    } catch (reason) {
      setLocalError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="account-gate">
      <section className="launch-card">
        <p className="eyebrow">QUORUMY</p>
        <h1>Un compte, votre clé Hugging Face.</h1>
        <p>
          Quorumy suit la réunion, cherche et repère les incohérences. Il ne
          parle que lorsque la parole lui est donnée. La clé reste sur le
          serveur, jamais dans la page.
        </p>
        <label>
          Nom
          <input
            value={name}
            autoComplete="username"
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Mot de passe
          <input
            type="password"
            value={password}
            autoComplete={
              mode === "register" ? "new-password" : "current-password"
            }
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <label>
          Clé Hugging Face
          <input
            type="password"
            value={hfToken}
            autoComplete="off"
            placeholder="hf_…"
            onChange={(event) => setHfToken(event.target.value)}
          />
        </label>
        <label>
          Modèle
          <input
            value={model}
            onChange={(event) => {
              setModel(event.target.value);
              setModelEdited(true);
            }}
          />
        </label>
        <p className="account-hint">
          {mode === "login"
            ? "Sans modification, la clé et le modèle déjà enregistrés sont conservés."
            : "Ajoutez :cheapest, :fastest ou :preferred pour choisir comment Hugging Face route le modèle."}
        </p>
        {(localError || error) && (
          <p className="error">{localError || error}</p>
        )}
        <button type="button" disabled={busy} onClick={() => void submit()}>
          {mode === "register" ? "Créer le compte" : "Entrer"}
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() =>
            setMode((current) =>
              current === "register" ? "login" : "register",
            )
          }
        >
          {mode === "register" ? "J’ai déjà un compte" : "Créer un compte"}
        </button>
      </section>
    </main>
  );
}
