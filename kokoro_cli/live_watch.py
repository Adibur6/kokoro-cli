from __future__ import annotations

import subprocess
import threading
import time

WATCH_POLL_SECS = 0.35
CHANGE_COUNT_SCRIPT = 'ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'


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
    console.print(f"Watching clipboard with voice '{voice}' on {device}... (Ctrl+C to stop)")

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

    try:
        while True:
            with state_lock:
                cancel.clear()
                next_text, state["pending"] = state["pending"], None
            if next_text is None:
                time.sleep(WATCH_POLL_SECS)
                continue
            if speak(console, pipe, voice, voice_path, device, speed, next_text, cancel=cancel):
                break
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow] Stopping watch mode...")
    finally:
        stop_watching.set()
