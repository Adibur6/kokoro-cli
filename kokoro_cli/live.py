from __future__ import annotations

import queue
import threading
import time

import numpy as np
import sounddevice as sd
import typer
from rich.live import Live

from kokoro_cli.audio import save_audio, to_int16, trim_silence
from kokoro_cli.cli_common import prepare_run
from kokoro_cli.config import SAMPLE_RATE
from kokoro_cli.live_display import Segment, render_display, split_into_segments
from kokoro_cli.model import load_pipeline

BLOCKSIZE = 4096


def run(
    text: str | None = typer.Argument(None, help="Text to speak (or use --file)"),
    file: list[str] = typer.Option([], "--file", "-f", help="Read text from a file (repeatable)"),
    voice: str = typer.Option("af_heart", "--voice", "-v", help="Voice name in Kokoro-82M/voices"),
    lang: str = typer.Option("a", "--lang", help="Language code: a=American English, b=British English"),
    device: str | None = typer.Option(None, "--device", help="cuda, mps or cpu (default: auto)"),
    speed: float = typer.Option(1.0, "--speed", min=0.25, max=4.0, help="Speech speed multiplier"),
    out: str | None = typer.Option(None, "--out", "-o", help="Also save the full stream to this file"),
) -> None:
    console, body, voice_path, device = prepare_run(text, file, voice, lang, device)

    with console.status("Loading model..."):
        pipe = load_pipeline(lang, device)

    console.print(f"Streaming with voice '{voice}' on {device}... (Ctrl+C to stop)")

    total_chars = len(body)
    audio_q: queue.Queue = queue.Queue()
    chunks: list[np.ndarray] = []
    chunk_chars: list[int] = []
    chunks_lock = threading.Lock()
    segments: list[Segment] = []
    segments_lock = threading.Lock()
    done = threading.Event()

    def producer() -> None:
        chunk_id = 0
        for result in pipe(body, voice=voice_path, speed=speed):
            a = np.asarray(result.audio.cpu().numpy(), dtype=np.float32)
            a = trim_silence(a)
            with chunks_lock:
                chunks.append(a)
                chunk_chars.append(len(result.graphemes))
            if result.tokens:
                with segments_lock:
                    segments.extend(split_into_segments(chunk_id, result.tokens))
            audio_q.put((chunk_id, to_int16(a)))
            chunk_id += 1
        audio_q.put(None)
        done.set()

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    state = {"current": None, "chunk_id": None, "played": 0}

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
            chunk_id, cur = item
            state["current"] = cur
            state["chunk_id"] = chunk_id
            state["played"] = 0
        n = min(frames, len(cur))
        outdata[:n, 0] = cur[:n]
        if n < frames:
            outdata[n:, 0] = 0
        state["played"] += n
        state["current"] = cur[n:] if n < len(cur) else None

    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCKSIZE, callback=callback
    )
    t0 = time.time()
    stream.start()
    try:
        with Live(console=console, refresh_per_second=12, transient=True) as live:
            while not done.is_set() or not audio_q.empty() or (
                state["current"] is not None and len(state["current"]) > 0
            ):
                with segments_lock:
                    snapshot = list(segments)
                with chunks_lock:
                    durations = [len(c) / SAMPLE_RATE for c in chunks]
                    synth_chars = sum(chunk_chars)
                cur_chunk_id = state["chunk_id"]
                elapsed = state["played"] / SAMPLE_RATE
                played_secs = (sum(durations[:cur_chunk_id]) + elapsed) if cur_chunk_id is not None else 0.0
                estimated_total = (sum(durations) / synth_chars * total_chars) if synth_chars else None
                live.update(render_display(snapshot, cur_chunk_id, elapsed, played_secs, estimated_total))
                time.sleep(0.05)
        thread.join()
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
