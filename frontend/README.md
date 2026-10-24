# Study Agent — AI Learning Workspace

A React + TypeScript frontend for the Study Agentic AI application. The redesign keeps the existing Vite/Tailwind stack and API integration while introducing a dark navy, glass-inspired interface.

## Run locally

Requirements: Node.js compatible with the versions in `package-lock.json`, plus the existing Python backend.

```bash
npm ci
cp .env.example .env
npm run dev
```

Open the Vite URL printed in the terminal (the project defaults to `http://localhost:5173`). Configure the API base URL in `.env` according to `.env.example` and start the Python/FastAPI backend separately.

## Checks

```bash
npm run typecheck
npm test
npm run build
```

The frontend uses the existing API layer for chat streaming, conversations, document upload/indexing, citations, quizzes, flashcards, progress, and health checks. The UI only displays agent activity and source metadata provided by the backend.
