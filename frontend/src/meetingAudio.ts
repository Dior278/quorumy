/** A short local signal, carried by the same browser tab as Quorumy's voice. */
export async function playMeetingTestSound(): Promise<void> {
  const context = new AudioContext();
  let source: AudioBufferSourceNode | undefined;
  let timeout: ReturnType<typeof setTimeout> | undefined;
  try {
    await Promise.race([
      (async () => {
        await context.resume();
        if (context.state !== "running") throw new Error("Audio unavailable");
        const buffer = context.createBuffer(
          1,
          context.sampleRate * 0.8,
          context.sampleRate,
        );
        const samples = buffer.getChannelData(0);
        for (let i = 0; i < samples.length; i++) {
          const time = i / context.sampleRate;
          const start = time < 0.4 ? 0.05 : 0.45;
          const local = time - start;
          if (local < 0 || local > 0.25) continue;
          const envelope = Math.min(1, local / 0.02, (0.25 - local) / 0.04);
          const frequency = time < 0.4 ? 523.25 : 659.25;
          samples[i] =
            0.15 * envelope * Math.sin(2 * Math.PI * frequency * local);
        }
        source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        await new Promise<void>((resolve) => {
          source!.onended = () => resolve();
          source!.start();
        });
      })(),
      new Promise<never>((_, reject) => {
        timeout = setTimeout(
          () => reject(new Error("Audio test timed out")),
          5000,
        );
      }),
    ]);
  } finally {
    clearTimeout(timeout);
    source?.disconnect();
    if (context.state !== "closed") await context.close();
  }
}
