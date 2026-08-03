from __future__ import annotations

import os
import select
import subprocess
import threading
import time
from collections import deque
from collections.abc import Iterator

from rich.live import Live

from kokoro_cli.live_display import HISTORY_MAX_ROWS, render_history_table, render_idle, render_watch_header

WATCH_POLL_SECS = 0.35
MAX_MONITOR_RESTARTS = 3
MONITOR_RESTART_DELAY_SECS = 0.5
CHANGE_COUNT_SCRIPT = 'ObjC.import("AppKit"); $.NSPasteboard.generalPasteboard.changeCount'
MONITOR_SCRIPT = """\
ObjC.import("AppKit");
var pb = $.NSPasteboard.generalPasteboard;
var last = pb.changeCount;
function emit(s) {
    var out = $.NSFileHandle.fileHandleWithStandardOutput;
    out.writeData($.NSString.alloc.initWithUTF8String(s).dataUsingEncoding($.NSUTF8StringEncoding));
}
while (true) {
    var cur = pb.changeCount;
    if (cur !== last) { last = cur; emit(cur + "\\n"); }
    $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.2));
}
"""
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


def _start_pasteboard_monitor() -> subprocess.Popen | None:
    """Long-lived osascript process that prints a line per clipboard change, so idle
    watch mode doesn't spawn a subprocess every poll."""
    try:
        return subprocess.Popen(
            ["osascript", "-l", "JavaScript", "-e", MONITOR_SCRIPT],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
    except OSError:
        return None


def _read_clipboard() -> str:
    try:
        return subprocess.run(["pbpaste"], capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _iter_monitor_changes(fd: int, stop_watching: threading.Event) -> Iterator[int]:
    """Yield each new pasteboard changeCount read from the monitor pipe.

    Returns (stops yielding) once the monitor's pipe hits EOF or errors, which
    the caller takes as its cue to fall back to polling.
    """
    while not stop_watching.is_set():
        try:
            ready, _, _ = select.select([fd], [], [], 0.5)
            if not ready:
                continue
            data = os.read(fd, 4096)
        except (OSError, ValueError):
            return
        if not data:
            return
        for line in data.decode(errors="replace").splitlines():
            try:
                yield int(line.strip())
            except ValueError:
                continue


def _iter_polled_changes(stop_watching: threading.Event) -> Iterator[int]:
    """Yield the pasteboard changeCount every WATCH_POLL_SECS, spawning osascript each time."""
    while not stop_watching.is_set():
        change_count = _pasteboard_change_count()
        if change_count is not None:
            yield change_count
        stop_watching.wait(WATCH_POLL_SECS)


def watch_clipboard(speak, console, pipe, voice: str, voice_path: str, device: str, speed: float) -> None:
    console.print(render_watch_header(voice, device))

    state = {"pending": None}
    state_lock = threading.Lock()
    cancel = threading.Event()
    stop_watching = threading.Event()
    monitor_state = {"proc": None}

    def handle_change(change_count: int) -> None:
        text = _read_clipboard().strip()
        if text:
            with state_lock:
                state["pending"] = text
            cancel.set()

    def changes() -> Iterator[int]:
        # Read from the monitor pipe. If it never starts or dies, respawn it up to
        # MAX_MONITOR_RESTARTS times before giving up and polling for the rest of
        # the session.
        restarts_left = MAX_MONITOR_RESTARTS
        while True:
            proc = _start_pasteboard_monitor()
            monitor_state["proc"] = proc
            if proc is not None:
                yield from _iter_monitor_changes(proc.stdout.fileno(), stop_watching)
                proc.poll()  # reap the dead monitor process
            if stop_watching.is_set() or restarts_left <= 0:
                break
            restarts_left -= 1
            stop_watching.wait(MONITOR_RESTART_DELAY_SECS)
        yield from _iter_polled_changes(stop_watching)

    def poll_clipboard() -> None:
        # Seed with the clipboard's current state so pre-existing content isn't
        # treated as a fresh copy the moment watching starts (or falls back).
        last_change_count = _pasteboard_change_count()
        for change_count in changes():
            if change_count != last_change_count:
                last_change_count = change_count
                handle_change(change_count)

    watcher = threading.Thread(target=poll_clipboard, daemon=True)
    watcher.start()

    spoken_count = 0
    history: deque = deque(maxlen=HISTORY_MAX_ROWS)
    idle_live: Live | None = None
    try:
        while True:
            with state_lock:
                cancel.clear()
                next_text, state["pending"] = state["pending"], None
            if next_text is None:
                if idle_live is None:
                    idle_live = Live(console=console, transient=True, refresh_per_second=12.5)
                    idle_live.start()
                    idle_live.update(render_idle(list(history), spoken_count))
                time.sleep(WATCH_POLL_SECS)
                continue
            if idle_live is not None:
                idle_live.stop()
                idle_live = None
            spoken_count += 1
            stats: dict = {}
            interrupted = speak(
                console, pipe, voice, voice_path, device, speed, next_text,
                cancel=cancel, announce=False, report_done=False, stats=stats, title=f"#{spoken_count}",
            )
            history.append((spoken_count, _snippet(next_text), stats.get("total", 0.0)))
            if interrupted:
                break
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted.[/yellow] Stopping watch mode...")
    finally:
        if idle_live is not None:
            idle_live.stop()
        if history:
            console.print(render_history_table(list(history)))
        stop_watching.set()
        proc = monitor_state["proc"]
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=1)
