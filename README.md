# Ears

See a sound you cannot hear. Ears turns a sound file into a picture and a plain-words report, so an AI agent (or a person without speakers) can judge a sound before saying it sounds right.

```
ears click.wav
ears click.wav --ref refs/plastic-button.wav
ears rain-loop.ogg --loop
```

For each file Ears writes a folder `<name>.ears/` next to it (or `--out <dir>`):

- `ears.png`: four stacked panels, dark theme, 1400 px wide:
  1. waveform (red lines mark transients),
  2. level envelope in dBFS over time (orange = reference),
  3. spectrogram on a log frequency axis, 20 Hz to 20 kHz, with octave lines (C1 to C10) and their frequencies,
  4. average spectrum with the five bands and the main partials named as notes (orange = reference).
- `ears.json`: every number below, plus the report text.
- A short plain-English report on stdout.

## What the report says

- Length, sample rate, channels.
- Peak and RMS in dBFS, integrated loudness in LUFS (files of 0.4 s or more), clipping, DC offset.
- Energy share by band: sub (<60 Hz), bass (60-250 Hz), low-mid (250 Hz-2 kHz), presence (2-6 kHz), air (>6 kHz).
- Spectral centroid with a word (very dark, dark, warm, bright, very bright) and the 85% roll-off.
- Tonality: the share of energy in clear spectral peaks, with a word (tonal, mixed, noisy). Spectral flatness is reported too.
- Main pitch and the next partials with note names and ratios (when tonal), and a periodic pitch for voices and melodies.
- Attack (10% to 90%) of the loudest moment, decay to -20 and -40 dB. Long, steady sounds get their level spread instead.
- Transients (clicks, hits): how many, and when.
- Stereo width: side-to-mid level and L/R correlation (stereo files).
- `--loop`: whether the seam from the end back to the start clicks (sample jump and spectral flux at the seam).
- `--ref <file>`: the biggest differences, ranked, in plain words, for example "Yours has 10 dB less energy under 100 Hz" or "Your sound decays (40 dB) in 77 ms, the reference in 45 ms".

Ears measures. It does not judge taste. It reads WAV, FLAC and OGG/Opus directly and anything else through ffmpeg.

## Getting sound out of an app

### Web Audio: `ears-render.js` and `ears-page`

`ears-render.js` is plain browser JavaScript (no build, no Node). It adds `window.Ears`:

```js
const { wav } = await Ears.render((ctx) => {
  const o = ctx.createOscillator(), g = ctx.createGain();
  o.frequency.value = 2349;
  g.gain.setValueAtTime(0.022, 0);
  g.gain.exponentialRampToValueAtTime(0.0001, 0.09);
  o.connect(g).connect(ctx.destination);
  o.start(0); o.stop(0.15);
}, { seconds: 0.3 });
Ears.download(wav, "tick.wav");
```

`ears-page` does the same for a page you did not write. It opens the page in headless Chrome, swaps `AudioContext` for an `OfflineAudioContext` before the page's scripts run, runs your expression, renders and saves a 16-bit WAV:

```
ears-page examples/tick.html --expr "playTick()" --seconds 0.3 --out tick.wav
ears-page http://localhost:3000 --expr "Sound.start(); Sound.tick()" --seconds 1 --out tick.wav
```

Needs Node and Playwright. Playwright is found through `$EARS_PLAYWRIGHT` (a folder whose `node_modules` holds `playwright` or `playwright-core`), then the current folder, then the global npm root. The browser is `$EARS_CHROME`, else the installed Google Chrome, else Playwright's Chromium.

Limits of the swap: the context's clock stays at 0 until rendering, so everything the page schedules "now" starts at 0, and timers that fire later are not captured. Everything else the page plays on that context (music, a background hum) is in the file too. `<audio>` elements, `createMediaElementSource` and AudioWorklets added later may not work. When a page is too tricky, copy its synth function into a small test page (see `examples/tick.html`).

### Android: `ears-adb`

```
ears-adb 5 out.wav            # add scrcpy args such as -s <serial>
```

Plain adb cannot record audio (`screenrecord` is video only). `ears-adb` uses [scrcpy](https://github.com/Genymobile/scrcpy) 2.0 or newer, which captures the device's audio output over USB or adb-over-network on Android 11+ (also emulators with API 30+). No app on the phone, no root. It records raw PCM to WAV, and on older scrcpy falls back to Opus plus ffmpeg. While recording, the phone's speaker may go quiet; scrcpy 3+ accepts `--audio-source=playback` to keep it playing.

Status: written from scrcpy's documented flags, **not yet tested on a device**.

## Reference sounds

`refs/` holds reference sounds, only CC0 or our own recordings, each listed with source and licence in [`refs/refs.md`](refs/refs.md). It also lists the references we want.

## Install

```
git clone <this repo> ears && cd ears && ./install.sh
```

`install.sh` needs no sudo and works on macOS and Linux. It:

1. makes a Python venv in `.venv` (with `uv` when present, else Python 3.9+ with `venv`) and installs numpy, scipy, soundfile, matplotlib and pyloudnorm,
2. writes the launchers `ears`, `ears-page` and `ears-adb` into `~/.claude/bin` (or `$EARS_BIN`),
3. copies the Claude Code skill to `~/.claude/skills/ears/SKILL.md` (or `$EARS_SKILLS`),
4. lists optional tools it did not find (ffmpeg, node, Playwright, adb, scrcpy).

No `venv`/`pip` and no sudo (for example Ubuntu without `python3-venv`)? Run `./install.sh --with-uv`: it fetches the `uv` binary from its GitHub release into `.tools/` inside this folder and uses it. Nothing else on the machine changes.

## Claude Code skill

The skill (`skill/SKILL.md`) tells an agent to run Ears after making or changing any sound, to Read the `ears.png`, to compare with a reference when one exists, and never to claim a sound is good without running Ears.

## Licence

MIT. See [LICENSE](LICENSE).
