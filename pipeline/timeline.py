"""Traduce timestamps calculados sobre la línea de tiempo pre-puente (retention_map,
camera_moves) a la línea de tiempo final, una vez el PASO 8 inserta puentes de 1s
en los cortes entre planos casi idénticos.
"""

from __future__ import annotations


def apply_shift(t: float, shifts: list[tuple[float, float]]) -> float:
    """shifts: [(punto_en_timeline_original, duración_insertada_en_ese_punto), ...]."""
    return t + sum(amount for point, amount in shifts if t >= point)


def load_shifts(path) -> list[tuple[float, float]]:
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [(s["point"], s["amount"]) for s in data.get("shifts", [])]


def shift_json_times(obj, shifts: list[tuple[float, float]]):
    """Recorre recursivamente un dict/list y desplaza cualquier 'start'/'end' numérico.
    Usado para trasladar subtitles_schedule.json / graphics_schedule.json (calculados
    contra la línea de tiempo pre-puente) a la línea de tiempo final tras el PASO 8.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in ("start", "end") and isinstance(v, (int, float)):
                out[k] = apply_shift(v, shifts)
            else:
                out[k] = shift_json_times(v, shifts)
        return out
    if isinstance(obj, list):
        return [shift_json_times(v, shifts) for v in obj]
    return obj
