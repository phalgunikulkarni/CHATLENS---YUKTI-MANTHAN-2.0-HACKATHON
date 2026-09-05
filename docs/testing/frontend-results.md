# Frontend Testing & Validation

A category-level record of frontend validation already performed for the
completed work. This is a record, not a test plan. Exact figures are stated only
where confidently known from the development record.

## Known results

- Frontend automated test suite (Vitest): **passing** — last recorded run
  **64 tests passed across 18 test files**.
- TypeScript type check (`tsc --noEmit`): **clean** (no type errors).
- Frontend production build (`npm run build`, i.e. `tsc -b && vite build`):
  **successful** — bundle generated (build artifact only; not a deployment).
- These results held after the retrieval-percentage UI removal and after the
  backend legacy-FAISS removal.

## Validation categories covered

### Authentication / account flow
Automated tests cover the dev-only auth/login lifecycle and the derivation of a
stable account id, plus persistence/restore behavior of the session.

### Account switching / reset behavior
Validated that changing the signed-in account (and logout) resets in-memory
account-specific state so a previous account's conversation/results are not shown
to the next account, and that the request layer stops sending the previous
account identity.

### Chat creation / New Chat behavior
Validated that New Chat creates a durable, backend-backed conversation and adopts
the canonical backend session id, without creating duplicate sessions.

### Chat history / persistence / hydration
Validated that the signed-in account's conversations load from the backend on
login/refresh, that selecting a conversation hydrates its persisted messages, and
that logout does not delete backend history (only clears in-memory state).

### Conversation state
Validated the conversation/store reducers, including account-change reset and the
hydration/loaded actions.

### API adapters and API contract behavior
Validated the HTTP adapter (including that the account header is attached through
the single request seam), the not-connected and mock adapters implementing the
same interface, and the chat API surface (create/list/get/delete/rename).

### Search interface & result rendering
Validated the search workspace behavior and result rendering, including result/
image cards.

### Image detail drawer
Validated the detail view rendering of a result, including the "Why this result?"
section.

### "Why this result?" explanation UI & retrieval-signal rendering
Validated that grounded explanation signals render as human-readable evidence,
that the empty state ("Explanation not available for this result.") is shown when
no evidence exists, and that no fabricated explanation is displayed.

### Removal of user-facing retrieval/similarity percentages
A regression test confirms that result cards and the explanation panel no longer
render a retrieval/similarity/match percentage, while the grounded
"Why this result?" affordance and signal type labels remain present.

### Frontend regression tests
The full Vitest suite (including pre-existing auth/onboarding/state tests) was
re-run after the UI change and after the backend FAISS removal to confirm no
regressions.

### TypeScript / type validation
`tsc --noEmit` was run and reported clean; the stricter build-time `tsc -b` also
passed as part of the production build.

### Production build validation
`npm run build` completed successfully, transforming the module graph and
emitting the production bundle. This validates the build only — not deployment.

## Not covered (because not implemented)

There is no frontend for Tasks 5–10 features or for agent/summarization/reminder/
scheduling/calendar functionality, as those are **not implemented**. They are not
claimed as tested.
