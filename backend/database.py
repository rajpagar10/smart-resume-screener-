"""Database setup, dependency injection, and a small built-in demo dataset."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

try:  # Supports both `uvicorn backend.main:app` and `uvicorn main:app` from backend/.
    from .models import Base, Candidate, JobDescription, MatchResult
except ImportError:  # pragma: no cover - exercised only by the direct module launch path
    from models import Base, Candidate, JobDescription, MatchResult


BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'smart_resume.db'}"
DATABASE_URL = os.getenv("SMART_RESUME_DATABASE_URL", DEFAULT_DATABASE_URL)


def _create_engine(database_url: str) -> Engine:
    """Create an SQLAlchemy engine with SQLite-safe connection settings."""
    options: dict[str, Any] = {}
    if database_url.startswith("sqlite"):
        options["connect_args"] = {"check_same_thread": False}
    return create_engine(database_url, **options)


engine = _create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_database(database_url: str) -> None:
    """Point the module at another database, primarily for isolated tests."""
    global DATABASE_URL, engine, SessionLocal
    engine.dispose()
    DATABASE_URL = database_url
    engine = _create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


DEMO_JOB_FILENAME = "demo-backend-engineer-jd.txt"
DEMO_JOB_TEXT = (
    "Senior Backend Engineer. Build Python/FastAPI services, design REST APIs, "
    "work with PostgreSQL or SQL, Docker, AWS, CI/CD, and React-adjacent product teams. "
    "Requires 4+ years of backend experience."
)


def _demo_candidate_payloads() -> list[dict[str, Any]]:
    """Return three strong, internally consistent candidates for the built-in showcase."""
    return [
        {
            "source_filename": "maya_patel_demo.txt",
            "raw_text": "Maya Patel\nmaya@example.com\nSkills: Python, FastAPI, PostgreSQL, Docker, AWS, CI/CD, REST APIs\nSenior Backend Engineer, Orbit Labs, 2020-2026\nB.Tech Computer Science, 2020",
            "name": "Maya Patel", "email": "maya@example.com", "phone": "+91 90000 10001",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "CI/CD", "REST APIs"],
            "experience": [{"title": "Senior Backend Engineer", "company": "Orbit Labs", "dates": "2020-2026"}],
            "education": [{"degree": "B.Tech Computer Science", "year": "2020"}],
            "score": 10,
            "justification": "Maya exceeds every core requirement with six years of senior Python backend experience and direct FastAPI, PostgreSQL, Docker, AWS, and CI/CD delivery. Her API design background makes her an immediate, low-risk fit for the role.",
            "matched_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "CI/CD", "REST APIs"],
            "missing_skills": [],
        },
        {
            "source_filename": "noah_kim_demo.txt",
            "raw_text": "Noah Kim\nnoah@example.com\nSkills: Python, FastAPI, PostgreSQL, Docker, CI/CD, REST APIs\nBackend Developer, Northstar, 2021-2026\nBSc Software Engineering, 2021",
            "name": "Noah Kim", "email": "noah@example.com", "phone": "+1 555 0102",
            "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "CI/CD", "REST APIs"],
            "experience": [{"title": "Backend Developer", "company": "Northstar", "dates": "2021-2026"}],
            "education": [{"degree": "BSc Software Engineering", "year": "2021"}],
            "score": 9,
            "justification": "Noah brings five years of directly relevant Python and FastAPI experience, with strong PostgreSQL, Docker, REST API, and CI/CD evidence. AWS delivery is not explicit, but his backend foundation is an excellent match.",
            "matched_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "CI/CD", "REST APIs"],
            "missing_skills": ["AWS"],
        },
        {
            "source_filename": "priya_shah_demo.txt",
            "raw_text": "Priya Shah\npriya@example.com\nSkills: Python, FastAPI, SQL, Docker, AWS, REST APIs\nBackend Engineer, Pixel House, 2022-2026\nB.Tech Information Technology, 2022",
            "name": "Priya Shah", "email": "priya@example.com", "phone": "+91 90000 10003",
            "skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "REST APIs"],
            "experience": [{"title": "Backend Engineer", "company": "Pixel House", "dates": "2022-2026"}],
            "education": [{"degree": "B.Tech Information Technology", "year": "2022"}],
            "score": 8,
            "justification": "Priya has four years of practical Python backend experience with FastAPI, SQL, Docker, AWS, and REST APIs. The resume has lighter CI/CD evidence, but she is a strong shortlist candidate with highly relevant delivery skills.",
            "matched_skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "REST APIs"],
            "missing_skills": ["CI/CD"],
        },
    ]


def load_demo_showcase(session: Session) -> JobDescription:
    """Make a fresh showcase active without deleting any non-demo uploads."""
    job = JobDescription(source_filename=DEMO_JOB_FILENAME, text=DEMO_JOB_TEXT)
    session.add(job)
    session.flush()
    for payload in _demo_candidate_payloads():
        score = payload.pop("score")
        justification = payload.pop("justification")
        matched_skills = payload.pop("matched_skills")
        missing_skills = payload.pop("missing_skills")
        candidate = session.scalar(
            select(Candidate).where(Candidate.source_filename == payload["source_filename"]).limit(1)
        )
        if candidate is None:
            candidate = Candidate(**payload)
            session.add(candidate)
        else:
            for field_name, field_value in payload.items():
                setattr(candidate, field_name, field_value)
        session.flush()
        session.add(MatchResult(candidate_id=candidate.id, job_description_id=job.id, score=score,
                                justification=justification, matched_skills=matched_skills,
                                missing_skills=missing_skills))
    session.commit()
    return job


def _seed_demo_data(session: Session) -> None:
    """Insert the showcase only when the database has never received a job description."""
    if session.scalar(select(JobDescription.id).limit(1)) is None:
        load_demo_showcase(session)


def initialize_database(seed_demo: bool = True) -> None:
    """Create tables and optionally make the first run dashboard demo-ready."""
    Base.metadata.create_all(bind=engine)
    if seed_demo:
        with SessionLocal() as session:
            _seed_demo_data(session)
