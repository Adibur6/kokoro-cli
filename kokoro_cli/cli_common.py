from __future__ import annotations

from rich.console import Console

from kokoro_cli.config import detect_device
from kokoro_cli.text import load_text
from kokoro_cli.voices import resolve_voice


def prepare_run(
    text: str | None,
    file: list[str],
    voice: str,
    lang: str,
    device: str | None,
) -> tuple[Console, str, str, str]:
    """Resolve text, voice path, and device — shared setup for tts/live/profile."""
    console = Console()
    body = load_text(text, file)
    voice_path = resolve_voice(voice)
    device = device or detect_device()
    return console, body, voice_path, device
