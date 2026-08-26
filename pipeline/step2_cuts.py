"""PASO 2 — Corte de silencios: construye cuts.json y re-encodea a work/clean.mp4.

Reglas (ver spec): silencios >0.5s con 0.15s de aire, muletillas aisladas, repeticiones
(>70% solape -> queda la última toma), falsos arranques, y el límite crítico de no
cortar más de una vez cada 2 frases habladas. Ningún corte cae a mitad de palabra:
todo límite de segmento proviene directamente de un start/end de palabra del JSON.
"""

from __future__ import annotations

from pathlib import Path

from . import config, text_utils, utils
from .models import CutsResult, KeptSegment, Phrase, RemovedSegment

_VERB_SUFFIXES = (
    "ar", "er", "ir",  # infinitivos
    "ando", "iendo",  # gerundios
    "ado", "ada", "ados", "adas", "ido", "ida", "idos", "idas",  # participios
    "o", "as", "a", "amos", "áis", "an",
    "es", "e", "emos", "éis", "en",
    "í", "iste", "ió", "imos", "isteis", "ieron",
    "aba", "abas", "ábamos", "abais", "aban",
    "aré", "arás", "ará", "aremos", "aréis", "arán",
)
_IRREGULAR_VERBS = {
    "es", "soy", "eres", "son", "somos", "está", "estoy", "están", "estamos",
    "hay", "voy", "vas", "va", "vamos", "van", "quiero", "quieres", "puedo",
    "puedes", "sabes", "sé", "tengo", "tienes", "tiene", "tenemos", "tienen",
    "dice", "digo", "dices", "hace", "hago", "haces", "ves", "veo", "ve",
    "creo", "crees", "cree", "pienso", "piensas", "piensa",
}


def _is_probably_verb(word: str) -> bool:
    w = text_utils.normalize(word)
    if not w:
        return False
    if w in _IRREGULAR_VERBS:
        return True
    return any(w.endswith(suf) for suf in _VERB_SUFFIXES if len(suf) < len(w))


def _word_set(phrase: Phrase) -> set[str]:
    return {text_utils.normalize(w.word) for w in phrase.words if text_utils.normalize(w.word)}


def _overlap_ratio(a: Phrase, b: Phrase) -> float:
    sa, sb = _word_set(a), _word_set(b)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    return inter / min(len(sa), len(sb))


def _is_isolated_filler(phrase: Phrase) -> bool:
    if len(phrase.words) != 1:
        return False
    return text_utils.normalize(phrase.words[0].word) in {text_utils.normalize(f) for f in config.FILLERS}


def _is_false_start(phrase: Phrase, next_phrase: Phrase | None) -> bool:
    if next_phrase is None:
        return False
    if len(phrase.words) > config.FALSE_START_MAX_WORDS:
        return False
    has_verb = any(_is_probably_verb(w.word) for w in phrase.words)
    if has_verb:
        return False
    gap = next_phrase.start - phrase.end
    return 0 <= gap <= config.FALSE_START_MAX_GAP


def _filter_phrases(phrases: list[Phrase]) -> tuple[list[Phrase], list[RemovedSegment]]:
    removed: list[RemovedSegment] = []
    kept: list[Phrase] = []

    # 1) repeticiones: si dos frases consecutivas solapan >70%, se conserva solo la última.
    dedup: list[Phrase] = []
    for phrase in phrases:
        if dedup and _overlap_ratio(dedup[-1], phrase) > config.REPETITION_OVERLAP_THRESHOLD:
            prev = dedup.pop()
            removed.append(RemovedSegment(prev.start, prev.end, prev.text, "repeticion"))
        dedup.append(phrase)

    # 2) muletillas aisladas
    after_fillers: list[Phrase] = []
    for phrase in dedup:
        if _is_isolated_filler(phrase):
            removed.append(RemovedSegment(phrase.start, phrase.end, phrase.text, "muletilla"))
        else:
            after_fillers.append(phrase)

    # 3) falsos arranques: frase sin verbo + reinicio de la misma idea justo después
    i = 0
    while i < len(after_fillers):
        phrase = after_fillers[i]
        nxt = after_fillers[i + 1] if i + 1 < len(after_fillers) else None
        if _is_false_start(phrase, nxt):
            removed.append(RemovedSegment(phrase.start, phrase.end, phrase.text, "falso_arranque"))
            i += 1
            continue
        kept.append(phrase)
        i += 1

    return kept, removed


