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
    "Run `kokoro install` to download it."
)
CORRUPT_HINT = (
    f"Model files in {MODEL_DIR} look corrupt or incomplete. "
    "Run `kokoro doctor` to verify, then `kokoro install` to repair."
)


def check_model_available() -> None:
    for path in (MODEL_WEIGHTS, MODEL_CONFIG):
        if not os.path.isfile(path):
            raise SystemExit(SETUP_HINT)
    # Empty file (interrupted copy, disk full); full md5 is `kokoro doctor`'s job.
    if os.path.getsize(MODEL_WEIGHTS) == 0 or os.path.getsize(MODEL_CONFIG) == 0:
        raise SystemExit(CORRUPT_HINT)


def load_pipeline(lang: str, device: str) -> KPipeline:
    check_model_available()
    # Guard only the file read, so device errors still surface as themselves.
    try:
        model = KModel(
            repo_id="hexgrad/Kokoro-82M",
            config=MODEL_CONFIG,
            model=MODEL_WEIGHTS,
        )
    except Exception as e:
        raise SystemExit(f"{CORRUPT_HINT}\n  (underlying error: {e})") from e
    model = model.to(device).eval()
    return KPipeline(
        lang_code=lang, repo_id="hexgrad/Kokoro-82M", model=model, device=device
    )
