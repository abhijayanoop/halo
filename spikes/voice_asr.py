"""Spike: local sherpa-onnx ASR latency and accuracy (NVIDIA Parakeet 110M).

Question: can a local sherpa-onnx ASR model transcribe speech fully offline,
with decode latency after speech ends under 1 second, AND get the words
right? (Follow-up to the first round: CTC decoding + no silence trimming
gave fast but inaccurate transcripts on live mic input.)

Models, downloaded from the k2-fsa/sherpa-onnx "asr-models" GitHub release
into spikes/models/ (gitignored, not committed):
  - parakeet-ctc-110m-en-int8/        sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000-int8
  - parakeet-transducer-110m-en-int8/ sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000-int8
  - silero_vad_v5.onnx                 for silence trimming before decoding

Usage:
    # Transcribe a wav file with the default (transducer + VAD):
    uv run --with sherpa-onnx --with soundfile --with numpy python spikes/voice_asr.py --wav <path.wav>

    # Record from the mic, trim silence, transcribe, and save the raw
    # recording so it can be re-used for other model/VAD combinations
    # without re-recording:
    uv run --with sherpa-onnx --with sounddevice --with soundfile --with numpy \
        python spikes/voice_asr.py --seconds 5 --save-wav spikes/my_voice.wav

    # Compare against the first round's CTC model, or without VAD trimming:
    uv run ... python spikes/voice_asr.py --wav spikes/my_voice.wav --model ctc
    uv run ... python spikes/voice_asr.py --wav spikes/my_voice.wav --no-vad

No secrets involved (the models are public), so no python-dotenv needed here.

Throwaway spike code. Never import this from halo/.
"""

import argparse
import sys
import time
from pathlib import Path

MODELS_DIR = Path(__file__).parent / "models"
MODEL_DIRS = {
    "ctc": MODELS_DIR / "parakeet-ctc-110m-en-int8",
    "transducer": MODELS_DIR / "parakeet-transducer-110m-en-int8",
}
VAD_MODEL_PATH = MODELS_DIR / "silero_vad_v5.onnx"
SAMPLE_RATE = 16000


def load_recognizer(model_dir: Path):
    import sherpa_onnx

    ctc_model = model_dir / "model.int8.onnx"
    if ctc_model.exists():
        return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(ctc_model),
            tokens=str(model_dir / "tokens.txt"),
            num_threads=2,
            decoding_method="greedy_search",
        )

    # Transducer export: separate encoder/decoder/joiner onnx files. Exact
    # filenames vary by export, so find them by role rather than hardcoding.
    (encoder,) = model_dir.glob("*encoder*.onnx")
    (decoder,) = model_dir.glob("*decoder*.onnx")
    (joiner,) = model_dir.glob("*joiner*.onnx")
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(encoder),
        decoder=str(decoder),
        joiner=str(joiner),
        tokens=str(model_dir / "tokens.txt"),
        num_threads=2,
        decoding_method="greedy_search",
    )


def read_wav(path: str) -> tuple:
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=False)
    if data.ndim > 1:
        data = data.mean(axis=1).astype(np.float32)
    return data, sr


def write_wav(path: str, samples, sample_rate: int) -> None:
    import soundfile as sf

    sf.write(path, samples, sample_rate)


def record_mic(seconds: float) -> tuple:
    import sounddevice as sd

    print(f"Recording {seconds:.1f}s from the default microphone... speak now.")
    audio = sd.rec(
        int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32"
    )
    sd.wait()
    print("Recording finished.")
    return audio.flatten(), SAMPLE_RATE


def trim_silence(samples, sample_rate: int):
    """Use Silero VAD to drop leading/trailing silence. Falls back to the
    original samples if VAD finds no speech at all (better to over-feed the
    recognizer than to silently return nothing).

    accept_waveform must be fed fixed-size windows (512 samples for Silero
    v5 at 16kHz) - a single call with the whole buffer silently
    under-processes it."""
    import numpy as np
    import sherpa_onnx

    window_size = 512
    config = sherpa_onnx.VadModelConfig(
        silero_vad=sherpa_onnx.SileroVadModelConfig(
            model=str(VAD_MODEL_PATH), window_size=window_size
        ),
        sample_rate=sample_rate,
    )
    vad = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=60)

    padded = np.pad(samples, (0, (-len(samples)) % window_size))
    for i in range(0, len(padded), window_size):
        vad.accept_waveform(padded[i : i + window_size])
    vad.flush()

    segments = []
    while not vad.empty():
        segments.append(vad.front.samples)
        vad.pop()

    if not segments:
        return samples
    return np.concatenate(segments)


def transcribe(recognizer, samples, sample_rate: int) -> tuple[str, float]:
    stream = recognizer.create_stream()
    stream.accept_waveform(sample_rate, samples)

    t0 = time.perf_counter()
    recognizer.decode_stream(stream)
    latency = time.perf_counter() - t0

    return stream.result.text, latency


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--wav",
        type=str,
        default=None,
        help="Transcribe this wav file instead of recording.",
    )
    parser.add_argument(
        "--seconds", type=float, default=5.0, help="Mic recording duration."
    )
    parser.add_argument(
        "--save-wav",
        type=str,
        default=None,
        help="Save the mic recording to this path.",
    )
    parser.add_argument(
        "--model",
        choices=["ctc", "transducer"],
        default="ctc",
        help="Which ASR model to use (transducer fails to load - see spikes/RESULTS.md).",
    )
    parser.add_argument(
        "--no-vad", action="store_true", help="Skip silence trimming before decoding."
    )
    args = parser.parse_args()

    model_dir = MODEL_DIRS[args.model]
    if not model_dir.exists():
        print(f"Model not found at {model_dir}.", file=sys.stderr)
        return 1
    if not args.no_vad and not VAD_MODEL_PATH.exists():
        print(f"VAD model not found at {VAD_MODEL_PATH}.", file=sys.stderr)
        return 1

    recognizer = load_recognizer(model_dir)

    if args.wav:
        samples, sr = read_wav(args.wav)
        source = f"wav file {args.wav}"
    else:
        samples, sr = record_mic(args.seconds)
        source = f"{args.seconds:.1f}s of live mic input"
        if args.save_wav:
            write_wav(args.save_wav, samples, sr)
            print(f"Saved raw recording to {args.save_wav}")

    if not args.no_vad:
        trimmed = trim_silence(samples, sr)
        trim_note = f" (trimmed {len(samples)} -> {len(trimmed)} samples via VAD)"
        samples = trimmed
    else:
        trim_note = " (no VAD trimming)"

    text, latency = transcribe(recognizer, samples, sr)

    print(f"Source: {source}")
    print(f"Model: {args.model}{trim_note}")
    print(f"Transcript: {text!r}")
    print(f"Decode latency after speech ended: {latency * 1000:.1f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
