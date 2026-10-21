import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuorumyState } from "../protocol";
import { Board, Transcript } from "./WorkspaceViews";

const base = {
  transcript: [],
  speeches: [],
  tasks: [],
  cards: [],
} as unknown as QuorumyState;

describe("Meeting evidence", () => {
  it("distinguishes interrupted and text-only answers from canceled voice drafts", () => {
    const speech = {
      reason: "direct_address",
      source_ids: [],
      room_epoch: 1,
      created_at: "2026-01-01T10:00:00Z",
    };
    const state = {
      ...base,
      speeches: [
        { ...speech, id: "done", text: "Réponse terminée", status: "finished" },
        {
          ...speech,
          id: "cut",
          text: "Réponse partielle",
          status: "interrupted",
        },
        {
          ...speech,
          id: "canceled",
          text: "Ancien brouillon annulé",
          status: "canceled",
        },
        {
          ...speech,
          id: "waiting",
          text: "Brouillon en attente",
          status: "waiting_gap",
        },
        {
          ...speech,
          id: "muted",
          text: "Réponse écrite utile",
          status: "suppressed",
          error: "voice_muted",
        },
        {
          ...speech,
          id: "blocked",
          text: "Répétition bloquée",
          status: "suppressed",
          error: "duplicate",
        },
      ],
    } as QuorumyState;
    render(<Transcript state={state} partial="" />);
    expect(screen.getByText("Réponse terminée")).toBeTruthy();
    expect(screen.getByText("Interrompue · texte préparé")).toBeTruthy();
    expect(screen.getByText("Réponse écrite utile")).toBeTruthy();
    expect(screen.queryByText("Ancien brouillon annulé")).toBeNull();
    expect(screen.queryByText("Brouillon en attente")).toBeNull();
    expect(screen.queryByText("Répétition bloquée")).toBeNull();
  });

  it("links research results from the actual tool payload to their board card", () => {
    const state = {
      ...base,
      cards: [
        {
          id: "card1",
          kind: "finding",
          title: "Document vérifié",
          body: "Résultat",
          source_ids: ["task1"],
        },
      ],
      tasks: [
        {
          id: "task1",
          result: {
            results: [
              { title: "Notice officielle", url: "https://example.org/notice" },
            ],
          },
        },
      ],
    } as unknown as QuorumyState;
    render(<Board state={state} />);
    expect(
      screen
        .getByRole("link", { name: "Notice officielle" })
        .getAttribute("href"),
    ).toBe("https://example.org/notice");
  });

  it("shows the question and distinct safe research sources under Quorumy's answer", () => {
    const state = {
      ...base,
      transcript: [
        { id: "question", text: "Quelle source ?", speaker: "Renard" },
      ],
      speeches: [
        {
          id: "answer",
          text: "Voici le résultat.",
          status: "finished",
          source_ids: ["research"],
        },
      ],
      tasks: [
        {
          id: "research",
          source_utterance_id: "question",
          result: {
            sources: [
              {
                title: "Document original",
                url: "https://example.org/evidence",
              },
              { title: "Lien dangereux", url: "javascript:alert(1)" },
              {
                title: "Identifiants cachés",
                url: "https://user:password@example.org/",
              },
            ],
            results: [
              { title: "Doublon", url: "https://example.org/evidence" },
              null,
              { title: "Sans URL" },
            ],
          },
        },
      ],
    } as unknown as QuorumyState;
    render(<Transcript state={state} partial="" />);
    fireEvent.click(screen.getByText("Origine de cette réponse"));
    expect(screen.getByText("Sources consultées · 1")).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(
      screen
        .getByRole("link", { name: "Document original" })
        .getAttribute("href"),
    ).toBe("https://example.org/evidence");
    expect(screen.queryByRole("link", { name: "Lien dangereux" })).toBeNull();
    expect(screen.getAllByText("Quelle source ?")).toHaveLength(2);
  });
});
