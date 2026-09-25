"""Text normalisation, abbreviation expansion, sentence/clause segmentation.

Offsets are always relative to the ORIGINAL description so that every evidence span
can be highlighted exactly in the UI.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.nlp.vocabulary import ABBREVIATIONS


@dataclass(frozen=True)
class Segment:
    text: str
    start: int
    end: int


def clean_text(text: str) -> str:
    """Validation-level cleanup that preserves character offsets 1:1 where possible."""
    text = unicodedata.normalize("NFKC", text or "")
    # Replace control chars/newlines by spaces (same length -> offsets unchanged)
    text = re.sub(r"[\r\n\t\x0b\x0c]", " ", text)
    return text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')


_ABBR_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in ABBREVIATIONS) + r")\b")


def expand_abbreviations(text: str) -> str:
    return _ABBR_RE.sub(lambda m: f"{m.group(1)} {ABBREVIATIONS[m.group(1)]}", text)


def normalize_for_model(text: str) -> str:
    """Lower-cased, abbreviation-expanded text used by ML components (not for evidence)."""
    t = expand_abbreviations(clean_text(text))
    t = t.lower()
    t = re.sub(r"lock[- ]?out[/ -]?(?:and[/ -]?)?tag[- ]?out", "lockout tagout", t)
    t = re.sub(r"lock[- ]out", "lockout", t)
    t = re.sub(r"[^a-z0-9%/\-\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@lru_cache(maxsize=1)
def _spacy_nlp():
    try:
        import spacy

        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
        return nlp
    except Exception:  # pragma: no cover - spaCy optional
        return None


def sentence_segments(text: str) -> list[Segment]:
    nlp = _spacy_nlp()
    segs: list[Segment] = []
    if nlp is not None:
        doc = nlp(text)
        for s in doc.sents:
            if s.text.strip():
                segs.append(Segment(s.text, s.start_char, s.end_char))
        if segs:
            return segs
    for m in re.finditer(r"[^.!?]+[.!?]?", text):
        if m.group(0).strip():
            segs.append(Segment(m.group(0), m.start(), m.end()))
    return segs


_CLAUSE_SPLIT = re.compile(r";|:|,\s*but\b|\bbut\b|\bwhile\b|\bhowever\b|,\s*and\b|\bwhereas\b|\balthough\b|,\s*which\b|,\s*so\b|\band then\b")


def clause_segments(text: str) -> list[Segment]:
    clauses: list[Segment] = []
    for sent in sentence_segments(text):
        last = 0
        for m in _CLAUSE_SPLIT.finditer(sent.text):
            if m.start() > last:
                clauses.append(Segment(sent.text[last : m.start()], sent.start + last, sent.start + m.start()))
            last = m.end()
        if last < len(sent.text):
            clauses.append(Segment(sent.text[last:], sent.start + last, sent.end))
    return [c for c in clauses if c.text.strip()]


def segment_containing(segments: list[Segment], pos: int) -> Segment | None:
    for s in segments:
        if s.start <= pos < s.end:
            return s
    return None


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
