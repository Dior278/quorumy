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
        { ...speech, id: "done", text: "Finished answer", status: "finished" },
        {
          ...speech,
          id: "cut",
          text: "Partial answer",
          status: "interrupted",
        },
        {
          ...speech,
          id: "canceled",
          text: "Canceled old draft",
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
          text: "Useful written answer",
          status: "suppressed",
          error: "voice_muted",
        },
        {
          ...speech,
          id: "blocked",
          text: "Blocked repetition",
          status: "suppressed",
          error: "duplicate",
        },
      ],
    } as QuorumyState;
    render(<Transcript state={state} partial="" />);
    expect(screen.getByText("Finished answer")).toBeTruthy();
    expect(screen.getByText("Interrupted · prepared text")).toBeTruthy();
    expect(screen.getByText("Useful written answer")).toBeTruthy();
    expect(screen.queryByText("Canceled old draft")).toBeNull();
    expect(screen.queryByText("Brouillon en attente")).toBeNull();
    expect(screen.queryByText("Blocked repetition")).toBeNull();
  });

  it("links research results from the actual tool payload to their board card", () => {
    const state = {
      ...base,
      cards: [
        {
          id: "card1",
          kind: "finding",
          title: "Verified document",
          body: "Result",
          source_ids: ["task1"],
        },
      ],
      tasks: [
        {
          id: "task1",
          result: {
            results: [
              { title: "Official notice", url: "https://example.org/notice" },
            ],
          },
        },
      ],
    } as unknown as QuorumyState;
    render(<Board state={state} />);
    expect(
      screen
        .getByRole("link", { name: "Official notice" })
        .getAttribute("href"),
    ).toBe("https://example.org/notice");
  });

  it("shows the question and distinct safe research sources under Quorumy's answer", () => {
    const state = {
      ...base,
      transcript: [{ id: "question", text: "Which source?", speaker: "You" }],
      speeches: [
        {
          id: "answer",
          text: "Here is the result.",
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
                title: "Original document",
                url: "https://example.org/evidence",
              },
              { title: "Unsafe link", url: "javascript:alert(1)" },
              {
                title: "Hidden credentials",
                url: "https://user:password@example.org/",
              },
            ],
            results: [
              { title: "Duplicate", url: "https://example.org/evidence" },
              null,
              { title: "No URL" },
            ],
          },
        },
      ],
    } as unknown as QuorumyState;
    render(<Transcript state={state} partial="" />);
    fireEvent.click(screen.getByText("Where this answer came from"));
    expect(screen.getByText("Sources checked · 1")).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(
      screen
        .getByRole("link", { name: "Original document" })
        .getAttribute("href"),
    ).toBe("https://example.org/evidence");
    expect(screen.queryByRole("link", { name: "Unsafe link" })).toBeNull();
    expect(screen.getAllByText("Which source?")).toHaveLength(2);
  });
});
