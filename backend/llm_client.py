"""The sole integration point for Anthropic Claude API requests."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import anthropic


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
CLAUDE_MODEL = "claude-sonnet-4-6"


class LLMClientError(RuntimeError):
    """Raised when Claude cannot provide a valid structured result."""


def _read_prompt(filename: str) -> str:
    """Read a bundled prompt template using UTF-8."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _extract_json(response_text: str) -> dict[str, Any]:
    """Parse the JSON object returned by Claude, tolerating accidental fences."""
    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMClientError("Claude returned malformed JSON.") from exc
    if not isinstance(result, dict):
        raise LLMClientError("Claude returned JSON that was not an object.")
    return result


class ClaudeClient:
    """Small, retrying client for Claude's structured extraction and matching calls."""

    def __init__(self, api_key: str | None = None) -> None:
        """Create a client using an explicit key or ANTHROPIC_API_KEY."""
        resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not resolved_key:
            raise LLMClientError("ANTHROPIC_API_KEY is not configured.")
        self._client = anthropic.Anthropic(api_key=resolved_key)

    def _request_json(self, prompt: str) -> dict[str, Any]:
        """Call Claude and retry exactly once for API or malformed JSON failures."""
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = self._client.messages.create(
                    model=CLAUDE_MODEL,
                    max_tokens=1200,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = "".join(
                    block.text for block in response.content if getattr(block, "type", None) == "text"
                )
                return _extract_json(response_text)
            except (anthropic.APIError, LLMClientError, ValueError) as exc:
                last_error = exc
        raise LLMClientError("Claude request failed after one retry. Please try again later.") from last_error

    def extract_resume(self, resume_text: str) -> dict[str, Any]:
        """Extract the required structured resume schema from raw text using Claude."""
        prompt = _read_prompt("extract_prompt.txt").replace("{resume_text}", resume_text)
        return self._request_json(prompt)

    def match_resume(self, resume_json: dict[str, Any], jd_text: str) -> dict[str, Any]:
        """Score one structured resume against a job description using Claude."""
        prompt = _read_prompt("match_prompt.txt")
        prompt = prompt.replace("{resume_json}", json.dumps(resume_json, ensure_ascii=False))
        prompt = prompt.replace("{jd_text}", jd_text)
        return self._request_json(prompt)
