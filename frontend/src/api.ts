import type { Bootstrap, ClientMessage } from "./protocol";

let accessToken = "";

export class AuthRequired extends Error {
  constructor() {
    super("Connectez-vous pour utiliser Quorumy.");
    this.name = "AuthRequired";
  }
}

export async function bootstrap(): Promise<Bootstrap> {
  const response = await fetch("/v1/bootstrap", { credentials: "include" });
  if (response.status === 401) throw new AuthRequired();
  if (!response.ok) throw new Error(`Bootstrap failed: ${response.status}`);
  const payload = (await response.json()) as Bootstrap;
  accessToken = payload.access_token;
  return payload;
}

export async function request(
  path: string,
  method = "GET",
  body?: object,
): Promise<Response> {
  const response = await fetch(path, {
    method,
    credentials: "include",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : `This action is unavailable (${response.status}).`,
    );
  }
  return response;
}

export async function download(path: string, filename: string): Promise<void> {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function liveSocket(): WebSocket {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return new WebSocket(`${scheme}://${location.host}/v1/live`);
}

export function send(socket: WebSocket, message: ClientMessage): void {
  if (socket.readyState === WebSocket.OPEN)
    socket.send(JSON.stringify(message));
}

export async function renameQuorumySession(
  sessionId: string,
  title: string,
): Promise<void> {
  await request(`/v1/sessions/${encodeURIComponent(sessionId)}`, "PATCH", {
    title,
  });
}

export async function deleteQuorumySession(sessionId: string): Promise<void> {
  await request(`/v1/sessions/${encodeURIComponent(sessionId)}`, "DELETE");
}

export function exportQuorumySession(sessionId: string): Promise<void> {
  return download(
    `/v1/sessions/${encodeURIComponent(sessionId)}/export`,
    `${sessionId}.md`,
  );
}

export type AccountBody = {
  name: string;
  password: string;
  hf_token?: string;
  model?: string;
};

async function accountRequest(path: string, body: AccountBody): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      typeof error.detail === "string" ? error.detail : "Connexion impossible.",
    );
  }
}

export function registerAccount(body: AccountBody): Promise<void> {
  return accountRequest("/v1/register", body);
}

export function loginAccount(body: AccountBody): Promise<void> {
  return accountRequest("/v1/login", body);
}
