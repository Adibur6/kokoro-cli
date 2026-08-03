import os

import numpy as np
import soundfile as sf

from kokoro_cli.config import SAMPLE_RATE

FORMATS = ("wav", "flac", "ogg", "mp3")
PCM_16_FORMATS = ("wav", "flac")


def save_audio(audio: np.ndarray, path: str, sample_rate: int = SAMPLE_RATE) -> None:
    """Write a float array in [-1, 1] to path, inferring format from extension."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    if ext not in FORMATS:
        raise SystemExit(f"Unsupported output format '.{ext}'. Use one of: {', '.join(FORMATS)}")
    subtype = "PCM_16" if ext in PCM_16_FORMATS else None
    sf.write(path, audio, sample_rate, subtype=subtype)


def to_int16(audio: np.ndarray) -> np.ndarray:
    return (audio * 32767).astype(np.int16)


def trim_silence(
    audio: np.ndarray,
    trim_secs: float = 0.35,
    keep_tail_secs: float = 0.03,
    threshold: float = 0.01,
    sample_rate: int = SAMPLE_RATE,
) -> np.ndarray:
    """Trim trailing (and all but the first chunk's leading) near-silence."""
    cutoff = int(trim_secs * sample_rate)
    n = len(audio)
    end = max(n - 1 - cutoff, 0)
    above = np.flatnonzero(np.abs(audio[end:n]) >= threshold)
    i = end + int(above[-1]) if above.size else end
    tail = int(keep_tail_secs * sample_rate)
    return audio[: i + tail]
