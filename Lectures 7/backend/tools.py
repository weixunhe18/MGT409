"""Tools the course agent can call.

Only ``search_courses`` lives here. Web search is OpenAI's native tool, wired in
``agent.py`` as a provider capability rather than a Python function.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from models import Course, CourseSearchResult

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA_PATH = ROOT / "data" / "yale_som_classes.json"

MAX_RESULTS = 15

# How a person might name a day -> canonical two-letter code.
_DAY_ALIASES = {
    "monday": "mo", "mon": "mo", "m": "mo", "mo": "mo",
    "tuesday": "tu", "tue": "tu", "tues": "tu", "t": "tu", "tu": "tu",
    "wednesday": "we", "wed": "we", "w": "we", "we": "we",
    "thursday": "th", "thu": "th", "thur": "th", "thurs": "th", "th": "th",
    "friday": "fr", "fri": "fr", "f": "fr", "fr": "fr",
    "saturday": "sa", "sat": "sa", "sa": "sa",
    "sunday": "su", "sun": "su", "su": "su",
}

# Codes as they appear inside "Daytimes", e.g. "T  Th 2:35 PM-3:55 PM".
# Matched as whole tokens so "T" (Tuesday) never swallows "Th" (Thursday).
_DAYTIME_CODES = {
    "m": "mo", "t": "tu", "w": "we", "th": "th", "f": "fr",
    "sa": "sa", "su": "su",
}


@lru_cache(maxsize=1)
def load_courses() -> list[Course]:
    """Parse the course JSON once and keep it in memory."""
    rows = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    return [Course.model_validate(row) for row in rows]


def _normalize_day(value: str) -> str:
    return _DAY_ALIASES.get(value.strip().lower(), value.strip().lower())


def course_days(course: Course) -> set[str]:
    """Canonical day codes a course meets on.

    ``Timings Day`` is populated for only ~11% of rows, so the meeting days really
    live in ``Daytimes`` ("M  W 8:30 AM-9:50 AM"). Read both and union them.
    """
    days: set[str] = set()

    for token in re.split(r"[,\s]+", course.day.strip()):
        code = _DAY_ALIASES.get(token.lower())
        if code:
            days.add(code)

    # Take only the letters before the first digit: "T  Th 2:35 PM-3:55 PM" -> "T  Th"
    head = re.match(r"^([A-Za-z\s]+?)\s*(?=\d)", course.daytimes.strip())
    if head:
        for token in head.group(1).split():
            code = _DAYTIME_CODES.get(token.lower())
            if code:
                days.add(code)

    return days


def _score(course: Course, terms: list[str]) -> int:
    """Rank matches so an exact number/title hit beats a stray description mention."""
    if not terms:
        return 1

    number = course.number.lower()
    title = course.title.lower()
    faculty = course.faculty.lower()
    category = course.category.lower()
    haystack = course.haystack()

    total = 0
    for term in terms:
        if term not in haystack:
            return 0  # every term must appear somewhere
        if term == number or term.replace(" ", "") == number.replace(" ", ""):
            total += 100
        elif term in number:
            total += 40
        elif term in title:
            total += 30
        elif term in faculty:
            total += 25
        elif term in category:
            total += 15
        else:
            total += 5
    return total


def search_courses(
    query: str = "",
    category: str = "",
    faculty: str = "",
    day: str = "",
    limit: int = MAX_RESULTS,
) -> dict:
    """Search the Yale SOM course catalog.

    Args:
        query: Free text matched against course number, title, faculty, category,
            description, faculty bio, meeting time and room. Multiple words are ANDed.
        category: Restrict to a course category, e.g. "Finance", "Core", "Marketing".
        faculty: Restrict to an instructor name, e.g. "Simonsohn" or "Uri".
        day: Restrict to a meeting day, e.g. "Monday", "Mon", or "Mo".
        limit: Maximum courses to return (capped at 15).

    Returns:
        Matching courses with their number, title, faculty, meeting time, room,
        units, description and syllabus link.
    """
    courses = load_courses()

    terms = [t for t in query.lower().split() if t]
    category_needle = category.strip().lower()
    faculty_needle = faculty.strip().lower()
    day_needle = _normalize_day(day) if day else ""

    scored: list[tuple[int, Course]] = []
    for course in courses:
        if category_needle and category_needle not in course.category.lower():
            continue
        if faculty_needle and faculty_needle not in course.faculty.lower():
            continue
        if day_needle and day_needle not in course_days(course):
            continue
        score = _score(course, terms)
        if score:
            scored.append((score, course))

    scored.sort(key=lambda pair: (-pair[0], pair[1].number, pair[1].section))

    capped = max(1, min(int(limit or MAX_RESULTS), MAX_RESULTS))
    top = scored[:capped]

    result = CourseSearchResult(
        query=query,
        filters={
            k: v
            for k, v in (
                ("category", category),
                ("faculty", faculty),
                ("day", day),
            )
            if v
        },
        total_matches=len(scored),
        returned=len(top),
        truncated=len(scored) > len(top),
        courses=[course.summary() for _, course in top],
    )
    return result.model_dump()
