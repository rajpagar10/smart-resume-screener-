"""FastAPI application for uploading, evaluating, and ranking resumes."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

try:  # Supports both package and `backend/` working-directory launches.
    from .database import get_db, initialize_database
    from .llm_client import GroqClient, LLMClientError
    from .matcher import MatchData, MatchError, match_resume
    from .models import Candidate, JobDescription, MatchResult
    from .resume_parser import ResumeData, ResumeParseError, extract_text_from_bytes, parse_resume_text
except ImportError:  # pragma: no cover - import fallback for `uvicorn main:app`
    from database import get_db, initialize_database
    from llm_client import GroqClient, LLMClientError
    from matcher import MatchData, MatchError, match_resume
    from models import Candidate, JobDescription, MatchResult
    from resume_parser import ResumeData, ResumeParseError, extract_text_from_bytes, parse_resume_text


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create database tables and the first-run demo dataset at application startup."""
    initialize_database(seed_demo=True)
    yield


app = FastAPI(title="Smart Resume Screener API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobDescriptionResponse(BaseModel):
    """Response returned after a job description is stored."""

    id: int
    source_filename: str | None
    text_length: int


class ResumeUploadResponse(BaseModel):
    """Response returned after raw resume files are stored."""

    uploaded: int
    candidate_ids: list[int]


class EvaluationResponse(BaseModel):
    """A non-crashing summary of an evaluation batch."""

    evaluated: int
    failed: int
    errors: list[str] = Field(default_factory=list)


class CandidateSummary(BaseModel):
    """Ranked candidate data used by the dashboard table."""

    id: int
    name: str
    email: str
    score: int
    matched_skills: list[str]
    missing_skills: list[str]
    justification: str
    shortlisted: bool


class CandidateDetail(CandidateSummary):
    """Full structured detail for an individual candidate."""

    source_filename: str
    phone: str
    skills: list[Any]
    experience: list[Any]
    education: list[Any]
    raw_text: str
    job_description_id: int | None


def _latest_job_description(session: Session) -> JobDescription | None:
    """Return the most recently submitted job description."""
    return session.scalar(select(JobDescription).order_by(JobDescription.id.desc()).limit(1))


def _candidate_summary(candidate: Candidate, result: MatchResult) -> CandidateSummary:
    """Map ORM entities to the stable ranked-candidate response shape."""
    return CandidateSummary(
        id=candidate.id,
        name=candidate.name or "Unnamed candidate",
        email=candidate.email,
        score=result.score,
        matched_skills=result.matched_skills,
        missing_skills=result.missing_skills,
        justification=result.justification,
        shortlisted=result.score >= 7,
    )


def _save_parsed_resume(candidate: Candidate, parsed: ResumeData) -> None:
    """Copy validated parsed fields onto an existing candidate row."""
    candidate.name = parsed.name
    candidate.email = parsed.email
    candidate.phone = parsed.phone
    candidate.skills = parsed.skills
    candidate.experience = parsed.experience
    candidate.education = parsed.education


def _save_match_result(
    session: Session, candidate: Candidate, job: JobDescription, match: MatchData
) -> None:
    """Replace this candidate's prior result for the current job with a fresh result."""
    session.execute(
        delete(MatchResult).where(
            MatchResult.candidate_id == candidate.id,
            MatchResult.job_description_id == job.id,
        )
    )
    session.add(
        MatchResult(
            candidate_id=candidate.id,
            job_description_id=job.id,
            score=match.score,
            justification=match.justification,
            matched_skills=match.matched_skills,
            missing_skills=match.missing_skills,
        )
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    """Provide a lightweight service readiness endpoint."""
    return {"status": "ok"}


@app.post("/upload-jd", response_model=JobDescriptionResponse)
async def upload_job_description(
    file: Annotated[UploadFile | None, File(description="A PDF or TXT job description")] = None,
    text: Annotated[str | None, Form(description="Pasted job description text")] = None,
    session: Session = Depends(get_db),
) -> JobDescriptionResponse:
    """Store a pasted or uploaded job description and make it the current one."""
    if file is not None and text and text.strip():
        raise HTTPException(status_code=400, detail="Provide either a file or pasted text, not both.")
    try:
        if file is not None:
            filename = file.filename or "job-description.txt"
            jd_text = extract_text_from_bytes(filename, await file.read())
            source_filename: str | None = filename
        elif text and text.strip():
            jd_text = text.strip()
            source_filename = None
        else:
            raise ResumeParseError("Provide a non-empty job description as text or a PDF/TXT file.")
    except ResumeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = JobDescription(text=jd_text, source_filename=source_filename)
    session.add(job)
    session.commit()
    session.refresh(job)
    return JobDescriptionResponse(id=job.id, source_filename=job.source_filename, text_length=len(job.text))


@app.post("/upload-resumes", response_model=ResumeUploadResponse)
async def upload_resumes(
    files: Annotated[list[UploadFile], File(description="One or more PDF or TXT resumes")],
    session: Session = Depends(get_db),
) -> ResumeUploadResponse:
    """Validate and persist one or more raw resumes for later LLM evaluation."""
    prepared_files: list[tuple[str, str]] = []
    try:
        for upload in files:
            filename = upload.filename or "resume.txt"
            prepared_files.append((filename, extract_text_from_bytes(filename, await upload.read())))
    except ResumeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not prepared_files:
        raise HTTPException(status_code=400, detail="Upload at least one resume file.")
    candidates = [Candidate(source_filename=name, raw_text=raw_text) for name, raw_text in prepared_files]
    session.add_all(candidates)
    session.commit()
    for candidate in candidates:
        session.refresh(candidate)
    return ResumeUploadResponse(uploaded=len(candidates), candidate_ids=[candidate.id for candidate in candidates])


@app.post("/evaluate", response_model=EvaluationResponse)
def evaluate_resumes(session: Session = Depends(get_db)) -> EvaluationResponse:
    """Run Groq extraction and matching for every resume against the current job."""
    job = _latest_job_description(session)
    if job is None:
        raise HTTPException(status_code=400, detail="Upload a job description before evaluating resumes.")
    candidates = list(session.scalars(select(Candidate).order_by(Candidate.id.asc())))
    if not candidates:
        raise HTTPException(status_code=400, detail="Upload at least one resume before evaluating.")

    try:
        client = GroqClient()
    except LLMClientError as exc:
        return EvaluationResponse(evaluated=0, failed=len(candidates), errors=[str(exc)])

    evaluated = 0
    errors: list[str] = []
    for candidate in candidates:
        try:
            parsed = parse_resume_text(candidate.raw_text, client)
            match = match_resume(parsed, job.text, client)
            _save_parsed_resume(candidate, parsed)
            _save_match_result(session, candidate, job, match)
            session.commit()
            evaluated += 1
        except (LLMClientError, ResumeParseError, MatchError, ValueError) as exc:
            session.rollback()
            errors.append(f"{candidate.source_filename}: {exc}")
    return EvaluationResponse(evaluated=evaluated, failed=len(errors), errors=errors)


@app.get("/candidates", response_model=list[CandidateSummary])
def list_candidates(session: Session = Depends(get_db)) -> list[CandidateSummary]:
    """Return candidates for the current job, sorted from highest score to lowest."""
    job = _latest_job_description(session)
    if job is None:
        return []
    rows = session.execute(
        select(Candidate, MatchResult)
        .join(MatchResult, MatchResult.candidate_id == Candidate.id)
        .where(MatchResult.job_description_id == job.id)
        .order_by(MatchResult.score.desc(), Candidate.id.asc())
    ).all()
    return [_candidate_summary(candidate, match) for candidate, match in rows]


@app.get("/candidates/{candidate_id}", response_model=CandidateDetail)
def get_candidate(candidate_id: int, session: Session = Depends(get_db)) -> CandidateDetail:
    """Return the full parsed resume and current-job match result for one candidate."""
    candidate = session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    job = _latest_job_description(session)
    result: MatchResult | None = None
    if job is not None:
        result = session.scalar(
            select(MatchResult)
            .where(
                MatchResult.candidate_id == candidate.id,
                MatchResult.job_description_id == job.id,
            )
            .order_by(MatchResult.id.desc())
            .limit(1)
        )
    if result is None:
        raise HTTPException(status_code=404, detail="Candidate has not been evaluated for the current job.")
    summary = _candidate_summary(candidate, result)
    return CandidateDetail(
        **summary.model_dump(),
        source_filename=candidate.source_filename,
        phone=candidate.phone,
        skills=candidate.skills,
        experience=candidate.experience,
        education=candidate.education,
        raw_text=candidate.raw_text,
        job_description_id=job.id if job else None,
    )
