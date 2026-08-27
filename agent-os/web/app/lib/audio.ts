/**
 * Browser audio for the Agent OS Meeting Room.
 *
 * Two AudioContexts, each created at the rate its side needs, so neither the
 * worklet nor the main thread ever resamples:
 *   capture  -> input_sample_rate  (16 kHz by default)
 *   playback -> output_sample_rate (24 kHz by default)
 *
 * Nothing here touches Google. It moves PCM between the microphone, our own
 * WebSocket, and the speakers.
 */

const CAPTURE_WORKLET = '/audio-worklets/capture.worklet.js';
const PLAYBACK_WORKLET = '/audio-worklets/playback.worklet.js';

export interface MeetingAudioOptions {
  inputSampleRate: number;
  outputSampleRate: number;
  /** Called with base64 PCM16 ready to put on the wire. */
  onFrame: (base64: string) => void;
  /** 0..1 microphone level, for the speaking indicator. */
  onLevel?: (level: number) => void;
  /** True while agent audio is actually being rendered. */
  onAgentAudio?: (playing: boolean) => void;
}

export class MicrophonePermissionError extends Error {}

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  // Chunked to avoid blowing the argument limit on long frames.
  const CHUNK = 0x8000;
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

function fromBase64(value: string): ArrayBuffer {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

export class MeetingAudio {
  private captureContext: AudioContext | null = null;
  private playbackContext: AudioContext | null = null;
  private captureNode: AudioWorkletNode | null = null;
  private playbackNode: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private muted = false;

  constructor(private readonly options: MeetingAudioOptions) {}

  get isMuted(): boolean {
    return this.muted;
  }

  /** Request the microphone and start both graphs. Throws if permission is denied. */
  async start(): Promise<void> {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    } catch (caught) {
      throw new MicrophonePermissionError(
        caught instanceof Error ? caught.message : 'Microphone access was refused.',
      );
    }

    const AudioCtor: typeof AudioContext =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;

    this.captureContext = new AudioCtor({ sampleRate: this.options.inputSampleRate });
    await this.captureContext.audioWorklet.addModule(CAPTURE_WORKLET);
    const source = this.captureContext.createMediaStreamSource(this.stream);
    this.captureNode = new AudioWorkletNode(this.captureContext, 'capture-processor');
    this.captureNode.port.onmessage = (event) => {
      const data = event.data as { type: string; buffer: ArrayBuffer; peak: number };
      if (data.type !== 'pcm') return;
      this.options.onLevel?.(data.peak);
      this.options.onFrame(toBase64(data.buffer));
    };
    source.connect(this.captureNode);
    // Keep the graph pulling without routing the mic to the speakers.
    const sink = this.captureContext.createGain();
    sink.gain.value = 0;
    this.captureNode.connect(sink).connect(this.captureContext.destination);

    this.playbackContext = new AudioCtor({ sampleRate: this.options.outputSampleRate });
    await this.playbackContext.audioWorklet.addModule(PLAYBACK_WORKLET);
    this.playbackNode = new AudioWorkletNode(this.playbackContext, 'playback-processor', {
      outputChannelCount: [1],
    });
    this.playbackNode.port.onmessage = (event) => {
      const data = event.data as { type: string; value: boolean };
      if (data.type === 'playing') {
        this.options.onAgentAudio?.(data.value);
      }
    };
    this.playbackNode.connect(this.playbackContext.destination);
  }

  /** Browsers suspend contexts created before a gesture; resume on join. */
  async resume(): Promise<void> {
    await this.captureContext?.resume();
    await this.playbackContext?.resume();
  }

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.captureNode?.port.postMessage({ type: 'mute', value: muted });
    this.stream?.getAudioTracks().forEach((track) => {
      track.enabled = !muted;
    });
  }

  /** Queue a base64 PCM16 chunk of agent audio. */
  enqueue(base64: string): void {
    if (!this.playbackNode) return;
    const buffer = fromBase64(base64);
    this.playbackNode.port.postMessage({ type: 'chunk', buffer }, [buffer]);
  }

  /** Drop buffered agent audio, e.g. when the client interrupts. */
  flush(): void {
    this.playbackNode?.port.postMessage({ type: 'flush' });
  }

  async stop(): Promise<void> {
    this.flush();
    this.captureNode?.disconnect();
    this.playbackNode?.disconnect();
    this.stream?.getTracks().forEach((track) => track.stop());
    await this.captureContext?.close().catch(() => undefined);
    await this.playbackContext?.close().catch(() => undefined);
    this.captureContext = null;
    this.playbackContext = null;
    this.captureNode = null;
    this.playbackNode = null;
    this.stream = null;
  }
}

/** Feature probe used to decide whether to offer the voice path at all. */
export function audioSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    typeof window.AudioWorkletNode !== 'undefined' &&
    typeof navigator !== 'undefined' &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}
