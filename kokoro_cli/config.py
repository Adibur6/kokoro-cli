import os
import sys

APP_NAME = "kokoro"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"

PROJECT_MODEL_DIR = os.path.join(ROOT, "Kokoro-82M")
MANIFEST = os.path.join(ROOT, "Kokoro-82M.md5")

LANG_CODES = {
    "a": "American English",
    "b": "British English",
    "e": "Spanish",
    "f": "French",
    "h": "Hindi",
    "i": "Italian",
    "j": "Japanese",
    "p": "Brazilian Portuguese",
    "z": "Chinese",
}

os.environ.setdefault("HF_HUB_OFFLINE", "1")


def data_dir() -> str:
    """OS user-data dir for installed runs (override with KOKORO_DATA_DIR)."""
    override = os.environ.get("KOKORO_DATA_DIR")
    if override:
        return override
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    return os.path.join(base, APP_NAME)


DATA_DIR = data_dir()
DATA_MODEL_DIR = os.path.join(DATA_DIR, "Kokoro-82M")


def resolve_model_dir() -> str:
    """Prefer a checkout-side model dir; fall back to the managed data dir."""
    if os.path.isdir(PROJECT_MODEL_DIR):
        return PROJECT_MODEL_DIR
    return DATA_MODEL_DIR


def default_out_dir() -> str:
    """Write output next to the checkout when running from one, else cwd."""
    if os.path.isfile(os.path.join(ROOT, "pyproject.toml")):
        return os.path.join(ROOT, "output")
    return os.getcwd()


MODEL_DIR = resolve_model_dir()
VOICES_DIR = os.path.join(MODEL_DIR, "voices")
OUT_DIR = default_out_dir()
MODEL_CONFIG = os.path.join(MODEL_DIR, "config.json")
MODEL_WEIGHTS = os.path.join(MODEL_DIR, "kokoro-v1_0.pth")


def detect_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
