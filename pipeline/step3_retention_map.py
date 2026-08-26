"""PASO 3 — Mapa de retención: ancla HOOK/KEY_LINES/NUMBERS/LISTS/ENTITIES/TOPIC_SHIFTS/
PUNCHLINES/CTA sobre la línea de tiempo de work/clean.mp4 (post-corte). Todo lo que
sigue (color, punch-ins, subtítulos, gráficos, sfx) se ancla exclusivamente a este mapa.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config, text_utils, utils
from .models import CutsResult, Phrase, RetentionAnchor, Word

_NUMBER_RE = re.compile(r"\d+([.,]\d+)?%?|\b(un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b", re.I)


def _remap_words(transcript: dict, cuts: CutsResult) -> list[Word]:
    words = text_utils.load_words(transcript)
    remapped: list[Word] = []
    for w in words:
        mid = (w.start + w.end) / 2
        new_mid = cuts.remap(mid)
        if new_mid is None:
            continue
        new_start = cuts.remap(w.start)
        new_end = cuts.remap(w.end)
        if new_start is None:
            new_start = new_mid
        if new_end is None:
            new_end = new_mid
        remapped.append(Word(word=w.word, start=new_start, end=new_end))
    remapped.sort(key=lambda w: w.start)
    return remapped


def _score_key_line(phrase: Phrase) -> float:
    score = 0.0
    if _NUMBER_RE.search(phrase.text):
        score += 1
    if len(phrase.words) >= 6:
        score += 1
    if text_utils.contains_any(phrase.text, config.THESIS_MARKERS):
        score += 2
    return score


def _score_punchline(phrase: Phrase) -> float:
    score = 0.0
    if text_utils.contains_any(phrase.text, config.PUNCHLINE_MARKERS):
        score += 2
    if phrase.text.strip().endswith("!"):
        score += 1
    return score


def _is_entity_word(word: Word, is_phrase_start: bool) -> bool:
    raw = word.word.strip()
    core = raw.strip(".,;:!?¡¿\"'")
    if len(core) < 3:
        return False
    if core.upper() in config.KNOWN_ENTITIES:
        return True
    if is_phrase_start:
        return False
    return core[0].isupper() and core[1:].islower()


def _jaccard_distance(a: Phrase, b: Phrase) -> float:
    sa = {text_utils.normalize(w.word) for w in a.words}
    sb = {text_utils.normalize(w.word) for w in b.words}
    if not sa or not sb:
        return 1.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return 1.0 - (inter / union if union else 0.0)


def build_map(transcript: dict, cuts: CutsResult) -> list[RetentionAnchor]:
    words = _remap_words(transcript, cuts)
    phrases = text_utils.group_phrases(words, config.MIN_SILENCE_DUR)
    total = cuts.final_duration
    anchors: list[RetentionAnchor] = []

    hook_words = [w for w in words if w.start < config.HOOK_DURATION]
    if hook_words:
        anchors.append(RetentionAnchor(
            "HOOK", 0.0, min(config.HOOK_DURATION, total),
            " ".join(w.word for w in hook_words), score=10.0,
        ))

    cta_start = max(0.0, total - config.CTA_DURATION)
    cta_words = [w for w in words if w.end > cta_start]
    if cta_words:
        anchors.append(RetentionAnchor(
            "CTA", cta_start, total,
            " ".join(w.word for w in cta_words), score=10.0,
        ))

    for phrase in phrases:
        kl_score = _score_key_line(phrase)
        if kl_score >= config.KEY_LINE_MIN_SCORE:
            anchors.append(RetentionAnchor("KEY_LINES", phrase.start, phrase.end, phrase.text, kl_score))

        if text_utils.contains_any(phrase.text, config.LIST_MARKERS):
            anchors.append(RetentionAnchor("LISTS", phrase.start, phrase.end, phrase.text, 2.0))

        if text_utils.contains_any(phrase.text, config.TOPIC_SHIFT_MARKERS):
            anchors.append(RetentionAnchor("TOPIC_SHIFTS", phrase.start, phrase.end, phrase.text, 2.0))

        pl_score = _score_punchline(phrase)
        if pl_score > 0:
            anchors.append(RetentionAnchor("PUNCHLINES", phrase.start, phrase.end, phrase.text, pl_score))

        for i, w in enumerate(phrase.words):
            if _NUMBER_RE.fullmatch(text_utils.normalize(w.word)) or re.search(r"\d", w.word):
                anchors.append(RetentionAnchor("NUMBERS", w.start, w.end, w.word, 1.5))
            if _is_entity_word(w, is_phrase_start=(i == 0)):
                anchors.append(RetentionAnchor("ENTITIES", w.start, w.end, w.word, 1.0))

    # divergencia léxica fuerte entre frases consecutivas -> también cambio de tema,
    # aunque no use un marcador de discurso explícito.
    for prev, phrase in zip(phrases, phrases[1:]):
        if _jaccard_distance(prev, phrase) > 0.9 and not text_utils.contains_any(
            phrase.text, config.TOPIC_SHIFT_MARKERS
        ):
            anchors.append(RetentionAnchor(
                "TOPIC_SHIFTS", phrase.start, phrase.end, phrase.text, 1.0,
                meta={"origen": "divergencia_lexica"},
            ))

    anchors.sort(key=lambda a: (a.start, a.kind))
    return anchors


def run(transcript_path: Path, cuts_path: Path) -> Path:
    transcript = utils.load_json(transcript_path)
    cuts = CutsResult.from_json(utils.load_json(cuts_path))

    anchors = build_map(transcript, cuts)
    payload = {
        "duration": cuts.final_duration,
        "anchors": [a.to_json() for a in anchors],
    }
    utils.save_json(config.RETENTION_MAP_PATH, payload)

    _print_report(anchors)
    utils.step_done("PASO 3 — Mapa de retención", config.RETENTION_MAP_PATH, cuts.final_duration)
    utils.checkpoint("PASO 3")
    return config.RETENTION_MAP_PATH


def _print_report(anchors: list[RetentionAnchor]) -> None:
    order = ["HOOK", "KEY_LINES", "NUMBERS", "LISTS", "ENTITIES", "TOPIC_SHIFTS", "PUNCHLINES", "CTA"]
    rows = []
    for kind in order:
        for a in [x for x in anchors if x.kind == kind]:
            rows.append([kind, f"{a.start:.2f}s", f"{a.end:.2f}s", f"{a.score:.1f}", a.text[:60]])
    utils.print_table(
        ["Tipo", "Inicio", "Fin", "Score", "Texto"], rows,
        title="PASO 3 — Mapa de retención",
    )
