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
        <h1>One account, your Hugging Face key.</h1>
        <p>
          Quorumy follows the meeting, researches, and spots inconsistencies. It
          speaks only when given the floor. The key stays on the server, never
          in the page.
        </p>
        <label>
          Name
          <input
            value={name}
            autoComplete="username"
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label>
          Password
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
          Hugging Face key
          <input
            type="password"
            value={hfToken}
            autoComplete="off"
            placeholder="hf_…"
            onChange={(event) => setHfToken(event.target.value)}
          />
        </label>
        <label>
          Model
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
            ? "Leave these unchanged to keep the saved key and model."
            : "Add :cheapest, :fastest, or :preferred to choose how Hugging Face routes the model."}
        </p>
        {(localError || error) && (
          <p className="error">{localError || error}</p>
        )}
        <button type="button" disabled={busy} onClick={() => void submit()}>
          {mode === "register" ? "Create account" : "Sign in"}
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
          {mode === "register"
            ? "I already have an account"
            : "Create an account"}
        </button>
      </section>
    </main>
  );
}
