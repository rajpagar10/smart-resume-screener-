"""File text extraction and validation of LLM-produced resume data."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import pdfplumber


class ResumeParseError(ValueError):
    """Raised when a resume file or its extracted schema is not usable."""


class ResumeExtractor(Protocol):
    """The narrow LLM interface needed by the resume parser."""

    def extract_resume(self, resume_text: str) -> dict[str, Any]:
        """Return a structured resume payload."""


@dataclass(frozen=True)
class ResumeData:
    """Validated, database-ready structured resume fields."""

    name: str
    email: str
    phone: str
    skills: list[str]
    experience: list[Any]
    education: list[Any]

    def to_dict(self) -> dict[str, Any]:
        """Return this resume data as an API and prompt-friendly dictionary."""
        return asdict(self)


def _as_text(value: Any, field_name: str) -> str:
    """Validate scalar text values, making absent values an empty string."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ResumeParseError(f"Resume field '{field_name}' must be a string.")
    return value.strip()


def _as_list(value: Any, field_name: str) -> list[Any]:
    """Validate list fields and provide an empty list for omitted fields."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ResumeParseError(f"Resume field '{field_name}' must be an array.")
    return value


def normalize_resume_data(payload: dict[str, Any]) -> ResumeData:
    """Ensure an LLM result conforms to the application's stable resume schema."""
    required_fields = {"name", "email", "phone", "skills", "experience", "education"}
    missing = required_fields.difference(payload)
    if missing:
        raise ResumeParseError(f"Resume JSON omitted required fields: {', '.join(sorted(missing))}.")
    skills = _as_list(payload["skills"], "skills")
    if not all(isinstance(skill, str) for skill in skills):
        raise ResumeParseError("Resume field 'skills' must contain only strings.")
    return ResumeData(
        name=_as_text(payload["name"], "name"),
        email=_as_text(payload["email"], "email"),
        phone=_as_text(payload["phone"], "phone"),
        skills=[skill.strip() for skill in skills if skill.strip()],
        experience=_as_list(payload["experience"], "experience"),
        education=_as_list(payload["education"], "education"),
    )


def parse_resume_text(raw_text: str, extractor: ResumeExtractor) -> ResumeData:
    """Ask the LLM to convert meaningful resume text into validated structured data."""
    if not raw_text.strip():
        raise ResumeParseError("The resume contains no extractable text.")
    return normalize_resume_data(extractor.extract_resume(raw_text))


def extract_text_from_bytes(filename: str, content: bytes) -> str:
    """Read UTF-8 text or text-based PDFs, rejecting unsupported or empty files."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".txt":
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ResumeParseError("Text files must be UTF-8 encoded.") from exc
    elif suffix == ".pdf":
        try:
            with pdfplumber.open(BytesIO(content)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ResumeParseError("The PDF could not be read. Upload a valid text-based PDF.") from exc
    else:
        raise ResumeParseError("Only PDF and TXT files are supported.")
    if not text.strip():
        raise ResumeParseError("The uploaded file contains no extractable text.")
    return text.strip()
