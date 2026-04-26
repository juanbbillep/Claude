"""Synthetic-signal tests for the cross-correlation math, no ffmpeg required.

Convention reminder: `offset_seconds` returned by `_xcorr_offset(ref, other, sr)`
is the reference-timeline timestamp where `other`'s local t=0 lands. So if
`other` is `ref` prepended with N samples of silence, `other`'s content event
that happens at ref-time 0 sits at other-local time N/sr — meaning other-local
t=0 maps to ref-time -N/sr, hence offset = -N/sr.
"""

from __future__ import annotations

import numpy as np

from app.multicam_sync import _xcorr_offset


def test_xcorr_recovers_known_offset_late_source():
    sr = 8_000
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    rng = np.random.default_rng(42)
    base = rng.standard_normal(t.size).astype(np.float32)

    shift_samples = 1234
    other = np.concatenate([np.zeros(shift_samples, dtype=np.float32), base])[: t.size]

    offset, conf = _xcorr_offset(base, other, sr)
    expected = -shift_samples / sr  # other starts AFTER ref → negative offset
    assert abs(offset - expected) < 4.0 / sr
    assert conf > 0.5


def test_xcorr_recovers_known_offset_early_source():
    sr = 8_000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    rng = np.random.default_rng(7)
    base = rng.standard_normal(t.size).astype(np.float32)

    shift_samples = 800
    shifted_base = np.concatenate([np.zeros(shift_samples, dtype=np.float32), base])[: t.size]

    offset, _ = _xcorr_offset(shifted_base, base, sr)
    expected = shift_samples / sr  # other starts BEFORE ref → positive offset
    assert abs(offset - expected) < 4.0 / sr
