# Reference sounds

Reference recordings to compare against with `ears <yours> --ref refs/<file>`.

Rule: only CC0 (public domain) files or our own recordings. Every file gets a row here with its source and licence. Nothing is added without a maintainer's approval.

All files below: WAV, 16 bit, 48 kHz, converted with ffmpeg from the original download (original sample rate and channels kept, resampled to 48 kHz). All fetched 2026-11-04 from Wikimedia Commons.

## In this folder

| File | What | Source page | Author | Licence | Trimmed | What Ears says |
|------|------|-------------|--------|---------|---------|----------------|
| click-plastic-mouse-switch.wav | Computer mouse micro switch, single click (plastic) | https://commons.wikimedia.org/wiki/File:Computer_mouse_single_click.ogg | Darklanlan | CC0 1.0 | none (0.77 s, mono) | very bright (centroid 12.4 kHz), 2 transients (press 0.30 s, release 0.38 s), 40 dB decay in 66 ms |
| click-metal-karabiner.wav | Climbing karabiner gate clicking shut (metal) | https://commons.wikimedia.org/wiki/File:457456_rudmer-rotteveel_karabiner-click-02.wav (from Freesound) | Rudmer Rotteveel | CC0 1.0 | none (1.16 s) | very bright (7.4 kHz), mixed tone plus noise, 7 transients (rattle then the shut click), very wide stereo, 40 dB decay in 43 ms |
| click-industrial-switch.wav | Chunky switch, two clicks (on, off) | https://commons.wikimedia.org/wiki/File:Clickick_switch.ogg | stephan (PDSounds) | Public domain | none (0.68 s) | very bright (7.4 kHz) but 28% energy in low-mid (body), noisy, 2 transients at 0.05 s and 0.20 s, 40 dB decay in 80 ms |
| click-dipswitch.wav | DIP switch flicked on and off (small, sharp) | https://commons.wikimedia.org/wiki/File:Dipswitch_on_off.ogg | stephan (PDSounds) | Public domain | none (2.85 s) | very bright (9.3 kHz), 92% in air band, noisy, 5 transients, 40 dB decay in 16 ms |
| rain-forest-light.wav | Light steady rain in deep woods, distant thunder, a bird (Illinois, USA). Not a tin roof, see gaps | https://commons.wikimedia.org/wiki/File:Light_Rain_Distant_Thunder_July_5th_2016.wav (from Freesound) | kvgarlic | CC0 1.0 | 20 s, from 30 s to 50 s of 110 s | bright (1.7 kHz), noisy, 58% low-mid and 28% presence, steady (level moves only 2 dB), very wide stereo (correlation 0.09) |
| train-passing-wirikuta.wav | Train passing in the Wirikuta Desert, Mexico: horn and engine with harmonics at 0.6-6 s and 6.7-13 s, track rattles and clacks from about 17 s | https://commons.wikimedia.org/wiki/File:Train_passing_by_in_the_Wirikuta_Desert_(Mexico,_SLP).wav (from Freesound) | Felix Blume | CC0 1.0 | 20 s, from 50 s to 70 s of 154 s (original 24 bit 96 kHz) | warm (962 Hz), 95% low-mid, tonal (77% in peaks, strong 1.34 kHz line), steady within 9 dB, narrow stereo, 11 transients mostly in the last 3 s |
| bell-bicycle-strike.wav | Bicycle bell, one ring, Zoom H2 | https://commons.wikimedia.org/wiki/File:Bell-ring.flac | qubodup | CC0 1.0 | none (3.0 s, original 24 bit 96 kHz) | very bright (12 kHz), 98% in air band, tonal, inharmonic partials (bell-like, main 11 kHz), 33 ms attack, 40 dB decay in 329 ms |

## Gaps (no clean CC0 or public domain file found on Commons, 2026-11-04)

- Rain on a tin or metal roof: none. The only Commons rain hits were forest rain (kept above), "Rain on a veranda and thunder" (PD, PDSounds, roof material not stated, not taken) and CC BY / CC BY-SA files (not allowed).
- Sea cave / surf: none. "Oceanwavescrushing.ogg" is CC BY 3.0 and "Lake Okeechobee Surf" is CC BY-SA 4.0, so both are skipped.
- Felt / soft piano single note: none. Commons only has CC0 piano MIDI files (not audio) and "Emotional piano.wav" (CC0, a low accompaniment phrase, not a single note; tried and dropped).
- Interior rail clacks: the train file above has clacks only at its end. "Taiwan railways EP727 train cars sounds.ogg" (CC0, Jidanni, 148 s, squeaks inside a rail car) was seen but not downloaded.
- Bell: only a small bicycle bell. A larger single strike with long decay (church bell, singing bowl) has no CC0 file; the ones found are CC BY / CC BY-SA, or PD "Striking a bell 15cm large.ogg" (60 s, stephan), not taken yet.
- Good next step for the gaps: Freesound CC0 files, which need a login to download.

## Wanted (still open)

| Want | Why | Suggested CC0 sources |
|------|-----|-----------------------|
| Rain on a tin roof | ambience check | Freesound CC0 ("rain tin roof", "rain metal roof") |
| Sea cave / surf | ambience check | Freesound CC0 ("sea cave", "waves rocks", "surf") |
| Felt piano note | tone and decay check | Freesound CC0 ("felt piano"); or record our own |
| Bell (small, struck), long decay | partials and long decay | Freesound CC0 ("bell strike", "singing bowl") |

When you add one: keep it short (under 30 s), WAV or FLAC, note the original URL, the author, the licence and the date in the table above.
