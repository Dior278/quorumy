import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SessionControls } from "./SessionControls";

function renderControls(
  overrides: Partial<Parameters<typeof SessionControls>[0]> = {},
) {
  const actions = {
    onLanguage: vi.fn(),
    onCurate: vi.fn(),
    onToggleVoice: vi.fn(),
    onToggleSubtitles: vi.fn(),
    onTogglePromptBar: vi.fn(),
    onRename: vi.fn(),
    onExport: vi.fn(),
    onPauseResume: vi.fn(),
    onEnd: vi.fn(),
  };
  render(
    <SessionControls
      language="en"
      languages={[
        { value: "en", label: "English" },
        { value: "fr", label: "Français" },
      ]}
      canCurate
      curatorRunning={false}
      voiceMode="active"
      subtitlesEnabled
      promptBarVisible
      listening
      {...actions}
      {...overrides}
    />,
  );
  return actions;
}

describe("SessionControls", () => {
  it("connects every visible action", () => {
    const actions = renderControls();
    fireEvent.click(screen.getByTitle("Organize the board"));
    fireEvent.click(screen.getByTitle("Mute voice"));
    fireEvent.click(screen.getByTitle("Hide subtitles"));
    fireEvent.click(screen.getByTitle("Hide typing"));
    fireEvent.click(screen.getByTitle("Rename the session"));
    fireEvent.click(screen.getByTitle("Export the session"));
    fireEvent.click(screen.getByTitle("Pause"));
    fireEvent.click(screen.getByTitle("End the session"));
    expect(actions.onCurate).toHaveBeenCalledOnce();
    expect(actions.onToggleVoice).toHaveBeenCalledOnce();
    expect(actions.onToggleSubtitles).toHaveBeenCalledOnce();
    expect(actions.onTogglePromptBar).toHaveBeenCalledOnce();
    expect(actions.onRename).toHaveBeenCalledOnce();
    expect(actions.onExport).toHaveBeenCalledOnce();
    expect(actions.onPauseResume).toHaveBeenCalledOnce();
    expect(actions.onEnd).toHaveBeenCalledOnce();
  });

  it("disables curation when there is no board content", () => {
    const actions = renderControls({ canCurate: false });
    const button = screen.getByTitle(
      "No ideas to organize",
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(actions.onCurate).not.toHaveBeenCalled();
  });

  it("reports voice and subtitle state accessibly", () => {
    renderControls({
      voiceMode: "muted",
      subtitlesEnabled: false,
      promptBarVisible: false,
    });
    expect(
      screen.getByTitle("Turn voice on").getAttribute("aria-pressed"),
    ).toBe("false");
    expect(
      screen.getByTitle("Show subtitles").getAttribute("aria-pressed"),
    ).toBe("false");
    expect(screen.getByTitle("Show typing").getAttribute("aria-pressed")).toBe(
      "false",
    );
  });
});
