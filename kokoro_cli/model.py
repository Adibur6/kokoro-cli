import os
import warnings

import torch
from kokoro import KPipeline
from kokoro.model import KModel

from kokoro_cli.config import MODEL_CONFIG, MODEL_DIR, MODEL_WEIGHTS

warnings.filterwarnings("ignore", message="dropout option adds dropout")
warnings.filterwarnings("ignore", message="`torch.nn.utils.weight_norm` is deprecated")

SETUP_HINT = (
    f"Model not found in {MODEL_DIR}. "
    "Run `./setup_kokoro.sh` from the project root to download it."
)


def check_model_available() -> None:
    if not os.path.isfile(MODEL_WEIGHTS) or not os.path.isfile(MODEL_CONFIG):
        raise SystemExit(SETUP_HINT)


def load_pipeline(lang: str, device: str) -> KPipeline:
    check_model_available()
    model = KModel(
        repo_id="hexgrad/Kokoro-82M",
        config=MODEL_CONFIG,
        model=MODEL_WEIGHTS,
    ).to(device).eval()
    return KPipeline(
        lang_code=lang, repo_id="hexgrad/Kokoro-82M", model=model, device=device
    )
