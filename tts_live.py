import argparse
import os
import queue
import threading
import time

import numpy as np
import sounddevice as sd
import torch
from kokoro import KPipeline
from kokoro.model import KModel

os.environ["HF_HUB_OFFLINE"] = "1"

MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Kokoro-82M")
VOICES_DIR = os.path.join(MODEL_DIR, "voices")
SAMPLE_RATE = 24000
TRIM_SECS = 0.35
KEEP_TAIL_SECS = 0.03
SILENCE_THRESHOLD = 0.01


def trim_silence(audio: np.ndarray) -> np.ndarray:
    """Trim trailing (and all but the first chunk's leading) near-silence."""
    cutoff = int(TRIM_SECS * SAMPLE_RATE)
    i = len(audio) - 1
    end = max(i - cutoff, 0)
    while i > end and abs(audio[i]) < SILENCE_THRESHOLD:
        i -= 1
    tail = int(KEEP_TAIL_SECS * SAMPLE_RATE)
    return audio[: i + tail]


def main():
    parser = argparse.ArgumentParser(description="Seamless live streaming Kokoro-82M text-to-speech")
    parser.add_argument("text", nargs="?", help="Text to speak (or use --file)")
    parser.add_argument("--file", help="Read input text from a file")
    parser.add_argument("--voice", default="af_heart", help=f"Voice name in {VOICES_DIR}")
    parser.add_argument("--lang", default="a", help="Language code: a=American English, b=British English")
    parser.add_argument("--device", default=None, help="cuda, mps or cpu (default: auto)")
    parser.add_argument("--out", default=None, help="Also save full output to this .wav path")
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

    print(f"Streaming with voice '{args.voice}' on {args.device}...")

    audio_q = queue.Queue()
    chunks = []
    chunks_lock = threading.Lock()
    done = threading.Event()

    def producer():
        for _, _, audio in pipe(text, voice=voice_path):
            a = audio.cpu().numpy() if isinstance(audio, torch.Tensor) else audio
            a = trim_silence(a)
            with chunks_lock:
                chunks.append(a)
            audio_q.put((a * 32767).astype(np.int16))
        audio_q.put(None)
        done.set()

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    state = {"current": None}

    def callback(outdata, frames, time_info, status):
        cur = state["current"]
        if cur is None or len(cur) == 0:
            try:
                item = audio_q.get_nowait()
            except queue.Empty:
                outdata.fill(0)
                return
            if item is None:
                state["current"] = None
                outdata.fill(0)
                return
            state["current"] = item
            cur = item
        n = min(frames, len(cur))
        outdata[:n, 0] = cur[:n]
        if n < frames:
            outdata[n:, 0] = 0
        state["current"] = cur[n:] if n < len(cur) else None

    stream = sd.OutputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=4096, callback=callback
    )
    t0 = time.time()
    stream.start()
    thread.join()
    while not audio_q.empty() or (state["current"] is not None and len(state["current"]) > 0):
        time.sleep(0.05)
    stream.stop()
    elapsed = time.time() - t0

    with chunks_lock:
        total = sum(len(c) for c in chunks) / SAMPLE_RATE
    print(f"Done. {total:.2f}s of audio streamed in {elapsed:.2f}s.")

    if args.out:
        from scipy.io import wavfile
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        wav = np.concatenate(chunks)
        wavfile.write(args.out, SAMPLE_RATE, (wav * 32767).astype(np.int16))
        print(f"Saved {len(wav) / SAMPLE_RATE:.2f}s of audio to {args.out}")

if __name__ == "__main__":
    main()
