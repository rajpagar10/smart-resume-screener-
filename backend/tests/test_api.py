"""API-level response shape test using a temporary SQLite database and fake Claude."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend import database, main


class FakeClaudeClient:
    """Fake client that makes the endpoint test deterministic and offline."""

    def extract_resume(self, resume_text: str) -> dict[str, Any]:
        """Return structured data for the uploaded fake resume."""
        return {
            "name": "Avery Chen",
            "email": "avery@example.com",
            "phone": "",
            "skills": ["Python", "FastAPI", "SQL"],
            "experience": [{"title": "Backend Engineer"}],
            "education": [],
        }

    def match_resume(self, resume_json: dict[str, Any], jd_text: str) -> dict[str, Any]:
        """Return a valid high-confidence recruiter result."""
        return {
            "score": 9,
            "justification": "Avery has the core requested backend skills. Their experience directly aligns with the role.",
            "matched_skills": ["Python", "FastAPI", "SQL"],
            "missing_skills": [],
        }


@pytest.fixture
def client(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Provide an isolated app client without demo rows or network calls."""
    database.configure_database(f"sqlite:///{tmp_path / 'test.db'}")
    database.initialize_database(seed_demo=False)
    monkeypatch.setattr(main, "initialize_database", lambda seed_demo=True: None)
    monkeypatch.setattr(main, "ClaudeClient", FakeClaudeClient)
    with TestClient(main.app) as test_client:
        yield test_client
    database.engine.dispose()


def test_candidates_endpoint_returns_ranked_response_shape(client: TestClient) -> None:
    """Uploading and evaluating should return the documented candidate table shape."""
    jd_response = client.post("/upload-jd", data={"text": "Python FastAPI backend engineer"})
    assert jd_response.status_code == 200

    upload_response = client.post(
        "/upload-resumes",
        files=[("files", ("avery.txt", b"Avery Chen\nPython FastAPI SQL", "text/plain"))],
    )
    assert upload_response.status_code == 200
    assert client.post("/evaluate").json()["evaluated"] == 1

    response = client.get("/candidates")
    assert response.status_code == 200
    candidate = response.json()[0]
    assert set(candidate) == {
        "id",
        "name",
        "email",
        "score",
        "matched_skills",
        "missing_skills",
        "justification",
        "shortlisted",
    }
    assert candidate["score"] == 9
    assert candidate["shortlisted"] is True
