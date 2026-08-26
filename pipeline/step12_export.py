"""PASO 12 — Export: compone base (color+punch-ins+puentes) + overlays de subtítulos y
gráficos (con alpha) + audio mezclado, y renderiza a las specs del bloque <input>.
"""

from __future__ import annotations

from pathlib import Path

from . import config, utils


def composite(
    assembled_video: Path,
    subtitles_overlay: Path | None,
    graphics_overlay: Path | None,
    mixed_audio: Path,
    dst: Path,
) -> Path:
    utils.require_binary("ffmpeg")

    inputs: list[str] = []
    next_idx = 0

    def add_input(path: Path) -> int:
        nonlocal next_idx
        inputs.extend(["-i", str(path)])
        idx = next_idx
        next_idx += 1
        return idx

    add_input(assembled_video)  # índice 0
    overlay_idx = []
    if subtitles_overlay and subtitles_overlay.exists():
        overlay_idx.append(add_input(subtitles_overlay))
    if graphics_overlay and graphics_overlay.exists():
        overlay_idx.append(add_input(graphics_overlay))
    audio_input_idx = add_input(mixed_audio)

    vf_base = (
        f"scale={config.OUTPUT_WIDTH}:{config.OUTPUT_HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={config.OUTPUT_WIDTH}:{config.OUTPUT_HEIGHT}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={config.OUTPUT_FPS},format=yuva420p"
    )
    filter_parts = [f"[0:v]{vf_base}[base]"]
    current = "base"
    for i, idx in enumerate(overlay_idx):
        out_label = f"comp{i}"
        filter_parts.append(f"[{current}][{idx}:v]overlay=shortest=1,format=yuv420p[{out_label}]")
        current = out_label
    filter_parts.append(f"[{current}]format=yuv420p[outv]")

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outv]", "-map", f"{audio_input_idx}:a",
        "-c:v", config.OUTPUT_VCODEC, "-preset", "slow", "-crf", "18",
        "-c:a", config.OUTPUT_ACODEC, "-b:a", config.OUTPUT_ABITRATE,
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-shortest",
        str(dst),
    ]
    utils.run(cmd)
    return dst


def run(
    assembled_video: Path,
    subtitles_overlay: Path,
    graphics_overlay: Path,
    mixed_audio: Path,
    output_name: str,
) -> Path:
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = config.OUTPUT_DIR / f"{output_name}_final.mp4"

    composite(assembled_video, subtitles_overlay, graphics_overlay, mixed_audio, dst)

    duration = utils.ffprobe_duration(dst)
    utils.step_done("PASO 12 — Export", dst, duration)
    return dst
