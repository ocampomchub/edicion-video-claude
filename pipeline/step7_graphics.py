"""PASO 7 — Gráficos (scheduler): anclados exclusivamente al mapa del PASO 3.
LISTS -> tarjeta numerada, NUMBERS -> contador, ENTITIES -> chip, KEY_LINES -> subrayado.
Máximo un gráfico simultáneo, densidad 4-8/min, nunca relleno por rellenar.
"""

from __future__ import annotations

from pathlib import Path

from . import config, utils

_KIND_TO_TYPE = {
    "LISTS": "list_item",
    "NUMBERS": "number_counter",
    "ENTITIES": "entity_chip",
    "KEY_LINES": "key_line_underline",
}


def _candidate_span(kind: str, anchor: dict) -> tuple[float, float]:
    if kind == "NUMBERS":
        start = anchor["start"]
        return start, max(anchor["end"], start + config.NUMBER_COUNT_DURATION * 2)
    if kind == "ENTITIES":
        start = anchor["start"]
        return start, start + config.ENTITY_CHIP_DURATION
    return anchor["start"], anchor["end"]


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return a[0] < b[1] and a[1] > b[0]


def build_graphics(retention_map: dict, duration: float) -> list[dict]:
    candidates = []
    for anchor in retention_map["anchors"]:
        gtype = _KIND_TO_TYPE.get(anchor["kind"])
        if gtype is None:
            continue
        start, end = _candidate_span(anchor["kind"], anchor)
        candidates.append({
            "type": gtype,
            "start": start,
            "end": end,
            "score": anchor["score"],
            "text": anchor["text"],
            "anchor_kind": anchor["kind"],
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)

    minutes = max(duration / 60.0, 1e-6)
    max_total = max(1, round(config.GRAPHICS_MAX_PER_MIN * minutes))

    selected: list[dict] = []
    for cand in candidates:
        if len(selected) >= max_total:
            break
        span = (cand["start"], cand["end"])
        if any(_overlaps(span, (s["start"], s["end"])) for s in selected):
            continue
        selected.append(cand)

    selected.sort(key=lambda c: c["start"])

    list_index = 0
    for g in selected:
        if g["type"] == "list_item":
            g["list_index"] = list_index
            list_index += 1

    return selected


def run(retention_map_path: Path, cuts_path: Path) -> Path:
    retention_map = utils.load_json(retention_map_path)
    duration = retention_map.get("duration") or utils.load_json(cuts_path)["final_duration"]

    graphics = build_graphics(retention_map, duration)
    payload = {
        "duration": duration,
        "palette": config.GRAPHIC_PALETTE,
        "graphics": graphics,
    }
    utils.save_json(config.GRAPHICS_SCHEDULE_PATH, payload)

    minutes = duration / 60.0
    density = len(graphics) / minutes if minutes > 0 else 0.0
    rows = [[g["type"], f"{g['start']:.2f}s", f"{g['end']:.2f}s", g["text"][:40]] for g in graphics]
    utils.print_table(["Tipo", "Inicio", "Fin", "Texto"], rows, title="PASO 7 — Gráficos")
    utils.print_table(
        ["Métrica", "Valor"],
        [["Densidad", f"{density:.2f} gráficos/min"], ["Total", str(len(graphics))]],
        title="PASO 7 — Resumen",
    )

    utils.step_done("PASO 7 — Gráficos (scheduler)", config.GRAPHICS_SCHEDULE_PATH)
    return config.GRAPHICS_SCHEDULE_PATH
