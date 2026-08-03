# `kokoro live --watch` UI improvement proposals

Proposed changes to make the three screens (idle, speaking, history) feel more
polished. #4, #6, #7, #8 are done; #1, #2, #3, #5 are still open.

1. [ ] **Header panel for startup** — wrap the "Watching clipboard..." line in a
   `Panel`/`rule` so voice/device/hotkeys read as a fixed header instead of a
   scrolling log line.
2. [ ] **Custom idle spinner** — style the `console.status` spinner
   (color/shape) instead of using Rich's default.
3. [ ] **Karaoke highlight color** — replace the `bold reverse` block-highlight
   on the active word with a distinct foreground color/underline so it reads
   as narration, not text selection.
4. [x] **Fold sentence number into panel title** — done. The `▶ #1 "..."` line
   is gone; `speak()` now takes a `title` param threaded through
   `render_display`/`render_frame` into `Panel(title=...)`.
5. [ ] **Unify percent/ETA with the progress bar** — merge the `54% ETA 0:05`
   text and the bar into one visual unit (e.g. bar subtitle) instead of two
   disconnected elements.
6. [x] **History as a table** — done. `render_history_header`/
   `render_history_row` in `live_display.py` render `#` / `Clip` / `Duration`
   as an aligned `Table.grid`, printed once the first clip finishes and once
   per clip after that, with a blank line between rows for spacing.
7. [x] **Trim redundant history text** — done, and went further than planned:
   the realtime-factor ratio was dropped entirely rather than condensed (it
   was often meaningless or misleading — e.g. showing an inflated ratio when
   a clip got interrupted mid-synthesis), so the table is just #/Clip/Duration.
8. [x] **One consistent accent color** — done. History rows and the panel now
   share a single accent (cyan for the index/border), everything else dim —
   no more cyan/green/yellow/pink mix.

## Priority

Highest impact first: #6 (history table) and #3/#4 (karaoke highlight + panel
title) are the cheapest, most visible wins. #1, #2, #5, #7, #8 are polish on
top of those.

## Relevant files

- `kokoro_cli/live_display.py` — panel/progress rendering for the speaking view
- `kokoro_cli/live_watch.py` — clipboard-watch loop, prints the history lines
- `kokoro_cli/live.py` — non-watch live speak loop, shares some of this display
