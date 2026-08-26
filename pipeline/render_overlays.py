"""Traslada los schedules de subtítulos/gráficos (PASOS 6-7, calculados sobre la
línea de tiempo pre-puente) a la línea de tiempo final tras el PASO 8, y renderiza
los dos overlays con Remotion (ProRes 4444, con canal alfa) para componerlos en
el PASO 12 sobre el vídeo base.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from . import config, timeline, utils


def _finalize_schedule(schedule_path: Path, shifts: list[tuple[float, float]], final_duration: float, out_path: Path) -> None:
    data = utils.load_json(schedule_path)
    shifted = timeline.shift_json_times(data, shifts)
    shifted["duration"] = final_duration
    utils.save_json(out_path, shifted)


def _npm_install_if_needed() -> None:
    node_modules = config.REMOTION_DIR / "node_modules"
    if node_modules.exists():
        return
    proc = subprocess.run(["npm", "install"], cwd=config.REMOTION_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"`npm install` falló en {config.REMOTION_DIR}.\n--- stderr ---\n{proc.stderr}"
        )


def _remotion_render(composition_id: str, props_path: Path, out_path: Path) -> None:
    cmd = [
        "npx", "remotion", "render", "src/index.ts", composition_id, str(out_path),
        f"--props={props_path}",
        "--codec=prores", "--prores-profile=4444",
    ]
    proc = subprocess.run(cmd, cwd=config.REMOTION_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Render de Remotion ({composition_id}) falló.\n"
            f"Comando: {' '.join(cmd)} (cwd={config.REMOTION_DIR})\n\n--- stderr ---\n{proc.stderr}"
        )


def run(assembled_video: Path, transitions_path: Path) -> tuple[Path, Path]:
    shifts = timeline.load_shifts(transitions_path) if transitions_path.exists() else []
    final_duration = utils.ffprobe_duration(assembled_video)

    _finalize_schedule(
        config.SUBTITLES_SCHEDULE_PATH, shifts, final_duration, config.SUBTITLES_SCHEDULE_FINAL_PATH
    )
    _finalize_schedule(
        config.GRAPHICS_SCHEDULE_PATH, shifts, final_duration, config.GRAPHICS_SCHEDULE_FINAL_PATH
    )

    _npm_install_if_needed()
    _remotion_render("Subtitles", config.SUBTITLES_SCHEDULE_FINAL_PATH, config.SUBTITLES_OVERLAY_PATH)
    _remotion_render("Graphics", config.GRAPHICS_SCHEDULE_FINAL_PATH, config.GRAPHICS_OVERLAY_PATH)

    utils.step_done("Render de overlays (subtítulos + gráficos)", config.SUBTITLES_OVERLAY_PATH)
    utils.step_done("Render de overlays (subtítulos + gráficos)", config.GRAPHICS_OVERLAY_PATH)
    return config.SUBTITLES_OVERLAY_PATH, config.GRAPHICS_OVERLAY_PATH
