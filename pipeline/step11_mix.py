"""PASO 11 — Mezcla de audio: voz limpia y a -14 LUFS, música a -26 LUFS con sidechain
duckeando contra la voz, SFX a -20 LUFS siempre por debajo, fades de música, máster a
-14 LUFS integrado / true peak -1.0dB.
"""

from __future__ import annotations

from pathlib import Path

from . import config, utils


def run(assembled_video: Path, music_path: Path, sfx_timeline_path: Path) -> Path:
    utils.require_binary("ffmpeg")

    events = utils.load_json(sfx_timeline_path)["events"]
    music_duration = utils.ffprobe_duration(music_path)
    fadeout_start = max(0.0, music_duration - config.MUSIC_FADE_OUT)

    inputs = ["-i", str(assembled_video), "-i", str(music_path)]
    for e in events:
        inputs += ["-i", str(config.SFX_DIR / e["sfx"])]

    filter_parts = [
        "[0:a]afftdn=nf=-25,highpass=f=80,"
        "acompressor=threshold=0.1:ratio=3:attack=20:release=250,"
        f"loudnorm=I={config.VOICE_LUFS}:TP={config.VOICE_TRUE_PEAK}:LRA=11[voice]",

        f"[1:a]loudnorm=I={config.MUSIC_LUFS}:TP=-2.0:LRA=11[music_norm]",
        "[music_norm][voice]sidechaincompress="
        "threshold=0.05:ratio=8:attack=20:release=400[music_duck]",
        f"[music_duck]afade=t=in:st=0:d={config.MUSIC_FADE_IN},"
        f"afade=t=out:st={fadeout_start:.3f}:d={config.MUSIC_FADE_OUT}[music_final]",
    ]

    sfx_labels = []
    for i, e in enumerate(events):
        delay_ms = max(0, round(e["at"] * 1000))
        gain = max(0.05, min(1.0, e.get("volume_ratio", 1.0)))
        label = f"sfx{i}"
        filter_parts.append(
            f"[{i + 2}:a]adelay={delay_ms}|{delay_ms},volume={gain}[{label}]"
        )
        sfx_labels.append(f"[{label}]")

    if sfx_labels:
        filter_parts.append(
            f"{''.join(sfx_labels)}amix=inputs={len(sfx_labels)}:duration=longest:"
            f"dropout_transition=0:normalize=0,"
            f"loudnorm=I={config.SFX_LUFS}:TP=-2.0:LRA=11[sfx_bed]"
        )
        master_inputs = "[voice][music_final][sfx_bed]"
        master_n = 3
    else:
        master_inputs = "[voice][music_final]"
        master_n = 2

    filter_parts.append(
        f"{master_inputs}amix=inputs={master_n}:duration=longest:dropout_transition=0:normalize=0,"
        f"loudnorm=I={config.MASTER_LUFS}:TP={config.MASTER_TRUE_PEAK}:LRA=11[master]"
    )

    # Además del máster, guardamos voz y cama de SFX por separado: el criterio de
    # éxito #7 (ningún SFX por encima del pico de voz en la misma ventana) necesita
    # poder comparar ambos aislados, no solo la mezcla ya sumada.
    outputs = [
        "-map", "[master]", "-ar", "48000", "-ac", "2", str(config.MIXED_AUDIO_PATH),
        "-map", "[voice]", "-ar", "48000", "-ac", "2", str(config.VOICE_ONLY_PATH),
    ]
    if sfx_labels:
        outputs += ["-map", "[sfx_bed]", "-ar", "48000", "-ac", "2", str(config.SFX_BED_PATH)]

    cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(filter_parts), *outputs]
    utils.run(cmd)

    utils.step_done("PASO 11 — Mezcla de audio", config.MIXED_AUDIO_PATH)
    return config.MIXED_AUDIO_PATH
