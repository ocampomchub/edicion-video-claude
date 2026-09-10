"""PASO 5 — Punch-ins y movimiento, anclados exclusivamente al mapa del PASO 3.

Punch-in 8-12% en KEY_LINES/PUNCHLINES (rampa 0.3-0.5s, salida por corte seco,
máx. 1 cada 6s, centrado en el rostro detectado). Reencuadre lateral 4% en
TOPIC_SHIFTS. Nada de esto se coloca fuera de un anchor marcado en el mapa.
"""

from __future__ import annotations

from pathlib import Path

from . import config, utils

LATERAL_ZOOM_MARGIN = 1.05  # zoom mínimo necesario para poder desplazar el encuadre 4%
DEFAULT_FACE_CENTER = (0.5, 0.38)  # fallback si no hay detector de rostro disponible


def _detect_face_center(frame_path: Path) -> tuple[float, float] | None:
    try:
        import cv2
    except ImportError:
        return None
    try:
        img = cv2.imread(str(frame_path))
        if img is None:
            return None
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) == 0:
            return None
        # la cara más grande = sujeto principal
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        h_img, w_img = img.shape[:2]
        fx = (x + w / 2) / w_img
        fy = (y + h / 2) / h_img
        return fx, fy
    except Exception as e:
        # La detección de rostro es opcional por diseño: si el build de OpenCV
        # instalado no la soporta (o falla por lo que sea), caemos al encuadre
        # por defecto en vez de tumbar todo el PASO 5.
        print(f"Aviso: detección de rostro falló ({e}); uso encuadre por defecto.")
        return None


def _face_center_at(video_path: Path, timestamp: float) -> tuple[float, float]:
    frame_path = config.WORK_DIR / "_face_probe.png"
    try:
        utils.extract_frame_png(video_path, timestamp, frame_path)
    except utils.FFmpegError:
        return DEFAULT_FACE_CENTER
    center = _detect_face_center(frame_path)
    return center or DEFAULT_FACE_CENTER


def _select_punch_anchors(anchors: list[dict]) -> list[dict]:
    candidates = [a for a in anchors if a["kind"] in ("KEY_LINES", "PUNCHLINES")]
    candidates.sort(key=lambda a: a["score"], reverse=True)
    selected: list[dict] = []
    for cand in candidates:
        if all(
            abs(cand["start"] - s["start"]) >= config.MIN_SECONDS_BETWEEN_PUNCHES
            for s in selected
        ):
            selected.append(cand)
    selected.sort(key=lambda a: a["start"])
    return selected


def _select_lateral_anchors(anchors: list[dict], punch_anchors: list[dict]) -> list[dict]:
    punch_spans = [(p["start"], p["end"]) for p in punch_anchors]

    def overlaps(a: dict) -> bool:
        return any(a["start"] < e and a["end"] > s for s, e in punch_spans)

    return [a for a in anchors if a["kind"] == "TOPIC_SHIFTS" and not overlaps(a)]


def build_camera_moves(retention_map: dict, video_path: Path) -> list[dict]:
    anchors = retention_map["anchors"]
    punch_anchors = _select_punch_anchors(anchors)
    lateral_anchors = _select_lateral_anchors(anchors, punch_anchors)

    moves: list[dict] = []
    for a in punch_anchors:
        fx, fy = _face_center_at(video_path, a["start"])
        zoom = config.PUNCH_ZOOM_MIN + (config.PUNCH_ZOOM_MAX - config.PUNCH_ZOOM_MIN) * min(
            1.0, a["score"] / 4.0
        )
        moves.append({
            "type": "punch_in",
            "start": a["start"],
            "end": a["end"],
            "zoom": round(zoom, 4),
            "ramp_duration": config.PUNCH_RAMP_DURATION,
            "fx": fx, "fy": fy,
            "anchor_kind": a["kind"],
            "text": a["text"],
        })

    for a in lateral_anchors:
        moves.append({
            "type": "lateral_reframe",
            "start": a["start"],
            "end": a["end"],
            "zoom": LATERAL_ZOOM_MARGIN,
            "ramp_duration": config.PUNCH_RAMP_DURATION,
            "shift": config.LATERAL_REFRAME_SHIFT,
            "anchor_kind": a["kind"],
            "text": a["text"],
        })

    moves.sort(key=lambda m: m["start"])
    return moves


