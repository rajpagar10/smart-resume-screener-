"""Resume-to-job matching validation and orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

try:  # Supports direct module execution from backend/.
    from .resume_parser import ResumeData
except ImportError:  # pragma: no cover - import fallback for `uvicorn main:app`
    from resume_parser import ResumeData


class MatchError(ValueError):
    """Raised when the LLM's match response does not meet the required contract."""


class ResumeMatcher(Protocol):
    """The narrow LLM interface used by matching code."""

    def match_resume(self, resume_json: dict[str, Any], jd_text: str) -> dict[str, Any]:
        """Return a structured scoring result."""


@dataclass(frozen=True)
class MatchData:
    """Validated score and explanation for a candidate-job pair."""

    score: int
    justification: str
    matched_skills: list[str]
    missing_skills: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Return the match data as a plain dictionary."""
        return asdict(self)


def _string_list(value: Any, field_name: str) -> list[str]:
    """Validate that an optional match field is an array of strings."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MatchError(f"Match field '{field_name}' must be an array of strings.")
    return [item.strip() for item in value if item.strip()]


def normalize_match_data(payload: dict[str, Any]) -> MatchData:
    """Validate and normalize the strict JSON contract in the matching prompt."""
    required_fields = {"score", "justification", "matched_skills", "missing_skills"}
    missing = required_fields.difference(payload)
    if missing:
        raise MatchError(f"Match JSON omitted required fields: {', '.join(sorted(missing))}.")
    score = payload["score"]
    if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 10:
        raise MatchError("Match field 'score' must be an integer from 1 to 10.")
    justification = payload["justification"]
    if not isinstance(justification, str) or not justification.strip():
        raise MatchError("Match field 'justification' must be a non-empty string.")
    return MatchData(
        score=score,
        justification=justification.strip(),
        matched_skills=_string_list(payload["matched_skills"], "matched_skills"),
        missing_skills=_string_list(payload["missing_skills"], "missing_skills"),
    )


def match_resume(resume: ResumeData, jd_text: str, matcher: ResumeMatcher) -> MatchData:
    """Request and validate a candidate score for a given job description."""
    if not jd_text.strip():
        raise MatchError("A non-empty job description is required for matching.")
    return normalize_match_data(matcher.match_resume(resume.to_dict(), jd_text))
