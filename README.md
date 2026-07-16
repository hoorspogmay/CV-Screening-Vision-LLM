# Talent Screen — AI Resume Screening System

A lightweight full-stack application for screening multiple resumes (PDF/DOCX) against recruiter-defined job requirements. It evaluates each candidate with an LLM, applies deterministic hiring-policy rules, and presents results in real time with CSV export support.

The system now supports generic job requirements rather than a fixed IT-only profile, including:

- variable job role and education requirements
- configurable minimum/maximum experience
- required skill lists
- overqualification handling
- richer recruiter-style reasoning guidance

## Project structure

```text
ats-screening/
├── backend/
│   ├── app/
│   │   ├── ai_provider.py            # provider factory and fallback logic
│   │   ├── config.py                 # environment-driven settings
│   │   ├── csv_export.py             # CSV generation for screening results
│   │   ├── file_utils.py             # PDF / DOCX text extraction
│   │   ├── google_provider.py        # Google/Gemini provider
│   │   ├── groq_provider.py          # Groq provider
│   │   ├── job_requirements.py       # job requirement schema
│   │   ├── job_rules.py              # deterministic hiring-policy rules
│   │   ├── main.py                   # FastAPI entrypoint
│   │   ├── openrouter_provider.py    # OpenRouter provider
│   │   ├── prompts.py                # generalized system prompt and user prompt builder
│   │   ├── providers_base.py         # AI provider interface
│   │   ├── resume_service.py         # job state, concurrency, result finalization
│   │   ├── schemas.py                # Pydantic models
│   │   └── screening.py              # upload, WebSocket, and export routes
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── components/               # UI panels, cards, navbar, upload area, toast container
    │   ├── hooks/                    # screening job + toast hooks
    │   ├── utils/api.js              # frontend API and WebSocket helpers
    │   └── styles/                   # app.css + global.css
    ├── index.html
    ├── package.json
    └── vite.config.js
```

## How it works

1. A recruiter uploads one or more PDF/DOCX resumes and optionally supplies a JSON payload of job requirements.
2. The frontend sends the files to `POST /api/screening/start`, which creates a job and starts background screening.
3. The backend extracts resume text, sends it to the selected AI provider, and applies deterministic hiring-policy rules.
4. Results are streamed to the UI over WebSocket as each resume completes.
5. The job can be exported as CSV through `GET /api/screening/export/{job_id}`.

## AI providers

The app currently supports multiple providers through a simple factory pattern:

- Groq
- OpenRouter
- Google/Gemini

The active provider is selected from the environment via `AI_PROVIDER` in the backend `.env` file.

## Setup and run

### Backend (Python 3.10+)

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Then edit `.env` and provide the key for your chosen provider, for example:

```env
AI_PROVIDER=groq
GROQ_API_KEY=your_real_key
```

Run the API:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/health
```

### Frontend (Node 18+)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Example requirement payload

The backend accepts a JSON payload in the `requirements` form field for flexible screening. Example:

```json
{
  "job_role": "Software Engineer",
  "required_education": "Bachelor",
  "min_experience": 3,
  "max_experience": 8,
  "required_skills": ["Python", "FastAPI", "PostgreSQL"],
  "allow_overqualified": false,
  "allow_internships": false
}
```

## Notes

- Resumes are stored in a temporary directory per job and are not persisted after processing.
- One failed resume does not stop the rest of the batch.
- CSV export includes the original reasoning text in the `Reason` column when available.
- The app is intentionally focused on one workflow: upload resumes, screen them, review results, and export them.
