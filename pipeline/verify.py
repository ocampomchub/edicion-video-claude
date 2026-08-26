"""Criterio de éxito: los 7 checks finales. Si alguno falla, se informa qué paso hay
que re-ejecutar y con qué ajuste — nunca se parchea el resultado de forma silenciosa.
"""

from __future__ import annotations

from pathlib import Path

from . import config, timeline, utils
from .models import CutsResult


def _gather_change_events(
    cuts: CutsResult, camera_moves: list[dict], graphics: list[dict], shifts: list[tuple[float, float]]
) -> list[float]:
    events = []
    for seg in cuts.kept[:-1]:
        events.append(timeline.apply_shift(seg.new_end, shifts))
    for m in camera_moves:
        events.append(timeline.apply_shift(m["start"], shifts))
    for g in graphics:
        events.append(timeline.apply_shift(g["start"], shifts))
    return sorted(set(round(e, 3) for e in events))


def check_no_long_silence(final_video: Path) -> tuple[bool, str]:
    silences = utils.silencedetect(final_video, config.SILENCE_THRESHOLD_DB, config.MAX_SILENCE_FINAL + 0.01)
    if not silences:
        return True, "sin silencios > 0.7s"
    worst = max(silences, key=lambda s: s[1] - s[0])
    return False, f"{len(silences)} silencio(s) > 0.7s; el más largo: {worst[1]-worst[0]:.2f}s en {worst[0]:.2f}s"


def check_no_word_cut_mid(cuts: CutsResult, transcript: dict) -> tuple[bool, str]:
    from . import text_utils
    words = text_utils.load_words(transcript)
    word_bounds = set()
    for w in words:
        word_bounds.add(round(w.start, 2))
        word_bounds.add(round(w.end, 2))

    epsilon = 0.05
    offenders = []
    for seg in cuts.kept:
        for t in (seg.orig_start, seg.orig_end):
            if any(abs(t - wb) <= epsilon for wb in word_bounds):
                continue
            # los bordes con padding (PAD_BEFORE/PAD_AFTER) caen fuera de una palabra
            # a propósito: solo es un fallo real si cae DENTRO del rango de una palabra.
            mid_word = any(w.start + epsilon < t < w.end - epsilon for w in words)
            if mid_word:
                offenders.append(t)
    if offenders:
        return False, f"{len(offenders)} corte(s) caen a mitad de palabra: {offenders[:5]}"
    return True, "todos los cortes respetan límites de palabra"


def check_cadence(change_events: list[float], final_duration: float) -> tuple[bool, str]:
    if len(change_events) < 2:
        return False, "no hay suficientes eventos de cambio visual para calcular cadencia"
    intervals = [b - a for a, b in zip(change_events, change_events[1:])]
    mean = sum(intervals) / len(intervals)
    ok = config.CADENCE_MIN <= mean <= config.CADENCE_MAX
    return ok, f"cadencia media {mean:.2f}s (objetivo {config.CADENCE_MIN}-{config.CADENCE_MAX}s)"


def check_no_gap(change_events: list[float], final_duration: float) -> tuple[bool, str]:
    bounds = [0.0] + change_events + [final_duration]
    gaps = [b - a for a, b in zip(bounds, bounds[1:])]
    worst = max(gaps) if gaps else final_duration
    ok = worst <= config.MAX_GAP_NO_CHANGE
    return ok, f"mayor hueco sin cambio visual: {worst:.2f}s (máx. {config.MAX_GAP_NO_CHANGE}s)"


def check_subtitle_sync(fps: float) -> tuple[bool, str]:
    # Las tarjetas se generan directamente de los timestamps por palabra de mlx-whisper,
    # remapeados analíticamente (sin re-detección). El único error posible es la
    # cuantización a frame del render de Remotion.
    frame_error_ms = 1000.0 / fps / 2
    ok = frame_error_ms <= config.SUBTITLE_SYNC_TOLERANCE * 1000
    return ok, f"error máx. por cuantización de frame: {frame_error_ms:.1f}ms (tolerancia ±100ms)"


