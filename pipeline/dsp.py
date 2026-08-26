"""Síntesis de audio en numpy puro (sin descargas, sin muestras de terceros).

Primitivas usadas por el PASO 9 (SFX) para construir los 6 sonidos exactamente
como los describe el spec: ruido rosa, barridos de band-pass con un filtro
state-variable (Chamberlin) de frecuencia de corte variable en el tiempo,
envolventes exponenciales/AR, y un reverb corto tipo comb para whoosh_long.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path

import numpy as np


def white_noise(n: int, seed: int | None = None) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.uniform(-1.0, 1.0, size=n).astype(np.float64)


def pink_noise(n: int, seed: int | None = None) -> np.ndarray:
    """Filtro de Paul Kellet: aproximación estándar de ruido rosa (~1/f) por IIR."""
    w = white_noise(n, seed)
    b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
    out = np.empty(n)
    for i in range(n):
        x = w[i]
        b0 = 0.99886 * b0 + x * 0.0555179
        b1 = 0.99332 * b1 + x * 0.0750759
        b2 = 0.96900 * b2 + x * 0.1538520
        b3 = 0.86650 * b3 + x * 0.3104856
        b4 = 0.55000 * b4 + x * 0.5329522
        b5 = -0.7616 * b5 - x * 0.0168980
        out[i] = b0 + b1 + b2 + b3 + b4 + b5 + b6 + x * 0.5362
        b6 = x * 0.115926
    return out / (np.max(np.abs(out)) + 1e-9)


def svf_bandpass_sweep(
    signal: np.ndarray, fs: int, f_start: float, f_end: float, q: float = 0.75, curve: str = "linear"
) -> np.ndarray:
    """Band-pass con frecuencia central variable en el tiempo (state-variable filter,
    topología Chamberlin). `curve` = 'linear' o 'exp' para la forma del barrido.
    """
    n = len(signal)
    t = np.linspace(0.0, 1.0, n)
    if curve == "exp":
        frac = (np.exp(3 * t) - 1) / (np.exp(3) - 1)
    else:
        frac = t
    fc = f_start + (f_end - f_start) * frac
    fc = np.clip(fc, 20.0, fs / 4.0)

    low = band = 0.0
    out = np.empty(n)
    for i in range(n):
        f = 2 * np.sin(np.pi * fc[i] / fs)
        high = signal[i] - low - q * band
        band = band + f * high
        low = low + f * band
        out[i] = band
    return out


def sine_sweep(f_start: float, f_end: float, n: int, fs: int, curve: str = "linear") -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)
    if curve == "exp":
        frac = (np.exp(3 * t) - 1) / (np.exp(3) - 1)
    else:
        frac = t
    inst_freq = f_start + (f_end - f_start) * frac
    phase = 2 * np.pi * np.cumsum(inst_freq) / fs
    return np.sin(phase)


def sine(freq: float, n: int, fs: int) -> np.ndarray:
    t = np.arange(n) / fs
    return np.sin(2 * np.pi * freq * t)


def exp_decay_env(n: int, tau_fraction: float = 0.25) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)
    tau = max(tau_fraction, 1e-3)
    return np.exp(-t / tau)


def exp_rise_env(n: int, k: float = 4.0) -> np.ndarray:
    t = np.linspace(0.0, 1.0, n)
    return (np.exp(k * t) - 1) / (np.exp(k) - 1)


def ar_env(n: int, fs: int, attack_s: float, decay_s: float) -> np.ndarray:
    attack_n = max(1, int(attack_s * fs))
    env = np.ones(n)
    attack_n = min(attack_n, n)
    env[:attack_n] = np.linspace(0.0, 1.0, attack_n)
    decay_start = attack_n
    tail = n - decay_start
    if tail > 0:
        tau = max(decay_s * fs, 1.0)
        env[decay_start:] = np.exp(-np.arange(tail) / tau)
    return env


def lowpass(signal: np.ndarray, alpha: float) -> np.ndarray:
    """Filtro paso-bajo de un polo, `alpha` en (0,1]; menor = más grave."""
    out = np.empty_like(signal)
    prev = 0.0
    for i, x in enumerate(signal):
        prev = prev + alpha * (x - prev)
        out[i] = prev
    return out


def short_comb_reverb(signal: np.ndarray, fs: int, delays_ms: tuple[float, ...] = (23, 41, 59), decay: float = 0.35) -> np.ndarray:
    out = signal.copy()
    for ms in delays_ms:
        d = int(fs * ms / 1000)
        if d >= len(signal):
            continue
        delayed = np.zeros_like(signal)
        delayed[d:] = signal[:-d] * decay
        out = out + delayed
    return out


def normalize(signal: np.ndarray, peak: float = 0.9) -> np.ndarray:
    m = np.max(np.abs(signal))
    if m < 1e-9:
        return signal
    return signal * (peak / m)


def declick(signal: np.ndarray, fs: int, ms: float = 3.0) -> np.ndarray:
    """Fade lineal de unos pocos ms al final, solo para evitar un click digital (no un fade audible)."""
    n = min(len(signal), int(fs * ms / 1000))
    if n <= 0:
        return signal
    out = signal.copy()
    out[-n:] *= np.linspace(1.0, 0.0, n)
    return out


def write_wav_stereo(path: Path, left: np.ndarray, right: np.ndarray, fs: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = min(len(left), len(right))
    left, right = left[:n], right[:n]
    interleaved = np.empty(2 * n, dtype=np.int16)
    interleaved[0::2] = np.clip(left * 32767, -32768, 32767).astype(np.int16)
    interleaved[1::2] = np.clip(right * 32767, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(fs)
        wf.writeframes(struct.pack(f"<{len(interleaved)}h", *interleaved))
