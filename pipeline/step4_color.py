"""PASO 4 — Color: LUT 33pt generada por código (no descargada), grano sutil y viñeta
muy suave. Estética: luz cálida de tungsteno en altas luces, negros levantados
(nunca 0 puro), sombras con insinuación fría/malva, magentas/rojos/morados +15% de
saturación selectiva SIN virar los tonos de piel a naranja, contraste medio-suave.
"""

from __future__ import annotations

import colorsys
from pathlib import Path

from . import config, utils


def _in_hue_range(hue_deg: float, lo: float, hi: float) -> bool:
    if lo <= hi:
        return lo <= hue_deg <= hi
    return hue_deg >= lo or hue_deg <= hi  # rango que envuelve 360->0


def _smoothstep(x: float, edge0: float, edge1: float) -> float:
    if edge0 == edge1:
        return 0.0 if x < edge0 else 1.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)


def _soft_scurve(x: float, k: float = 0.12) -> float:
    return x + k * (x - 0.5) * (1 - abs(2 * x - 1))


def _grade_pixel(r: float, g: float, b: float) -> tuple[float, float, float]:
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    hue_deg = h * 360.0

    # +15% saturación selectiva en magenta/rojo/morado, nunca en tonos de piel.
    is_skin = _in_hue_range(hue_deg, *config.SKIN_HUE_RANGE)
    is_boosted = any(_in_hue_range(hue_deg, lo, hi) for lo, hi in config.BOOSTED_HUE_RANGES)
    if is_boosted and not is_skin:
        s = min(1.0, s * (1 + config.SELECTIVE_SATURATION_BOOST))

    r, g, b = colorsys.hsv_to_rgb(h, s, v)

    # Altas luces cálidas tipo tungsteno (ámbar: R/G arriba, B abajo).
    # Sombras con insinuación fría/malva (mezcla de rojo+azul, verde abajo).
    warm = _smoothstep(v, 0.5, 1.0)
    cool = _smoothstep(1.0 - v, 0.5, 1.0)
    r = r + warm * 0.07 + cool * 0.02
    g = g + warm * 0.03 - cool * 0.03
    b = b - warm * 0.09 + cool * 0.05

    # Negros levantados: el punto negro nunca cae a 0 puro.
    r = config.BLACK_LIFT + r * (1 - config.BLACK_LIFT)
    g = config.BLACK_LIFT + g * (1 - config.BLACK_LIFT)
    b = config.BLACK_LIFT + b * (1 - config.BLACK_LIFT)

    # Contraste medio-suave, curva en S ligera.
    r, g, b = _soft_scurve(r), _soft_scurve(g), _soft_scurve(b)
    r, g, b = min(1.0, max(0.0, r)), min(1.0, max(0.0, g)), min(1.0, max(0.0, b))

    if is_skin:
        # El shift cálido de altas luces no puede virar el tono de piel hacia
        # naranja: se conserva el matiz (hue) original, solo cambian brillo/contraste.
        _, s_out, v_out = colorsys.rgb_to_hsv(r, g, b)
        r, g, b = colorsys.hsv_to_rgb(h, s_out, v_out)

    return (r, g, b)


def generate_lut(size: int = config.LUT_SIZE) -> str:
    lines = [
        "TITLE \"grade\"",
        f"LUT_3D_SIZE {size}",
        "DOMAIN_MIN 0.0 0.0 0.0",
        "DOMAIN_MAX 1.0 1.0 1.0",
    ]
    step = 1.0 / (size - 1)
    for bi in range(size):
        b = bi * step
        for gi in range(size):
            g = gi * step
            for ri in range(size):
                r = ri * step
                rr, gg, bb = _grade_pixel(r, g, b)
                lines.append(f"{rr:.6f} {gg:.6f} {bb:.6f}")
    return "\n".join(lines) + "\n"


def _apply_grade(src: Path, dst: Path, lut_path: Path) -> None:
    utils.require_binary("ffmpeg")
    vf = (
        f"lut3d=file='{lut_path}',"
        f"noise=alls={config.NOISE_STRENGTH}:allf=t+u,"
        f"vignette=angle={config.VIGNETTE_ANGLE}"
    )
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy",
        str(dst),
    ]
    utils.run(cmd)


def _export_preview(src_clean: Path, src_graded: Path, timestamp: float, dst: Path) -> None:
    utils.require_binary("ffmpeg")
    before_png = config.WORK_DIR / "_grade_before.png"
    after_png = config.WORK_DIR / "_grade_after.png"
    utils.extract_frame_png(src_clean, timestamp, before_png)
    utils.extract_frame_png(src_graded, timestamp, after_png)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(before_png), "-i", str(after_png),
        "-filter_complex",
        "[0:v]drawtext=text='ANTES':fontcolor=white:fontsize=48:x=20:y=20:box=1:boxcolor=black@0.5[a];"
        "[1:v]drawtext=text='DESPUÉS':fontcolor=white:fontsize=48:x=20:y=20:box=1:boxcolor=black@0.5[b];"
        "[a][b]hstack=inputs=2[out]",
        "-map", "[out]", "-frames:v", "1",
        str(dst),
    ]
    utils.run(cmd)


def _pick_preview_timestamp(retention_map_path: Path, duration: float) -> float:
    if retention_map_path.exists():
        data = utils.load_json(retention_map_path)
        key_lines = [a for a in data.get("anchors", []) if a["kind"] == "KEY_LINES"]
        if key_lines:
            best = max(key_lines, key=lambda a: a["score"])
            return (best["start"] + best["end"]) / 2
    return duration / 2


def run(clean_video: Path, retention_map_path: Path | None = None) -> Path:
    config.LUTS_DIR.mkdir(parents=True, exist_ok=True)
    lut_text = generate_lut()
    config.GRADE_LUT_PATH.write_text(lut_text, encoding="utf-8")

    _apply_grade(clean_video, config.GRADED_VIDEO_PATH, config.GRADE_LUT_PATH)

    duration = utils.ffprobe_duration(clean_video)
    ts = _pick_preview_timestamp(retention_map_path or config.RETENTION_MAP_PATH, duration)
    _export_preview(clean_video, config.GRADED_VIDEO_PATH, ts, config.GRADE_PREVIEW_PATH)

    utils.step_done("PASO 4 — Color", config.GRADED_VIDEO_PATH, duration)
    utils.step_done("PASO 4 — Preview antes/después", config.GRADE_PREVIEW_PATH)
    utils.checkpoint("PASO 4")
    return config.GRADED_VIDEO_PATH