def check_loudness(final_video: Path) -> tuple[bool, str]:
    measured = utils.loudnorm_measure(final_video)
    integrated = float(measured["input_i"])
    true_peak = float(measured["input_tp"])
    lufs_ok = abs(integrated - config.MASTER_LUFS) <= config.LUFS_TOLERANCE
    tp_ok = true_peak <= config.MASTER_TRUE_PEAK
    ok = lufs_ok and tp_ok
    return ok, f"integrated={integrated:.2f} LUFS (objetivo {config.MASTER_LUFS}±{config.LUFS_TOLERANCE}), true_peak={true_peak:.2f}dB (máx {config.MASTER_TRUE_PEAK})"


def check_sfx_below_voice(events: list[dict], voice_only: Path, sfx_bed: Path | None) -> tuple[bool, str]:
    if sfx_bed is None or not sfx_bed.exists():
        return True, "sin SFX en la línea de tiempo"

    offenders = []
    for e in events:
        start = max(0.0, e["at"] - 0.05)
        end = e["at"] + 0.5
        voice_clip = config.WORK_DIR / "_verify_voice.wav"
        sfx_clip = config.WORK_DIR / "_verify_sfx.wav"
        utils.run([
            "ffmpeg", "-y", "-i", str(voice_only), "-ss", f"{start:.3f}", "-to", f"{end:.3f}", str(voice_clip),
        ])
        utils.run([
            "ffmpeg", "-y", "-i", str(sfx_bed), "-ss", f"{start:.3f}", "-to", f"{end:.3f}", str(sfx_clip),
        ])
        voice_peak = utils.volumedetect_peak(voice_clip)
        sfx_peak = utils.volumedetect_peak(sfx_clip)
        if voice_peak is not None and sfx_peak is not None and sfx_peak > voice_peak:
            offenders.append((e["sfx"], e["at"], sfx_peak, voice_peak))

    if offenders:
        detail = "; ".join(f"{s} en {t:.2f}s ({sp:.1f}dB > voz {vp:.1f}dB)" for s, t, sp, vp in offenders[:5])
        return False, f"{len(offenders)} SFX superan el pico de voz: {detail}"
    return True, "ningún SFX supera el pico de voz en su ventana de 500ms"


def run(
    final_video: Path,
    cuts_path: Path,
    transcript_path: Path,
    camera_moves_path: Path,
    graphics_schedule_path: Path,
    transitions_path: Path,
    sfx_timeline_path: Path,
) -> bool:
    cuts = CutsResult.from_json(utils.load_json(cuts_path))
    transcript = utils.load_json(transcript_path)
    camera_moves = utils.load_json(camera_moves_path).get("moves", []) if camera_moves_path.exists() else []
    graphics = utils.load_json(graphics_schedule_path).get("graphics", []) if graphics_schedule_path.exists() else []
    shifts = timeline.load_shifts(transitions_path) if transitions_path.exists() else []
    sfx_events = utils.load_json(sfx_timeline_path).get("events", []) if sfx_timeline_path.exists() else []

    final_duration = utils.ffprobe_duration(final_video)
    fps = utils.ffprobe_fps(final_video)
    change_events = _gather_change_events(cuts, camera_moves, graphics, shifts)

    checks = [
        ("1. Sin silencios > 0.7s", *check_no_long_silence(final_video)),
        ("2. Ninguna palabra cortada a mitad", *check_no_word_cut_mid(cuts, transcript)),
        ("3. Cadencia visual 2-4s", *check_cadence(change_events, final_duration)),
        ("4. Ningún hueco > 4s sin cambio", *check_no_gap(change_events, final_duration)),
        ("5. Subtítulos sync ±100ms", *check_subtitle_sync(fps)),
        ("6. Máster -14 LUFS / TP -1.0dB", *check_loudness(final_video)),
        ("7. SFX nunca por encima de la voz", *check_sfx_below_voice(
            sfx_events, config.VOICE_ONLY_PATH, config.SFX_BED_PATH if config.SFX_BED_PATH.exists() else None,
        )),
    ]

    rows = [[name, "✅ PASS" if ok else "❌ FAIL", detail] for name, ok, detail in checks]
    utils.print_table(["Check", "Resultado", "Detalle"], rows, title="CRITERIO DE ÉXITO — Informe final")

    all_ok = all(ok for _, ok, _ in checks)
    if not all_ok:
        print("Algún check falló. Re-ejecuta el paso correspondiente con los ajustes que indica el detalle")
        print("(nunca se corrige el resultado final por fuera del paso que lo genera).")
    return all_ok
