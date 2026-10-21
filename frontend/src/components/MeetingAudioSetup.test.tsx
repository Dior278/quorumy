import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { playMeetingTestSound } from "../meetingAudio";
import { MeetingAudioSetup } from "./MeetingAudioSetup";

vi.mock("../meetingAudio", () => ({ playMeetingTestSound: vi.fn() }));

describe("meeting sound check", () => {
  it("requires a participant to confirm reception after local playback", async () => {
    let finish!: () => void;
    vi.mocked(playMeetingTestSound).mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        }),
    );
    render(<MeetingAudioSetup />);
    fireEvent.click(screen.getByText("Faire entendre Quorumy dans l’appel"));
    fireEvent.click(
      screen.getByRole("button", { name: "Jouer le son de test" }),
    );
    const playing = screen.getByRole("button", {
      name: "Lecture…",
    }) as HTMLButtonElement;
    expect(playing.disabled).toBe(true);
    expect(screen.queryByRole("status")).toBeNull();
    finish();
    await waitFor(() =>
      expect(screen.getByRole("status").textContent).toContain(
        "Un participant doit confirmer",
      ),
    );
    expect(
      (
        screen.getByRole("button", {
          name: "Jouer le son de test",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false);
  });

  it("allows retry after the browser cannot play the signal", async () => {
    vi.mocked(playMeetingTestSound).mockRejectedValueOnce(
      new Error("No audio output"),
    );
    render(<MeetingAudioSetup />);
    fireEvent.click(screen.getByText("Faire entendre Quorumy dans l’appel"));
    fireEvent.click(
      screen.getByRole("button", { name: "Jouer le son de test" }),
    );
    await waitFor(() =>
      expect(screen.getByRole("alert").textContent).toContain(
        "n’a pas pu être joué",
      ),
    );
    expect(screen.queryByRole("status")).toBeNull();
    vi.mocked(playMeetingTestSound).mockResolvedValueOnce();
    fireEvent.click(
      screen.getByRole("button", { name: "Jouer le son de test" }),
    );
    await waitFor(() => expect(screen.getByRole("status")).toBeTruthy());
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
