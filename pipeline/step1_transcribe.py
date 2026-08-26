"""PASO 1 — Transcripción: WAV 16kHz mono + mlx-whisper large-v3 con timestamps por palabra."""

from __future__ import annotations

from pathlib import Path

from . import config, utils


def run(input_video: Path) -> Path:
    audio_path = config.WORK_DIR / "audio.wav"
    utils.extract_audio_wav(input_video, audio_path, sample_rate=16000)

    try:
        import mlx_whisper
    except ImportError as e:
        raise RuntimeError(
            "mlx-whisper no está instalado. Este paso requiere Apple Silicon + "
            "`pip install mlx-whisper` (ver README)."
        ) from e

    result = mlx_whisper.transcribe(
        str(audio_path),
        path_or_hf_repo="mlx-community/whisper-large-v3-mlx",
        word_timestamps=True,
    )

    segments = []
    for seg in result.get("segments", []):
        words = [
            {"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
            for w in seg.get("words", [])
        ]
        segments.append({
            "text": seg["text"].strip(),
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "words": words,
        })

    transcript = {
        "language": result.get("language", "es"),
        "text": result.get("text", "").strip(),
        "segments": segments,
    }
    utils.save_json(config.TRANSCRIPT_PATH, transcript)

    duration = utils.ffprobe_duration(input_video)
    utils.step_done("PASO 1 — Transcripción", config.TRANSCRIPT_PATH, duration)
    return config.TRANSCRIPT_PATH
