"""Scenario tests for the transient detector: what a listener would call a click, and what they would not."""

import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ears  # noqa: E402

SR = 44100


def write_wav(x: np.ndarray) -> str:
    f = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(f.name, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return f.name


def tone(seconds: float, freq: float = 440.0) -> np.ndarray:
    t = np.arange(int(SR * seconds)) / SR
    return 0.5 * np.sin(2 * np.pi * freq * t)


def test_a_fade_out_is_not_a_click():
    # The bug found in testing: a 1 s 440 Hz tone with a 100 ms fade-out was flagged at 0.89 s.
    x = tone(1.0)
    n = int(SR * 0.1)
    x[-n:] *= np.linspace(1, 0, n)
    r = ears.analyze(write_wav(x))
    late = [s for s in r["transients_s"] if s > 0.5]
    assert late == [], f"fade-out reported as transients at {late}"


def test_a_slow_fade_in_and_out_has_no_clicks_in_the_middle():
    x = tone(2.0)
    n = int(SR * 0.5)
    x[:n] *= np.linspace(0, 1, n)
    x[-n:] *= np.linspace(1, 0, n)
    r = ears.analyze(write_wav(x))
    middle = [s for s in r["transients_s"] if 0.2 < s < 1.9]
    assert middle == [], f"smooth fades reported as transients at {middle}"


def test_real_clicks_are_still_found():
    x = np.zeros(int(SR * 1.5))
    for at in (0.3, 0.7, 1.1):
        i = int(SR * at)
        burst = np.random.default_rng(1).normal(0, 0.6, int(SR * 0.004))
        x[i : i + len(burst)] += burst * np.linspace(1, 0, len(burst))
    r = ears.analyze(write_wav(x))
    found = r["transients_s"]
    for at in (0.3, 0.7, 1.1):
        assert any(abs(s - at) < 0.03 for s in found), f"click at {at} s missed; found {found}"


def test_a_note_struck_after_silence_is_one_transient():
    x = np.concatenate([np.zeros(int(SR * 0.4)), tone(0.8) * np.exp(-np.arange(int(SR * 0.8)) / (SR * 0.2))])
    r = ears.analyze(write_wav(x))
    found = r["transients_s"]
    assert len(found) == 1 and abs(found[0] - 0.4) < 0.03, f"expected one onset at 0.4 s, found {found}"
