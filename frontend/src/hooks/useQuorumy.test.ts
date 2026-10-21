import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useQuorumy } from "./useQuorumy";

const mocks = vi.hoisted(() => ({
  bootstrap: vi.fn(),
  capture: vi.fn(),
  stopCapture: vi.fn(),
  stopPlayback: vi.fn(),
  speaking: false,
  beginPcmStream: vi.fn(),
  pushPcmChunk: vi.fn(),
  playAudio: vi.fn(),
}));

class FakeSocket {
  static instances: FakeSocket[] = [];
  readyState = 0;
  onopen?: () => Promise<void>;
  onclose?: (event: { code: number }) => void;
  onmessage?: (event: { data: string }) => void;
  sent: Array<Record<string, unknown>> = [];
  constructor() {
    FakeSocket.instances.push(this);
  }
  send(text: string) {
    this.sent.push(JSON.parse(text));
  }
  async open() {
    this.readyState = 1;
    await this.onopen?.();
  }
  close(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
  receive(message: object) {
    this.onmessage?.({ data: JSON.stringify(message) });
  }
}

vi.mock("../api", () => ({
  AuthRequired: class AuthRequired extends Error {},
  registerAccount: vi.fn(),
  loginAccount: vi.fn(),
  bootstrap: mocks.bootstrap,
  liveSocket: () => new FakeSocket(),
  send: (socket: FakeSocket, message: object) => {
    if (socket.readyState === 1) socket.send(JSON.stringify(message));
  },
  deleteQuorumySession: vi.fn(),
  exportQuorumySession: vi.fn(),
  renameQuorumySession: vi.fn(),
}));
vi.mock("../audio", () => ({
  AudioBridge: class {
    start = mocks.capture;
    stopCapture = mocks.stopCapture;
    stopPlayback = mocks.stopPlayback;
    stopCue = vi.fn();
    get participantSpeaking() {
      return mocks.speaking;
    }
    beginPcmStream = mocks.beginPcmStream;
    pushPcmChunk = mocks.pushPcmChunk;
    playAudio = mocks.playAudio;
  },
}));

const pausedState = {
  session_id: "session-one",
  session_status: "paused",
  language: "fr",
  capture_mode: "microphone",
};
const payload = {
  protocol_version: 14,
  display_name: "Quorumy",
  access_token: "token-one",
  state: pausedState,
  sessions: [],
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.clearAllMocks();
  FakeSocket.instances = [];
  mocks.bootstrap.mockResolvedValue(payload);
  mocks.stopCapture.mockResolvedValue(undefined);
  mocks.speaking = false;
});
afterEach(() => {
  vi.useRealTimers();
});

