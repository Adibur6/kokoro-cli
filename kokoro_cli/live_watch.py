from __future__ import annotations

import select
import subprocess
import sys
import termios
import threading
import time
import tty

WATCH_POLL_SECS = 0.35
ESC = "\x1b"


def listen_for_escape(cancel: threading.Event, stop_watching: threading.Event) -> None:
    """Watch stdin for Esc and cancel the in-flight utterance. No-op outside a real terminal."""
    if not sys.stdin.isatty():
        return
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while not stop_watching.is_set():
            ready, _, _ = select.select([sys.stdin], [], [], 0.2)
            if ready and sys.stdin.read(1) == ESC:
                cancel.set()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def watch_clipboard(speak, console, pipe, voice: str, voice_path: str, device: str, speed: float) -> None:
    console.print(f"Watching clipboard with voice '{voice}' on {device}... (Ctrl+C to stop, Esc to skip)")

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
    escape_listener = threading.Thread(target=listen_for_escape, args=(cancel, stop_watching), daemon=True)
    escape_listener.start()

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
