"""The sole integration point for Groq's fast free-tier chat-completions API."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "llama-3.3-70b-versatile"


class LLMClientError(RuntimeError):
    """Raised when Groq cannot provide valid structured data."""


def _read_prompt(filename: str) -> str:
    """Read a bundled prompt template using UTF-8."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _extract_json(response_text: str) -> dict[str, Any]:
    """Parse a JSON object, tolerating accidental Markdown code fences."""
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMClientError("Groq returned malformed JSON.") from exc
    if not isinstance(result, dict):
        raise LLMClientError("Groq returned JSON that was not an object.")
    return result


def _response_text(response: dict[str, Any]) -> str:
    """Extract assistant text from a successful OpenAI-compatible Groq response."""
    try:
        text = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        detail = response.get("error", {}).get("message", "No completion text was returned.")
        raise LLMClientError(f"Groq returned an unexpected response: {detail}") from exc
    if not isinstance(text, str) or not text.strip():
        raise LLMClientError("Groq returned an empty response.")
    return text


def _http_error_message(error: HTTPError) -> str:
    """Extract Groq's safe error reason without exposing request credentials."""
    try:
        body = json.loads(error.read().decode("utf-8"))
        detail = body.get("error", {}).get("message", "No error detail was returned.")
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        detail = "No error detail was returned."
    return f"Groq returned HTTP {error.code}: {detail}"


class GroqClient:
    """Small, retrying client for Groq's fast JSON Object Mode completions."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        """Configure Groq from GROQ_API_KEY and an optional model override."""
        resolved_key = api_key or os.getenv("GROQ_API_KEY")
        if not resolved_key:
            raise LLMClientError("GROQ_API_KEY is not configured.")
        self._api_key = resolved_key
        self._model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)

    def _request_json(self, prompt: str) -> dict[str, Any]:
        """Call Groq and retry exactly once for API or malformed JSON failures."""
        payload = json.dumps(
            {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": 1200,
            }
        ).encode("utf-8")
        request = Request(
            GROQ_API_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        last_error: Exception | None = None
        for _ in range(2):
            try:
                with urlopen(request, timeout=60) as response:
                    response_data = json.loads(response.read().decode("utf-8"))
                return _extract_json(_response_text(response_data))
            except HTTPError as exc:
                last_error = LLMClientError(_http_error_message(exc))
            except (URLError, OSError, ValueError, LLMClientError) as exc:
                last_error = exc
        raise LLMClientError(f"Groq request failed after one retry: {last_error}") from last_error

    def extract_resume(self, resume_text: str) -> dict[str, Any]:
        """Extract the required structured resume schema from raw text using Groq."""
        prompt = _read_prompt("extract_prompt.txt").replace("{resume_text}", resume_text)
        return self._request_json(prompt)

    def match_resume(self, resume_json: dict[str, Any], jd_text: str) -> dict[str, Any]:
        """Score one structured resume against a job description using Groq."""
        prompt = _read_prompt("match_prompt.txt")
        prompt = prompt.replace("{resume_json}", json.dumps(resume_json, ensure_ascii=False))
        prompt = prompt.replace("{jd_text}", jd_text)
        return self._request_json(prompt)
