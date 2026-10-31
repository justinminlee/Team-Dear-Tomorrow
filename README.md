<<<<<<< HEAD
# Team-Dear-Tomorrow
=======
# ALT+ME — Future Me AI

> Meet the person you might become. Hackathon theme: **What If…?**

Talk to a hypothetical future version of yourself. Not a prediction, an exploration.

## Team
| Name | Role |
|---|---|
| Justin | Team Lead, AI and Backend |
| Jack | Frontend, UI and UX |
| Peter | Voice, Data and Integration |

## Structure
```
alt-me/
  frontend/   Next.js (App Router) + TypeScript + Tailwind
  backend/    FastAPI + SQLite + LLM provider abstraction
  docs/       Architecture and demo notes
  .env.example
```

## Setup (fresh Mac)
Full instructions will be completed once the code is generated. Quick outline:

```bash
cp .env.example backend/.env        # then fill in ANTHROPIC_API_KEY
cd backend && uv venv && source .venv/bin/activate && uv pip install -r requirements.txt
uvicorn app.main:app --reload       # http://localhost:8000
cd ../frontend && pnpm install && pnpm dev   # http://localhost:3000
```

## Git workflow
- `main`: always demo-ready, no direct pushes
- One branch per person per feature: `justin/backend-api`, `jack/chat-ui`, `peter/voice`
- Open a Pull Request, get one review, then merge
- Never commit `.env` or API keys
>>>>>>> 03e7afe (Initial commit)
