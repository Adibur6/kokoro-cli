import os

from kokoro_cli.config import VOICES_DIR


def list_voices() -> list[str]:
    if not os.path.isdir(VOICES_DIR):
        return []
    return sorted(f[:-3] for f in os.listdir(VOICES_DIR) if f.endswith(".pt"))


def resolve_voice(name: str) -> str:
    """Return the .pt path for a voice name (or an existing path if given)."""
    if name.endswith(".pt") and os.path.isfile(name):
        return name
    path = os.path.join(VOICES_DIR, f"{name}.pt")
    if not os.path.isfile(path):
        voices = list_voices()
        raise SystemExit(
            f"Voice '{name}' not found. Run `kokoro voices` for the list "
            f"({len(voices)} available)."
        )
    return path
