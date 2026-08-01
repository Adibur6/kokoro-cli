from __future__ import annotations

from dataclasses import dataclass

from rich.panel import Panel
from rich.text import Text

SENTENCE_END = (".", "!", "?")
MAX_WIDTH = 88


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
            style = "bold reverse"
        elif dim:
            style = "dim"
        else:
            style = "bold"
        line.append(tok.text, style=style)
        if tok.whitespace:
            line.append(tok.whitespace, style="dim" if dim else None)
    return line


def render_frame(segments: list[Segment], chunk_id: int | None, elapsed: float):
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
    frame = Text()
    for offset in (-1, 0, 1):
        i = idx + offset
        if 0 <= i < len(segments):
            frame.append(render_line(segments[i].tokens, elapsed=elapsed if offset == 0 else None, dim=offset != 0))
        if offset != 1:
            frame.append("\n")
    return Panel(frame, border_style="cyan", width=MAX_WIDTH)
