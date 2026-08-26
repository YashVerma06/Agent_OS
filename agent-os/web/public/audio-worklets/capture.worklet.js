/**
 * Microphone capture worklet.
 *
 * Runs on the audio render thread and converts Float32 samples to the 16-bit
 * PCM the Live API expects. The AudioContext is created at the target sample
 * rate on the main thread, so no resampling happens here — resampling in the
 * render thread is the usual source of clicks and drift.
 *
 * Frames are batched to FRAME_SAMPLES before posting, because one message per
 * 128-sample render quantum floods the main thread.
 */

const FRAME_SAMPLES = 2048;

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._buffer = new Float32Array(FRAME_SAMPLES);
    this._offset = 0;
    this._peak = 0;
    this._muted = false;

    this.port.onmessage = (event) => {
      const data = event.data || {};
      if (data.type === 'mute') {
        this._muted = Boolean(data.value);
      }
    };
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }
    const channel = input[0];
    if (!channel) {
      return true;
    }

    // Stay alive while muted; just don't forward anything upstream.
    if (this._muted) {
      this._offset = 0;
      return true;
    }

    for (let i = 0; i < channel.length; i += 1) {
      const sample = channel[i];
      const magnitude = sample < 0 ? -sample : sample;
      if (magnitude > this._peak) {
        this._peak = magnitude;
      }

      this._buffer[this._offset] = sample;
      this._offset += 1;

      if (this._offset === FRAME_SAMPLES) {
        // Build once, then transfer that exact buffer. Converting twice would
        // post one array and neuter a different one.
        const pcm = this._toInt16(this._buffer);
        this.port.postMessage(
          { type: 'pcm', buffer: pcm.buffer, peak: this._peak },
          [pcm.buffer],
        );
        this._offset = 0;
        this._peak = 0;
      }
    }

    return true;
  }

  _toInt16(floats) {
    const out = new Int16Array(floats.length);
    for (let i = 0; i < floats.length; i += 1) {
      const clamped = Math.max(-1, Math.min(1, floats[i]));
      out[i] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
    }
    return out;
  }
}

registerProcessor('capture-processor', CaptureProcessor);
