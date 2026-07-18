# AI Cost Router

Intelligent task routing that selects the cheapest AI execution path and proves it with live cost tracking.

![Demo](docs/demo.gif)

## The Problem

Most AI systems route every task to a premium LLM. Extracting a date? Premium model. Classifying a sentence? Premium model. That is expensive and unnecessary.

## The Solution

| Tier | Execution | Cost | Example Tasks |
|------|-----------|------|---------------|
| LOCAL | Python regex / stdlib | $0.00 | Date extraction, word count, ticker parsing |
| SMALL | Gemini Flash | ~$0.0002 | Classification, sentiment, short summaries |
| PREMIUM | Claude / Gemini | ~$0.003 | Executive summaries, risk analysis, investment thesis |

Running 8 mixed tasks achieves **85%+ cost savings** vs sending everything to a premium model.

## Quick Start

**Backend**

    cd backend
    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env
    python -m uvicorn main:app --reload

**Frontend**

    cd frontend
    npm install
    npm run dev

Dashboard: http://localhost:5173 — Only GEMINI_API_KEY required. Get one free at https://aistudio.google.com/apikey

## Tech Stack

- Backend: Python 3.12, FastAPI, Pydantic v2, python-dotenv
- Frontend: React 18, Vite, Tailwind CSS v3, Recharts
- AI: Google Gemini (primary), OpenAI and Anthropic (optional fallbacks)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /routes | Full routing map and cost per tier |
| POST | /analyze | Single task routing and result |
| POST | /batch | Multiple tasks and aggregate savings summary |

## License

MIT
