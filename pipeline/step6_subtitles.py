"""PASO 6 — Subtítulos (scheduler): agrupa las palabras remapeadas a la línea de tiempo
de work/clean.mp4 en tarjetas de 2-4 palabras, y decide qué palabras llevan el énfasis
de NUMBERS/ENTITIES (máximo una cada 4 segundos). El render final (quemado, con la
tipografía/color/entrada del spec) lo hace el proyecto Remotion a partir de este JSON.
"""

from __future__ import annotations

from pathlib import Path

from . import config, text_utils, utils
from .models import CutsResult, Word

MIN_WORDS = config.SUBTITLE_WORDS_MIN
MAX_WORDS = config.SUBTITLE_WORDS_MAX


def _remap_words(transcript: dict, cuts: CutsResult) -> list[Word]:
    words = text_utils.load_words(transcript)
    remapped: list[Word] = []
    for w in words:
        mid = (w.start + w.end) / 2
        if cuts.remap(mid) is None:
            continue
        new_start = cuts.remap(w.start)
        new_end = cuts.remap(w.end)
        if new_start is None or new_end is None:
            continue
        remapped.append(Word(word=w.word, start=new_start, end=new_end))
    remapped.sort(key=lambda w: w.start)
    return remapped


def _chunk_phrase_words(words: list[Word]) -> list[list[Word]]:
    n = len(words)
    if n <= MAX_WORDS:
        return [words] if n > 0 else []
    num_chunks = -(-n // MAX_WORDS)  # ceil
    base = n // num_chunks
    remainder = n % num_chunks
    chunks, i = [], 0
    for c in range(num_chunks):
        size = base + (1 if c < remainder else 0)
        size = max(size, 1)
        chunks.append(words[i:i + size])
        i += size
    return [c for c in chunks if c]


def _emphasis_word_keys(retention_map: dict) -> set[tuple[float, float]]:
    keys = set()
    for a in retention_map["anchors"]:
        if a["kind"] in ("NUMBERS", "ENTITIES"):
            keys.add((round(a["start"], 3), round(a["end"], 3)))
    return keys


def build_cards(transcript: dict, cuts: CutsResult, retention_map: dict) -> list[dict]:
    words = _remap_words(transcript, cuts)
    phrases = text_utils.group_phrases(words, config.MIN_SILENCE_DUR)
    emphasis_keys = _emphasis_word_keys(retention_map)

    raw_cards: list[list[Word]] = []
    for phrase in phrases:
        raw_cards.extend(_chunk_phrase_words(phrase.words))

    # candidatas a énfasis, en orden cronológico, con límite de 1 cada 4s.
    last_emphasis_time = -1e9
    cards = []
    for chunk in raw_cards:
        card_words = []
        for w in chunk:
            key = (round(w.start, 3), round(w.end, 3))
            is_candidate = key in emphasis_keys
            emphasize = False
            if is_candidate and w.start - last_emphasis_time >= config.MIN_SECONDS_BETWEEN_EMPHASIS:
                emphasize = True
                last_emphasis_time = w.start
            card_words.append({"text": w.word, "start": w.start, "end": w.end, "emphasize": emphasize})
        cards.append({
            "start": chunk[0].start,
            "end": chunk[-1].end,
            "words": card_words,
        })
    return cards


def run(transcript_path: Path, cuts_path: Path, retention_map_path: Path) -> Path:
    transcript = utils.load_json(transcript_path)
    cuts = CutsResult.from_json(utils.load_json(cuts_path))
    retention_map = utils.load_json(retention_map_path)

    cards = build_cards(transcript, cuts, retention_map)
    payload = {
        "duration": cuts.final_duration,
        "style": {
            "font": config.SUBTITLE_FONT,
            "weight": config.SUBTITLE_WEIGHT,
            "color": config.SUBTITLE_COLOR,
            "emphasisColor": config.SUBTITLE_EMPHASIS_COLOR,
            "shadowOpacity": config.SUBTITLE_SHADOW_OPACITY,
            "bottomSafePct": config.SUBTITLE_BOTTOM_SAFE_PCT,
            "entryRisePx": config.SUBTITLE_ENTRY_RISE_PX,
            "entryFrames": config.SUBTITLE_ENTRY_FRAMES,
            "emphasisScale": config.SUBTITLE_EMPHASIS_SCALE,
        },
        "cards": cards,
    }
    utils.save_json(config.SUBTITLES_SCHEDULE_PATH, payload)

    n_emphasis = sum(1 for c in cards for w in c["words"] if w["emphasize"])
    utils.print_table(
        ["Métrica", "Valor"],
        [["Tarjetas", str(len(cards))], ["Palabras enfatizadas", str(n_emphasis)]],
        title="PASO 6 — Subtítulos (scheduler)",
    )
    utils.step_done("PASO 6 — Subtítulos (scheduler)", config.SUBTITLES_SCHEDULE_PATH)
    return config.SUBTITLES_SCHEDULE_PATH
