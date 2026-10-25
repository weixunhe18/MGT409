"""Spec-conflict check: does the supplier state something that contradicts the shareable spec?

Real pattern (private replay): a supplier said the probe was copper while the spec, and their own listing, said
stainless steel. The agent let it pass; Wei caught it ("your spec sheet says stainless. so copper or stainless?").
This check is deterministic code, no model call: it compares what the supplier states with the spec line about
the same part, for materials and for numbers with units.

A supplier PROPOSING a change ("EPDM instead of silicone?") names the spec's material too, so it is not reported
here; the engineering-change rule handles proposals.
"""

from __future__ import annotations

import re

from .knowledge import KnowledgeBase, tokenize

# Longest names first, so "pc/abs" wins over "abs" and "stainless steel" over "steel".
_MATERIALS = [
    ("stainless steel", "stainless steel"), ("stainless", "stainless steel"), ("pc/abs", "PC/ABS"),
    ("polycarbonate", "PC"), ("hot melt", "hot melt adhesive"), ("hot glue", "hot melt adhesive"),
    ("copper", "copper"), ("brass", "brass"), ("bronze", "bronze"), ("aluminium", "aluminum"),
    ("aluminum", "aluminum"), ("zinc", "zinc"), ("nickel", "nickel"), ("abs", "ABS"), ("nylon", "nylon"),
    ("pa66", "nylon"), ("tpe", "TPE"), ("tpu", "TPU"), ("silicone", "silicone"), ("epdm", "EPDM"), ("nbr", "NBR"),
    ("pvc", "PVC"), ("enig", "ENIG"), ("hasl", "HASL"), ("osp", "OSP"), ("p20", "P20"), ("h13", "H13"),
    ("epoxy", "epoxy"), ("polyurethane", "polyurethane"), ("vhb", "VHB tape"), ("steel", "steel"),
]
_MAT_RE = re.compile(r"(?<![\w/])(" + "|".join(re.escape(k) for k, _ in _MATERIALS) + r")(?![\w/])", re.I)
_CANON = {k: v for k, v in _MATERIALS}
# Label words that say nothing about WHICH part ("Probe material" is about the probe).
_GENERIC = {"material", "type", "size", "color", "colour", "requir", "spec", "standard", "general", "main", "product"}
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:\.(?=\d)[^.!?\n]*)*[.!?]?")
_NUM_UNIT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(mm|cm|m|µm|um|awg|v|kv|ma|mah|°|%|gsm)\b", re.I)
_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s?(mm|cm|m|µm|um|v|°|%|gsm)?\s?(?:to|–|-)\s?(\d+(?:\.\d+)?)\s?(mm|cm|m|µm|um|v|°|%|gsm)\b",
                       re.I)
_LIMIT_RE = re.compile(r"\b(max(?:imum)?|min(?:imum)?)\s+(\d+(?:\.\d+)?)\s?(mm|cm|m|µm|um|v|°|%|gsm)\b|"
                       r"(\d+(?:\.\d+)?)\s?(mm|cm|m|µm|um|v|°|%|gsm)\s+(max(?:imum)?|min(?:imum)?)\b", re.I)


def materials_in(text: str) -> set[str]:
    found, rest = set(), text.lower()
    for m in _MAT_RE.finditer(rest):
        found.add(_CANON[m.group(1).lower()])
    if "stainless steel" in found:
        found.discard("steel")
    return found


def _part_tokens(label: str) -> set[str]:
    return {t for t in tokenize(label) if t not in _GENERIC}


def _numeric_limits(text: str) -> list[tuple[str, float, float]]:
    """(unit, low, high) from '3.0 mm to 4.0 mm', '0.2–0.4 mm', 'maximum 2.5 mm', '1.6 mm min'."""
    limits = []
    for m in _RANGE_RE.finditer(text):
        unit = (m.group(4) or m.group(2) or "").lower()
        limits.append((unit, float(m.group(1)), float(m.group(3))))
    for m in _LIMIT_RE.finditer(text):
        word = (m.group(1) or m.group(6) or "").lower()
        value, unit = float(m.group(2) or m.group(4)), (m.group(3) or m.group(5)).lower()
        limits.append((unit, value, float("inf")) if word.startswith("min") else (unit, float("-inf"), value))
    return limits


def _best(facts_scored: list[tuple[float, object]]) -> list:
    top = max((r for r, _ in facts_scored), default=0)
    return [f for r, f in facts_scored if r == top and r > 0]


def find_conflicts(text: str, kb: KnowledgeBase, limit: int = 4) -> list[dict]:
    """Supplier statements that contradict a shareable spec line. Questions are not claims and are skipped."""
    conflicts: list[dict] = []
    clauses = []
    for raw in _SENTENCE_RE.findall(text or ""):
        sentence = raw.strip()
        if not sentence or sentence.endswith("?") or len(sentence) > 300:
            continue
        # Materials are judged per clause ("probe is copper, casing is ABS" = two claims); numbers per sentence,
        # because "wall is 2.0 mm, but near the boss it is 2.8 mm" needs "wall" from the first half.
        parts = [c.strip() for c in re.split(r",\s+|;\s*", sentence) if c.strip()]
        clauses += [(c, True, False) for c in parts] + [(sentence, False, True)]
    for clause, check_materials, check_numbers in clauses:
        words = tokenize(clause)
        said = materials_in(clause) if check_materials else set()
        numbers = [(float(v), u.lower()) for v, u in _NUM_UNIT_RE.findall(clause)] if check_numbers else []
        # Compare only with the spec line(s) that best match the part the clause is about ("the probe is copper"
        # is about "Probe material", not "Probe casing"), separately for materials and for numbers.
        mat_scored, num_scored = [], []
        for fact in kb.facts:
            part = _part_tokens(fact.label)
            if not part or fact.tbd or not (part & words):
                continue
            ratio = len(part & words) / len(part)
            if said and materials_in(fact.text):
                mat_scored.append((ratio, fact))
            if numbers and _numeric_limits(fact.text):
                num_scored.append((ratio, fact))
        for fact in _best(mat_scored):
            required = materials_in(fact.text)
            if not (said & required):
                conflicts.append({"claim": clause, "spec": f"{fact.label}: {fact.text}", "kind": "material",
                                  "detail": f"says {', '.join(sorted(said))}; spec says {', '.join(sorted(required))}"})
        for fact in _best(num_scored):
            hit = None
            for value, unit in numbers:
                for lim_unit, low, high in _numeric_limits(fact.text):
                    if unit == lim_unit and not (low <= value <= high):
                        rng = (f"{low:g}–{high:g} {unit}" if low > float("-inf") and high < float("inf") else
                               f"max {high:g} {unit}" if low == float("-inf") else f"min {low:g} {unit}")
                        hit = f"{value:g} {unit} is outside {rng}"
                        break
                if hit:
                    break
            if hit:
                conflicts.append({"claim": clause, "spec": f"{fact.label}: {fact.text}", "kind": "number",
                                  "detail": hit})
    unique, seen = [], set()
    for c in conflicts:
        key = (c["claim"], c["spec"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:limit]
