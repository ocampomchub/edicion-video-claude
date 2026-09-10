"""Wrapper sobre musicgen-mlx (Apple Silicon: https://github.com/andrade0/musicgen-mlx).
Nunca descarga música: todo se genera localmente con el modelo ya instalado.

Ese proyecto no se publica en PyPI — se instala con `git clone` + `make install`
(ver README, sección de instalación). Expone el paquete Python `audiocraft_mlx`
y, si `make install` registró el entry point, el CLI `musicgen-mlx`.
Probamos primero la API Python (más rápida, sin overhead de subprocess) y caemos
al CLI si el paquete no está instalado en este intérprete. Si ninguna funciona,
falla con un mensaje explícito — nunca fingimos un resultado.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import utils

DEFAULT_MODEL = "facebook/musicgen-small"


class MusicGenUnavailable(RuntimeError):
    pass


def _try_python_api(prompt: str, duration: float, seed: int, out_path: Path) -> bool:
    try:
        from audiocraft_mlx.models.musicgen import MusicGen  # type: ignore
    except ImportError:
        return False

    try:
        import mlx.core as mx  # type: ignore
        mx.random.seed(seed)
    except ImportError:
        pass

    import numpy as np
    from . import dsp

    model = MusicGen.get_pretrained(DEFAULT_MODEL)
    model.set_generation_params(duration=duration)
    audio = model.generate([prompt], progress=False)

    wav = np.asarray(audio[0], dtype=np.float64)  # shape [channels, samples]
    if wav.ndim == 1:
        left = right = wav
    else:
        left, right = wav[0], wav[-1]
    dsp.write_wav_stereo(out_path, dsp.normalize(left), dsp.normalize(right), int(model.sample_rate))
    return True


def _try_cli(prompt: str, duration: float, out_path: Path) -> bool:
    if shutil.which("musicgen-mlx") is None:
        return False
    cmd = [
        "musicgen-mlx", prompt,
        "-m", DEFAULT_MODEL,
        "-d", str(duration),
        "-o", str(out_path),
        "--no-open",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise utils.FFmpegError(cmd, proc.returncode, proc.stderr)
    return out_path.exists()


def generate_segment(prompt: str, duration: float, seed: int, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if _try_python_api(prompt, duration, seed, out_path):
        return out_path
    # El CLI de musicgen-mlx no expone semilla; distintas llamadas pueden sonar igual.
    if _try_cli(prompt, duration, out_path):
        return out_path
    raise MusicGenUnavailable(
        "No se encontró musicgen-mlx instalado en este entorno (ni el paquete Python "
        "`audiocraft_mlx` ni el CLI `musicgen-mlx` en PATH). Instálalo con:\n"
        "  git clone https://github.com/andrade0/musicgen-mlx.git ~/musicgen-mlx-src\n"
        "  cd ~/musicgen-mlx-src && make install\n"
        "(hazlo con el venv del pipeline activado, así el paquete queda disponible aquí). "
        "Este pipeline nunca descarga música de internet como alternativa."
    )
