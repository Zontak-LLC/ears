---
name: ears
description: Judge a sound you cannot hear. Use after making or changing any sound (a synth, a click, a chime, a voice clip, an ambience, an app's audio), before saying it sounds right. Turns the sound into a picture (ears.png) and a plain-words report, and compares it with a reference.
---

# Ears

You cannot hear. Ears lets you see and measure a sound instead. Never say a sound is good, fixed, softer, brighter, click-free or "like X" without running Ears on it first.

## Steps

1. Get the sound as a file.
   - A file already exists (.wav, .ogg, .flac, .mp3): use it.
   - Web Audio in a page: `ears-page <url-or-file> --expr "<js that plays the sound>" --seconds N --out sound.wav`. It swaps the page's AudioContext for an OfflineAudioContext, so no speakers are needed. Background sounds the page also starts (a hum, music) are in the file too.
   - A synth function you wrote: load `ears-render.js` in a page and call `Ears.render(ctx => { ... }, { seconds: N })`; or put it in a tiny test page and use `ears-page`.
   - An Android app: `ears-adb <seconds> out.wav` (scrcpy 2.0+, Android 11+).
2. Run `ears sound.wav` (add `--loop` for a loop, `--ref other.wav` to compare). Output goes to `sound.ears/` next to the file.
3. Read `sound.ears/ears.png` with the Read tool. Look at all four panels: waveform, level envelope, spectrogram, average spectrum.
4. Read the report. Check the numbers that matter for this sound: peak and loudness, band shares, brightness, pitch and partials, attack and decay, transients (clicks), loop seam, stereo width.
5. When a reference exists (in the Ears `refs/` folder, or one the user gave), run with `--ref` and act on the ranked differences.
6. Tell the user what Ears showed, with the numbers, and the PNG path. Say what you could not check (Ears measures; it does not judge taste).

## Rules

- No Ears run, no claim. "It should sound softer" is a guess; "peak fell from -12 to -20 dBFS, decay 45 ms to 18 ms" is a check.
- After each change to the sound, run Ears again and compare with the previous file (`--ref old.wav`).
- Look for: clipping, clicks at start/end or at a loop seam, energy where it should not be (mud under 250 Hz, harshness at 2-6 kHz), a level far from the rest of the app.
