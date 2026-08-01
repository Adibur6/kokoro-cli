from __future__ import annotations

import queue
import threading
import time

import numpy as np
import sounddevice as sd
import typer

from kokoro_cli.audio import save_audio, to_int16, trim_silence
from kokoro_cli.cli_common import prepare_run
from kokoro_cli.config import SAMPLE_RATE
from kokoro_cli.model import load_pipeline

BLOCKSIZE = 4096


def run(
    text: str | None = typer.Argument(None, help="Text to speak (or use --file)"),
    file: list[str] = typer.Option([], "--file", "-f", help="Read text from a file (repeatable)"),
    voice: str = typer.Option("af_heart", "--voice", "-v", help="Voice name in Kokoro-82M/voices"),
    lang: str = typer.Option("a", "--lang", help="Language code: a=American English, b=British English"),
    device: str | None = typer.Option(None, "--device", help="cuda, mps or cpu (default: auto)"),
    out: str | None = typer.Option(None, "--out", "-o", help="Also save the full stream to this file"),
) -> None:
    console, body, voice_path, device = prepare_run(text, file, voice, lang, device)

    with console.status("Loading model..."):
        pipe = load_pipeline(lang, device)

    console.print(f"Streaming with voice '{voice}' on {device}... (Ctrl+C to stop)")

    audio_q: queue.Queue = queue.Queue()
    chunks: list[np.ndarray] = []
    chunks_lock = threading.Lock()
    done = threading.Event()

    def producer() -> None:
        for _gs, _ps, audio in pipe(body, voice=voice_path):
            a = np.asarray(audio.cpu().numpy(), dtype=np.float32)
            a = trim_silence(a)
            with chunks_lock:
                chunks.append(a)
            audio_q.put(to_int16(a))
        audio_q.put(None)
        done.set()

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    state = {"current": None}

    def callback(outdata, frames, time_info, status) -> None:
        cur = state["current"]
        if cur is None or len(cur) == 0:
            try:
                item = audio_q.get_nowait()
            except queue.Empty:
                outdata.fill(0)
                return
            if item is None:
                state["current"] = None
                outdata.fill(0)
                return
            state["current"] = item
            cur = item
        n = min(frames, len(cur))
        outdata[:n, 0] = cur[:n]
        if n < frames:
            outdata[n:, 0] = 0
        state["current"] = cur[n:] if n < len(cur) else None

    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCKSIZE, callback=callback
    )
    t0 = time.time()
    stream.start()
    try:
        thread.join()
        while not audio_q.empty() or (state["current"] is not None and len(state["current"]) > 0):
            time.sleep(0.05)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow] Stopping playback...")
    stream.stop()

    with chunks_lock:
        total = sum(len(c) for c in chunks) / SAMPLE_RATE
    console.print(f"Done. {total:.2f}s of audio streamed in {time.time() - t0:.2f}s.")

    if out and chunks:
        wav = np.concatenate(chunks)
        save_audio(wav, out)
        console.print(f"Saved {len(wav) / SAMPLE_RATE:.2f}s of audio to {out}")
