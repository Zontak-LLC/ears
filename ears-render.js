/*
 * ears-render.js: render Web Audio in an OfflineAudioContext and get a 16-bit WAV.
 * Plain browser JavaScript, no build step, no Node. Load it with a <script> tag
 * (or inject it, as ears-page does). It adds `window.Ears`.
 *
 *   const { wav, buffer } = await Ears.render((ctx) => {
 *     const o = ctx.createOscillator(), g = ctx.createGain();
 *     o.frequency.value = 440; g.gain.setValueAtTime(0.2, 0);
 *     g.gain.exponentialRampToValueAtTime(0.0001, 0.5);
 *     o.connect(g).connect(ctx.destination); o.start(0); o.stop(0.5);
 *   }, { seconds: 1 });
 *   Ears.download(wav, "beep.wav");   // or: await Ears.renderAndDownload(synth, { seconds: 1 }, "beep.wav")
 *
 * The synth gets an OfflineAudioContext. Schedule from time 0 (ctx.currentTime is 0).
 * It may return a Promise (for example, to load a sample first).
 */
(function (root) {
  "use strict";

  /** Encode an AudioBuffer as a 16-bit PCM WAV. Returns an ArrayBuffer. */
  function toWav(buffer) {
    const ch = buffer.numberOfChannels;
    const sr = buffer.sampleRate;
    const n = buffer.length;
    const bytes = 44 + n * ch * 2;
    const ab = new ArrayBuffer(bytes);
    const v = new DataView(ab);
    const str = (o, s) => {
      for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i));
    };
    str(0, "RIFF");
    v.setUint32(4, bytes - 8, true);
    str(8, "WAVE");
    str(12, "fmt ");
    v.setUint32(16, 16, true);
    v.setUint16(20, 1, true); // PCM
    v.setUint16(22, ch, true);
    v.setUint32(24, sr, true);
    v.setUint32(28, sr * ch * 2, true);
    v.setUint16(32, ch * 2, true);
    v.setUint16(34, 16, true);
    str(36, "data");
    v.setUint32(40, n * ch * 2, true);
    const data = [];
    for (let c = 0; c < ch; c++) data.push(buffer.getChannelData(c));
    let o = 44;
    for (let i = 0; i < n; i++) {
      for (let c = 0; c < ch; c++) {
        const s = Math.max(-1, Math.min(1, data[c][i]));
        v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
        o += 2;
      }
    }
    return ab;
  }

  /** Run synth(ctx) in an OfflineAudioContext for `seconds`. Resolves to { buffer, wav }. */
  async function render(synth, opts = {}) {
    const seconds = opts.seconds ?? 2;
    const sampleRate = opts.sampleRate ?? 48000;
    const channels = opts.channels ?? 2;
    const OAC = root.OfflineAudioContext || root.webkitOfflineAudioContext;
    if (!OAC) throw new Error("ears-render: this browser has no OfflineAudioContext");
    const ctx = new OAC(channels, Math.ceil(seconds * sampleRate), sampleRate);
    await synth(ctx);
    const buffer = await ctx.startRendering();
    return { buffer, wav: toWav(buffer) };
  }

  /** Save an ArrayBuffer as a file through a temporary link (browser only). */
  function download(wav, name = "ears.wav") {
    const url = URL.createObjectURL(new Blob([wav], { type: "audio/wav" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function renderAndDownload(synth, opts, name) {
    const { wav } = await render(synth, opts);
    download(wav, name);
    return wav;
  }

  /** Base64 of an ArrayBuffer (used by ears-page to pass the WAV out of the page). */
  function toBase64(ab) {
    const u = new Uint8Array(ab);
    let s = "";
    for (let i = 0; i < u.length; i += 0x8000) s += String.fromCharCode.apply(null, u.subarray(i, i + 0x8000));
    return btoa(s);
  }

  /*
   * Capture mode (used by ears-page): replace AudioContext with an OfflineAudioContext
   * of a fixed length before the page's own scripts run. Every context the page makes
   * is kept in Ears.contexts; ears-page renders the first one after your --expr has run.
   * Notes: currentTime stays 0 until rendering, so sounds the page schedules "now" start
   * at 0. resume()/suspend() before rendering are no-ops. Media elements
   * (createMediaElementSource) and AudioWorklets loaded later may not work.
   */
  function capture(seconds, sampleRate = 48000) {
    const OAC = root.OfflineAudioContext || root.webkitOfflineAudioContext;
    const contexts = [];
    function Fake(options) {
      const sr = (options && options.sampleRate) || sampleRate;
      const ctx = new OAC(2, Math.ceil(seconds * sr), sr);
      ctx.resume = () => Promise.resolve();
      ctx.suspend = () => Promise.resolve();
      ctx.close = () => Promise.resolve();
      contexts.push(ctx);
      return ctx; // returning an object from a constructor makes `new Fake()` give it back
    }
    root.AudioContext = Fake;
    root.webkitAudioContext = Fake;
    api.contexts = contexts;
    return contexts;
  }

  async function renderCaptured(index = 0) {
    const ctx = api.contexts && api.contexts[index];
    if (!ctx) throw new Error("ears-render: the page made no AudioContext (did --expr start the sound?)");
    const buffer = await ctx.startRendering();
    return toBase64(toWav(buffer));
  }

  const api = { render, toWav, download, renderAndDownload, toBase64, capture, renderCaptured, contexts: [] };
  root.Ears = api;
})(typeof window !== "undefined" ? window : globalThis);
