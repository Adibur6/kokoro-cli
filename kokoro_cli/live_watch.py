from __future__ import annotations

import subprocess
import threading
import time

WATCH_POLL_SECS = 0.35
CHANGE_COUNT_SCRIPT = 'ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'
SNIPPET_LIMIT = 60


def _snippet(text: str, limit: int = SNIPPET_LIMIT) -> str:
    """One-line, whitespace-collapsed preview of clipboard text for the watch log."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return f'"{collapsed}"'
    return f'"{collapsed[:limit].rstrip()}…"'


def _pasteboard_change_count() -> int | None:
    """macOS bumps this on every copy, even re-copying identical text — unlike diffing content."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", CHANGE_COUNT_SCRIPT],
            capture_output=True, text=True, check=True,
        )
        return int(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None


def watch_clipboard(speak, console, pipe, voice: str, voice_path: str, device: str, speed: float) -> None:
    console.print(
        f"Watching clipboard with voice '{voice}' on {device}... "
        "(Ctrl+C to stop, Space to pause, Esc to skip)"
    )

    state = {"pending": None}
    state_lock = threading.Lock()
    cancel = threading.Event()
    stop_watching = threading.Event()

    def poll_clipboard() -> None:
        last_change_count = _pasteboard_change_count()
        while not stop_watching.is_set():
            change_count = _pasteboard_change_count()
            if change_count is not None and change_count != last_change_count:
                last_change_count = change_count
                try:
                    clip = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
                except (subprocess.CalledProcessError, FileNotFoundError):
                    clip = ""
                text = clip.strip()
                if text:
                    with state_lock:
                        state["pending"] = text
                    cancel.set()
            stop_watching.wait(WATCH_POLL_SECS)

    watcher = threading.Thread(target=poll_clipboard, daemon=True)
    watcher.start()

    spoken_count = 0
    idle_status = None
    try:
        while True:
            with state_lock:
                cancel.clear()
                next_text, state["pending"] = state["pending"], None
            if next_text is None:
                if idle_status is None:
                    idle_status = console.status(f"Watching for the next clip... ({spoken_count} spoken)")
                    idle_status.start()
                time.sleep(WATCH_POLL_SECS)
                continue
            if idle_status is not None:
                idle_status.stop()
                idle_status = None
            spoken_count += 1
            console.print(f"[cyan]▶[/cyan] #{spoken_count}  {_snippet(next_text)}")
            if speak(console, pipe, voice, voice_path, device, speed, next_text, cancel=cancel, announce=False):
                break
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow] Stopping watch mode...")
    finally:
        if idle_status is not None:
            idle_status.stop()
        stop_watching.set()
