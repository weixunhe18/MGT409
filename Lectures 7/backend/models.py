"""Pydantic models for the Yale SOM course explorer.

Every field in ``data/yale_som_classes.json`` is a string, including numeric-looking
ones like ``Units`` and date-like ones like ``20260902 000000.000``. The models below
keep the raw strings and expose tidy snake_case names via aliases, so the JSON can be
loaded without lossy coercion while the rest of the code reads naturally.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Course(BaseModel):
    """One row of ``yale_som_classes.json``."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    course_id: str = Field(default="", alias="Course ID")
    number: str = Field(default="", alias="Course Number")
    title: str = Field(default="", alias="Course Title")
    section: str = Field(default="", alias="Section")
    category: str = Field(default="", alias="Course Category")
    course_type: str = Field(default="", alias="Course Type")
    description: str = Field(default="", alias="Course Description")
    units: str = Field(default="", alias="Units")

    faculty: str = Field(default="", alias="Faculty 1")
    faculty_email: str = Field(default="", alias="Faculty 1 Email")
    faculty_bio: str = Field(default="", alias="faculty_bio")

    daytimes: str = Field(default="", alias="Daytimes")
    day: str = Field(default="", alias="Timings Day")
    start_time: str = Field(default="", alias="Timings StartTime")
    end_time: str = Field(default="", alias="Timings EndTime")
    room: str = Field(default="", alias="Room")

    session: str = Field(default="", alias="Course Session")
    session_start: str = Field(default="", alias="Course Session Start date")
    session_end: str = Field(default="", alias="Course Session End Date")
    term_code: str = Field(default="", alias="TermCode")

    bid_or_permission: str = Field(default="", alias="Bid Or Permission")
    syllabus: str = Field(default="", alias="Syllabus")
    old_syllabus: str = Field(default="", alias="Old Syllabus")
    visible: str = Field(default="", alias="Visible")

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, value: Any) -> Any:
        # 79 rows carry Room=" " and a few carry padded titles/numbers; a lone space
        # is truthy everywhere downstream and renders as an empty field.
        return value.strip() if isinstance(value, str) else value

    def haystack(self) -> str:
        """Lowercased blob of the searchable fields, used for text matching."""
        return " ".join(
            (
                self.number,
                self.title,
                self.category,
                self.course_type,
                self.faculty,
                self.faculty_email,
                self.description,
                self.faculty_bio,
                self.daytimes,
                self.day,
                self.room,
                self.session,
            )
        ).lower()

    def summary(self) -> dict[str, Any]:
        """Compact form handed to the model — trimmed so tool output stays readable."""
        return {
            "number": self.number,
            "title": self.title,
            "section": self.section,
            "category": self.category,
            "units": self.units,
            "faculty": self.faculty,
            "faculty_email": self.faculty_email.strip(),
            "when": self.daytimes,
            "room": self.room,
            "session": self.session,
            "bid_or_permission": self.bid_or_permission,
            "description": _clip(self.description, 600),
            "faculty_bio": _clip(self.faculty_bio, 400),
            "syllabus": self.syllabus,
        }


class CourseSearchResult(BaseModel):
    """What ``search_courses`` hands back to the agent."""

    query: str = ""
    filters: dict[str, str] = Field(default_factory=dict)
    total_matches: int = 0
    returned: int = 0
    truncated: bool = False
    courses: list[dict[str, Any]] = Field(default_factory=list)


class ToolCallRecord(BaseModel):
    """One tool invocation, as written to the audit trail."""

    tool: str
    kind: str = "function"
    args: dict[str, Any] = Field(default_factory=dict)
    result_preview: str = ""


class AuditEntry(BaseModel):
    """One full agent loop, appended to ``output/audit_trail.json``."""

    time: str
    model: str
    user_message: str
    thoughts: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    reply: str = ""
    tools_used: list[str] = Field(default_factory=list)
    stop_reason: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """Return shape ``main.py`` expects from ``run_agent``."""

    reply: str
    tools_used: list[str] = Field(default_factory=list)


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"
