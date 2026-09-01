# ChatLens Frontend

Browser-based React single-page application delivering the ChatLens core loop:
**Remember -> Search -> Refine -> Explain -> Act**.

This is the `frontend/` module only. Ingestion, OCR, CLIP embeddings, hybrid
retrieval, ranking, explanations, and the conversational agent are owned by other
team members and consumed over HTTP through a single isolated API service layer
(`src/api/`).

## Data integrity

The Frontend renders **only backend-provided data**. It never fabricates retrieval
signals, match scores, timestamps, personal history, source information, or
metadata. When a field is absent from a response, the UI is omitted rather than
filled with a placeholder. Demo data (`src/data/`, `src/api/adapters/mockAdapter.ts`)
is clearly labelled synthetic and isolated from production API code.

## Stack

- Vite + React 18 + TypeScript (strict)
- State: React Context + `useReducer` (no extra state library)
- Tests: Vitest + React Testing Library + fast-check (property-based)
- Lint: ESLint flat config + typescript-eslint

## Scripts

| Command           | What it does                                           |
| ----------------- | ------------------------------------------------------ |
| `npm run dev`     | Start the Vite dev server (default: mock adapter).     |
| `npm run build`   | Type-check (`tsc -b`) then produce a production build. |
| `npm run preview` | Preview the production build locally.                  |
| `npm test`        | Run the test suite once (`vitest --run`).              |
| `npm run lint`    | Lint the source with ESLint.                           |

## API adapter selection

All server communication goes through `src/api/` (`ApiService`):

- **Mock adapter (default).** With no `VITE_API_BASE_URL`, the app runs fully
  offline against synthetic curated responses. This is what powers the demo.
- **HTTP adapter.** Set `VITE_API_BASE_URL` to point at a live backend.

```bash
# .env (enables the HTTP adapter)
VITE_API_BASE_URL=http://localhost:8000
```

## PROPOSED API contract - requires backend sign-off

The endpoints in `src/api/contract.ts` are a **proposed contract that requires
backend team sign-off**. They are **not implemented** in this repository. The
Frontend does not depend on them being confirmed; by default it uses the mock
adapter. Proposed endpoints: `POST /api/search`, `POST /api/refine`,
`GET /api/results/{id}/explanation`, `POST /api/actions/summarize`,
`POST /api/actions/roadmap`, `POST /api/actions/schedule/propose`,
`POST /api/actions/schedule/confirm`, `POST /api/images`,
`GET /api/images/{id}/status`.