def _build_segments(
    phrases: list[Phrase], original_duration: float
) -> tuple[list[KeptSegment], list[RemovedSegment]]:
    removed: list[RemovedSegment] = []
    if not phrases:
        return [], removed

    cursor_new = 0.0
    kept_segments: list[KeptSegment] = []

    phrases_since_last_cut = config.MIN_PHRASES_BETWEEN_CUTS  # permite cortar desde el inicio

    span_start = max(0.0, phrases[0].start - config.PAD_BEFORE)
    span_end = min(original_duration, phrases[0].end + config.PAD_AFTER)
    span_text_parts = [phrases[0].text]

    def close_span() -> None:
        nonlocal cursor_new
        kept_segments.append(_finalize_span(span_start, span_end, " ".join(span_text_parts), cursor_new))
        cursor_new += span_end - span_start

    for prev_phrase, phrase in zip(phrases, phrases[1:]):
        gap = phrase.start - prev_phrase.end
        can_cut = phrases_since_last_cut >= config.MIN_PHRASES_BETWEEN_CUTS
        must_cap = gap > config.MAX_KEPT_SILENCE

        if can_cut:
            # Corte real: cerramos el segmento actual y abrimos uno nuevo.
            close_span()
            removed.append(RemovedSegment(prev_phrase.end, phrase.start, "", "silencio"))
            phrases_since_last_cut = 0
            span_start = max(0.0, phrase.start - config.PAD_BEFORE)
            span_end = min(original_duration, phrase.end + config.PAD_AFTER)
            span_text_parts = [phrase.text]
        elif must_cap:
            # La cadencia mínima aún no se cumple (no cuenta como "corte" en el
            # reporte de ritmo), pero el silencio conservado igual se topa a
            # MAX_KEPT_SILENCE partiendo el clip: si no, un silencio largo se
            # coló sin que ninguna regla lo hubiera recortado de verdad.
            half_cap = config.MAX_KEPT_SILENCE / 2
            span_end = prev_phrase.end + half_cap
            close_span()
            removed.append(RemovedSegment(
                prev_phrase.end + half_cap, phrase.start - half_cap,
                "", "silencio_recortado",
            ))
            span_start = max(0.0, phrase.start - half_cap)
            span_end = min(original_duration, phrase.end + config.PAD_AFTER)
            span_text_parts = [phrase.text]
            phrases_since_last_cut += 1
        else:
            span_end = min(original_duration, phrase.end + config.PAD_AFTER)
            span_text_parts.append(phrase.text)
            phrases_since_last_cut += 1

    close_span()
    return kept_segments, removed


def _finalize_span(orig_start: float, orig_end: float, text: str, new_start: float) -> KeptSegment:
    duration = orig_end - orig_start
    return KeptSegment(
        orig_start=orig_start, orig_end=orig_end,
        new_start=new_start, new_end=new_start + duration,
        text=text.strip(),
    )


def _reencode(input_video: Path, segments: list[KeptSegment], dst: Path) -> None:
    """Re-encodea (nunca stream copy) concatenando los segmentos conservados."""
    utils.require_binary("ffmpeg")
    n = len(segments)
    filter_parts = []
    v_labels, a_labels = [], []
    for i, seg in enumerate(segments):
        filter_parts.append(
            f"[0:v]trim=start={seg.orig_start:.3f}:end={seg.orig_end:.3f},"
            f"setpts=PTS-STARTPTS[v{i}]"
        )
        filter_parts.append(
            f"[0:a]atrim=start={seg.orig_start:.3f}:end={seg.orig_end:.3f},"
            f"asetpts=PTS-STARTPTS[a{i}]"
        )
        v_labels.append(f"[v{i}]")
        a_labels.append(f"[a{i}]")

    concat_inputs = "".join(f"{v}{a}" for v, a in zip(v_labels, a_labels))
    filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")
    filter_complex = ";".join(filter_parts)

    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        str(dst),
    ]
    utils.run(cmd)


def run(input_video: Path, transcript_path: Path) -> Path:
    transcript = utils.load_json(transcript_path)
    words = text_utils.load_words(transcript)
    phrases = text_utils.group_phrases(words, config.MIN_SILENCE_DUR)

    kept_phrases, removed_content = _filter_phrases(phrases)

    original_duration = utils.ffprobe_duration(input_video)
    segments, removed_silence = _build_segments(kept_phrases, original_duration)

    all_removed = sorted(removed_content + removed_silence, key=lambda r: r.orig_start)

    final_duration = segments[-1].new_end if segments else 0.0
    result = CutsResult(
        kept=segments, removed=all_removed,
        original_duration=original_duration, final_duration=final_duration,
    )
    utils.save_json(config.CUTS_PATH, result.to_json())

    _reencode(input_video, segments, config.CLEAN_VIDEO_PATH)

    _print_report(result)
    utils.step_done("PASO 2 — Corte de silencios", config.CLEAN_VIDEO_PATH, final_duration)
    utils.checkpoint("PASO 2")
    return config.CLEAN_VIDEO_PATH


def _print_report(result: CutsResult) -> None:
    num_cuts = len(result.kept) - 1 if result.kept else 0
    cadence = result.final_duration / num_cuts if num_cuts > 0 else 0.0

    utils.print_table(
        ["Métrica", "Valor"],
        [
            ["Duración original", f"{result.original_duration:.2f}s"],
            ["Duración final", f"{result.final_duration:.2f}s"],
            ["Nº de cortes", str(num_cuts)],
            ["Cadencia media de corte", f"{cadence:.2f}s"],
        ],
        title="PASO 2 — Resumen del corte",
    )

    longest = sorted(result.removed, key=lambda r: r.orig_end - r.orig_start, reverse=True)[:5]
    rows = [
        [f"{r.orig_start:.2f}s", f"{(r.orig_end - r.orig_start):.2f}s", r.reason, r.text or "(silencio)"]
        for r in longest
    ]
    utils.print_table(
        ["Inicio", "Duración", "Motivo", "Texto"], rows,
        title="PASO 2 — 5 fragmentos más largos eliminados",
    )
