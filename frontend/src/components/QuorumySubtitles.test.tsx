import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QuorumySubtitles } from "./QuorumySubtitles";

describe("QuorumySubtitles", () => {
  it("shows only Quorumy spoken text while enabled", () => {
    const { rerender } = render(
      <QuorumySubtitles
        enabled
        text="I found the source."
        companionName="Quorumy"
      />,
    );
    expect(screen.getByRole("status").textContent).toContain(
      "I found the source.",
    );
    rerender(
      <QuorumySubtitles
        enabled={false}
        text="Hidden"
        companionName="Quorumy"
      />,
    );
    expect(screen.queryByRole("status")).toBeNull();
    rerender(
      <QuorumySubtitles
        enabled
        text="Current spoken phrase"
        companionName="Quorumy"
      />,
    );
    expect(screen.getByRole("status").textContent).toContain(
      "Current spoken phrase",
    );
  });

  it("shows the current trailing clauses without ellipsis for long speech", () => {
    const longText =
      "The first sentence explains the background in detail. " +
      "The second sentence contains the current spoken point. " +
      "The final sentence is what participants should read now.";
    render(
      <QuorumySubtitles enabled text={longText} companionName="Quorumy" />,
    );
    const subtitle = screen.getByRole("status");
    expect(subtitle.textContent).toContain(
      "The final sentence is what participants should read now.",
    );
    expect(subtitle.textContent).not.toContain("...");
  });
});
