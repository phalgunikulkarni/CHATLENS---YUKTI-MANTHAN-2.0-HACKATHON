# Integration / End-to-End Validation

A category-level record of the broader validation performed across the ChatLens
application for the completed work. This is a record, not a test plan. It also
distinguishes the *type* of validation used for each area.

## Types of validation used

- **Automated testing** — backend pytest suite and frontend Vitest suite.
- **Build / type validation** — `tsc --noEmit`, `tsc -b`, and the Vite
  production build.
- **Import / startup checks** — backend `import main` smoke check.
- **Architecture / code-path checks** — tracing the retrieval/account/chat code
  paths and source searches (e.g. confirming no active FAISS imports remain).
- **Manual / end-to-end (code-path) validation** — reasoning through the
  frontend → backend → retrieval → frontend flow against the actual code.

> No live production/deployment testing has been performed. "Production build"
> here means generating the build artifact locally, not deploying or testing a
> hosted environment.

## Known results

- Backend suite: **63 passed** (last recorded run).
- Frontend suite: **64 passed across 18 files** (last recorded run).
- TypeScript: **clean**. Production build: **successful**. Backend import smoke:
  **successful**. FAISS-removal source check: **no active FAISS imports remain**.

## Validation categories covered

### Frontend ↔ backend communication
The API contract and adapters were validated (automated frontend tests) and the
request/response shapes on the backend were validated (automated backend tests),
including the account header being attached on the frontend and required on the
backend.

### Authentication / account context propagation
Validated that the account identity is set on login, attached to outbound
requests through the single request seam, required by account-scoped backend
endpoints, and cleared on logout/account switch. Combined coverage across the
frontend auth/adapter tests and the backend resolver/endpoint tests.

### Chat persistence flow
Validated end-to-end at the code-path level and through both suites: New Chat →
backend-authoritative session → search/refine turns persisted → list/hydrate on
refresh/re-login → logout preserves backend history.

### Search request → backend retrieval → frontend rendering
Validated the path from the search interface through the backend search endpoint,
into the retrieval bridge and the `ml/` retrieval engine, back through result
mapping, and into result rendering. Heavy ML components were represented by
deterministic test doubles in the harness (no mock application data).

### Retrieval result / explanation flow
Validated that results carry grounded, bounded signals and that the
"Why this result?" UI renders only real evidence (or an honest empty state), with
user-facing retrieval percentages removed.

### Account-related state flow (Tasks 1–4)
Validated the account identity bridge, account-scoped chat persistence/hydration,
frontend chat integration, and per-account access/indexing state as an integrated
flow across the completed work.

### Application startup / import validation
Backend `import main` smoke check succeeded, confirming initialization
(table creation + additive column-ensure) works without the removed legacy code.

### Frontend production build
`npm run build` succeeded (build artifact only).

### Backend and frontend test-suite validation
Both suites were run (and re-run after major changes) with the results above.

### Intended non-FAISS retrieval architecture
Validated that the current retrieval path uses the non-FAISS Chroma/CLIP/OCR
hybrid engine via the backend retrieval bridge, and that the application operates
without the legacy FAISS files.

### Removal of accidentally reintroduced legacy FAISS/processing/retrieval code
Validated that `backend/processing/` and `backend/retrieval/` were removed, that
no active FAISS/legacy imports remain (source search), and that suites/build/
import all still pass after removal.

## Not covered (because not implemented)

Integration/end-to-end validation of Tasks 5–10 and of agent/summarization/
reminder/scheduling/calendar features has **not** been performed because those
features are **not implemented**. They are pending, not failing.
