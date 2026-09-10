"""Wrappers de shell (ffmpeg/ffprobe) y utilidades de reporte compartidas por todos los pasos."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


class FFmpegError(RuntimeError):
    def __init__(self, cmd: list[str], returncode: int, stderr: str):
        self.cmd = cmd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(
            f"ffmpeg falló ({returncode}).\nComando: {' '.join(cmd)}\n\n--- stderr ---\n{stderr}"
        )


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"No se encontró '{name}' en PATH. Instálalo antes de continuar "
            f"(este pipeline nunca improvisa un filtro alternativo sin avisar)."
        )


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Ejecuta un comando y, si falla, muestra el comando exacto y el error (regla crítica del pipeline)."""
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise FFmpegError(cmd, proc.returncode, proc.stderr)
    return proc


def ffprobe_duration(path: Path) -> float:
    require_binary("ffprobe")
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    proc = run(cmd)
    return float(proc.stdout.strip())


def ffprobe_fps(path: Path) -> float:
    require_binary("ffprobe")
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    proc = run(cmd)
    num, den = proc.stdout.strip().split("/")
    return float(num) / float(den)


def ffprobe_dimensions(path: Path) -> tuple[int, int]:
    require_binary("ffprobe")
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
        str(path),
    ]
    proc = run(cmd)
    w, h = proc.stdout.strip().split("x")
    return int(w), int(h)


def extract_audio_wav(src: Path, dst: Path, sample_rate: int = 16000) -> None:
    require_binary("ffmpeg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", str(sample_rate), "-vn",
        str(dst),
    ]
    run(cmd)


def extract_frame_png(src: Path, timestamp: float, dst: Path) -> None:
    require_binary("ffmpeg")
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{timestamp:.3f}", "-i", str(src),
        "-frames:v", "1", str(dst),
    ]
    run(cmd)


def silencedetect(src: Path, noise_db: float, min_dur: float) -> list[tuple[float, float]]:
    """Devuelve lista de (start, end) de silencios usando el filtro silencedetect de ffmpeg."""
    require_binary("ffmpeg")
    cmd = [
        "ffmpeg", "-i", str(src),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ]
    proc = run(cmd, check=False)  # ffmpeg -f null devuelve 0 normalmente; el log va a stderr
    silences: list[tuple[float, float]] = []
    start = None
    for line in proc.stderr.splitlines():
        line = line.strip()
        if "silence_start:" in line:
            start = float(line.split("silence_start:")[1].strip())
        elif "silence_end:" in line and start is not None:
            end_part = line.split("silence_end:")[1].strip()
            end = float(end_part.split("|")[0].strip())
            silences.append((start, end))
            start = None
    return silences


def loudnorm_measure(src: Path) -> dict:
    """Primera pasada de loudnorm en modo medición (print_format json)."""
    require_binary("ffmpeg")
    cmd = [
        "ffmpeg", "-i", str(src),
        "-af", "loudnorm=I=-14:TP=-1.0:LRA=11:print_format=json",
        "-f", "null", "-",
    ]
    proc = run(cmd, check=False)
    text = proc.stderr
    start = text.rfind("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise RuntimeError(f"No se pudo parsear la salida de loudnorm:\n{text}")
    return json.loads(text[start:end + 1])


def volumedetect_peak(src: Path) -> float | None:
    """Pico máximo (dBFS) de un stream de audio usando el filtro volumedetect."""
    require_binary("ffmpeg")
    cmd = ["ffmpeg", "-i", str(src), "-af", "volumedetect", "-f", "null", "-"]
    proc = run(cmd, check=False)
    for line in proc.stderr.splitlines():
        if "max_volume:" in line:
            return float(line.split("max_volume:")[1].replace("dB", "").strip())
    return None


# ---------------------------------------------------------------------------
# Reporte en tabla (sin dependencias externas)
# ---------------------------------------------------------------------------

def print_table(headers: list[str], rows: list[list[str]], title: str | None = None) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    def fmt_row(cells: list[str]) -> str:
        return " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells))

    if title:
        print(f"\n=== {title} ===")
    sep = "-+-".join("-" * w for w in widths)
    print(fmt_row(headers))
    print(sep)
    for row in rows:
        print(fmt_row(row))
    print()


def checkpoint(step_name: str) -> None:
    print(f"\n>>> CHECKPOINT: {step_name} completado. Esperando tu aprobación para continuar.\n")
    sys.stdout.flush()


def step_done(step_name: str, artifact: Path | None, duration: float | None = None) -> None:
    msg = f"✅ {step_name}"
    if artifact is not None:
        msg += f" -> {artifact}"
    if duration is not None:
        msg += f" (duración actual del clip: {duration:.2f}s)"
    print(msg)


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
