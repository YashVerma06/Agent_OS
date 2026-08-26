/**
 * Agent audio playback worklet.
 *
 * Holds a queue of Int16 PCM chunks decoded on the main thread and drains them
 * into the render quantum. Queueing here rather than scheduling many short
 * BufferSources avoids the gaps you get when chunks arrive slightly late.
 *
 * `flush` empties the queue, which is what barge-in needs: when the client
 * starts talking over the agent, the already-buffered agent audio must stop
 * rather than continue playing over them.
 */

class PlaybackProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._queue = [];
    this._offset = 0;
    this._playing = false;

    this.port.onmessage = (event) => {
      const data = event.data || {};
      if (data.type === 'chunk' && data.buffer) {
        this._queue.push(new Int16Array(data.buffer));
      } else if (data.type === 'flush') {
        this._queue = [];
        this._offset = 0;
        this._setPlaying(false);
      }
    };
  }

  _setPlaying(value) {
    if (this._playing !== value) {
      this._playing = value;
      this.port.postMessage({ type: 'playing', value });
    }
  }

  process(_inputs, outputs) {
    const output = outputs[0];
    if (!output || output.length === 0) {
      return true;
    }
    const channel = output[0];

    if (this._queue.length === 0) {
      channel.fill(0);
      this._setPlaying(false);
      return true;
    }

    this._setPlaying(true);

    for (let i = 0; i < channel.length; i += 1) {
      if (this._queue.length === 0) {
        channel[i] = 0;
        continue;
      }

      const chunk = this._queue[0];
      channel[i] = chunk[this._offset] / 0x8000;
      this._offset += 1;

      if (this._offset >= chunk.length) {
        this._queue.shift();
        this._offset = 0;
      }
    }

    // Mirror to any additional output channels so the agent is not panned left.
    for (let c = 1; c < output.length; c += 1) {
      output[c].set(channel);
    }

    return true;
  }
}

registerProcessor('playback-processor', PlaybackProcessor);