def _zoompan_filter(move: dict, fps: float, width: int, height: int) -> str:
    ramp_frames = max(1, round(move["ramp_duration"] * fps))
    zoom_target = move["zoom"]

    if move["type"] == "punch_in":
        fx, fy = move["fx"], move["fy"]
    else:
        # reencuadre lateral: desplaza el centro un 4% en horizontal, sin zoom perceptible.
        direction = 1 if int(move["start"] * 1000) % 2 == 0 else -1
        fx = 0.5 + direction * move["shift"]
        fy = 0.5

    zoom_expr = f"if(lte(on,{ramp_frames}),1+({zoom_target - 1:.5f})*on/{ramp_frames},{zoom_target:.5f})"
    x_expr = f"max(0,min(iw-iw/zoom,iw*{fx:.4f}-(iw/zoom/2)))"
    y_expr = f"max(0,min(ih-ih/zoom,ih*{fy:.4f}-(ih/zoom/2)))"

    return (
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':"
        f"d=1:s={width}x{height}:fps={fps}"
    )


def _apply_moves(src: Path, moves: list[dict], dst: Path) -> None:
    utils.require_binary("ffmpeg")
    duration = utils.ffprobe_duration(src)
    fps = utils.ffprobe_fps(src)
    width, height = utils.ffprobe_dimensions(src)

    if not moves:
        cmd = ["ffmpeg", "-y", "-i", str(src), "-c", "copy", str(dst)]
        utils.run(cmd)
        return

    # timeline de segmentos: alterna "normal" y "movimiento" cubriendo [0, duration)
    boundaries = [0.0]
    for m in moves:
        boundaries += [m["start"], m["end"]]
    boundaries.append(duration)
    boundaries = sorted(set(round(b, 3) for b in boundaries if 0.0 <= b <= duration))

    filter_parts = []
    v_labels, a_labels = [], []
    for i, (seg_start, seg_end) in enumerate(zip(boundaries, boundaries[1:])):
        if seg_end - seg_start <= 0.001:
            continue
        move = next((m for m in moves if abs(m["start"] - seg_start) < 0.01), None)
        vf = f"[0:v]trim=start={seg_start:.3f}:end={seg_end:.3f},setpts=PTS-STARTPTS"
        if move:
            vf += f",{_zoompan_filter(move, fps, width, height)}"
        vf += f"[v{i}]"
        filter_parts.append(vf)
        filter_parts.append(
            f"[0:a]atrim=start={seg_start:.3f}:end={seg_end:.3f},asetpts=PTS-STARTPTS[a{i}]"
        )
        v_labels.append(f"[v{i}]")
        a_labels.append(f"[a{i}]")

    n = len(v_labels)
    concat_inputs = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
    filter_complex = ";".join(filter_parts)

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        str(dst),
    ]
    utils.run(cmd)


def run(graded_video: Path, retention_map_path: Path) -> Path:
    retention_map = utils.load_json(retention_map_path)
    moves = build_camera_moves(retention_map, graded_video)
    utils.save_json(config.CAMERA_MOVES_PATH, {"moves": moves})

    _apply_moves(graded_video, moves, config.MOVED_VIDEO_PATH)

    rows = [
        [m["type"], f"{m['start']:.2f}s", f"{m['end']:.2f}s", f"{m['zoom']:.3f}", m["anchor_kind"], m["text"][:40]]
        for m in moves
    ]
    utils.print_table(
        ["Tipo", "Inicio", "Fin", "Zoom", "Anchor", "Texto"], rows,
        title="PASO 5 — Punch-ins y reencuadres",
    )

    duration = utils.ffprobe_duration(config.MOVED_VIDEO_PATH)
    utils.step_done("PASO 5 — Punch-ins y movimiento", config.MOVED_VIDEO_PATH, duration)
    return config.MOVED_VIDEO_PATH
