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


def _seed_demo_data(session: Session) -> None:
    """Insert three compact, pre-scored demo candidates when the database is empty."""
    if session.scalar(select(JobDescription.id).limit(1)) is not None:
        return

    job = JobDescription(
        source_filename="demo-backend-engineer-jd.txt",
        text=(
            "Senior Backend Engineer. Build Python/FastAPI services, design REST APIs, "
            "work with PostgreSQL or SQL, Docker, AWS, CI/CD, and React-adjacent product teams. "
            "Requires 4+ years of backend experience."
        ),
    )
    session.add(job)
    session.flush()

    demo_candidates: list[dict[str, Any]] = [
        {
            "source_filename": "maya_patel_demo.txt",
            "raw_text": "Maya Patel\nmaya@example.com\nSkills: Python, FastAPI, SQL, Docker, AWS, CI/CD\nSenior Backend Engineer, Orbit Labs, 2020-2026\nB.Tech Computer Science, 2020",
            "name": "Maya Patel",
            "email": "maya@example.com",
            "phone": "+91 90000 10001",
            "skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "CI/CD"],
            "experience": [{"title": "Senior Backend Engineer", "company": "Orbit Labs", "dates": "2020-2026"}],
            "education": [{"degree": "B.Tech Computer Science", "year": "2020"}],
            "score": 9,
            "justification": "Maya has six years of directly relevant backend experience and covers the core Python, FastAPI, SQL, Docker, AWS, and CI/CD requirements. Her senior engineering background is a strong match for the role.",
            "matched_skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "CI/CD"],
            "missing_skills": [],
        },
        {
            "source_filename": "noah_kim_demo.txt",
            "raw_text": "Noah Kim\nnoah@example.com\nSkills: Python, Django, PostgreSQL, Docker, REST APIs\nBackend Developer, Northstar, 2021-2026\nBSc Software Engineering, 2021",
            "name": "Noah Kim",
            "email": "noah@example.com",
            "phone": "+1 555 0102",
            "skills": ["Python", "Django", "PostgreSQL", "Docker", "REST APIs"],
            "experience": [{"title": "Backend Developer", "company": "Northstar", "dates": "2021-2026"}],
            "education": [{"degree": "BSc Software Engineering", "year": "2021"}],
            "score": 8,
            "justification": "Noah has five years of relevant Python backend experience and strong REST, PostgreSQL, and Docker exposure. FastAPI, AWS, and CI/CD evidence is not explicit, but his foundation is highly transferable.",
            "matched_skills": ["Python", "PostgreSQL", "Docker", "REST APIs"],
            "missing_skills": ["FastAPI", "AWS", "CI/CD"],
        },
        {
            "source_filename": "priya_shah_demo.txt",
            "raw_text": "Priya Shah\npriya@example.com\nSkills: JavaScript, React, CSS, Figma\nFrontend Developer, Pixel House, 2022-2026\nBA Design, 2022",
            "name": "Priya Shah",
            "email": "priya@example.com",
            "phone": "+91 90000 10003",
            "skills": ["JavaScript", "React", "CSS", "Figma"],
            "experience": [{"title": "Frontend Developer", "company": "Pixel House", "dates": "2022-2026"}],
            "education": [{"degree": "BA Design", "year": "2022"}],
            "score": 4,
            "justification": "Priya offers useful React collaboration context but her recent work is frontend-focused. The resume does not show the required Python backend, database, cloud, or container experience.",
            "matched_skills": ["React"],
            "missing_skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "CI/CD"],
        },
    ]

    for candidate_data in demo_candidates:
        score = candidate_data.pop("score")
        justification = candidate_data.pop("justification")
        matched_skills = candidate_data.pop("matched_skills")
        missing_skills = candidate_data.pop("missing_skills")
        candidate = Candidate(**candidate_data)
        session.add(candidate)
        session.flush()
        session.add(
            MatchResult(
                candidate_id=candidate.id,
                job_description_id=job.id,
                score=score,
                justification=justification,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
            )
        )
    session.commit()


def initialize_database(seed_demo: bool = True) -> None:
    """Create tables and optionally make the first run dashboard demo-ready."""
    Base.metadata.create_all(bind=engine)
    if seed_demo:
        with SessionLocal() as session:
            _seed_demo_data(session)
