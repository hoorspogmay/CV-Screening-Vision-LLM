# Talent Screen — AI IT Resume Screening System

A minimal, focused application that accepts multiple IT resumes (PDF/DOCX),
screens each one with an LLM against a built-in general-IT job profile, and
sorts them into **Accepted** / **Rejected** in real time. Results can be
exported to CSV.

## Project structure

```
ats-screening/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app entrypoint
│   │   ├── config.py                  # Settings (.env driven)
│   │   ├── models/schemas.py          # Pydantic models
│   │   ├── routes/screening.py        # /api/screening endpoints (upload, WS, export)
│   │   ├── services/
│   │   │   ├── ai_provider.py         # Provider factory / registry (the ONE switch point)
│   │   │   ├── prompts.py             # Shared IT screening prompt
│   │   │   ├── resume_service.py      # Job manager + concurrent processing
│   │   │   └── providers/
│   │   │       ├── base.py            # AIProvider abstract interface
│   │   │       └── groq_provider.py   # Default provider (Groq)
│   │   └── utils/
│   │       ├── file_utils.py          # PDF / DOCX text extraction
│   │       └── csv_export.py          # CSV generation
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.jsx
    │   ├── components/                # Navbar, UploadArea, ProgressPanel, ResultsPanel, CandidateCard, etc.
    │   ├── hooks/                     # useScreeningJob (upload + WebSocket), useToasts
    │   ├── utils/api.js                # fetch / WebSocket helpers
    │   └── styles/                    # global.css (tokens) + app.css (components)
    ├── index.html
    ├── vite.config.js
    └── package.json
```

## How it works

1. The recruiter drops in PDF/DOCX resumes (or a whole folder) and clicks **Start Screening**.
2. The frontend uploads all files in one request to `POST /api/screening/start`, which returns a `job_id` and immediately kicks off background processing.
3. The frontend opens a WebSocket to `/api/screening/ws/{job_id}`. Each resume is extracted and sent to the AI provider **concurrently** (bounded by `MAX_CONCURRENT_EVALUATIONS`); as soon as one finishes, it's broadcast over the socket and appears instantly in the Accepted or Rejected panel.
4. A resume that fails to extract or evaluate is logged as an error and processing continues for the rest of the batch — one bad file never stops the job.
5. Once every resume has been processed, **Export CSV** downloads `Candidate Name, File Name, Decision, Skills Summary, Education Summary, Experience Summary, Reason` for the batch.

## Switching AI providers

The app defaults to **Groq**. To use a different provider, only two things change — no other file is touched:

1. Implement a new class in `backend/app/services/providers/<name>_provider.py` that satisfies the `AIProvider` interface (`evaluate_resume`).
2. Register it in `backend/app/services/ai_provider.py`'s `PROVIDER_REGISTRY`, then set `AI_PROVIDER=<name>` in `.env`.

## Setup & installation

### Backend (Python 3.10+, FastAPI)

```bash
cd backend
python -m venv .venv
# Windows (Git Bash):
source .venv/Scripts/activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and set GROQ_API_KEY=your_real_key
```

Run the API from the backend folder:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API is now live at `http://localhost:8000` (health check: `GET /api/health`).

### Frontend (Node 18+, React + Vite)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` requests (including the WebSocket) to `http://localhost:8000`, so both servers just need to be running side by side — no extra config.

### Production build

```bash
cd frontend
npm run build       # outputs frontend/dist
```

Serve `frontend/dist` with any static host, and point it at your deployed backend (update `vite.config.js` proxy target, or serve both behind the same reverse proxy).

## Notes

- No login, dashboard, ranking, or analytics — by design, this app does exactly one thing.
- Resumes are written to a temporary directory per job and are not persisted after processing.
- If you rotate your Groq key, just update `GROQ_API_KEY` in `.env` and restart the backend.
