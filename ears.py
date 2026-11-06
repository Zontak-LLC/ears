#!/usr/bin/env python3
"""Ears: turn a sound file into a picture (ears.png), numbers (ears.json) and a plain-words report.

Usage: ears <file.wav|.mp3|.ogg|...> [--ref <file>] [--out <dir>] [--loop] [--quiet]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import soundfile as sf
from scipy import signal

BANDS = [  # name, low Hz, high Hz
    ("sub", 0, 60),
    ("bass", 60, 250),
    ("low-mid", 250, 2000),
    ("presence", 2000, 6000),
    ("air", 6000, 1e9),
]
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
EPS = 1e-12


# ---------------------------------------------------------------- loading

def load(path: str) -> tuple[np.ndarray, int]:
    """Return (samples [n, channels] float64 in -1..1, sample rate). Falls back to ffmpeg."""
    try:
        data, sr = sf.read(path, always_2d=True, dtype="float64")
        if len(data):
            return data, sr
    except Exception:
        pass
    if not shutil.which("ffmpeg"):
        sys.exit(f"ears: cannot read {path} with soundfile, and ffmpeg is not installed.")
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "decoded.wav")
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", path, "-acodec", "pcm_f32le", wav],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            sys.exit(f"ears: ffmpeg could not decode {path}: {r.stderr.strip()}")
        data, sr = sf.read(wav, always_2d=True, dtype="float64")
    return data, sr


# ---------------------------------------------------------------- helpers

def db(x: float) -> float:
    return 20 * math.log10(max(x, EPS))


def pdb(x: float) -> float:
    return 10 * math.log10(max(x, EPS))


def note_name(f: float) -> str:
    if not f or f <= 0:
        return "-"
    midi = 69 + 12 * math.log2(f / 440)
    n = int(round(midi))
    cents = int(round((midi - n) * 100))
    name = f"{NOTE_NAMES[n % 12]}{n // 12 - 1}"
    return name if abs(cents) < 3 else f"{name} {cents:+d}c"


def hz(f: float | None) -> str:
    if f is None:
        return "-"
    return f"{f / 1000:.2f} kHz" if f >= 1000 else f"{f:.0f} Hz"


def ms(t: float | None) -> str:
    if t is None:
        return "-"
    return f"{t * 1000:.0f} ms" if t < 1 else f"{t:.2f} s"


def frame_rms(x: np.ndarray, win: int, hop: int) -> np.ndarray:
    if len(x) < win:
        x = np.pad(x, (0, win - len(x)))
    n = 1 + (len(x) - win) // hop
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    return np.sqrt(np.mean(x[idx] ** 2, axis=1))


def avg_spectrum(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Average power spectrum (Welch). Short clips use one zero-padded window."""
    n = len(x)
    nper = min(8192, n)
    nfft = max(8192, 1 << (nper - 1).bit_length())
    f, p = signal.welch(x, sr, nperseg=nper, nfft=nfft, window="hann", scaling="spectrum")
    return f, p


