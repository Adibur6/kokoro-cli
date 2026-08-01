# Kokoro TTS Chrome Extension — Plan

## Goal
Use the local Kokoro-82M TTS from a Chrome extension. Two entry points:

1. **Right-click "Speak selection"** on highlighted text (main requested feature).
2. **Popup** — type text, pick a voice, Speak / Stop.

## Architecture

```
Chrome Extension (MV3)
  ├─ context menu "Speak selection" → uses info.selectionText from click event
  ├─ context menu "Stop TTS"
  └─ popup (text + voice dropdown + Speak/Stop)
            │  fetch() → http://127.0.0.1:8765/*
            ▼
tts_server.py  (stdlib http.server, bind 127.0.0.1 only)
  ├─ GET  /voices  → JSON list of voices from Kokoro-82M/voices
  ├─ POST /tts     → {text, voice, lang} → Kokoro pipeline → stream to speakers
  ├─ POST /stop    → stop current playback (interrupt)
  └─ CORS headers  → Access-Control-Allow-Origin: * + OPTIONS preflight
```

## Files

### 1. `tts_server.py`
- stdlib only (`http.server`, `ThreadingHTTPServer`, no new deps).
- Loads `KModel` + `KPipeline` once at startup (MPS/CPU/CUDA auto-detect).
- Reuses the streaming playback design from `tts_live.py`:
  - `Speaker` class wrapping `sd.OutputStream` + an audio `queue.Queue`.
  - Producer thread iterates `pipe(text, voice=...)`, trims silence, enqueues int16 chunks.
- Interruption: `/tts` sets a `stop_event` on the current producer, swaps to a fresh queue; `/stop` clears the queue + signal.
- `voice` param accepts a name (`af_heart`) or full `.pt` path; validates existence → 400 if missing.
- Empty text → 400.

### 2. `extension/` — WXT + React + Tailwind + shadcn/ui
Modern UI stack chosen. WXT scaffolds the MV3 extension (manifest auto-generated from config), React powers the popup, Tailwind + shadcn/ui give the component look (cards, buttons, select, toast).

| File / dir | Purpose |
|---|---|
| `wxt.config.ts` | WXT config; `manifest` block → permissions `contextMenus`, `scripting`, `storage`, `activeTab`; host_permissions `http://127.0.0.1:8765/*` |
| `entrypoints/background.ts` | Registers context menus on install/startup; `onClicked` handler reads `info.selectionText`; does the `fetch` (so playback continues after popup closes); `onMessage` handler for popup Speak/Stop; default voice in `chrome.storage.local` |
| `entrypoints/popup/` | `index.html` + `main.tsx` + `App.tsx` — React popup (textarea, voice `Select`, `Button` Speak/Stop, `sonner` toast for errors) |
| `components/ui/*` | shadcn/ui components (button, select, card, textarea) |
| `components.json` | shadcn config (aliases, tailwind css) |
| `lib/utils.ts` | shadcn `cn()` helper |
| `assets/` | Tailwind CSS entry (`app.css` with design tokens) |

Setup commands (run in `extension/`):
```
pnpm dlx wxt@latest init
pnpm add tailwindcss @tailwindcss/vite  # or Tailwind v4 plugin
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button select card textarea
```
Dev: `pnpm dev` (HMR) → `pnpm build` → `pnpm zip` for `chrome://extensions` unpacked load. Load the `extension/.output/chrome-mv3` folder.

## Notes / decisions
- **Fetch from background, not popup**: popup can close mid-request; background keeps the fetch alive so playback continues.
- **No content script needed**: `chrome.contextMenus` provides `info.selectionText` in the click event for `selection` context.
- **CORS is required**: extension page → localhost is a cross-origin request; server sends `Access-Control-Allow-Origin: *` and answers OPTIONS preflight.
- **Voice list**: auto-scanned from `Kokoro-82M/voices/` (af_*, am_*, bf_*, etc.).
- **Port**: default `8765`, overridable with `--port`.
- **Streaming, not one-shot**: `/tts` does NOT wait for the whole utterance. The producer thread iterates `pipe(text, ...)`, which yields audio per sentence/phrase. Each chunk is trimmed + converted to int16 and pushed to the audio queue immediately, so playback starts on the *first* sentence while later sentences are still being synthesized in the background. `/tts` returns right after the producer thread starts (low time-to-first-audio); the HTTP response is just a "started" ack. Total time-to-finish is the same as one-shot, but perceived latency is much lower. `/stop` sets a `stop_event` on the current producer (breaks between chunks) and clears the queue → instant interruption mid-sentence.
- **UI stack**: WXT + React + Tailwind + shadcn/ui (full build pipeline chosen over dependency-free CSS). WXT generates the MV3 manifest; shadcn components are copied into the repo (no CDN, MV3-safe). Requires a build step (`pnpm dev` / `pnpm build`).

## Steps
1. Write `tts_server.py`.
2. Verify with curl:
   - `GET /voices`
   - `POST /tts` with short text → confirm audio plays
   - `POST /stop`
3. Scaffold `extension/` with WXT + React + Tailwind + shadcn/ui.
4. Implement background context menus + popup UI.
5. Test in Chrome:
   - `chrome://extensions` → Developer mode → Load unpacked → select `extension/.output/chrome-mv3`.
   - Right-click highlighted text → "Speak selection".
   - Popup → type text → Speak / Stop.
