from __future__ import annotations

import subprocess
import threading
import time

WATCH_POLL_SECS = 0.35


def watch_clipboard(speak, console, pipe, voice: str, voice_path: str, device: str, speed: float) -> None:
    console.print(f"Watching clipboard with voice '{voice}' on {device}... (Ctrl+C to stop)")

    state = {"last_seen": None, "pending": None}
    state_lock = threading.Lock()
    cancel = threading.Event()
    stop_watching = threading.Event()

    def poll_clipboard() -> None:
        while not stop_watching.is_set():
            try:
                clip = subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
            except (subprocess.CalledProcessError, FileNotFoundError):
                clip = ""
            text = clip.strip()
            with state_lock:
                changed = bool(text) and text != state["last_seen"]
                if changed:
                    state["last_seen"] = text
                    state["pending"] = text
            if changed:
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
