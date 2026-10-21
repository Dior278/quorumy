import { beforeEach, describe, expect, it, vi } from "vitest";

import { AudioBridge } from "./audio";

class FakeNode {
  gain = { value: 1 };
  onaudioprocess: ((event: AudioProcessingEvent) => void) | null = null;
  connect() {
    return this;
  }
  disconnect() {}
}

class FakeContext {
  static processors: FakeNode[] = [];
  state = "running";
  sampleRate = 48000;
  destination = new FakeNode();
  createGain() {
    return new FakeNode();
  }
  createMediaStreamSource() {
    return new FakeNode();
  }
  createScriptProcessor() {
    const node = new FakeNode();
    FakeContext.processors.push(node);
    return node;
  }
  async resume() {}
  async close() {
    this.state = "closed";
  }
}

function stream(
  audioTracks: MediaStreamTrack[],
  videoTracks: MediaStreamTrack[] = [],
): MediaStream {
  return {
    getAudioTracks: () => audioTracks,
    getVideoTracks: () => videoTracks,
    getTracks: () => [...audioTracks, ...videoTracks],
  } as unknown as MediaStream;
}

class PlaybackNode extends FakeNode {
  buffer?: AudioBuffer;
  onended?: () => void;
  start = vi.fn();
  stop = vi.fn();
}

class PlaybackContext extends FakeContext {
  static sources: PlaybackNode[] = [];
  static decode = vi.fn();
  decodeAudioData = PlaybackContext.decode;
  createBuffer() {
    return {
      getChannelData: () => new Float32Array(1),
    } as unknown as AudioBuffer;
  }
  createBufferSource() {
    const source = new PlaybackNode();
    PlaybackContext.sources.push(source);
    return source;
  }
}

describe("AudioBridge playback lifecycle", () => {
  beforeEach(() => {
    PlaybackContext.sources = [];
    PlaybackContext.decode = vi.fn();
    vi.stubGlobal("AudioContext", PlaybackContext);
  });

  it("does not start decoded audio after playback was stopped", async () => {
    let decoded!: (buffer: AudioBuffer) => void;
    PlaybackContext.decode.mockImplementation(
      () =>
        new Promise<AudioBuffer>((resolve) => {
          decoded = resolve;
        }),
    );
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    const pending = bridge.playAudio("AAA=", "opus", 24000);
    bridge.stopPlayback();
    decoded({} as AudioBuffer);
    await Promise.resolve();
    try {
      expect(PlaybackContext.sources).toHaveLength(0);
    } finally {
      for (const source of PlaybackContext.sources) source.onended?.();
      await pending;
    }
  });

  it("keeps control of the new audio when the old source ends late", async () => {
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    const first = bridge.playAudio("AAA=", "pcm_24000", 24000);
    const oldSource = PlaybackContext.sources[0];
    const second = bridge.playAudio("AAA=", "pcm_24000", 24000);
    const newSource = PlaybackContext.sources[1];
    oldSource.onended?.();
    await first;
    bridge.stopPlayback();
    try {
      expect(newSource.stop).toHaveBeenCalledOnce();
    } finally {
      newSource.onended?.();
      await second;
    }
  });
});

