"""Unit tests for structured resume parsing."""

from typing import Any

from backend.resume_parser import ResumeData, parse_resume_text


class FakeExtractor:
    """Minimal fake that avoids a live Claude request."""

    def extract_resume(self, resume_text: str) -> dict[str, Any]:
        """Return a representative strict extraction response."""
        assert "Ada Lovelace" in resume_text
        return {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "phone": "+44 20 1234 5678",
            "skills": ["Python", "FastAPI"],
            "experience": [{"title": "Engineer", "company": "Analytical Co."}],
            "education": [{"degree": "BSc Mathematics"}],
        }


def test_parse_resume_text_returns_validated_schema() -> None:
    """The parser should return database-ready structured data from an LLM payload."""
    parsed: ResumeData = parse_resume_text("Ada Lovelace\nPython, FastAPI", FakeExtractor())

    assert parsed.name == "Ada Lovelace"
    assert parsed.skills == ["Python", "FastAPI"]
    assert parsed.experience[0]["title"] == "Engineer"
