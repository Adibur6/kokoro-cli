# kokoro-tts

Local text-to-speech using the [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) model, wrapped in a single `kokoro` CLI.

## User Setup

```bash
# 1. Python environment
python3 -m venv .venv

# 2. Install the CLI
.venv/bin/pip install .

# 3. Download the model + voices (md5-verified)
kokoro install
```

`kokoro install` downloads only files that are missing or whose md5 doesn't match the expected hashes in `Kokoro-82M.md5`, and retries transient failures. The model is stored in the OS user-data dir (`~/Library/Application Support/kokoro-tts` on macOS, `~/.local/share/kokoro-tts` on Linux).

Run `kokoro doctor` to see where the model lives and whether it's complete. `kokoro uninstall` removes the downloaded model data.

## Development Setup

```bash
# 1. Python environment
python3 -m venv .venv

# 2. Install the CLI in editable mode
.venv/bin/pip install -e .

# 3. Download the model + voices directly into the checkout (Kokoro-82M/)
#    instead of the OS user-data dir, by pointing KOKORO_DATA_DIR at the repo root
KOKORO_DATA_DIR="$(pwd)" kokoro install
```

`resolve_model_dir()` (`kokoro_cli/config.py`) prefers a checkout-side `Kokoro-82M/` whenever it already has `kokoro-v1_0.pth` + `config.json`. Once the model lands there, every later command (including without the `KOKORO_DATA_DIR` override) uses it automatically — handy for keeping the model alongside the code you're editing. If you already have a `Kokoro-82M/` folder from elsewhere, just drop it at the repo root and run `kokoro install` to backfill any missing/mismatched files against the manifest.

## Commands

| Command | Purpose |
|---|---|
| `kokoro tts "text"` | Generate speech to a file (wav/mp3/flac/ogg) |
| `kokoro live "text"` | Stream speech live to speakers, sentence by sentence |
| `kokoro profile "text"` | Benchmark the pipeline |
| `kokoro voices` | List available voices |
| `kokoro install` | Download the model + voices (md5-verified, resumable) |
| `kokoro uninstall` | Remove downloaded model data |
| `kokoro doctor` | Show model location and completeness |

Run `kokoro --help` for options on any command.

### Examples

```bash
# Save speech to output/output.wav
kokoro tts "Hello, world." --voice af_heart

# Stream to speakers
kokoro live "Hello, world."

# Read from a file, write mp3
kokoro tts --file samples/migration.txt --out output/migration.mp3

# Read from stdin
echo "Hello from stdin" | kokoro tts -

# List voices
kokoro voices
```

Common options: `--voice` (any name from `Kokoro-82M/voices/`, default `af_heart`), `--lang` (`a` = American English, `b` = British English, plus `e`/`f`/`h`/`i`/`j`/`p`/`z` for Spanish/French/Hindi/Italian/Japanese/Portuguese/Chinese), `--device` (`cuda`, `mps`, or `cpu`; auto-detected).
