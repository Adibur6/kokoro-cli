from __future__ import annotations

import queue
import select
import sys
import termios
import threading
import time
import tty

import numpy as np
import sounddevice as sd
import typer
from rich.console import Console
from rich.live import Live

from kokoro_cli.audio import save_audio, to_int16, trim_silence
from kokoro_cli.cli_common import prepare_run
from kokoro_cli.config import SAMPLE_RATE, detect_device
from kokoro_cli.live_display import Segment, render_display, split_into_segments
from kokoro_cli.live_watch import watch_clipboard
from kokoro_cli.model import load_pipeline
from kokoro_cli.voices import resolve_voice

BLOCKSIZE = 4096
SPACE = " "
ESC = "\x1b"


def listen_for_keys(cancel: threading.Event, paused: threading.Event, stop_listening: threading.Event) -> None:
    """Space toggles pause, Esc cancels. No-op outside a real terminal."""
    if not sys.stdin.isatty():
        return
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop_listening.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if not ready:
                continue
            ch = sys.stdin.read(1)
            if ch == SPACE:
                paused.clear() if paused.is_set() else paused.set()
            elif ch == ESC:
                cancel.set()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def speak(
    console,
    pipe,
    voice: str,
    voice_path: str,
    device: str,
    speed: float,
    body: str,
    *,
    out: str | None = None,
    cancel: threading.Event | None = None,
    announce: bool = True,
) -> bool:
    """Synthesize and play one utterance with the live animation. Returns True on Ctrl+C."""
    cancel = cancel or threading.Event()
    paused = threading.Event()
    stop_listening = threading.Event()
    if announce:
        console.print(f"Streaming with voice '{voice}' on {device}... (Ctrl+C to stop, Space to pause, Esc to skip)")

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
            if cancel.is_set():
                break
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
    key_listener = threading.Thread(target=listen_for_keys, args=(cancel, paused, stop_listening), daemon=True)
    key_listener.start()

    state = {"current": None, "chunk_id": None, "played": 0}

    def callback(outdata, frames, time_info, status) -> None:
        if paused.is_set():
            outdata.fill(0)
            return
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
    interrupted = False
    try:
        with Live(console=console, refresh_per_second=12, transient=True) as live:
            while not cancel.is_set() and (
                not done.is_set() or not audio_q.empty() or (
                    state["current"] is not None and len(state["current"]) > 0
                )
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
                live.update(
                    render_display(
                        snapshot, cur_chunk_id, elapsed, played_secs, estimated_total, paused=paused.is_set()
                    )
                )
                time.sleep(0.05)
    except KeyboardInterrupt:
        interrupted = True
        cancel.set()
        console.print("\n[yellow]Interrupted.[/yellow] Stopping playback...")
    finally:
        stop_listening.set()
        stream.stop()
        stream.close()
        thread.join()
        key_listener.join(timeout=1)

    with chunks_lock:
        total = sum(len(c) for c in chunks) / SAMPLE_RATE
    console.print(f"Done. {total:.2f}s of audio streamed in {time.time() - t0:.2f}s.")

    if out and chunks:
        wav = np.concatenate(chunks)
        save_audio(wav, out)
        console.print(f"Saved {len(wav) / SAMPLE_RATE:.2f}s of audio to {out}")

    return interrupted


def run(
    text: str | None = typer.Argument(None, help="Text to speak (or use --file)"),
    file: list[str] = typer.Option([], "--file", "-f", help="Read text from a file (repeatable)"),
    voice: str = typer.Option("af_heart", "--voice", "-v", help="Voice name in Kokoro-82M/voices"),
    lang: str = typer.Option("a", "--lang", help="Language code: a=American English, b=British English"),
    device: str | None = typer.Option(None, "--device", help="cuda, mps or cpu (default: auto)"),
    speed: float = typer.Option(1.0, "--speed", min=0.25, max=4.0, help="Speech speed multiplier"),
    out: str | None = typer.Option(None, "--out", "-o", help="Also save the full stream to this file"),
    watch: bool = typer.Option(
        False, "--watch", help="Watch the clipboard and speak newly copied text (Ctrl+C to stop)"
    ),
) -> None:
    if watch:
        if text or file:
            raise SystemExit("--watch reads from the clipboard; don't pass text or --file.")
        if out:
            raise SystemExit("--watch doesn't support --out (there's no single utterance to save).")
        console = Console()
        voice_path = resolve_voice(voice)
        device = device or detect_device()
        with console.status("Loading model..."):
            pipe = load_pipeline(lang, device)
        watch_clipboard(speak, console, pipe, voice, voice_path, device, speed)
        return

    console, body, voice_path, device = prepare_run(text, file, voice, lang, device)
    with console.status("Loading model..."):
        pipe = load_pipeline(lang, device)
    speak(console, pipe, voice, voice_path, device, speed, body, out=out)