describe("connection recovery", () => {
  it("ignores a late stop for a previous speech", async () => {
    const { unmount } = renderHook(() => useQuorumy());
    const socket = FakeSocket.instances[0];
    await act(async () => {
      await socket.open();
    });
    act(() => {
      socket.receive({
        type: "speech.authorized",
        speech_id: "current",
        text: "Answer",
        audio: null,
      });
      socket.receive({
        type: "speech.audio.chunk",
        speech_id: "current",
        data_base64: "AAA=",
        sample_rate: 24000,
      });
    });
    mocks.stopPlayback.mockClear();
    act(() => {
      socket.receive({ type: "speech.stop", speech_id: "previous" });
      socket.receive({
        type: "speech.audio.chunk",
        speech_id: "current",
        data_base64: "AAA=",
        sample_rate: 24000,
      });
    });
    expect(mocks.stopPlayback).not.toHaveBeenCalled();
    expect(mocks.beginPcmStream).toHaveBeenCalledOnce();
    unmount();
  });

  it("keeps a newer speech active when old audio decoding fails", async () => {
    let reject!: (error: Error) => void;
    mocks.playAudio.mockImplementationOnce(
      () =>
        new Promise<void>((_, fail) => {
          reject = fail;
        }),
    );
    const { unmount } = renderHook(() => useQuorumy());
    const socket = FakeSocket.instances[0];
    await act(async () => {
      await socket.open();
    });
    act(() => {
      socket.receive({
        type: "speech.authorized",
        speech_id: "previous",
        text: "Old",
        audio: { data_base64: "AAA=", format: "opus", sample_rate: 24000 },
      });
      socket.receive({
        type: "speech.authorized",
        speech_id: "current",
        text: "New",
        audio: null,
      });
    });
    await act(async () => {
      reject(new Error("Decode failed"));
    });
    act(() => {
      socket.receive({
        type: "speech.audio.chunk",
        speech_id: "current",
        data_base64: "AAA=",
        sample_rate: 24000,
      });
    });
    expect(mocks.pushPcmChunk).toHaveBeenCalledOnce();
    unmount();
  });

  it("rejects late speech authorization while a participant speaks", async () => {
    const { unmount } = renderHook(() => useQuorumy());
    const socket = FakeSocket.instances[0];
    await act(async () => {
      await socket.open();
    });
    mocks.speaking = true;
    act(() => {
      socket.receive({
        type: "speech.authorized",
        speech_id: "late",
        text: "Late answer",
        audio: null,
      });
      socket.receive({
        type: "speech.audio.chunk",
        speech_id: "late",
        data_base64: "AAA=",
        sample_rate: 24000,
      });
    });
    expect(socket.sent).toContainEqual({
      type: "playback.interrupted",
      speech_id: "late",
    });
    expect(mocks.beginPcmStream).not.toHaveBeenCalled();
    expect(mocks.pushPcmChunk).not.toHaveBeenCalled();
    unmount();
  });

  it("rejects a first chunk when a participant starts after authorization", async () => {
    const { unmount } = renderHook(() => useQuorumy());
    const socket = FakeSocket.instances[0];
    await act(async () => {
      await socket.open();
    });
    act(() => {
      socket.receive({
        type: "speech.authorized",
        speech_id: "late",
        text: "Late answer",
        audio: null,
      });
    });
    mocks.speaking = true;
    act(() => {
      socket.receive({
        type: "speech.audio.chunk",
        speech_id: "late",
        data_base64: "AAA=",
        sample_rate: 24000,
      });
    });
    expect(socket.sent).toContainEqual({
      type: "playback.interrupted",
      speech_id: "late",
    });
    expect(mocks.pushPcmChunk).not.toHaveBeenCalled();
    unmount();
  });
  it("refreshes authentication and preserves the draft without resuming capture", async () => {
    const { result, unmount } = renderHook(() => useQuorumy());
    const first = FakeSocket.instances[0];
    await act(async () => {
      await first.open();
      first.receive({ type: "backend.hello", protocol_version: 14 });
    });
    act(() => result.current.setManual("Draft to keep"));
    act(() => first.close(1006));
    expect(mocks.stopCapture).toHaveBeenCalled();
    expect(mocks.stopPlayback).toHaveBeenCalled();
    expect(result.current.consent).toBe(false);
    expect(result.current.reconnecting).toBe(true);
    mocks.bootstrap.mockResolvedValue({
      ...payload,
      access_token: "token-two",
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    const second = FakeSocket.instances[1];
    await act(async () => {
      await second.open();
      second.receive({ type: "backend.hello", protocol_version: 14 });
      second.receive({
        type: "state.snapshot",
        state: pausedState,
        sessions: [],
      });
    });
    expect(second.sent[0].access_token).toBe("token-two");
    expect(second.sent[0].client_id).toBe(first.sent[0].client_id);
    expect(result.current.manual).toBe("Draft to keep");
    expect(result.current.state?.session_status).toBe("paused");
    expect(result.current.connected).toBe(true);
    expect(result.current.reconnecting).toBe(false);
    expect(mocks.capture).not.toHaveBeenCalled();
    expect(second.sent.some((m) => m.command === "resume")).toBe(false);
    unmount();
  });

  it("backs off across failed connections and cancels retries on unmount", async () => {
    const { unmount } = renderHook(() => useQuorumy());
    await act(async () => {
      FakeSocket.instances[0].close(1006);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(500);
    });
    expect(FakeSocket.instances).toHaveLength(2);
    act(() => FakeSocket.instances[1].close(1006));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(999);
    });
    expect(FakeSocket.instances).toHaveLength(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(FakeSocket.instances).toHaveLength(3);
    act(() => FakeSocket.instances[2].close(1006));
    unmount();
    await vi.advanceTimersByTimeAsync(20000);
    expect(FakeSocket.instances).toHaveLength(3);
  });

  it("does not retry rejected connections until the user asks", async () => {
    const { result, unmount } = renderHook(() => useQuorumy());
    await act(async () => {
      FakeSocket.instances[0].close(1008);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20000);
    });
    expect(FakeSocket.instances).toHaveLength(1);
    expect(result.current.reconnecting).toBe(false);
    act(() => result.current.reconnect());
    expect(FakeSocket.instances).toHaveLength(2);
    unmount();
  });
});
