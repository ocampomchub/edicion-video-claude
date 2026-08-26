"""PASO 10 — Música: prompt escrito a partir del tono de la transcripción, generada
con musicgen-mlx (nunca descargada). Genera 2 variantes y PARA para que el usuario elija.
"""

from __future__ import annotations

import math
from pathlib import Path

from . import config, musicgen_backend, utils

ENERGETIC_WORDS = {
    "increíble", "brutal", "impresionante", "rápido", "ahora", "ya", "urgente",
    "explota", "revienta", "locura", "flipante", "épico", "wow", "boom",
}
CALM_WORDS = {
    "tranquilo", "despacio", "suave", "calma", "relajado", "poco a poco",
    "con cuidado", "paciencia", "sereno",
}


def analyze_tone(transcript: dict) -> dict:
    text = transcript.get("text", "").lower()
    words = text.split()
    total = max(len(words), 1)
    energetic = sum(1 for w in words if w.strip(".,!?¡¿") in ENERGETIC_WORDS)
    calm = sum(1 for w in words if w.strip(".,!?¡¿") in CALM_WORDS)
    energy_score = (energetic - calm) / total
    return {"energy_score": energy_score, "energetic_hits": energetic, "calm_hits": calm}


def build_prompt(tone: dict, platform: str) -> str:
    energy = tone["energy_score"]
    if energy > 0.01:
        bpm = 108
        descriptors = "punchy lo-fi instrumental, tight muted drums, bright electric piano, subtle vinyl texture"
    elif energy < -0.01:
        bpm = 78
        descriptors = "warm lo-fi instrumental, soft Rhodes piano, brushed drums, vinyl texture"
    else:
        bpm = 90
        descriptors = "warm lo-fi instrumental, soft Rhodes piano, muted drums, vinyl texture"
    return f"{descriptors}, {bpm} BPM, no vocals"


def _crossfade_chain(segments: list[Path], out_path: Path, crossfade: float) -> None:
    utils.require_binary("ffmpeg")
    if len(segments) == 1:
        cmd = ["ffmpeg", "-y", "-i", str(segments[0]), "-c", "copy", str(out_path)]
        utils.run(cmd)
        return

    inputs = []
    for seg in segments:
        inputs += ["-i", str(seg)]

    filter_parts = []
    prev_label = "0:a"
    for i in range(1, len(segments)):
        out_label = f"xf{i}" if i < len(segments) - 1 else "outa"
        filter_parts.append(
            f"[{prev_label}][{i}:a]acrossfade=d={crossfade}:c1=tri:c2=tri[{out_label}]"
        )
        prev_label = out_label

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts), "-map", "[outa]", str(out_path)]
    utils.run(cmd)


def generate_variant(prompt: str, target_duration: float, seed_base: int, out_path: Path) -> Path:
    n_segments = max(1, math.ceil(target_duration / config.MUSICGEN_SEGMENT_SECONDS))
    tmp_dir = config.MUSIC_DIR / "_segments"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    segments = []
    for i in range(n_segments):
        seg_path = tmp_dir / f"{out_path.stem}_seg{i:02d}.wav"
        musicgen_backend.generate_segment(
            prompt, config.MUSICGEN_SEGMENT_SECONDS, seed=seed_base + i, out_path=seg_path,
        )
        segments.append(seg_path)

    if n_segments == 1:
        cmd = ["ffmpeg", "-y", "-i", str(segments[0]), "-t", f"{target_duration:.3f}", str(out_path)]
        utils.run(cmd)
    else:
        _crossfade_chain(segments, out_path, config.MUSICGEN_CROSSFADE)

    return out_path


def run(transcript_path: Path, target_duration: float, platform: str) -> tuple[Path, Path]:
    transcript = utils.load_json(transcript_path)
    tone = analyze_tone(transcript)
    prompt = build_prompt(tone, platform)
    utils.save_json(config.MUSIC_PROMPT_PATH, {"tone": tone, "prompt": prompt, "platform": platform})

    variant_a = generate_variant(prompt, target_duration, seed_base=1, out_path=config.MUSIC_DIR / "variant_a.wav")
    variant_b = generate_variant(prompt, target_duration, seed_base=97, out_path=config.MUSIC_DIR / "variant_b.wav")

    utils.print_table(
        ["Campo", "Valor"],
        [
            ["Energy score", f"{tone['energy_score']:.3f}"],
            ["Prompt", prompt],
            ["Variante A", str(variant_a)],
            ["Variante B", str(variant_b)],
        ],
        title="PASO 10 — Música",
    )
    utils.step_done("PASO 10 — Música (2 variantes)", config.MUSIC_DIR)
    utils.checkpoint("PASO 10 — elige variante A o B antes de mezclar")
    return variant_a, variant_b