describe("AudioBridge capture", () => {
  const microphoneTrack = { stop: vi.fn() } as unknown as MediaStreamTrack;
  const systemTrack = { stop: vi.fn() } as unknown as MediaStreamTrack;
  const videoTrack = {
    stop: vi.fn(),
    getSettings: () => ({ displaySurface: "browser" }),
  } as unknown as MediaStreamTrack;
  const getUserMedia = vi.fn();
  const getDisplayMedia = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    FakeContext.processors = [];
    vi.stubGlobal("AudioContext", FakeContext);
    Object.defineProperty(navigator, "mediaDevices", {
      configurable: true,
      value: { getUserMedia, getDisplayMedia },
    });
    getUserMedia.mockResolvedValue(stream([microphoneTrack]));
    getDisplayMedia.mockResolvedValue(stream([systemTrack], [videoTrack]));
  });

  it("captures microphone and shared system audio in mixed mode", async () => {
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    const result = await bridge.start("mixed");
    expect(result).toEqual({ microphone: true, system: true });
    expect(getUserMedia).toHaveBeenCalledOnce();
    expect(getDisplayMedia).toHaveBeenCalledOnce();
    expect(videoTrack.stop).toHaveBeenCalledOnce();
    await bridge.stopCapture();
    expect(microphoneTrack.stop).toHaveBeenCalled();
    expect(systemTrack.stop).toHaveBeenCalled();
  });

  it("stops the microphone when the requested shared audio is absent", async () => {
    getDisplayMedia.mockResolvedValue(stream([], [videoTrack]));
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    await expect(bridge.start("mixed")).rejects.toThrow(
      "No shared audio track",
    );
    expect(microphoneTrack.stop).toHaveBeenCalled();
  });

  it("rejects system-only capture when the selected surface has no audio", async () => {
    getDisplayMedia.mockResolvedValue(stream([], [videoTrack]));
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    await expect(bridge.start("system")).rejects.toThrow(
      "No shared audio track",
    );
  });

  it("releases a permission result arriving after capture was stopped", async () => {
    let resolve!: (value: MediaStream) => void;
    getUserMedia.mockImplementation(
      () =>
        new Promise<MediaStream>((r) => {
          resolve = r;
        }),
    );
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    const pending = bridge.start("microphone");
    const assertion = expect(pending).rejects.toThrow("Capture canceled");
    await vi.waitFor(() => expect(getUserMedia).toHaveBeenCalledOnce());
    await bridge.stopCapture();
    resolve(stream([microphoneTrack]));
    await assertion;
    expect(microphoneTrack.stop).toHaveBeenCalledOnce();
    expect(FakeContext.processors).toHaveLength(0);
  });

  it("does not request media in text mode", async () => {
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), vi.fn());
    await bridge.start("text");
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(getDisplayMedia).not.toHaveBeenCalled();
  });

  it("detects participants from both microphone and shared meeting tab", async () => {
    const onFloor = vi.fn();
    const bridge = new AudioBridge(vi.fn(), onFloor, vi.fn(), vi.fn());
    await bridge.start("mixed");
    const [mixProcessor, floorProcessor] = FakeContext.processors;
    const loud = new Float32Array(2048).fill(0.2);
    const event = {
      inputBuffer: { getChannelData: () => loud },
    } as unknown as AudioProcessingEvent;

    mixProcessor.onaudioprocess?.(event);
    expect(onFloor).not.toHaveBeenCalled();
    floorProcessor.onaudioprocess?.(event);
    floorProcessor.onaudioprocess?.(event);
    expect(onFloor).toHaveBeenCalledWith(true);
    await bridge.stopCapture();
  });

  it.each(["mixed", "system"] as const)(
    "interrupts Quorumy for a remote participant in %s mode",
    async (mode) => {
      const onFloor = vi.fn();
      const onBargeIn = vi.fn();
      const bridge = new AudioBridge(vi.fn(), onFloor, vi.fn(), onBargeIn);
      await bridge.start(mode);
      Object.defineProperty(bridge, "playbackActive", {
        value: true,
        writable: true,
      });
      const remote = FakeContext.processors.at(-1)!;
      const event = {
        inputBuffer: {
          getChannelData: () => new Float32Array(2048).fill(0.04),
        },
      } as unknown as AudioProcessingEvent;
      remote.onaudioprocess?.(event);
      remote.onaudioprocess?.(event);
      expect(onFloor).toHaveBeenLastCalledWith(true);
      expect(onBargeIn).toHaveBeenCalledOnce();
      expect(bridge.participantSpeaking).toBe(true);
      await bridge.stopCapture();
    },
  );

  it("keeps the floor occupied while either participant is still speaking", async () => {
    const now = vi.spyOn(performance, "now").mockReturnValue(0);
    try {
      const onFloor = vi.fn();
      const bridge = new AudioBridge(vi.fn(), onFloor, vi.fn(), vi.fn());
      await bridge.start("mixed");
      const [, microphone, remote] = FakeContext.processors;
      const event = (level: number) =>
        ({
          inputBuffer: {
            getChannelData: () => new Float32Array(2048).fill(level),
          },
        }) as unknown as AudioProcessingEvent;
      microphone.onaudioprocess?.(event(0.1));
      microphone.onaudioprocess?.(event(0.1));
      remote.onaudioprocess?.(event(0.1));
      remote.onaudioprocess?.(event(0.1));
      now.mockReturnValue(800);
      remote.onaudioprocess?.(event(0.1));
      microphone.onaudioprocess?.(event(0));
      expect(onFloor.mock.calls).toEqual([[true]]);
      now.mockReturnValue(1500);
      remote.onaudioprocess?.(event(0));
      expect(onFloor.mock.calls).toEqual([[true], [false]]);
      await bridge.stopCapture();
    } finally {
      now.mockRestore();
    }
  });

  it("does not mistake Quorumy in whole-system capture for a remote interruption", async () => {
    getDisplayMedia.mockResolvedValue(
      stream(
        [systemTrack],
        [
          {
            stop: vi.fn(),
            getSettings: () => ({ displaySurface: "monitor" }),
          } as unknown as MediaStreamTrack,
        ],
      ),
    );
    const onBargeIn = vi.fn();
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), onBargeIn);
    await bridge.start("system");
    Object.defineProperty(bridge, "playbackActive", {
      value: true,
      writable: true,
    });
    const event = {
      inputBuffer: { getChannelData: () => new Float32Array(2048).fill(0.2) },
    } as unknown as AudioProcessingEvent;
    for (let i = 0; i < 8; i++)
      FakeContext.processors[1].onaudioprocess?.(event);
    expect(onBargeIn).not.toHaveBeenCalled();
    await bridge.stopCapture();
  });

  it("does not treat mixed output energy as barge-in during Quorumy playback", async () => {
    const onFloor = vi.fn();
    const onBargeIn = vi.fn();
    const bridge = new AudioBridge(vi.fn(), onFloor, vi.fn(), onBargeIn);
    await bridge.start("mixed");
    Object.defineProperty(bridge, "playbackActive", {
      value: true,
      writable: true,
    });
    const [mixProcessor, floorProcessor] = FakeContext.processors;
    const loud = new Float32Array(2048).fill(0.2);
    const event = {
      inputBuffer: { getChannelData: () => loud },
    } as unknown as AudioProcessingEvent;

    for (let index = 0; index < 4; index += 1)
      mixProcessor.onaudioprocess?.(event);
    expect(onBargeIn).not.toHaveBeenCalled();
    for (let index = 0; index < 6; index += 1)
      floorProcessor.onaudioprocess?.(event);
    expect(onBargeIn).toHaveBeenCalledOnce();
    await bridge.stopCapture();
  });
  it("does not interrupt playback for moderate microphone leakage", async () => {
    const onBargeIn = vi.fn();
    const bridge = new AudioBridge(vi.fn(), vi.fn(), vi.fn(), onBargeIn);
    await bridge.start("mixed");
    Object.defineProperty(bridge, "playbackActive", {
      value: true,
      writable: true,
    });
    const floorProcessor = FakeContext.processors[1];
    const leakage = new Float32Array(2048).fill(0.055);
    const event = {
      inputBuffer: { getChannelData: () => leakage },
    } as unknown as AudioProcessingEvent;

    for (let index = 0; index < 10; index += 1)
      floorProcessor.onaudioprocess?.(event);
    expect(onBargeIn).not.toHaveBeenCalled();
    await bridge.stopCapture();
  });
});
