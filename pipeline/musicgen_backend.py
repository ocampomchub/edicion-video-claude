"""Wrapper sobre musicgen-mlx (Apple Silicon). Nunca descarga música: todo se genera
localmente con el modelo ya instalado en la máquina del usuario.

La interfaz exacta de `musicgen-mlx` varía entre versiones/forks del proyecto, así que
este wrapper prueba, en orden: (1) la API Python si está instalada como paquete,
(2) el binario de CLI `musicgen-mlx` en PATH. Si ninguna funciona, falla con un
mensaje explícito en vez de fingir un resultado — regla crítica del pipeline.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import utils


class MusicGenUnavailable(RuntimeError):
    pass


def _try_python_api(prompt: str, duration: float, seed: int, out_path: Path) -> bool:
    try:
        import musicgen_mlx  # type: ignore
    except ImportError:
        return False

    # La API pública de musicgen-mlx ha expuesto distintos puntos de entrada según
    # la versión; probamos los más comunes y, si ninguno encaja, dejamos que el
    # usuario adapte esta función a la suya (ver README).
    if hasattr(musicgen_mlx, "generate"):
        audio, sr = musicgen_mlx.generate(prompt, duration=duration, seed=seed)
    elif hasattr(musicgen_mlx, "MusicGen"):
        model = musicgen_mlx.MusicGen.from_pretrained("facebook/musicgen-small")
        audio, sr = model.generate(prompt, duration=duration, seed=seed)
    else:
        return False

    import numpy as np
    from . import dsp

    audio = np.asarray(audio, dtype=np.float64)
    if audio.ndim == 1:
        left = right = audio
    else:
        left, right = audio[0], audio[-1]
    dsp.write_wav_stereo(out_path, dsp.normalize(left), dsp.normalize(right), int(sr))
    return True


def _try_cli(prompt: str, duration: float, seed: int, out_path: Path) -> bool:
    if shutil.which("musicgen-mlx") is None:
        return False
    cmd = [
        "musicgen-mlx", "generate",
        "--prompt", prompt,
        "--duration", str(duration),
        "--seed", str(seed),
        "--output", str(out_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise utils.FFmpegError(cmd, proc.returncode, proc.stderr)
    return out_path.exists()


def generate_segment(prompt: str, duration: float, seed: int, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if _try_python_api(prompt, duration, seed, out_path):
        return out_path
    if _try_cli(prompt, duration, seed, out_path):
        return out_path
    raise MusicGenUnavailable(
        "No se encontró musicgen-mlx (ni como paquete Python ni como CLI en PATH). "
        "Instálalo antes de continuar; este pipeline nunca descarga música de internet "
        "como alternativa. Si tu versión expone otra API, ajusta "
        "pipeline/musicgen_backend.py::_try_python_api."
    )