def stft_mag(x: np.ndarray, sr: int, n_fft: int, hop: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    xp = np.pad(x, (n_fft // 2, n_fft // 2))
    f, t, z = signal.stft(xp, sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=None, padded=True)
    return f, t - (n_fft // 2) / sr, np.abs(z)


# ---------------------------------------------------------------- analysis

def analyze(path: str, loop: bool = False) -> dict:
    data, sr = load(path)
    n, ch = data.shape
    mono = data.mean(axis=1)
    dur = n / sr
    peak = float(np.max(np.abs(data))) if n else 0.0
    rms = float(np.sqrt(np.mean(data ** 2))) if n else 0.0
    clip_n = int(np.sum(np.abs(data) >= 0.999))
    res: dict = {
        "file": os.path.abspath(path),
        "sample_rate": sr,
        "channels": ch,
        "duration_s": dur,
        "peak_dbfs": db(peak),
        "rms_dbfs": db(rms),
        "crest_db": db(peak) - db(rms),
        "clipped_samples": clip_n,
        "dc_offset": float(np.mean(mono)),
    }

    # Integrated loudness (needs >= 0.4 s).
    try:
        import pyloudnorm as pyln
        res["lufs"] = float(pyln.Meter(sr).integrated_loudness(data)) if dur >= 0.4 else None
        if res["lufs"] is not None and not math.isfinite(res["lufs"]):
            res["lufs"] = None
    except Exception:
        res["lufs"] = None

    # Average spectrum, bands, centroid, flatness.
    f, p = avg_spectrum(mono, sr)
    res["_spectrum"] = (f, p)
    audible = (f >= 20) & (f <= 20000)
    total = float(np.sum(p[audible])) + EPS
    bands = {}
    for name, lo, hi in BANDS:
        sel = audible & (f >= lo) & (f < hi)
        bands[name] = 100 * float(np.sum(p[sel])) / total
    res["band_share_pct"] = bands
    res["below_100hz_pct"] = 100 * float(np.sum(p[audible & (f < 100)])) / total
    res["centroid_hz"] = float(np.sum(f[audible] * p[audible]) / total)
    cum = np.cumsum(p[audible]) / total
    res["rolloff85_hz"] = float(f[audible][min(np.searchsorted(cum, 0.85), audible.sum() - 1)])

    n_fft = 2048 if sr > 30000 else 1024
    hop = n_fft // 4
    sf_, st, S = stft_mag(mono, sr, n_fft, hop)
    pw = S ** 2
    fr_e = pw.sum(axis=0)
    loud = fr_e > (fr_e.max() * 1e-4 if fr_e.max() > 0 else 1)
    band = (sf_ >= 20) & (sf_ <= 20000)
    pb = pw[band][:, loud] + EPS
    flat = np.exp(np.mean(np.log(pb), axis=0)) / np.mean(pb, axis=0) if pb.size else np.array([1.0])
    res["flatness"] = float(np.median(flat))
    res["tonal_share"] = tonal_share(f, p, sr)

    # Pitch: strongest spectral peaks (partials) and a periodic f0 when there is one.
    res["partials"] = partials(f, p)
    res["f0"] = periodic_f0(mono, sr)
    if res["f0"]:  # Drop a "pitch" that is only a subharmonic of higher partials.
        f0 = res["f0"]["median_hz"]
        near = (f >= f0 * 0.94) & (f <= f0 * 1.06)
        if not near.any() or 10 * math.log10((p[near].max() + EPS) / (p.max() + EPS)) < -30:
            res["f0"] = None

    # Envelope: fine (attack/decay) and coarse (level spread).
    fine_win, fine_hop = max(1, int(sr * 0.002)), max(1, int(sr * 0.0005))
    env = frame_rms(mono, fine_win, fine_hop)
    env_db = 20 * np.log10(env + EPS)
    ip = int(np.argmax(env))
    pk = env[ip] if len(env) else 0
    res["peak_time_s"] = ip * fine_hop / sr
    # Attack of the loudest event: from where it last rose past 10% of the peak to where it first reached 90%.
    below = np.where(env[:ip] < 0.1 * pk)[0]
    i10 = below[-1] + 1 if len(below) else 0
    i90 = i10 + int(np.argmax(env[i10: ip + 1] >= 0.9 * pk)) if pk > 0 else ip
    res["attack_s"] = (i90 - i10) * fine_hop / sr if pk > 0 else None
    after = np.where(env_db[ip:] < env_db[ip] - 40)[0]
    res["decay40_s"] = after[0] * fine_hop / sr if len(after) else None
    after20 = np.where(env_db[ip:] < env_db[ip] - 20)[0]
    res["decay20_s"] = after20[0] * fine_hop / sr if len(after20) else None
    cw = max(1, int(sr * (0.05 if dur > 1 else 0.005)))
    ch_hop = max(1, cw // 2)
    coarse = 20 * np.log10(frame_rms(mono, cw, ch_hop) + EPS)
    res["_envelope"] = (np.arange(len(coarse)) * ch_hop / sr + cw / 2 / sr, coarse, cw / sr)
    live = coarse[coarse > coarse.max() - 60] if len(coarse) else coarse
    res["level_spread_db"] = float(np.percentile(live, 90) - np.percentile(live, 10)) if len(live) else 0.0

    # Transients: spectral flux peaks.
    res["transients_s"] = transients(S, st, sr, hop)

    # Stereo.
    if ch >= 2:
        L, R = data[:, 0], data[:, 1]
        mid, side = (L + R) / 2, (L - R) / 2
        res["side_to_mid_db"] = pdb(np.mean(side ** 2)) - pdb(np.mean(mid ** 2))
        den = math.sqrt(float(np.sum(L ** 2) * np.sum(R ** 2))) + EPS
        res["lr_correlation"] = float(np.sum(L * R) / den)
    if loop:
        res["loop"] = loop_seam(mono, sr)
    res["_mono"] = mono
    res["_spec"] = (sf_, st, S)
    return res


def tonal_share(f: np.ndarray, p: np.ndarray, sr: int) -> float:
    """Share of energy in narrow peaks that stand 6 dB+ over the local (1/3-octave median) floor.
    Unlike flatness, it does not mistake a dark or sloped noise for a tone."""
    sel = (f >= 20) & (f <= min(20000, sr / 2 * 0.95))
    fx, px = f[sel], p[sel] + EPS
    if len(fx) < 16:
        return 0.0
    grid = np.geomspace(fx[0], fx[-1], int(48 * math.log2(fx[-1] / fx[0])) + 2)
    ldb = np.interp(np.log(grid), np.log(fx), 10 * np.log10(px))
    floor = signal.medfilt(ldb, 17)
    floor_lin = 10 ** (np.interp(np.log(fx), np.log(grid), floor) / 10)
    # Where bins are coarse (low notes), a 1/3-octave window holds too few bins; also use a 15-bin median.
    floor_lin = np.minimum(floor_lin, signal.medfilt(px, 15))
    peak = px > floor_lin * 4
    return float(np.sum(px[peak] - floor_lin[peak]) / np.sum(px))


def partials(f: np.ndarray, p: np.ndarray, k: int = 6) -> list[dict]:
    sel = (f >= 20) & (f <= 20000)
    pdb_ = 10 * np.log10(p + EPS)
    top = pdb_[sel].max() if sel.any() else 0
    df = f[1] - f[0]
    peaks, props = signal.find_peaks(pdb_, prominence=10, distance=max(1, int(15 / df)))
    peaks = [i for i in peaks if sel[i] and pdb_[i] > top - 40]
    peaks.sort(key=lambda i: -pdb_[i])
    out = []
    for i in peaks[:k]:
        # Parabolic interpolation for a sharper frequency.
        if 0 < i < len(p) - 1:
            a, b, c = pdb_[i - 1], pdb_[i], pdb_[i + 1]
            d = 0.5 * (a - c) / (a - 2 * b + c + EPS)
        else:
            d = 0
        fr = float(f[i] + d * df)
        out.append({"hz": fr, "note": note_name(fr), "db_rel": float(pdb_[i] - top)})
    return out


def periodic_f0(x: np.ndarray, sr: int) -> dict | None:
    """Simple YIN-like f0 per 40 ms frame, 50-1000 Hz. Returns median when enough frames are periodic."""
    win = int(sr * 0.04)
    hop = win // 2
    if len(x) < win * 2:
        return None
    lo, hi = int(sr / 1000), int(sr / 50)
    energy_floor = np.max(np.abs(x)) ** 2 * 1e-4
    f0s, total = [], 0
    for s in range(0, len(x) - win - hi, hop):
        fr = x[s: s + win + hi]
        if np.mean(fr[:win] ** 2) < energy_floor:
            continue
        total += 1
        d = np.array([np.sum((fr[:win] - fr[tau: tau + win]) ** 2) for tau in range(lo, hi)])
        cm = d * np.arange(1, len(d) + 1) / (np.cumsum(d) + EPS)
        cand = np.where(cm < 0.15)[0]
        if len(cand):
            j = cand[0]
            while j + 1 < len(cm) and cm[j + 1] < cm[j]:
                j += 1
            f0s.append(sr / (j + lo))
    if total == 0 or len(f0s) < max(3, 0.2 * total):
        return None
    f0s = np.array(f0s)
    return {
        "median_hz": float(np.median(f0s)),
        "low_hz": float(np.percentile(f0s, 10)),
        "high_hz": float(np.percentile(f0s, 90)),
        "voiced_share": len(f0s) / total,
    }


def transients(S: np.ndarray, t: np.ndarray, sr: int, hop: int) -> list[float]:
    L = np.log1p(1000 * S / (S.max() + EPS))
    flux = np.concatenate([[0], np.maximum(0, np.diff(L, axis=1)).sum(axis=0)])
    if flux.max() <= 0:
        return []
    med = np.median(flux)
    mad = np.median(np.abs(flux - med)) * 1.4826 + EPS
    height = max(med + 4 * mad, 0.1 * flux.max())
    peaks, _ = signal.find_peaks(flux, height=height, distance=max(1, int(0.05 * sr / hop)))
    # Keep only audible ones: the frame after the onset must be within 40 dB of the loudest frame.
    e = (S ** 2).sum(axis=0)
    peaks = [i for i in peaks if e[min(i + 1, len(e) - 1)] > e.max() * 1e-4]
    # Keep only real rises in level: about 20 ms after the peak must be louder than 20 ms before (by 1.2x, about 0.8 dB:
    # enough to drop a fade, small enough to keep track clacks over a loud engine; checked on the refs/ sounds).
    # Without this, the bend where a smooth fade begins smears a little flux across bins and reads as a click.
    k = max(1, int(0.02 * sr / hop))
    peaks = [i for i in peaks if e[min(i + k, len(e) - 1)] > 1.2 * e[max(i - k, 0)] + EPS]
    return [float(max(0.0, t[i])) for i in peaks]


def loop_seam(x: np.ndarray, sr: int) -> dict:
    d = np.abs(np.diff(x))
    jump = abs(float(x[0] - x[-1]))
    p999 = float(np.percentile(d, 99.9)) + EPS
    # Spectral flux across the seam vs. the flux inside the file.
    w = int(sr * 0.1)
    n_fft = 1024 if sr > 30000 else 512
    hop = n_fft // 4
    seam = np.concatenate([x[-w:], x[:w]])
    _, _, Ss = stft_mag(seam, sr, n_fft, hop)
    _, _, Sb = stft_mag(x, sr, n_fft, hop)
    ref = Sb.max() + EPS

    def flux(S):
        L = np.log1p(1000 * S / ref)
        return np.maximum(0, np.diff(L, axis=1)).sum(axis=0)

    fb, fs = flux(Sb), flux(Ss)
    mid = len(fs) // 2
    seam_flux = float(fs[max(0, mid - 2): mid + 2].max())
    body99 = float(np.percentile(fb, 99)) + EPS
    clicks = jump > 2 * p999 or seam_flux > 1.5 * body99
    return {
        "sample_jump": jump,
        "jump_vs_p999": jump / p999,
        "seam_flux": seam_flux,
        "seam_flux_vs_p99": seam_flux / body99,
        "clicks": bool(clicks),
        # A fade at either end makes a loop dip in level (a gap, not a click).
        "end_vs_median_db": seam_level(x[-int(sr * 0.05):], x, sr),
        "start_vs_median_db": seam_level(x[: int(sr * 0.05)], x, sr),
    }


def seam_level(part: np.ndarray, x: np.ndarray, sr: int) -> float:
    w = max(1, int(sr * 0.05))
    lv = frame_rms(x, w, w)
    med = float(np.median(lv[lv > 0])) if np.any(lv > 0) else EPS
    return db(float(np.sqrt(np.mean(part ** 2)))) - db(med)


# ---------------------------------------------------------------- words

def bright_word(c: float) -> str:
    if c < 300:
        return "very dark"
    if c < 800:
        return "dark"
    if c < 1500:
        return "warm"
    if c < 3000:
        return "bright"
    return "very bright"


def headline_tone(r: dict) -> str:
    if r["f0"] and r["f0"]["voiced_share"] > 0.3:
        return f"pitched ~{hz(r['f0']['median_hz'])}"
    return tone_word(r["tonal_share"]).split(" (")[0]


def tone_word(ts: float) -> str:
    if ts > 0.5:
        return "tonal (clear pitches)"
    if ts > 0.15:
        return "mixed (tones plus noise)"
    return "noisy (no clear pitch)"


def width_word(sm: float, corr: float) -> str:
    if corr < 0:
        return "out of phase (will cancel in mono)"
    if sm < -30:
        return "mono (both sides the same)"
    if sm < -12:
        return "narrow"
    if sm < -4:
        return "wide"
    return "very wide"


def report(r: dict) -> str:
    out = []
    name = os.path.basename(r["file"])
    out.append(f"EARS: {name}")
    out.append(
        f"Length {r['duration_s']:.2f} s, {r['sample_rate']} Hz, "
        f"{'stereo' if r['channels'] == 2 else 'mono' if r['channels'] == 1 else str(r['channels']) + ' channels'}."
    )
    if r["sample_rate"] < 40000:
        out.append(f"Note: the file holds nothing above {hz(r['sample_rate'] / 2)} (its sample rate).")
    lufs = f"{r['lufs']:.1f} LUFS" if r["lufs"] is not None else "LUFS n/a (shorter than 0.4 s or silent)"
    out.append(f"Peak {r['peak_dbfs']:.1f} dBFS, RMS {r['rms_dbfs']:.1f} dBFS, loudness {lufs}.")
    if r["clipped_samples"]:
        out.append(f"CLIPPING: {r['clipped_samples']} samples hit full scale.")
    else:
        out.append("No clipping.")
    if abs(r["dc_offset"]) > 0.01:
        out.append(f"DC offset {r['dc_offset']:.3f}: the wave is not centred on zero.")
    b = r["band_share_pct"]
    out.append(
        "Energy by band: " + ", ".join(f"{k} {v:.0f}%" for k, v in b.items()) + "."
    )
    top = max(b, key=b.get)
    out.append(f"Most energy is in the {top} band.")
    out.append(
        f"Centroid {hz(r['centroid_hz'])}: it sounds {bright_word(r['centroid_hz'])}. "
        f"85% of the energy is below {hz(r['rolloff85_hz'])}."
    )
    out.append(
        f"{r['tonal_share'] * 100:.0f}% of the energy sits in clear peaks (flatness {r['flatness']:.3f}): "
        f"{tone_word(r['tonal_share'])}."
    )
    parts = r["partials"]
    if parts and r["tonal_share"] > 0.15:
        main = parts[0]
        out.append(f"Main pitch {hz(main['hz'])} ({main['note']}).")
        if len(parts) > 1:
            rest = ", ".join(
                f"{hz(q['hz'])} {q['note']} (x{q['hz'] / main['hz']:.2f}, {q['db_rel']:.0f} dB)" for q in parts[1:5]
            )
            out.append(f"Other partials: {rest}.")
            ratios = [q["hz"] / main["hz"] for q in parts[1:5]]
            if all(abs(x - round(x)) < 0.03 for x in ratios):
                out.append("The partials sit on whole-number ratios: a harmonic, musical tone.")
            else:
                out.append("Some partials are not whole-number ratios: a bell-like or inharmonic tone.")
    f0 = r["f0"]
    if f0:
        out.append(
            f"Periodic pitch (voice or melody) around {hz(f0['median_hz'])} ({note_name(f0['median_hz'])}), "
            f"moving {hz(f0['low_hz'])}-{hz(f0['high_hz'])}, in {f0['voiced_share'] * 100:.0f}% of the sounding time."
        )
        if r["tonal_share"] <= 0.15:
            out.append("The pitch moves, so the average spectrum looks noisy; the voice is still pitched.")
    att, dec = r["attack_s"], r["decay40_s"]
    if r["duration_s"] > 2 and r["level_spread_db"] < 12:
        out.append(
            f"Steady sound: the level moves only {r['level_spread_db']:.0f} dB (10th to 90th percentile). "
            "Attack and decay of the whole file mean little here."
        )
    else:
        out.append(f"Loudest moment at {r['peak_time_s']:.3f} s; its attack (10% to 90%) takes {ms(att)}.")
        if dec is not None:
            out.append(f"It decays 40 dB in {ms(dec)} after the peak (20 dB in {ms(r['decay20_s'])}).")
        else:
            out.append("It does not fall 40 dB below the peak before the file ends.")
        out.append(f"The level moves {r['level_spread_db']:.0f} dB over the file.")
    tr = r["transients_s"]
    if tr:
        times = ", ".join(f"{t:.2f}" for t in tr[:12]) + (" ..." if len(tr) > 12 else "")
        rate = f" (about {len(tr) / r['duration_s']:.1f} per second)" if r["duration_s"] > 2 else ""
        out.append(f"{len(tr)} transient(s){rate} at s: {times}.")
    else:
        out.append("No sharp transients (clicks or hits).")
    if "side_to_mid_db" in r:
        out.append(
            f"Stereo: {width_word(r['side_to_mid_db'], r['lr_correlation'])}; side is {r['side_to_mid_db']:.0f} dB "
            f"under mid, L/R correlation {r['lr_correlation']:.2f}."
        )
    if "loop" in r:
        lp = r["loop"]
        verdict = "The loop seam CLICKS." if lp["clicks"] else "The loop seam is clean."
        out.append(
            f"{verdict} End-to-start jump is {lp['jump_vs_p999']:.1f}x the 99.9th-percentile sample step; "
            f"seam flux is {lp['seam_flux_vs_p99']:.1f}x the 99th percentile inside the file."
        )
        dip = min(lp["end_vs_median_db"], lp["start_vs_median_db"])
        if dip < -6:
            out.append(
                f"But the level dips at the seam: last 50 ms {lp['end_vs_median_db']:.0f} dB, first 50 ms "
                f"{lp['start_vs_median_db']:.0f} dB against the median. A fade at the ends leaves a gap when looped."
            )
    return "\n".join(out)


def compare(a: dict, b: dict) -> list[str]:
    """Ranked plain-words differences between yours (a) and the reference (b)."""
    items: list[tuple[float, str]] = []

    def band_db(r, key):
        v = r["below_100hz_pct"] if key == "under 100 Hz" else r["band_share_pct"][key]
        return pdb(v / 100)

    labels = {"under 100 Hz": "under 100 Hz", "bass": "in the bass (60-250 Hz)",
              "low-mid": "in the low-mids (250 Hz-2 kHz)", "presence": "in the presence band (2-6 kHz)",
              "air": "in the air band (>6 kHz)"}
    for key, lab in labels.items():
        d = band_db(a, key) - band_db(b, key)
        d = max(-60, min(60, d))
        if abs(d) >= 3:
            items.append((abs(d) / 3, f"Yours has {abs(d):.0f} dB {'more' if d > 0 else 'less'} energy {lab} (share of the total)."))
    ca, cb = a["centroid_hz"], b["centroid_hz"]
    r = math.log2(ca / cb)
    if abs(r) > 0.2:
        items.append((abs(r) * 3, f"Yours is {'brighter' if r > 0 else 'darker'}: centroid {hz(ca)} vs {hz(cb)}."))
    if a["lufs"] is not None and b["lufs"] is not None:
        d = a["lufs"] - b["lufs"]
        if abs(d) >= 2:
            items.append((abs(d) / 3, f"Yours is {abs(d):.1f} LU {'louder' if d > 0 else 'quieter'} ({a['lufs']:.1f} vs {b['lufs']:.1f} LUFS)."))
    else:
        d = a["peak_dbfs"] - b["peak_dbfs"]
        if abs(d) >= 3:
            items.append((abs(d) / 3, f"Your peak is {abs(d):.0f} dB {'higher' if d > 0 else 'lower'} ({a['peak_dbfs']:.1f} vs {b['peak_dbfs']:.1f} dBFS)."))
    def steady(r):
        return r["duration_s"] > 2 and r["level_spread_db"] < 12

    shape = [] if steady(a) or steady(b) else [("decay40_s", "decays (40 dB)"), ("attack_s", "attacks (10-90%)")]
    for key, word in shape:
        x, y = a[key], b[key]
        if x and y and abs(math.log2(x / y)) > 0.4:
            items.append((abs(math.log2(x / y)) * 3, f"Your sound {word} in {ms(x)}, the reference in {ms(y)}."))
        elif (x is None) != (y is None) and key == "decay40_s":
            who = "Yours" if x is None else "The reference"
            items.append((4, f"{who} never falls 40 dB before its end; the other does, in {ms(x or y)}."))
    fa, fb = a["tonal_share"], b["tonal_share"]
    if tone_word(fa) != tone_word(fb):
        items.append((3, f"Yours is {tone_word(fa).split(' (')[0]}, the reference is {tone_word(fb).split(' (')[0]} ({fa * 100:.0f}% vs {fb * 100:.0f}% of energy in clear peaks)."))
    pa, pb_ = a["partials"], b["partials"]
    if pa and pb_ and fa > 0.15 and fb > 0.15:
        st = 12 * math.log2(pa[0]["hz"] / pb_[0]["hz"])
        if abs(st) > 0.5:
            items.append((min(abs(st), 12) / 2, f"Main pitch: yours {hz(pa[0]['hz'])} ({pa[0]['note']}), the reference {hz(pb_[0]['hz'])} ({pb_[0]['note']}), {abs(st):.1f} semitones {'higher' if st > 0 else 'lower'}."))
    ta, tb = len(a["transients_s"]), len(b["transients_s"])
    ra, rb = ta / a["duration_s"], tb / b["duration_s"]
    if abs(ra - rb) > 0.5 and max(ra, rb) > 2 * min(ra, rb):
        items.append((2, f"Transients: yours {ra:.1f} per second, the reference {rb:.1f} per second."))
    if "side_to_mid_db" in a and "side_to_mid_db" in b:
        d = a["side_to_mid_db"] - b["side_to_mid_db"]
        if abs(d) > 4:
            items.append((abs(d) / 4, f"Yours is {'wider' if d > 0 else 'narrower'} in stereo (side/mid {a['side_to_mid_db']:.0f} dB vs {b['side_to_mid_db']:.0f} dB)."))
    elif ("side_to_mid_db" in a) != ("side_to_mid_db" in b):
        items.append((1, f"Yours is {'stereo' if 'side_to_mid_db' in a else 'mono'}, the reference is {'stereo' if 'side_to_mid_db' in b else 'mono'}."))
    if a["clipped_samples"] and not b["clipped_samples"]:
        items.append((10, f"Yours clips ({a['clipped_samples']} samples); the reference does not."))
    items.sort(key=lambda t: -t[0])
    return [s for _, s in items[:8]] or ["No big differences found: the two sound alike by these measures."]


# ---------------------------------------------------------------- picture

def plot(r: dict, ref: dict | None, png: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    BG, FG, GRID = "#111418", "#d8dde3", "#2b3138"
    C1, C2 = "#5fd3f3", "#f3a95f"
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG, "axes.edgecolor": GRID, "axes.labelcolor": FG,
        "xtick.color": FG, "ytick.color": FG, "text.color": FG, "font.size": 12, "axes.titlesize": 13,
        "axes.titleweight": "bold", "axes.titlelocation": "left",
    })
    fig = plt.figure(figsize=(14, 14), dpi=100)
    gs = fig.add_gridspec(4, 1, height_ratios=[1, 1, 2.2, 1.6], hspace=0.42, left=0.08, right=0.97, top=0.93, bottom=0.05)
    mono, sr, dur = r["_mono"], r["sample_rate"], r["duration_s"]
    lufs = f"{r['lufs']:.1f} LUFS" if r["lufs"] is not None else "LUFS n/a"
    fig.suptitle(
        f"{os.path.basename(r['file'])}   {dur:.2f} s · peak {r['peak_dbfs']:.1f} dBFS · {lufs} · "
        f"centroid {hz(r['centroid_hz'])} · {headline_tone(r)}",
        x=0.08, ha="left", fontsize=15, fontweight="bold",
    )
    tmax = dur
    # 1 waveform (min/max per pixel column).
    ax = fig.add_subplot(gs[0])
    cols = 1400
    if len(mono) > cols * 4:
        k = len(mono) // cols
        m = mono[: k * cols].reshape(cols, k)
        tt = (np.arange(cols) + 0.5) * k / sr
        ax.fill_between(tt, m.min(axis=1), m.max(axis=1), color=C1, lw=0)
    else:
        ax.plot(np.arange(len(mono)) / sr, mono, color=C1, lw=0.8)
    for t in r["transients_s"][:200]:
        ax.axvline(t, color="#ff5f7a", lw=0.8, alpha=0.6)
    lim = max(1e-6, np.max(np.abs(mono))) * 1.1
    ax.set_ylim(-lim, lim)
    ax.set_xlim(0, tmax)
    ax.set_title("Waveform (mono mix; red lines = transients)")
    ax.set_xlabel("seconds")
    ax.grid(color=GRID, lw=0.6)
    # 2 loudness envelope.
    ax = fig.add_subplot(gs[1])
    et, ev, ew = r["_envelope"]
    ax.plot(et, ev, color=C1, lw=1.4, label="yours" if ref else None)
    if ref:
        rt, rv, _ = ref["_envelope"]
        ax.plot(rt, rv, color=C2, lw=1.2, alpha=0.9, label="reference")
        ax.legend(loc="upper right", facecolor=BG, edgecolor=GRID)
        tmax = max(tmax, ref["duration_s"])
    top = max(ev.max(), ref["_envelope"][1].max() if ref else -200)
    ax.set_ylim(top - 70, top + 5)
    ax.set_xlim(0, tmax if ref else dur)
    ax.axhline(r["peak_dbfs"], color=GRID, lw=0.8, ls="--")
    ax.set_title(f"Level envelope (RMS dBFS, {ew * 1000:.0f} ms window)")
    ax.set_xlabel("seconds")
    ax.set_ylabel("dBFS")
    ax.grid(color=GRID, lw=0.6)
    # 3 log-frequency spectrogram.
    ax = fig.add_subplot(gs[2])
    if dur < 1:
        n_fft = 512 if sr > 30000 else 256
        hop = max(1, n_fft // 16)
        sf_, st, S = stft_mag(mono, sr, n_fft, hop)
    else:
        sf_, st, S = r["_spec"]
        if S.shape[1] > 3000:
            step = S.shape[1] // 1500
            S, st = S[:, ::step], st[::step]
    Sdb = 20 * np.log10(S + EPS)
    vmax = Sdb.max()
    keep = sf_ >= 15
    ax.pcolormesh(st, sf_[keep], Sdb[keep], shading="auto", cmap="magma", vmin=vmax - 90, vmax=vmax, rasterized=True)
    ax.set_yscale("log")
    ax.set_ylim(20, 20000)
    ax.set_xlim(0, dur)
    for o in range(1, 11):
        fc = 16.3516 * 2 ** o
        if 20 <= fc <= min(20000, sr / 2):
            ax.axhline(fc, color="#ffffff", lw=0.5, alpha=0.35)
            ax.text(dur * 0.995, fc * 1.03, f"C{o}  {hz(fc)}", color="#ffffff", alpha=0.8, fontsize=10, ha="right", va="bottom")
    if sr / 2 < 20000:
        ax.axhspan(sr / 2, 20000, color="#222830", zorder=3)
        ax.text(dur * 0.01, sr / 2 * 1.1, f"nothing above {hz(sr / 2)} (sample rate)", fontsize=10, color=FG, zorder=4)
    ax.set_yticks([20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_yticklabels(["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    ax.set_title("Spectrogram (log frequency, 90 dB range; lines = octaves of C)")
    ax.set_xlabel("seconds")
    ax.set_ylabel("Hz")
    # 4 average spectrum.
    ax = fig.add_subplot(gs[3])
    f, p = r["_spectrum"]

    def smooth_db(f, p):
        sel = (f >= 20) & (f <= 20000)
        y = 10 * np.log10(p[sel] + EPS)
        return f[sel], y

    fx, y = smooth_db(f, p)
    off = y.max()
    ax.plot(fx, y - off, color=C1, lw=1.1, label="yours" if ref else None)
    if ref:
        rf, rp = ref["_spectrum"]
        fr, yr = smooth_db(rf, rp)
        ax.plot(fr, yr - yr.max(), color=C2, lw=1.0, alpha=0.9, label="reference")
        ax.legend(loc="upper right", facecolor=BG, edgecolor=GRID)
    shades = ["#1d2b33", "#1a2228", "#1d2b33", "#1a2228", "#1d2b33"]
    for (name, lo, hi), sh in zip(BANDS, shades):
        lo, hi = max(lo, 20), min(hi, 20000)
        ax.axvspan(lo, hi, color=sh, zorder=0)
        ax.text(math.sqrt(lo * hi), -86, f"{name} {r['band_share_pct'][name]:.0f}%", ha="center", va="bottom", fontsize=11)
    shown: list[float] = []
    for q in r["partials"][:5] if r["tonal_share"] > 0.15 else []:
        if any(abs(math.log2(q["hz"] / s)) < 0.15 for s in shown):
            continue
        crowded = any(abs(math.log2(q["hz"] / s)) < 0.6 for s in shown)
        shown.append(q["hz"])
        # A label close to one already drawn goes on the left side of its peak.
        ax.annotate(
            f"{q['note']}\n{hz(q['hz'])}", (q["hz"], q["db_rel"]), textcoords="offset points",
            xytext=(-5 if crowded else 5, -2), ha="right" if crowded else "left",
            fontsize=10, color="#ffe08a", va="top",
        )
    ax.set_xscale("log")
    ax.set_xlim(20, 20000)
    ax.set_ylim(-90, 12)
    ax.set_xticks([20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax.set_xticklabels(["20", "50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"])
    ax.set_title("Average spectrum (dB relative to its top" + (", orange = reference)" if ref else ")"))
    ax.set_xlabel("Hz")
    ax.set_ylabel("dB")
    ax.grid(color=GRID, lw=0.6)
    fig.savefig(png, facecolor=BG)
    plt.close(fig)


# ---------------------------------------------------------------- main

def public(r: dict) -> dict:
    return {k: v for k, v in r.items() if not k.startswith("_")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ears", description="See a sound: picture, numbers and a plain-words report.")
    ap.add_argument("file")
    ap.add_argument("--ref", help="reference sound to compare against")
    ap.add_argument("--out", help="output folder (default: <file>.ears/ next to the file)")
    ap.add_argument("--loop", action="store_true", help="check whether the loop seam (end to start) clicks")
    ap.add_argument("--quiet", action="store_true", help="print only the paths")
    a = ap.parse_args(argv)
    if not os.path.exists(a.file):
        sys.exit(f"ears: no such file: {a.file}")
    out = a.out or os.path.splitext(a.file)[0] + ".ears"
    os.makedirs(out, exist_ok=True)
    r = analyze(a.file, loop=a.loop)
    ref = analyze(a.ref, loop=a.loop) if a.ref else None
    png, js = os.path.join(out, "ears.png"), os.path.join(out, "ears.json")
    plot(r, ref, png)
    text = report(r)
    doc = public(r)
    if ref:
        diffs = compare(r, ref)
        doc["reference"] = public(ref)
        doc["differences"] = diffs
        text += f"\n\nCOMPARED WITH {os.path.basename(a.ref)} (biggest first):\n" + "\n".join(f"- {d}" for d in diffs)
    doc["report"] = text
    with open(js, "w") as fh:
        json.dump(doc, fh, indent=2)
    if not a.quiet:
        print(text)
    print(f"\nPicture: {png}\nNumbers: {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
