from __future__ import annotations

import time

import numpy as np
import typer
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from kokoro_cli.audio import save_audio
from kokoro_cli.cli_common import prepare_run
from kokoro_cli.config import OUT_DIR
from kokoro_cli.model import load_pipeline


def run(
    text: str | None = typer.Argument(None, help="Text to speak (or use --file)"),
    file: list[str] = typer.Option([], "--file", "-f", help="Read text from a file (repeatable)"),
    voice: str = typer.Option("af_heart", "--voice", "-v", help="Voice name in Kokoro-82M/voices"),
    lang: str = typer.Option("a", "--lang", help="Language code: a=American English, b=British English"),
    device: str | None = typer.Option(None, "--device", help="cuda, mps or cpu (default: auto)"),
    out: str = typer.Option(f"{OUT_DIR}/output.wav", "--out", "-o", help="Output path (.wav/.mp3/.flac/.ogg)"),
) -> None:
    console, body, voice_path, device = prepare_run(text, file, voice, lang, device)

    t0 = time.time()
    with console.status("Loading model..."):
        pipe = load_pipeline(lang, device)

    chunks: list[np.ndarray] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Synthesizing...", total=None)
        for _gs, _ps, audio in pipe(body, voice=voice_path):
            chunks.append(np.asarray(audio.cpu().numpy(), dtype=np.float32))
            progress.update(task, total=len(chunks))
        progress.update(task, completed=len(chunks), total=len(chunks))

    wav = np.concatenate(chunks)
    save_audio(wav, out)
    secs = len(wav) / 24000
    console.print(f"[green]Saved[/green] {secs:.2f}s of audio to {out} "
                  f"in {time.time() - t0:.2f}s (voice {voice}, device {device})")
