from __future__ import annotations

from dataclasses import dataclass

from rich.console import Group
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

SENTENCE_END = (".", "!", "?")
MAX_WIDTH = 88
VISIBLE_LINES = 5


@dataclass
class Segment:
    """A sentence-sized run of tokens from one synthesized chunk, used for display."""

    chunk_id: int
    tokens: list


def split_into_segments(chunk_id, tokens) -> list[Segment]:
    """Group a chunk's tokens into sentence-sized segments for the 3-line display."""
    segments = []
    current = []
    for tok in tokens:
        current.append(tok)
        if tok.text.endswith(SENTENCE_END):
            segments.append(Segment(chunk_id, current))
            current = []
    if current:
        segments.append(Segment(chunk_id, current))
    return segments


def render_line(tokens, *, elapsed: float | None = None, dim: bool = False) -> Text:
    current = None
    if elapsed is not None:
        timed = [t for t in tokens if t.start_ts is not None and t.start_ts <= elapsed]
        if timed:
            current = max(timed, key=lambda t: t.start_ts)
    line = Text()
    for tok in tokens:
        if tok is current:
            style = "bold cyan underline"
        elif dim:
            style = "dim"
        else:
            style = "bold"
        line.append(tok.text, style=style)
        if tok.whitespace:
            line.append(tok.whitespace, style="dim" if dim else None)
    return line


def _render_text_frame(segments: list[Segment], chunk_id: int | None, elapsed: float) -> Text:
    if chunk_id is None:
        return Text("Synthesizing...", style="dim italic")
    in_chunk = [i for i, s in enumerate(segments) if s.chunk_id == chunk_id]
    if not in_chunk:
        return Text("Synthesizing...", style="dim italic")
    # Pick the furthest-along segment in this chunk whose first word has started.
    idx = in_chunk[0]
    for i in in_chunk:
        starts = [t.start_ts for t in segments[i].tokens if t.start_ts is not None]
        if starts and min(starts) <= elapsed:
            idx = i
    half = VISIBLE_LINES // 2
    offsets = range(-half, half + 1)
    frame = Text()
    for offset in offsets:
        i = idx + offset
        if 0 <= i < len(segments):
            frame.append(render_line(segments[i].tokens, elapsed=elapsed if offset == 0 else None, dim=offset != 0))
        if offset != offsets[-1]:
            frame.append("\n")
    return frame


def format_duration(seconds: float) -> str:
    m, s = divmod(max(0, int(seconds)), 60)
    return f"{m}:{s:02d}"


def render_progress(played_secs: float, estimated_total: float | None, *, paused: bool = False):
    """Bar + ETA, extrapolated from the speech rate (seconds/char) observed so far."""
    if not estimated_total:
        return Text(" Estimating...", style="dim")
    fraction = max(0.0, min(played_secs / estimated_total, 1.0))
    remaining = format_duration(estimated_total - played_secs)
    label = "⏸ Paused — Space to resume" if paused else f"{fraction * 100:4.0f}%  ETA {remaining}"
    row = Table.grid(padding=(0, 1))
    row.add_column()
    row.add_column()
    row.add_row(
        ProgressBar(total=1.0, completed=fraction, width=MAX_WIDTH - 24),
        Text(label, style="yellow bold" if paused else "dim"),
    )
    return row


HISTORY_NUM_WIDTH = 3
HISTORY_SNIPPET_WIDTH = 56
HISTORY_DURATION_WIDTH = 8


def _history_grid() -> Table:
    grid = Table.grid(padding=(0, 1))
    grid.add_column(width=HISTORY_NUM_WIDTH, justify="right")
    grid.add_column(width=HISTORY_SNIPPET_WIDTH, no_wrap=True, overflow="ellipsis")
    grid.add_column(width=HISTORY_DURATION_WIDTH, justify="right")
    return grid


def render_history_header() -> Table:
    grid = _history_grid()
    grid.add_row(Text("#", style="dim"), Text("Clip", style="dim"), Text("Duration", style="dim"))
    return grid


def render_history_row(index: int, snippet: str, duration: float) -> Table:
    grid = _history_grid()
    grid.add_row(
        Text(str(index), style="cyan bold"),
        Text(snippet, style="dim"),
        Text(f"{duration:.2f}s", style="dim"),
    )
    return grid


def render_display(
    segments: list[Segment],
    chunk_id: int | None,
    elapsed: float,
    played_secs: float,
    estimated_total: float | None,
    *,
    paused: bool = False,
    title: str | None = None,
) -> Panel:
    """Sentence window and progress bar as one bordered unit, not two disconnected blocks."""
    body = Group(
        _render_text_frame(segments, chunk_id, elapsed),
        Text(),
        render_progress(played_secs, estimated_total, paused=paused),
    )
    return Panel(body, title=title, title_align="left", border_style="cyan", width=MAX_WIDTH)
