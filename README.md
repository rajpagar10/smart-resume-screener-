# Smart Resume Screener

Smart Resume Screener is a lightweight, full-stack applicant-screening tool. It accepts PDF or UTF-8 text resumes and a job description, uses Claude Sonnet 4.6 to turn resumes into structured evidence, and produces a recruiter-readable 1–10 fit score with matched and missing skills. The dashboard highlights candidates scoring 7 or higher.

The repository starts with one demo job description and three high-scoring built-in demo resumes/results, so the ranked dashboard is useful immediately. Live evaluation requires an Anthropic API key with available API credits.

## Architecture

```text
PDF/TXT resumes + JD
        │
        ▼
 FastAPI upload endpoints
        │
        ├── PDF/TXT text parser (pdfplumber / UTF-8)
        │          │
        │          ▼
        │  Claude extraction ──► structured resume JSON
        │                              │
        │                              ▼
        └──────────────────────► Claude matching (score + rationale)
                                       │
                                       ▼
                                  SQLite / SQLAlchemy
                                       │
                                       ▼
                              FastAPI ranked candidate API
                                       │
                                       ▼
                              React + Vite dashboard
```

## Repository layout

```text
smart-resume-screener/
├── backend/
│   ├── prompts/
│   │   ├── extract_prompt.txt
│   │   └── match_prompt.txt
│   ├── tests/
│   │   ├── test_api.py
│   │   ├── test_matcher.py
│   │   └── test_resume_parser.py
│   ├── database.py
│   ├── llm_client.py
│   ├── main.py
│   ├── matcher.py
│   ├── models.py
│   ├── requirements.txt
│   └── resume_parser.py
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── .env.example
├── .gitignore
└── README.md
```

`backend/smart_resume.db` is created locally on first launch and deliberately ignored by Git. The three demo records live in `backend/database.py`, keeping the repo small and avoiding committed binary data.

## Exact LLM prompts

`backend/prompts/extract_prompt.txt`

```text
You are an expert resume parser. Convert the resume text below into a JSON object with exactly these keys:
"name", "email", "phone", "skills", "experience", "education".

Rules:
- Return strict JSON only, with no Markdown code fences or commentary.
- Use empty strings for unavailable name, email, or phone values.
- Use arrays for skills, experience, and education. Each experience and education item may be a concise object or string when details are limited.
- Do not invent details that are not present in the resume.

Example resume:
Jane Doe | jane@example.com | +1 555 0100
Skills: Python, FastAPI, SQL
Experience: Backend Engineer at Acme, 2021-2024
Education: BSc Computer Science, State University, 2021

Example output:
{"name":"Jane Doe","email":"jane@example.com","phone":"+1 555 0100","skills":["Python","FastAPI","SQL"],"experience":[{"title":"Backend Engineer","company":"Acme","dates":"2021-2024"}],"education":[{"degree":"BSc Computer Science","institution":"State University","year":"2021"}]}

Resume text:
{resume_text}
```

`backend/prompts/match_prompt.txt`

```text
You are a technical recruiter. Compare the following resume with the job description.
Resume: {resume_json}
Job Description: {jd_text}
Rate the candidate's fit on a scale of 1–10.
Return strict JSON: {"score": <int>, "justification": "<2-3 sentence explanation>", "matched_skills": [...], "missing_skills": [...]}
```

## Setup and run

Prerequisites: Python 3.10+ and Node.js 18+.

1. Create the Python environment and install only the backend/test dependencies:

   ```powershell
   cd smart-resume-screener
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend/requirements.txt
   ```

2. Create an Anthropic API key in the [Anthropic Console](https://console.anthropic.com/), then set it in the shell that starts FastAPI:

   ```powershell
   $env:ANTHROPIC_API_KEY = "your_anthropic_api_key_here"
   ```

   Live requests use the fixed `claude-sonnet-4-6` model. Never commit the key.

3. Start the API from the project root:

   ```powershell
   uvicorn backend.main:app --reload
   ```

   The API is available at `http://localhost:8000`; interactive OpenAPI docs are at `http://localhost:8000/docs`.

4. In a second terminal, start the dashboard:

   ```powershell
   cd smart-resume-screener/frontend
   npm install
   npm run dev
   ```

   Open the URL Vite prints (normally `http://localhost:5173`). The seeded candidates are visible even before a live Claude evaluation.

5. Run the test suite from the project root:

   ```powershell
   pytest backend/tests -q
   ```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/upload-jd` | Upload a `.pdf`/`.txt` job description as `file`, or paste it in `text`. |
| `POST` | `/upload-resumes` | Upload one or more `.pdf`/`.txt` files in multipart field `files`. |
| `POST` | `/evaluate` | Extract and score all stored resumes against the latest job description. |
| `GET` | `/candidates` | Get candidates for the latest job, ranked by score descending. |
| `GET` | `/candidates/{id}` | Get a candidate's full parsed detail and current-job result. |

Example PowerShell requests:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/upload-jd -Form @{ text = 'Senior Python FastAPI engineer with SQL and AWS' }
Invoke-RestMethod -Method Post http://localhost:8000/upload-resumes -Form @{ files = Get-Item .\resume.txt }
Invoke-RestMethod -Method Post http://localhost:8000/evaluate
Invoke-RestMethod http://localhost:8000/candidates
```

Example `GET /candidates` response:

```json
[
  {
    "id": 1,
    "name": "Maya Patel",
    "email": "maya@example.com",
    "score": 9,
    "matched_skills": ["Python", "FastAPI", "SQL", "Docker", "AWS", "CI/CD"],
    "missing_skills": [],
    "justification": "Maya has six years of directly relevant backend experience and covers the core requirements.",
    "shortlisted": true
  }
]
```

## Tech choices

- **FastAPI** provides typed, documented multipart and JSON APIs with little framework overhead.
- **SQLite + SQLAlchemy** makes the project downloadable and durable without an external database service.
- **pdfplumber** extracts text from text-based PDFs; plain text resumes need no extra parser.
- **Anthropic Claude `claude-sonnet-4-6`** performs the two tasks requiring judgment. `backend/llm_client.py` is the only module that touches the Anthropic API.
- **React + Vite** gives a compact dashboard with a fast local development path and no component-library dependency.

## Reliability and limitations

- Invalid file types and unreadable/empty files receive clear `400` responses. Claude API errors and malformed JSON are retried once, then included as a safe batch evaluation error instead of crashing the server.
- Only text-based PDFs are supported. Scanned image PDFs need OCR, which is intentionally not included to keep dependencies small.
- LLM scores are decision support, not an automated hiring decision. Add human review, audit logging, bias testing, role-specific rubrics, data retention controls, and access controls before production use.
- Future improvements: deduplicate uploaded resumes, support OCR and DOCX, add user authentication, isolate jobs into projects, make rubric weights configurable, and add asynchronous batch processing for larger candidate sets.

## Screenshot

<img width="1582" height="912" alt="Screenshot 2026-07-15 000009" src="https://github.com/user-attachments/assets/ae1fe484-955b-4a03-bc66-c19ee653c5ac" />

# Demo Video

https://github.com/user-attachments/assets/8437eefb-7463-4144-98e8-6c34964367f2




