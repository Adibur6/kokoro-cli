import argparse
import os

import torch
from kokoro import KPipeline
from kokoro.model import KModel

os.environ["HF_HUB_OFFLINE"] = "1"

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kokoro-82M")
DEFAULT_VOICE = "af_heart"
VOICES_DIR = os.path.join(MODEL_DIR, "voices")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

def main():
    parser = argparse.ArgumentParser(description="Local Kokoro-82M text-to-speech")
    parser.add_argument("text", nargs="?", help="Text to speak (or use --file)")
    parser.add_argument("--file", help="Read input text from a file")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Voice name in {VOICES_DIR}")
    parser.add_argument("--out", default=os.path.join(OUT_DIR, "output.wav"), help="Output .wav path")
    parser.add_argument("--lang", default="a", help="Language code: a=American English, b=British English")
    parser.add_argument("--device", default=None, help="cuda, mps or cpu (default: auto)")
    args = parser.parse_args()

    if args.text and args.file:
        raise SystemExit("Provide either text or --file, not both.")
    text = args.text or (open(args.file, encoding="utf-8").read() if args.file else None)
    if not text:
        raise SystemExit("No text provided.")

    if args.device is None:
        if torch.cuda.is_available():
            args.device = "cuda"
        elif torch.backends.mps.is_available():
            args.device = "mps"
        else:
            args.device = "cpu"

    k_model = KModel(
        config=os.path.join(MODEL_DIR, "config.json"),
        model=os.path.join(MODEL_DIR, "kokoro-v1_0.pth"),
    ).to(args.device).eval()

    pipe = KPipeline(lang_code=args.lang, model=k_model, device=args.device)
    voice_path = args.voice if args.voice.endswith(".pt") else os.path.join(VOICES_DIR, f"{args.voice}.pt")

    print(f"Generating speech with voice '{args.voice}' on {args.device}...")
    chunks = []
    for i, (gs, ps, audio) in enumerate(pipe(text, voice=voice_path)):
        chunks.append(audio)

    from scipy.io import wavfile
    import numpy as np
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    wav = np.concatenate(chunks)
    wavfile.write(args.out, 24000, (wav * 32767).astype(np.int16))
    print(f"Saved {len(wav) / 24000:.2f}s of audio to {args.out}")

if __name__ == "__main__":
    main()
