"""Orquestador del pipeline. Ejecuta los pasos en orden y PARA en los checkpoints
obligatorios (fin de PASO 2, PASO 3, PASO 4, PASO 10, y antes del render final del
PASO 12) esperando aprobación explícita antes de continuar.

Uso típico:
    python -m pipeline.cli init --input /ruta/video.mp4 --platform Reels
    python -m pipeline.cli run            # corre hasta el próximo checkpoint
    ... revisas la tabla / el preview ...
    python -m pipeline.cli run            # continúa tras tu aprobación
    ... en el checkpoint de música ...
    python -m pipeline.cli choose-music a
    python -m pipeline.cli run
    python -m pipeline.cli run            # confirmación final -> renderiza
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import (
    config, render_overlays, step1_transcribe, step2_cuts, step3_retention_map,
    step4_color, step5_punchins, step6_subtitles, step7_graphics, step8_transitions,
    step9_sfx, step10_music, step11_mix, step12_export, utils, verify,
)

STATE_PATH = config.WORK_DIR / "pipeline_state.json"

STEP_ORDER = [
    "transcribe", "cuts", "map", "color", "punchins", "subtitles", "graphics",
    "transitions", "sfx", "music", "mix", "render_overlays", "export", "verify",
]
CHECKPOINT_AFTER = {"cuts", "map", "color", "music"}
CHECKPOINT_BEFORE = {"export"}


def _load_state() -> dict:
    if STATE_PATH.exists():
        return utils.load_json(STATE_PATH)
    return {}


def _save_state(state: dict) -> None:
    utils.save_json(STATE_PATH, state)


def cmd_init(args: argparse.Namespace) -> None:
    input_video = Path(args.input).resolve()
    if not input_video.exists():
        raise SystemExit(f"No existe el vídeo de entrada: {input_video}")

    config.WORK_DIR.mkdir(parents=True, exist_ok=True)
    state = {
        "input_video": str(input_video),
        "platform": args.platform,
        "output_name": args.output_name or input_video.stem,
        "last_completed": None,
        "chosen_music_variant": None,
    }
    _save_state(state)
    print(f"Inicializado. Vídeo: {input_video}  Plataforma: {args.platform}")
    print("Ejecuta `python -m pipeline.cli run` para empezar.")


def cmd_status(args: argparse.Namespace) -> None:
    state = _load_state()
    if not state:
        print("Sin estado. Ejecuta `init` primero.")
        return
    for k, v in state.items():
        print(f"{k}: {v}")


def _run_step(name: str, state: dict) -> None:
    input_video = Path(state["input_video"])
    platform = state["platform"]

    if name == "transcribe":
        step1_transcribe.run(input_video)

    elif name == "cuts":
        step2_cuts.run(input_video, config.TRANSCRIPT_PATH)

    elif name == "map":
        step3_retention_map.run(config.TRANSCRIPT_PATH, config.CUTS_PATH)

    elif name == "color":
        step4_color.run(config.CLEAN_VIDEO_PATH, config.RETENTION_MAP_PATH)

    elif name == "punchins":
        step5_punchins.run(config.GRADED_VIDEO_PATH, config.RETENTION_MAP_PATH)

    elif name == "subtitles":
        step6_subtitles.run(config.TRANSCRIPT_PATH, config.CUTS_PATH, config.RETENTION_MAP_PATH)

    elif name == "graphics":
        step7_graphics.run(config.RETENTION_MAP_PATH, config.CUTS_PATH)

    elif name == "transitions":
        step8_transitions.run(config.MOVED_VIDEO_PATH, config.CUTS_PATH, config.RETENTION_MAP_PATH)

    elif name == "sfx":
        step9_sfx.run(
            config.CUTS_PATH, config.RETENTION_MAP_PATH, config.CAMERA_MOVES_PATH,
            config.GRAPHICS_SCHEDULE_PATH, config.TRANSITIONS_PATH,
        )

    elif name == "music":
        target_duration = utils.ffprobe_duration(config.ASSEMBLED_VIDEO_PATH)
        step10_music.run(config.TRANSCRIPT_PATH, target_duration, platform)

    elif name == "mix":
        variant = state.get("chosen_music_variant")
        if variant not in ("a", "b"):
            raise SystemExit(
                "Falta elegir variante de música. Ejecuta `choose-music a` o `choose-music b`."
            )
        music_path = config.MUSIC_DIR / f"variant_{variant}.wav"
        step11_mix.run(config.ASSEMBLED_VIDEO_PATH, music_path, config.SFX_TIMELINE_PATH)

    elif name == "render_overlays":
        render_overlays.run(config.ASSEMBLED_VIDEO_PATH, config.TRANSITIONS_PATH)

    elif name == "export":
        output_name = state["output_name"]
        final_video = step12_export.run(
            config.ASSEMBLED_VIDEO_PATH, config.SUBTITLES_OVERLAY_PATH,
            config.GRAPHICS_OVERLAY_PATH, config.MIXED_AUDIO_PATH, output_name,
        )
        state["final_video"] = str(final_video)

    elif name == "verify":
        final_video = Path(state["final_video"])
        ok = verify.run(
            final_video, config.CUTS_PATH, config.TRANSCRIPT_PATH, config.CAMERA_MOVES_PATH,
            config.GRAPHICS_SCHEDULE_PATH, config.TRANSITIONS_PATH, config.SFX_TIMELINE_PATH,
        )
        state["verify_passed"] = ok

    else:
        raise ValueError(f"Paso desconocido: {name}")


def cmd_run(args: argparse.Namespace) -> None:
    state = _load_state()
    if not state:
        raise SystemExit("Sin estado. Ejecuta `init --input ... --platform ...` primero.")

    last = state.get("last_completed")
    start_idx = STEP_ORDER.index(last) + 1 if last else 0

    for name in STEP_ORDER[start_idx:]:
        if name in CHECKPOINT_BEFORE and not args.force:
            print(f"\n>>> Checkpoint antes de '{name}'. Revisa lo anterior y ejecuta "
                  f"`run --force` para confirmar y lanzar el render final.\n")
            return

        _run_step(name, state)
        state["last_completed"] = name
        _save_state(state)

        if name in CHECKPOINT_AFTER and not args.force:
            print(f"\n>>> Checkpoint tras '{name}'. Revisa la tabla/preview de arriba y "
                  f"vuelve a ejecutar `run` cuando lo apruebes.\n")
            return

        if args.until and name == args.until:
            return

    print("\nPipeline completo.")


def cmd_choose_music(args: argparse.Namespace) -> None:
    state = _load_state()
    if not state:
        raise SystemExit("Sin estado. Ejecuta `init` primero.")
    state["chosen_music_variant"] = args.variant
    _save_state(state)
    print(f"Variante de música elegida: {args.variant}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pipeline.cli")
    sub = p.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Inicializa el proyecto con el vídeo de entrada")
    p_init.add_argument("--input", required=True, help="Ruta al vídeo en crudo (nunca se modifica)")
    p_init.add_argument("--platform", required=True, choices=["Reels", "TikTok", "Shorts"])
    p_init.add_argument("--output-name", default=None)
    p_init.set_defaults(func=cmd_init)

    p_run = sub.add_parser("run", help="Corre el pipeline hasta el próximo checkpoint")
    p_run.add_argument("--force", action="store_true", help="Salta el checkpoint pendiente (úsalo solo tras aprobar)")
    p_run.add_argument("--until", default=None, choices=STEP_ORDER, help="Detente después de este paso")
    p_run.set_defaults(func=cmd_run)

    p_status = sub.add_parser("status", help="Muestra el estado actual")
    p_status.set_defaults(func=cmd_status)

    p_music = sub.add_parser("choose-music", help="Elige la variante de música (a/b) antes de mezclar")
    p_music.add_argument("variant", choices=["a", "b"])
    p_music.set_defaults(func=cmd_choose_music)

    return p


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
