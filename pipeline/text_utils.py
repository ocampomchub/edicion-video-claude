"""Utilidades de texto/frases compartidas entre el corte de silencios y el mapa de retención."""

from __future__ import annotations

import re
import unicodedata

from .models import Phrase, Word


def normalize(word: str) -> str:
    w = word.strip().lower()
    w = "".join(c for c in unicodedata.normalize("NFD", w) if unicodedata.category(c) != "Mn")
    w = re.sub(r"[^a-z0-9]", "", w)
    return w


def load_words(transcript: dict) -> list[Word]:
    words: list[Word] = []
    for seg in transcript["segments"]:
        for w in seg["words"]:
            words.append(Word.from_dict(w))
    words.sort(key=lambda w: w.start)
    return words


def group_phrases(words: list[Word], min_gap: float) -> list[Phrase]:
    if not words:
        return []
    phrases: list[Phrase] = []
    current = [words[0]]
    for prev, w in zip(words, words[1:]):
        if w.start - prev.end < min_gap:
            current.append(w)
        else:
            phrases.append(Phrase(words=current))
            current = [w]
    phrases.append(Phrase(words=current))
    return phrases


def contains_any(text: str, markers: list[str]) -> bool:
    norm = " ".join(normalize(t) for t in text.split())
    return any(" ".join(normalize(t) for t in m.split()) in norm for m in markers)
