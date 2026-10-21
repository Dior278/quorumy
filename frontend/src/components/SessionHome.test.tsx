import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionSummary } from "../protocol";
import { SessionHome } from "./SessionHome";

const session = {
  session_id: "s1",
  title: "Budget",
  status: "closed",
  preview: "",
  utterance_count: 4,
  open_commitments: 2,
  created_at: "2026-10-21T10:00:00Z",
  updated_at: "2026-10-21T10:00:00Z",
} as SessionSummary;

describe("Session home memory", () => {
  it("tells the next meeting which confirmed commitments are waiting", () => {
    render(
      <SessionHome
        sessions={[session]}
        language="fr"
        captureMode="text"
        consent={false}
        connected
        starting={false}
        error=""
        onConsent={() => undefined}
        onLanguage={() => undefined}
        onCapture={() => undefined}
        onStart={() => undefined}
        onOpen={() => undefined}
        onRename={() => undefined}
        onDelete={() => undefined}
        onExport={() => undefined}
      />,
    );
    expect(
      screen.getByText(/2 engagements confirmés vous attendent/),
    ).toBeTruthy();
  });
});
