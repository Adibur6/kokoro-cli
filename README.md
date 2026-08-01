# kokoro-tts

Local text-to-speech using the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model, with a planned Chrome extension (WXT + React) to speak selected text.

## Setup

```bash
# 1. Python environment
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Download the model + voices (curl, md5-verified)
./setup_kokoro.sh
```

`setup_kokoro.sh` downloads only files that are missing or whose md5 doesn't match the expected hashes in `Kokoro-82M.md5`.

## Scripts

| Script | Purpose |
|---|---|
| `tts.py` | Generate speech to a `.wav` file |
| `tts_live.py` | Stream speech live to speakers, sentence by sentence |
| `tts_profiler.py` | Benchmark the pipeline |

### Usage

```bash
# Save speech to output/output.wav
.venv/bin/python tts.py "Hello, world." --voice af_heart

# Stream to speakers
.venv/bin/python tts_live.py "Hello, world."

# Read from a file
.venv/bin/python tts_live.py --file samples/migration.txt
```

Common options: `--voice` (any name from `Kokoro-82M/voices/`, default `af_heart`), `--lang` (`a` = American English, `b` = British English), `--device` (`cuda`, `mps`, or `cpu`; auto-detected).

## Chrome extension (planned)

See `extension_plan.md`: a WXT + React + Tailwind + shadcn/ui extension with a right-click "Speak selection" menu, backed by a local HTTP server (`server/`, not yet built).
