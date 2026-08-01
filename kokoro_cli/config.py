import os

APP_NAME = "kokoro"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(ROOT, "Kokoro-82M")
VOICES_DIR = os.path.join(MODEL_DIR, "voices")
OUT_DIR = os.path.join(ROOT, "output")
SAMPLE_RATE = 24000

MODEL_CONFIG = os.path.join(MODEL_DIR, "config.json")
MODEL_WEIGHTS = os.path.join(MODEL_DIR, "kokoro-v1_0.pth")
DEFAULT_VOICE = "af_heart"

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


def detect_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
