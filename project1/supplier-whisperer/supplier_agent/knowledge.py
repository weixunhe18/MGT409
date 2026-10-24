"""Product knowledge base.

The spec is split into ``## sections`` tagged [SHAREABLE] or [CONFIDENTIAL].
Untagged sections are treated as confidential (fail closed).

Only SHAREABLE text is ever sent to a language model or quoted in a reply.
CONFIDENTIAL text is used for one thing only: building the leak-detection list
(prices, dates, codenames) that the outbound compliance check scans for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

STOPWORDS = frozenset(
    """
    a an the and or but if then else of to in on at by for from with without into onto about as
    is are was were be been being am do does did done doing have has had having
    can could will would shall should may might must need needs needed
    we you your yours our ours us i me my he she they them their it its this that these those there here
    what which who whom whose when where why how much many more most some any all each every both either
    no not only also just very too so than such same other another
    please pls kindly advise advice help confirm check let know thanks thank hi hello dear regards best br
    sir madam team mr ms below above following point points question questions answer
    one two three few now still yet again use using used get got make made want like right ok okay sure
    note kind type email mail old mention mentioned tell ask asked plan planned
    mm cm um deg degree degrees pc pcs unit units set sets
    wei kevin lily jason amy
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:\.[0-9]+)?")
_SUFFIXES = ("ings", "ing", "edly", "ed", "es", "s", "e")


def stem(word: str) -> str:
    """Tiny suffix stripper so 'textured'/'texture' and 'walls'/'wall' match."""
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def tokenize(text: str) -> set[str]:
    out: set[str] = set()
    for tok in _TOKEN_RE.findall(text.lower()):
        if len(tok) < 2 or tok in STOPWORDS:
            continue
        if tok.isalpha():
            tok = stem(tok)
            if tok in STOPWORDS:
                continue
        out.add(tok)
    return out


@dataclass
class Fact:
    section: str
    label: str
    text: str
    label_tokens: set[str] = field(default_factory=set)
    body_tokens: set[str] = field(default_factory=set)
    tbd: bool = False

    @property
    def display(self) -> str:
        return f"{self.label}: {self.text}"


@dataclass
class Section:
    title: str
    shareable: bool
    body: str
    facts: list[Fact] = field(default_factory=list)


@dataclass
class Match:
    fact: Fact
    score: int
    label_hits: int
    confidence: float

    @property
    def answerable(self) -> bool:
        return not self.fact.tbd


_HEADING_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$")
_TAG_RE = re.compile(r"\[(SHAREABLE|CONFIDENTIAL)\]", re.IGNORECASE)
_FACT_RE = re.compile(r"^\s*[-*]\s+\*\*(?P<label>[^*]+?)\*\*\s*:?\s*(?P<body>.*)$")
_TBD_RE = re.compile(r"\bTBD\b")

MONEY_RE = re.compile(r"(?:\$|\busd\s?|\bus\$|\brmb\s?|\bcny\s?|¥|€)\s?\d[\d,]*(?:\.\d+)?", re.IGNORECASE)
_BIG_NUMBER_RE = re.compile(r"\b\d{1,3}(?:,\d{3})+\b")
_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,}(?:-[A-Z0-9]+)+\b")
_MONTH_DAY_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b"
)

MIN_SCORE = 4  # needs at least one label hit plus supporting words


class KnowledgeBase:
    def __init__(self, sections: list[Section], source: Path | None = None):
        self.sections = sections
        self.source = source

    @classmethod
    def load(cls, path: Path) -> "KnowledgeBase":
        return cls.from_markdown(path.read_text(encoding="utf-8"), source=path)

    @classmethod
    def from_markdown(cls, text: str, source: Path | None = None) -> "KnowledgeBase":
        sections: list[Section] = []
        current: Section | None = None
        lines: list[str] = []

        def close() -> None:
            if current is not None:
                current.body = "\n".join(lines).strip()
                if current.shareable:
                    current.facts = _parse_facts(current.title, current.body)
                sections.append(current)

        for line in text.splitlines():
            m = _HEADING_RE.match(line)
            if m:
                close()
                raw_title = m.group("title")
                tag = _TAG_RE.search(raw_title)
                shareable = bool(tag and tag.group(1).upper() == "SHAREABLE")
                title = _TAG_RE.sub("", raw_title).strip()
                current = Section(title=title, shareable=shareable, body="")
                lines = []
            elif current is not None:
                lines.append(line)
        close()
        return cls(sections, source)

    # ------------------------------------------------------------------ views
    @property
    def shareable_sections(self) -> list[Section]:
        return [s for s in self.sections if s.shareable]

    @property
    def confidential_sections(self) -> list[Section]:
        return [s for s in self.sections if not s.shareable]

    @property
    def facts(self) -> list[Fact]:
        return [f for s in self.shareable_sections for f in s.facts]

    def shareable_text(self) -> str:
        return "\n\n".join(f"## {s.title}\n{s.body}" for s in self.shareable_sections)

    def confidential_text(self) -> str:
        return "\n\n".join(f"## {s.title}\n{s.body}" for s in self.confidential_sections)

    def sensitive_terms(self, extra: list[str] | None = None) -> list[str]:
        """Leak-detection list: money amounts, big numbers, codes and dates that appear
        in CONFIDENTIAL sections but never in SHAREABLE ones, plus policy terms."""
        conf = self.confidential_text()
        share_low = self.shareable_text().lower()
        found: list[str] = []
        for regex in (MONEY_RE, _BIG_NUMBER_RE, _CODE_RE, _MONTH_DAY_RE):
            for m in regex.finditer(conf):
                term = m.group(0).strip()
                if term and term.lower() not in share_low and term not in found:
                    found.append(term)
        for term in extra or []:
            term = str(term).strip()
            if term and term not in found:
                found.append(term)
        return found

    # ----------------------------------------------------------------- search
    def search(self, question: str) -> Match | None:
        """Best SHAREABLE fact for a question, or None if nothing matches well.

        Label words count triple. If the best match is a TBD fact the caller must
        treat the question as unanswerable (we never fall through to a weaker fact).
        """
        q = tokenize(question)
        if not q:
            return None
        best: Match | None = None
        for fact in self.facts:
            label_hits = len(q & fact.label_tokens)
            body_hits = len(q & (fact.body_tokens - fact.label_tokens))
            score = 3 * label_hits + body_hits
            if best is None or score > best.score:
                best = Match(fact=fact, score=score, label_hits=label_hits, confidence=0.0)
        if best is None or best.label_hits < 1 or best.score < MIN_SCORE:
            return None
        best.confidence = round(min(1.0, 0.45 + 0.08 * best.score), 2)
        return best


def _parse_facts(section_title: str, body: str) -> list[Fact]:
    facts: list[Fact] = []
    for line in body.splitlines():
        m = _FACT_RE.match(line)
        if not m:
            continue
        label = m.group("label").strip().rstrip(":").strip()
        text = m.group("body").strip().lstrip(":").strip()
        facts.append(
            Fact(
                section=section_title,
                label=label,
                text=text,
                label_tokens=tokenize(label),
                body_tokens=tokenize(text),
                tbd=bool(_TBD_RE.search(text)),
            )
        )
    return facts
