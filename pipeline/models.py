"""Dataclasses ligeras para las estructuras que viajan entre pasos como JSON."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Word:
    word: str
    start: float
    end: float

    @staticmethod
    def from_dict(d: dict) -> "Word":
        return Word(word=d["word"], start=float(d["start"]), end=float(d["end"]))


@dataclass
class Phrase:
    """Grupo de palabras contiguas separadas por pausas < MIN_SILENCE_DUR."""
    words: list[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end

    @property
    def text(self) -> str:
        return " ".join(w.word.strip() for w in self.words)


@dataclass
class KeptSegment:
    """Segmento del vídeo original que sobrevive al corte de silencios."""
    orig_start: float
    orig_end: float
    new_start: float
    new_end: float
    text: str


@dataclass
class RemovedSegment:
    orig_start: float
    orig_end: float
    text: str
    reason: str


@dataclass
class CutsResult:
    kept: list[KeptSegment]
    removed: list[RemovedSegment]
    original_duration: float
    final_duration: float

    def to_json(self) -> dict:
        return {
            "original_duration": self.original_duration,
            "final_duration": self.final_duration,
            "kept": [asdict(k) for k in self.kept],
            "removed": [asdict(r) for r in self.removed],
        }

    @staticmethod
    def from_json(d: dict) -> "CutsResult":
        return CutsResult(
            kept=[KeptSegment(**k) for k in d["kept"]],
            removed=[RemovedSegment(**r) for r in d["removed"]],
            original_duration=d["original_duration"],
            final_duration=d["final_duration"],
        )

    def remap(self, orig_time: float) -> float | None:
        """Traduce un timestamp del vídeo original a su posición en clean.mp4, o None si fue cortado."""
        for seg in self.kept:
            if seg.orig_start <= orig_time <= seg.orig_end:
                offset = orig_time - seg.orig_start
                return seg.new_start + offset
        return None


@dataclass
class RetentionAnchor:
    kind: str  # HOOK/KEY_LINES/NUMBERS/LISTS/ENTITIES/TOPIC_SHIFTS/PUNCHLINES/CTA
    start: float
    end: float
    text: str
    score: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict:
        return asdict(self)
