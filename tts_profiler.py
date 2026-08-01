import argparse
import os
import time

import numpy as np
import torch
from kokoro import KPipeline
from kokoro.model import KModel

os.environ["HF_HUB_OFFLINE"] = "1"

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kokoro-82M")
VOICES_DIR = os.path.join(MODEL_DIR, "voices")
SAMPLE_RATE = 24000


def main():
    parser = argparse.ArgumentParser(
        description="Profile Kokoro-82M: time to first word, synthesis speed, and whether inference stays ahead of playback"
    )
    parser.add_argument("text", nargs="?", help="Text to synthesize (or use --file)")
    parser.add_argument("--file", help="Read input text from a file")
    parser.add_argument("--voice", default="af_heart", help=f"Voice name in {VOICES_DIR}")
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

    t0 = time.time()
    k_model = KModel(
        config=os.path.join(MODEL_DIR, "config.json"),
        model=os.path.join(MODEL_DIR, "kokoro-v1_0.pth"),
    ).to(args.device).eval()
    t_model = time.time() - t0

    pipe = KPipeline(lang_code=args.lang, model=k_model, device=args.device)
    t_ready = time.time() - t0
    voice_path = args.voice if args.voice.endswith(".pt") else os.path.join(VOICES_DIR, f"{args.voice}.pt")

    print(f"[{t_ready:6.2f}s] model loaded ({t_model:.2f}s) + pipeline ready, device={args.device}")

    rows = []
    for i, (gs, ps, audio) in enumerate(pipe(text, voice=voice_path)):
        a = audio.cpu().numpy() if isinstance(audio, torch.Tensor) else audio
        dur = len(a) / SAMPLE_RATE
        rows.append((i, time.time() - t0, dur))
        print(f"chunk {i}: synth_done@{rows[-1][1]:.2f}s  dur={dur:.2f}s", flush=True)

    if not rows:
        raise SystemExit("No audio produced.")

    total_dur = sum(r[2] for r in rows)
    t_first = rows[0][1]
    t_synth_end = rows[-1][1]

    print(f"\n=== SIMULATED PLAYBACK (starts when chunk 0 is ready) ===")
    play_pos = t_first
    stall = False
    for i, t_synth, dur in rows:
        print(
            f"chunk {i}: synth_done@{t_synth:6.2f}s  plays {play_pos:6.2f}->{play_pos + dur:6.2f}s  margin={play_pos - t_synth:+6.2f}s",
            flush=True,
        )
        if play_pos - t_synth < 0:
            stall = True
        play_pos += dur

    print(f"\nTIME TO FIRST WORD (cold start): {t_first:.2f}s  (model {t_model:.2f}s + G2P init {t_ready - t_model:.2f}s + first chunk {t_first - t_ready:.2f}s)")
    print(f"Total audio: {total_dur:.2f}s | all synthesis done @{t_synth_end:.2f}s")
    print(f"Inference finished {total_dur - t_synth_end:.2f}s BEFORE playback would end")
    rt = total_dur / t_synth_end if t_synth_end > 0 else 0
    print(f"Real-time factor: {rt:.2f}x realtime synthesis (excl. model load)")
    print("STALL RISK:", "YES (inference falls behind)" if stall else "NO (inference stays ahead of playback)")


if __name__ == "__main__":
    main()
