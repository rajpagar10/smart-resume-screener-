"""Unit tests for LLM match-score validation."""

from typing import Any

from backend.matcher import MatchData, match_resume
from backend.resume_parser import ResumeData


class FakeMatcher:
    """Minimal fake that returns a valid recruiter assessment."""

    def match_resume(self, resume_json: dict[str, Any], jd_text: str) -> dict[str, Any]:
        """Return a fixed result after checking the passed context."""
        assert resume_json["skills"] == ["Python", "FastAPI"]
        assert "backend" in jd_text.lower()
        return {
            "score": 8,
            "justification": "The candidate has the core backend skills and relevant experience. AWS is the only clear gap.",
            "matched_skills": ["Python", "FastAPI"],
            "missing_skills": ["AWS"],
        }


def test_match_resume_returns_score_and_skill_gaps() -> None:
    """A valid LLM payload should become a typed match result."""
    resume = ResumeData(
        name="Ada Lovelace",
        email="ada@example.com",
        phone="",
        skills=["Python", "FastAPI"],
        experience=[],
        education=[],
    )

    result: MatchData = match_resume(resume, "Senior backend developer with AWS", FakeMatcher())

    assert result.score == 8
    assert result.matched_skills == ["Python", "FastAPI"]
    assert result.missing_skills == ["AWS"]
