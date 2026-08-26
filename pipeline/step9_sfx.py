"""PASO 9 — Efectos de sonido: la librería de 6 SFX se sintetiza con dsp.py (numpy),
nunca se descarga. Colocación anclada al mapa de retención y al EDL de cortes/punch-ins.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import config, dsp, timeline, utils
from .models import CutsResult

FS = config.SFX_SAMPLE_RATE


# ---------------------------------------------------------------------------
# Síntesis de la librería (idempotente: si ya existen, no se regeneran)
# ---------------------------------------------------------------------------

def _synth_whoosh_short() -> tuple[np.ndarray, np.ndarray]:
    n = int(0.180 * FS)
    env = dsp.exp_decay_env(n, tau_fraction=0.30)
    left = dsp.svf_bandpass_sweep(dsp.pink_noise(n, seed=101), FS, 400, 6000, q=0.85, curve="exp")
    right = dsp.svf_bandpass_sweep(dsp.pink_noise(n, seed=202), FS, 400, 6000, q=0.85, curve="exp")
    left, right = dsp.declick(left * env, FS), dsp.declick(right * env, FS)
    return dsp.normalize(left), dsp.normalize(right)


def _synth_whoosh_long() -> tuple[np.ndarray, np.ndarray]:
    n = int(0.450 * FS)
    env = dsp.exp_decay_env(n, tau_fraction=0.45)
    left = dsp.svf_bandpass_sweep(dsp.pink_noise(n, seed=103), FS, 350, 5500, q=0.8, curve="linear")
    right = dsp.svf_bandpass_sweep(dsp.pink_noise(n, seed=204), FS, 350, 5500, q=0.8, curve="linear")
    left = dsp.short_comb_reverb(left * env, FS)
    right = dsp.short_comb_reverb(right * env, FS)
    left, right = dsp.declick(left, FS), dsp.declick(right, FS)
    return dsp.normalize(left), dsp.normalize(right)


def _synth_impact_soft() -> tuple[np.ndarray, np.ndarray]:
    n = int(0.300 * FS)
    t = np.arange(n) / FS
    freq = 60.0 - 20.0 * (t / t[-1])  # pitch-drop
    phase = 2 * np.pi * np.cumsum(freq) / FS
    tone = np.sin(phase)
    noise = dsp.lowpass(dsp.white_noise(n, seed=105), alpha=0.06)
    env = dsp.exp_decay_env(n, tau_fraction=0.14)
    mono = dsp.declick((tone * 0.8 + noise * 0.35) * env, FS)
    mono = dsp.normalize(mono)
    return mono, mono.copy()


def _synth_riser() -> tuple[np.ndarray, np.ndarray]:
    n = int(2.5 * FS)
    env = dsp.exp_rise_env(n, k=4.5)
    noise = dsp.svf_bandpass_sweep(dsp.pink_noise(n, seed=107), FS, 200, 8000, q=0.75, curve="exp")
    tone = dsp.sine_sweep(100.0, 1600.0, n, FS, curve="exp")
    mono = noise * 0.7 + tone * 0.4
    mono = mono * env
    mono = dsp.declick(mono, FS, ms=3.0)  # corta seco: solo un micro-fade anti-click
    mono = dsp.normalize(mono)
    return mono, mono.copy()


def _synth_pop() -> tuple[np.ndarray, np.ndarray]:
    n = int(0.090 * FS)
    tone = dsp.sine(800.0, n, FS)
    env = dsp.ar_env(n, FS, attack_s=0.002, decay_s=0.028)  # decae a ~-60dB en ~80ms
    mono = dsp.normalize(tone * env)
    return mono, mono.copy()


def _synth_ding() -> tuple[np.ndarray, np.ndarray]:
    n = int(0.600 * FS)
    tone = 0.6 * dsp.sine(880.0, n, FS) + 0.4 * dsp.sine(1320.0, n, FS)
    env = dsp.exp_decay_env(n, tau_fraction=0.55)
    mono = dsp.normalize(dsp.declick(tone * env, FS))
    return mono, mono.copy()


_SYNTH = {
    "whoosh_short.wav": _synth_whoosh_short,
    "whoosh_long.wav": _synth_whoosh_long,
    "impact_soft.wav": _synth_impact_soft,
    "riser.wav": _synth_riser,
    "pop.wav": _synth_pop,
    "ding.wav": _synth_ding,
}


def build_library(force: bool = False) -> dict[str, Path]:
    config.SFX_DIR.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, fn in _SYNTH.items():
        dst = config.SFX_DIR / name
        if force or not dst.exists():
            left, right = fn()
            dsp.write_wav_stereo(dst, left, right, FS)
        paths[name] = dst
    return paths


# ---------------------------------------------------------------------------
# Colocación en la línea de tiempo final
# ---------------------------------------------------------------------------

def _shifted(t: float, shifts: list[tuple[float, float]]) -> float:
    return timeline.apply_shift(t, shifts)


def _peak_anchor(anchors: list[dict]) -> dict | None:
    candidates = [a for a in anchors if a["kind"] in ("KEY_LINES", "PUNCHLINES")]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a["score"])


def build_sfx_timeline(
    cuts: CutsResult,
    retention_map: dict,
    camera_moves: list[dict],
    graphics_schedule: list[dict],
    shifts: list[tuple[float, float]],
    final_duration: float,
) -> list[dict]:
    events: list[dict] = []
    anchors = retention_map["anchors"]

    # HOOK: el sonido que decide si se quedan.
    events.append({"sfx": "impact_soft.wav", "at": 0.0, "volume_ratio": 1.0, "reason": "hook"})

    # Cada corte del PASO 2.
    for seg in cuts.kept[:-1]:
        t = _shifted(seg.new_end, shifts)
        events.append({
            "sfx": "whoosh_short.wav", "at": t,
            "volume_ratio": config.CUT_SFX_VOLUME_RATIO, "reason": "corte",
        })

    # Cada punch-in, sincronizado al frame exacto de inicio del zoom.
    for move in camera_moves:
        if move["type"] != "punch_in":
            continue
        t = _shifted(move["start"], shifts)
        events.append({
            "sfx": "whoosh_short.wav", "at": t,
            "volume_ratio": config.CUT_SFX_VOLUME_RATIO, "reason": "punch_in",
        })

    # Entrada de cada gráfico.
    for g in graphics_schedule:
        t = _shifted(g["start"], shifts)
        events.append({"sfx": "pop.wav", "at": t, "volume_ratio": 1.0, "reason": "grafico"})

    # Riser + impacto en el punto de mayor carga (máx. 2 impactos totales, contando el del hook).
    peak = _peak_anchor(anchors)
    impacts_used = 1  # el del hook
    if peak is not None and impacts_used < config.MAX_IMPACTS_TOTAL:
        peak_t = _shifted(peak["start"], shifts)
        if peak_t > config.HOOK_DURATION + 0.5:  # que no coincida con el impacto del hook
            riser_start = max(0.0, peak_t - 2.5)
            events.append({
                "sfx": "riser.wav", "at": riser_start,
                "volume_ratio": 1.0, "reason": "riser_previo_al_climax",
                "duration_hint": peak_t - riser_start,
            })
            events.append({"sfx": "impact_soft.wav", "at": peak_t, "volume_ratio": 1.0, "reason": "climax"})
            impacts_used += 1

    # CTA final.
    cta = next((a for a in anchors if a["kind"] == "CTA"), None)
    if cta is not None:
        events.append({
            "sfx": "ding.wav", "at": _shifted(cta["start"], shifts),
            "volume_ratio": 1.0, "reason": "cta",
        })

    events.sort(key=lambda e: e["at"])

    if final_duration < 30.0 and len(events) > config.MAX_SFX_SHORT_VIDEO:
        events = _trim_to_budget(events, config.MAX_SFX_SHORT_VIDEO)

    return events


def _trim_to_budget(events: list[dict], budget: int) -> list[dict]:
    mandatory_reasons = {"hook", "climax", "riser_previo_al_climax", "cta"}
    mandatory = [e for e in events if e["reason"] in mandatory_reasons]
    optional = [e for e in events if e["reason"] not in mandatory_reasons]

    remaining = max(0, budget - len(mandatory))
    if remaining <= 0 or not optional:
        kept_optional = []
    elif remaining >= len(optional):
        kept_optional = optional
    else:
        step = len(optional) / remaining
        kept_optional = [optional[int(i * step)] for i in range(remaining)]

    result = mandatory + kept_optional
    result.sort(key=lambda e: e["at"])
    return result


def run(
    cuts_path: Path,
    retention_map_path: Path,
    camera_moves_path: Path,
    graphics_schedule_path: Path,
    transitions_path: Path,
) -> Path:
    build_library()

    cuts = CutsResult.from_json(utils.load_json(cuts_path))
    retention_map = utils.load_json(retention_map_path)
    camera_moves = utils.load_json(camera_moves_path).get("moves", []) if camera_moves_path.exists() else []
    graphics_schedule = (
        utils.load_json(graphics_schedule_path).get("graphics", [])
        if graphics_schedule_path.exists() else []
    )
    shifts = timeline.load_shifts(transitions_path) if transitions_path.exists() else []
    final_duration = utils.ffprobe_duration(config.ASSEMBLED_VIDEO_PATH) if config.ASSEMBLED_VIDEO_PATH.exists() else cuts.final_duration

    events = build_sfx_timeline(cuts, retention_map, camera_moves, graphics_schedule, shifts, final_duration)
    utils.save_json(config.SFX_TIMELINE_PATH, {"events": events})

    rows = [[e["reason"], e["sfx"], f"{e['at']:.2f}s", f"{e['volume_ratio']*100:.0f}%"] for e in events]
    utils.print_table(["Motivo", "SFX", "Momento", "Vol. relativo a voz"], rows, title="PASO 9 — SFX")

    utils.step_done("PASO 9 — Efectos de sonido", config.SFX_TIMELINE_PATH)
    return config.SFX_TIMELINE_PATH
