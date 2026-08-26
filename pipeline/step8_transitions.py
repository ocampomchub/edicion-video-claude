"""PASO 8 — Transiciones: en cada corte del PASO 2, el tipo se decide por lo que marca
el mapa de retención (corte seco por defecto, whip-pan en TOPIC_SHIFTS, fade al cerrar
un bloque informativo). Nunca transiciones decorativas. Si dos planos consecutivos son
casi idénticos, se inserta un puente de 1s en vez de dejar que el corte lea como error.
"""

from __future__ import annotations

from pathlib import Path

from . import config, utils
from .models import CutsResult

CLOSING_KINDS = {"KEY_LINES", "PUNCHLINES", "LISTS"}


def _cut_boundaries(cuts: CutsResult) -> list[float]:
    return [seg.new_end for seg in cuts.kept[:-1]]


def _assign_transition_type(boundary: float, anchors: list[dict]) -> str:
    for a in anchors:
        if a["kind"] == "TOPIC_SHIFTS" and (abs(a["start"] - boundary) <= 0.6 or abs(a["end"] - boundary) <= 0.6):
            return "whip_pan"
    for a in anchors:
        if a["kind"] in CLOSING_KINDS and abs(a["end"] - boundary) <= 0.3:
            return "fade"
    return "cut"


def _ssim_score(before_png: Path, after_png: Path) -> float | None:
    utils.require_binary("ffmpeg")
    cmd = ["ffmpeg", "-i", str(before_png), "-i", str(after_png), "-lavfi", "ssim", "-f", "null", "-"]
    proc = utils.run(cmd, check=False)
    for line in proc.stderr.splitlines():
        if "All:" in line:
            try:
                return float(line.split("All:")[1].split()[0])
            except (IndexError, ValueError):
                continue
    return None


def _needs_bridge(src: Path, boundary: float, duration: float) -> bool:
    before_png = config.WORK_DIR / "_shot_before.png"
    after_png = config.WORK_DIR / "_shot_after.png"
    t_before = max(0.0, boundary - 0.08)
    t_after = min(duration - 0.02, boundary + 0.08)
    try:
        utils.extract_frame_png(src, t_before, before_png)
        utils.extract_frame_png(src, t_after, after_png)
    except utils.FFmpegError:
        return False
    score = _ssim_score(before_png, after_png)
    return score is not None and score >= config.SHOT_SIMILARITY_THRESHOLD


def _insert_bridges(src: Path, bridge_points: list[float], dst: Path) -> None:
    """Congela el último frame antes de cada bridge_point durante BRIDGE_DURATION segundos
    (tpad/apad), dentro del mismo filter_complex de trim+concat que usan los demás pasos.
    """
    utils.require_binary("ffmpeg")
    duration = utils.ffprobe_duration(src)
    boundaries = sorted(set([0.0] + bridge_points + [duration]))

    filter_parts = []
    v_labels, a_labels = [], []
    for i, (s, e) in enumerate(zip(boundaries, boundaries[1:])):
        if e - s <= 0.001:
            continue
        is_bridge = any(abs(e - b) < 0.01 for b in bridge_points)
        vf = f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS"
        af = f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS"
        if is_bridge:
            vf += f",tpad=stop_mode=clone:stop_duration={config.BRIDGE_DURATION}"
            af += f",apad=pad_dur={config.BRIDGE_DURATION}"
        vf += f"[v{i}]"
        af += f"[a{i}]"
        filter_parts += [vf, af]
        v_labels.append(f"[v{i}]")
        a_labels.append(f"[a{i}]")

    n = len(v_labels)
    concat_inputs = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex", ";".join(filter_parts),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        str(dst),
    ]
    utils.run(cmd)


def run(moved_video: Path, cuts_path: Path, retention_map_path: Path) -> Path:
    cuts = CutsResult.from_json(utils.load_json(cuts_path))
    retention_map = utils.load_json(retention_map_path)
    anchors = retention_map["anchors"]

    boundaries = _cut_boundaries(cuts)
    duration = utils.ffprobe_duration(moved_video)

    cut_records = []
    bridge_points = []
    for b in boundaries:
        ttype = _assign_transition_type(b, anchors)
        needs_bridge = _needs_bridge(moved_video, b, duration)
        cut_records.append({"boundary": b, "type": ttype, "bridge": needs_bridge})
        if needs_bridge:
            bridge_points.append(b)

    if bridge_points:
        _insert_bridges(moved_video, bridge_points, config.ASSEMBLED_VIDEO_PATH)
    else:
        utils.run(["ffmpeg", "-y", "-i", str(moved_video), "-c", "copy", str(config.ASSEMBLED_VIDEO_PATH)])

    shifts = [{"point": p, "amount": config.BRIDGE_DURATION} for p in sorted(bridge_points)]
    utils.save_json(config.TRANSITIONS_PATH, {"cuts": cut_records, "shifts": shifts})

    total = len(cut_records) or 1
    counts = {"cut": 0, "whip_pan": 0, "fade": 0}
    for c in cut_records:
        counts[c["type"]] += 1
    rows = [[t, str(n), f"{100 * n / total:.0f}%"] for t, n in counts.items()]
    rows.append(["puentes insertados", str(len(bridge_points)), ""])
    utils.print_table(["Transición", "Nº", "%"], rows, title="PASO 8 — Transiciones")

    final_duration = utils.ffprobe_duration(config.ASSEMBLED_VIDEO_PATH)
    utils.step_done("PASO 8 — Transiciones", config.ASSEMBLED_VIDEO_PATH, final_duration)
    return config.ASSEMBLED_VIDEO_PATH
