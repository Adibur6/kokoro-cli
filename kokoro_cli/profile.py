from __future__ import annotations

import time

import numpy as np
import typer
from rich.console import Console

from kokoro_cli.config import SAMPLE_RATE
from kokoro_cli.model import load_pipeline
from kokoro_cli.text import load_text
from kokoro_cli.voices import resolve_voice


def run(
    text: str | None = typer.Argument(None, help="Text to synthesize (or use --file)"),
    file: list[str] = typer.Option([], "--file", "-f", help="Read text from a file (repeatable)"),
    voice: str = typer.Option("af_heart", "--voice", "-v", help="Voice name in Kokoro-82M/voices"),
    lang: str = typer.Option("a", "--lang", help="Language code: a=American English, b=British English"),
    device: str | None = typer.Option(None, "--device", help="cuda, mps or cpu (default: auto)"),
) -> None:
    console = Console()
    body = load_text(text, file)
    resolve_voice(voice)

    from kokoro_cli.config import detect_device

    device = device or detect_device()

    t0 = time.time()
    pipe = load_pipeline(lang, device)
    t_model = time.time() - t0
    t_ready = time.time() - t0
    voice_path = resolve_voice(voice)

    console.print(f"[{t_ready:6.2f}s] model loaded ({t_model:.2f}s) + pipeline ready, device={device}")

    rows = []
    for i, (gs, ps, audio) in enumerate(pipe(body, voice=voice_path)):
        a = np.asarray(audio.cpu().numpy(), dtype=np.float32)
        dur = len(a) / SAMPLE_RATE
        rows.append((i, time.time() - t0, dur))
        console.print(f"chunk {i}: synth_done@{rows[-1][1]:.2f}s  dur={dur:.2f}s")

    if not rows:
        raise SystemExit("No audio produced.")

    total_dur = sum(r[2] for r in rows)
    t_first = rows[0][1]
    t_synth_end = rows[-1][1]

    console.print("\n=== SIMULATED PLAYBACK (starts when chunk 0 is ready) ===")
    play_pos = t_first
    stall = False
    for i, t_synth, dur in rows:
        margin = play_pos - t_synth
        console.print(
            f"chunk {i}: synth_done@{t_synth:6.2f}s  plays {play_pos:6.2f}->{play_pos + dur:6.2f}s  margin={margin:+6.2f}s"
        )
        if margin < 0:
            stall = True
        play_pos += dur

    console.print(
        f"\nTIME TO FIRST WORD (cold start): {t_first:.2f}s  "
        f"(model {t_model:.2f}s + G2P init {t_ready - t_model:.2f}s + first chunk {t_first - t_ready:.2f}s)"
    )
    console.print(f"Total audio: {total_dur:.2f}s | all synthesis done @{t_synth_end:.2f}s")
    console.print(f"Inference finished {total_dur - t_synth_end:.2f}s BEFORE playback would end")
    rt = total_dur / t_synth_end if t_synth_end > 0 else 0
    console.print(f"Real-time factor: {rt:.2f}x realtime synthesis (excl. model load)")
    console.print(
        "STALL RISK:", "YES (inference falls behind)" if stall else "NO (inference stays ahead of playback)"
    )
