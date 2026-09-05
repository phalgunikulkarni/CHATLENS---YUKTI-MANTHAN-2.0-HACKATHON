# Backend Testing & Validation

A category-level record of backend validation already performed for the completed
work (Tasks 1–4 of account-scoped-chat-and-isolation, plus the legacy FAISS
removal). This is a record, not a test plan. Exact figures are stated only where
confidently known from the development record.

## Known results

- Backend automated test suite (pytest, `backend/tests`): **passing** — last
  recorded run **63 passed** (with pre-existing deprecation warnings unrelated to
  the tested behavior).
- Backend import/startup smoke (`import main`): **successful** — the application
  module imports cleanly.
- Re-validation after removing the accidentally reintroduced legacy FAISS
  pipeline: backend suite still **63 passed**; import smoke still successful; a
  source search confirmed **no active FAISS/legacy imports remain**.

## Validation categories covered

### Backend API behavior
Automated tests exercise the FastAPI endpoints for the implemented surface
(health, search, refine, chat CRUD, access grant/status, image status/file
gating), including expected success and rejection responses.

### Account identity / account handling
The account resolution layer (`X-Account-Id` → resolved account) was validated,
including acceptance of a valid account id and rejection of missing/malformed
identity on account-scoped endpoints. Both example-based and property-based
tests were used for the resolver's accepted-format behavior.

### Account-scoped chat functionality (Tasks 2)
Validated at the repository and endpoint level: conversation creation with a
single owning account; listing scoped to the owner; retrieval/open of an owned
conversation; append of search turns and refinement turns; rename; delete; and
account-scoped clear. Cross-account access attempts were validated to be
rejected (explicit authorization/not-found behavior rather than returning another
account's data).

### Chat creation, persistence, retrieval and hydration
Validated that conversations and messages persist to the database and can be
listed and re-read (supporting refresh/re-login hydration on the frontend), and
that result references are persisted without filesystem paths or binaries.

### Access / indexing state behavior (Task 4)
Validated that access/indexing state is maintained per account (independent
state per account, independent status reporting), that granting access derives
roots server-side and returns without blocking (asynchronous indexing preserved),
and that one account's state/failure does not affect another account. The
server-side scope restriction (only the intended user-facing folders) was
validated, including rejection of out-of-scope paths.

### Search / retrieval API behavior
Validated that the search/refine endpoints run the retrieval call and return the
expected response shape, and that account identity is required to reach them.

### Retrieval result mapping
Validated the mapping from retrieval-engine results to the frontend-facing result
shape, including that similarity is derived from real per-channel signals and
bounded, and that explanations are only present when grounded evidence exists
(never fabricated).

### OCR / visual / semantic retrieval paths
The intended non-FAISS retrieval path (CLIP visual, OCR/text, semantic, hybrid/
RRF via the `ml/` engine, reached through the backend retrieval bridge) was
exercised through the backend using deterministic, non-mock test doubles for the
heavy ML layer so behavior could be validated without invoking large models.
No mock *data* was introduced into the application; test doubles exist only in
the test harness.

### Authentication / account-related backend behavior
Validated that account-scoped endpoints reject unattributed requests and operate
only against the resolved account. (Authentication remains the existing dev-only
identity bridge; no new auth subsystem was introduced or claimed.)

### Database / repository behavior
Validated the chat repository operations and the additive schema handling
(account ownership columns and the result-reference structure), including that
the additive column-ensure path does not destroy existing data.

### Regression testing for Tasks 1–4
After each phase and after the FAISS removal, the full backend suite was re-run
to confirm no regression in previously completed work.

### Backend import / startup validation
`import main` was run as a smoke check to confirm the app initializes (including
table creation and additive column-ensure) without the removed legacy modules.

### Validation after legacy FAISS removal
After deleting `backend/processing/` and `backend/retrieval/`, the suite passed,
the import smoke succeeded, and a source search confirmed no remaining active
FAISS/legacy imports.

## Not covered (because not implemented)

Tasks 5–10 (account-scoped Chroma tagging/filtering, account-scoped retrieval
isolation, account-aware watcher, account-scoped library/image serving,
authorized_locations migration, full isolation suite) and all agent/summarization/
reminder/scheduling/calendar functionality are **not implemented** and therefore
**not** tested as implemented.
