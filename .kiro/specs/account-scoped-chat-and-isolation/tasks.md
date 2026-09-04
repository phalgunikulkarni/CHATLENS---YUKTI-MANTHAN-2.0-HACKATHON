# Implementation Plan: Account-Scoped Chat and Isolation (Phase 1)

## Overview

This plan converts the account-scoped-chat-and-isolation design into a series of
small, independently verifiable, low-risk coding tasks organized under the mandated
phases **A–J** (mapped to top-level numeric tasks **1–10**). It is a **scoping refactor, not a redesign**: retrieval, ranking,
fusion/RRF, dedup, `Max_Results=5`, real cosine-derived 0–100 similarity, grounded
"Why this result?" behavior, and the Desktop/Downloads/Documents/Pictures-only scan
policy are preserved exactly. Account scoping is applied as an **additional gate**
that only restricts the candidate set / owner, never replacing existing logic.

Implementation language follows the design: **Python** for the backend/`ml` seam,
**TypeScript/React** for the frontend. The design uses concrete languages (not
pseudocode), so no language selection question is required.

**Hard constraints reflected throughout:**
- Phase 1 only. DEV-ONLY frontend auth is kept; **no real auth/JWT/OAuth/passwords**.
- Reuse `stableAccountId(email) => acct-<hex>`; `X-Account-Id` header is the account
  bridge. This is **application-level isolation, NOT security-grade auth** (spoofable
  header is a documented, accepted limitation — flagged, not fixed).
- Local-folder policy preserved exactly: only Desktop/Downloads/Documents/Pictures via
  `default_user_scope`; roots derived server-side; no native folder picker; no
  arbitrary `C:\`/AppData/repo/caller-supplied paths.
- Account filtering happens **before** ranking/fusion/dedup/result selection
  (Chroma `where={"account_id": ...}` inside `collection.query` per channel).
- Filesystem security checks in `resolve_image_path` (realpath, source-root containment,
  symlink/traversal, allowed extensions) preserved; account check is additive.
- Migrations are **additive + abort-on-failure**, leave existing data intact, never
  fabricate ownership, never delete/recreate stores.
- Logout clears account-specific in-memory frontend state but must NOT delete persisted
  chats. New Chat is backend-persisted (durable), not frontend-only.
- Agent orchestration and deployment/CI-CD are **out of scope**.

**Convention:** sub-tasks marked with `*` are optional (tests) and are NOT implemented
by the coding agent automatically. Top-level tasks are never optional. Each task lists
_Requirements:_ and _Design:_ traceability.

---

## Tasks

- [x] 1. Phase A — Account Identity Bridge

  - [x] 1.1 Backend account resolver dependency
    - **Purpose:** Resolve and validate the `X-Account-Id` header into an `account_id`
      on user-owned endpoints, rejecting unattributed requests before any data access.
    - **Files/modules:** `backend/account.py` (new)
    - **Implementation steps:**
      - Add `ACCOUNT_RE = re.compile(r"^acct-[0-9a-f]+$")`.
      - Add `resolve_account(x_account_id: str | None = Header(default=None)) -> str`
        that raises `HTTPException(status_code=401, detail=...)` when the header is
        missing or fails the regex, and returns the value otherwise.
      - Perform NO data access on the reject path.
    - **Acceptance criteria:**
      - Valid `acct-<hex>` → returned unchanged.
      - Missing header → 401, no data touched.
      - Malformed value (not `^acct-[0-9a-f]+$`) → 401, no data touched.
    - **Tests required:** 1.9 (`*`) covers resolver directly.
    - **Dependencies:** none.
    - _Requirements: R2.1, R2.2, R2.3_
    - _Design: Components §1 (Account Identity Bridge → Backend resolve); Error Handling (missing/invalid → 401)_

  - [x] 1.2 Frontend module-level account holder
    - **Purpose:** Provide a non-React place the HTTP adapter can read the active
      account id from, set/cleared by auth lifecycle.
    - **Files/modules:** `frontend/src/api/accountContext.ts` (new)
    - **Implementation steps:**
      - Store `accountId: string | null` as a module-level variable.
      - Export `setAccountId(id)`, `clearAccountId()`, `getAccountId()`.
    - **Acceptance criteria:**
      - `getAccountId()` returns the last set value, `null` after clear.
      - No React import; usable from the adapter.
    - **Tests required:** none directly (exercised by 1.4/1.8 tests).
    - **Dependencies:** none.
    - _Requirements: R1.2_
    - _Design: Components §1 (module-level account holder `api/accountContext.ts`)_

  - [x] 1.3 Wire AuthContext to the account holder + store reset
    - **Purpose:** Set/clear the account holder on login/restore/logout and reset
      in-memory state so no prior-account data is displayed after logout/account change.
    - **Files/modules:** `frontend/src/features/auth/AuthContext.tsx`
    - **Implementation steps:**
      - On login and session restore: call `setAccountId(user.id)` with the existing
        `stableAccountId`-derived id (do NOT generate a new id).
      - On logout: call `clearAccountId()` and dispatch the store reset action (1.5).
      - On account change (login as a different account): dispatch reset before hydrate.
    - **Acceptance criteria:**
      - After login the holder equals `user.id`.
      - After logout the holder is `null` and the reset action is dispatched.
    - **Tests required:** 1.8 (`*`).
    - **Dependencies:** 1.2, 1.5.
    - _Requirements: R1.2, R1.3, R1.4_
    - _Design: Components §1 (set/clear on login/restore/logout; dispatch store reset)_

  - [x] 1.4 Inject `X-Account-Id` in the HTTP adapter
    - **Purpose:** Attach the account header to every user-owned request without
      changing existing request behavior.
    - **Files/modules:** `frontend/src/api/adapters/httpAdapter.ts`
    - **Implementation steps:**
      - In the private `post`/`get` helpers, read `getAccountId()`; when present, add
        `"X-Account-Id": <id>` to the existing headers.
      - Preserve base-URL selection, `Content-Type`, and `absolutize*` behavior exactly.
    - **Acceptance criteria:**
      - When signed in, every user-owned call carries `X-Account-Id` = the account id.
      - baseURL/Content-Type/absolutize behavior unchanged when the header is added.
    - **Tests required:** 1.8 (`*`).
    - **Dependencies:** 1.2.
    - _Requirements: R1.1, R1.5_
    - _Design: Components §1 (HttpAdapter single injection point)_

  - [x] 1.5 Store reset action for account change/logout
    - **Purpose:** Reset conversation/conversations/results/actions slices on
      login/logout so no prior-account content leaks into the UI.
    - **Files/modules:** `frontend/src/state/store.tsx`
    - **Implementation steps:**
      - Add `ACCOUNT_CHANGED` / `STATE_RESET` action handling.
      - Reset only the conversation, conversations, results, and actions slices to initial.
    - **Acceptance criteria:**
      - Dispatching the reset returns those slices to initial values.
      - Other unrelated slices are untouched.
    - **Tests required:** 1.8 (`*`).
    - **Dependencies:** none.
    - _Requirements: R1.4_
    - _Design: Components §1; Frontend State (ACCOUNT_CHANGED/STATE_RESET reset slices)_

  - [x] 1.6 Apply `Depends(resolve_account)` to existing user-owned endpoints
    - **Purpose:** Thread the resolved `account_id` into search/refine/library/image/
      access endpoints; non-owned endpoints (e.g. `/health`) stay exempt.
    - **Files/modules:** `backend/main.py`
    - **Implementation steps:**
      - Add `account: str = Depends(resolve_account)` to `/api/search`, `/api/refine`,
        `/api/library`, `/api/images/{id}/file`, `/api/images/{id}/status`,
        `/api/access/grant`, `/api/access/status`.
      - Do NOT add the dependency to `/health` or other non-owned endpoints.
      - Pass `account` down to the service calls (thread only; behavior wired in later
        phases — keep signatures forward-compatible).
    - **Acceptance criteria:**
      - User-owned endpoints reject missing/invalid header with 401.
      - `/health` works with no header.
    - **Tests required:** 1.9 (`*`), plus per-endpoint tests in later phases.
    - **Dependencies:** 1.1.
    - _Requirements: R2.1, R2.2, R2.3, R2.4, R2.5_
    - _Design: Architecture (target request flow); Components §1 (applied via Depends)_

  - [x]* 1.7 Property test — resolver header format (Property 1)
    - **Property 1: Account header format resolution**
    - **Validates: Requirements R2.1, R2.3**
    - **Files/modules:** `backend/tests/test_account_resolver_pbt.py` (new)
    - Use hypothesis, ≥100 iterations; assert `resolve_account(s)` returns `s` iff
      `s` matches `^acct-[0-9a-f]+$`, else 401 and no data access. Tag with feature name
      + property number.
    - _Requirements: R2.1, R2.3_
    - _Design: Correctness Properties → Property 1_

  - [x]* 1.8 Frontend tests — header injection, logout reset, holder lifecycle (Property 2)
    - **Property 2: Frontend attaches signed-in account id to every user-owned request**
    - **Validates: Requirements R1.1, R1.2**
    - **Files/modules:** `frontend/src/api/adapters/httpAdapter.test.ts` (new),
      `frontend/src/features/auth/AuthContext.test.tsx` (new)
    - Fake `fetch` capturing headers; assert `X-Account-Id` present and equals the
      account id; logout clears header and resets store slices. Use fast-check for the
      property (≥100 iterations); tag with feature name + property number.
    - _Requirements: R1.1, R1.2, R1.3, R1.4, R1.5_
    - _Design: Testing Strategy (Frontend vitest); Correctness Properties → Property 2_

  - [x]* 1.9 Backend tests — resolver + endpoint gating example tests
    - **Purpose:** Assert 401 on missing/malformed header for user-owned endpoints and
      that `/health` is exempt.
    - **Files/modules:** `backend/tests/test_account_endpoints.py` (new)
    - Use FastAPI `TestClient`; cover missing header, malformed header, valid header.
    - _Requirements: R2.2, R2.3, R2.4_
    - _Design: Error Handling (status code policy)_

  - [x] 1.10 Checkpoint — identity bridge builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [x] 2. Phase B — Backend Chat Persistence

  - [x] 2.1 Add pytest harness + `ml/` fakes
    - **Purpose:** Establish backend test infrastructure that avoids torch/CLIP/OCR.
    - **Files/modules:** `backend/tests/__init__.py` (new), `backend/tests/conftest.py`
      (new), `backend/tests/fakes.py` (new), minimal `pytest.ini` or `pyproject` test
      config (new)
    - **Implementation steps:**
      - Add fake `ChromaStore` (in-memory dict honoring `where={"account_id"}` and
        account-qualified ids), fake `Retriever` (deterministic ranked results), fake
        `LibraryIndexer`/`FolderWatcher` (record calls; simulate success/failure/batch).
      - Provide a TestClient fixture and a temp SQLite DB fixture.
    - **Acceptance criteria:**
      - `pytest` discovers and runs a trivial smoke test with no torch/CLIP/OCR import.
    - **Tests required:** self-validating smoke test.
    - **Dependencies:** none.
    - _Requirements: R16 (harness enabling)_
    - _Design: Testing Strategy (Backend harness + fakes)_

  - [x] 2.2 Revive/extend chat schema models (additive)
    - **Purpose:** Add ownership + result-reference structures to the ORM models.
    - **Files/modules:** `backend/models.py`
    - **Implementation steps:**
      - `SearchSession`: add `account_id` (indexed) and `title`.
      - `SearchMessage`: add denormalized `account_id` (indexed).
      - `SearchContext`: add `account_id`.
      - New `SearchResultRef` table: `id`, `message_id` (FK→search_messages),
        `session_id`, `account_id`, `image_id`, `rank`, `display_metadata_json`.
        **No** `file_path`/`absolute_path`/`source_root`/binary columns.
      - `Image`: add optional `account_id` (indexed) — additive/deferred.
    - **Acceptance criteria:**
      - Models import cleanly; `SearchResultRef` has no path/binary column.
    - **Tests required:** exercised by 2.4/2.5/2.6 tests.
    - **Dependencies:** 2.1.
    - _Requirements: R13.1, R4.5_
    - _Design: Data Models (SQLite schema evolution; SearchResultRef table decision (a))_

  - [x] 2.3 Chat DTO schemas
    - **Purpose:** Define request/response shapes for chat endpoints; keep
      `TurnResponse` unchanged.
    - **Files/modules:** `backend/schemas.py`
    - **Implementation steps:**
      - Add `ConversationSummary`, `ConversationDetail`, `ChatMessage`, `ResultRef`,
        `CreateChat` DTOs.
      - Do NOT change `TurnResponse` shape.
    - **Acceptance criteria:**
      - DTOs serialize; `ResultRef` carries only `image_id` + display metadata.
    - **Tests required:** exercised by 2.7 tests.
    - **Dependencies:** 2.2.
    - _Requirements: R4.6, R5.6_
    - _Design: Files/Modules Affected (schemas.py); Data Models_

  - [x] 2.4 `chat_repo` — conversation creation + ownership helper
    - **Purpose:** Backend-authoritative session creation with a single owner and the
      `_owned_or_raise` gate.
    - **Files/modules:** `backend/chat_repo.py` (new)
    - **Implementation steps:**
      - `create_conversation(db, account_id, title=None) -> session_id` mints a
        server-owned `SearchSession.id`, sets `account_id` = resolved account, never
        null/anonymous/previous/global; does not modify existing conversations.
      - `_owned_or_raise(db, account_id, session_id)`: 404 when session missing, 403
        when owned by another account.
    - **Acceptance criteria:**
      - Created conversation has exactly one owner = resolver account.
      - `_owned_or_raise` returns row for owner, raises 404/403 correctly.
    - **Tests required:** 2.9 (`*`) Property 3.
    - **Dependencies:** 2.2.
    - _Requirements: R3.1, R3.2, R3.3, R3.4, R3.5_
    - _Design: Components §2 (chat_repo; `_owned_or_raise`); Data Models (session id decision)_

  - [x] 2.5 `chat_repo` — persist search turns
    - **Purpose:** Persist the user query and result references for a search turn.
    - **Files/modules:** `backend/chat_repo.py`
    - **Implementation steps:**
      - `append_search_turn(db, account_id, session_id, query, results)`: persist a user
        `SearchMessage` (with `created_at`), and one `SearchResultRef` per result with
        `image_id`, `rank`, `display_metadata_json` (no path/binary). Zero results →
        message with no refs. Use `_owned_or_raise` first.
    - **Acceptance criteria:**
      - Reload yields same query + exact ref count; refs contain no path/binary keys.
    - **Tests required:** 2.10 (`*`) Property 4.
    - **Dependencies:** 2.4.
    - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5_
    - _Design: Components §2 (`append_search_turn`); Data Models (SearchResultRef)_

  - [x] 2.6 `chat_repo` — persist refinement turns
    - **Purpose:** Append refinement message + clues/context to the same owned session.
    - **Files/modules:** `backend/chat_repo.py`
    - **Implementation steps:**
      - `append_refine_turn(db, account_id, session_id, message, clues, results)`:
        `_owned_or_raise` first; append `SearchMessage` + persisted clues/context; do NOT
        create a new conversation; cross-account/nonexistent → 403/404, no persistence.
    - **Acceptance criteria:**
      - Refinement appends to same session; cross-account raises 403; missing raises 404;
        no message persisted on rejection.
    - **Tests required:** 2.11 (`*`) Property 5, 2.14 (`*`) Property 9.
    - **Dependencies:** 2.4.
    - _Requirements: R5.1, R5.2, R5.3, R5.4, R5.5_
    - _Design: Components §2 (`append_refine_turn`); Error Handling_

  - [x] 2.7 `chat_repo` — list/get/delete/clear (account-scoped)
    - **Purpose:** Account-scoped read and deletion CRUD.
    - **Files/modules:** `backend/chat_repo.py`
    - **Implementation steps:**
      - `list_conversations(db, account_id)` → only owned summaries.
      - `get_conversation(db, account_id, session_id)` → messages (ascending by
        created_at) + refs + context, via `_owned_or_raise`.
      - `delete_conversation(db, account_id, session_id)` via `_owned_or_raise`.
      - `clear_conversations(db, account_id)` → only owned rows; no delete-all-accounts op.
    - **Acceptance criteria:**
      - List returns only owner rows; cross-account get/delete → 403; missing → 404; no
        200-with-empty substitute.
    - **Tests required:** 2.12 (`*`) Property 6, 2.13 (`*`) Property 8, 2.14 (`*`) Property 9.
    - **Dependencies:** 2.4.
    - _Requirements: R6.1, R6.2, R6.3, R6.4, R6.5, R8.1, R8.2, R8.3, R8.4_
    - _Design: Components §2; Error Handling (status code policy)_

  - [x] 2.8 Chat endpoints in `main.py`
    - **Purpose:** Expose durable chat CRUD and thread `account_id` into search/refine
      persistence.
    - **Files/modules:** `backend/main.py`
    - **Implementation steps:**
      - Add `POST /api/chats` (create → returns canonical `session_id`),
        `GET /api/chats` (list, account-scoped), `GET /api/chats/{session_id}`
        (messages+refs+context), `DELETE /api/chats/{session_id}`, optional
        `PATCH /api/chats/{session_id}` (rename). All via `Depends(resolve_account)`.
      - In `/api/search` and `/api/refine`, call `chat_repo.append_search_turn` /
        `append_refine_turn`; keep `TurnResponse` shape unchanged.
    - **Acceptance criteria:**
      - Endpoints return the documented status codes; `TurnResponse` shape unchanged.
    - **Tests required:** 2.12–2.14 (`*`).
    - **Dependencies:** 1.6, 2.4, 2.5, 2.6, 2.7, 2.3.
    - _Requirements: R3.2, R4.6, R5.6, R6.1, R6.2, R8.1_
    - _Design: Components §2; Files/Modules Affected (main.py chat endpoints)_

  - [x]* 2.9 Property test — single-owner conversations (Property 3)
    - **Property 3: Single-owner conversations**
    - **Validates: Requirements R3.1, R3.3, R3.4, R3.5, R14.2**
    - **Files/modules:** `backend/tests/test_chat_create_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R3.1, R3.3, R3.4, R3.5, R14.2_
    - _Design: Correctness Properties → Property 3_

  - [x]* 2.10 Property test — search turn round-trip (Property 4)
    - **Property 4: Search turn persistence round-trip**
    - **Validates: Requirements R4.1, R4.2, R4.3, R4.4, R4.5**
    - **Files/modules:** `backend/tests/test_chat_search_turn_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R4.1, R4.2, R4.3, R4.4, R4.5_
    - _Design: Correctness Properties → Property 4_

  - [x]* 2.11 Property test — refinement appends same conversation (Property 5)
    - **Property 5: Refinement appends to the same owned conversation**
    - **Validates: Requirements R5.1, R5.2, R5.3**
    - **Files/modules:** `backend/tests/test_chat_refine_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R5.1, R5.2, R5.3_
    - _Design: Correctness Properties → Property 5_

  - [x]* 2.12 Property test — chat list/order account-scoped (Property 6)
    - **Property 6: Chat list and ordering are account-scoped**
    - **Validates: Requirements R6.1, R6.2**
    - **Files/modules:** `backend/tests/test_chat_list_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R6.1, R6.2_
    - _Design: Correctness Properties → Property 6_

  - [x]* 2.13 Property test — owned-only deletion (Property 8)
    - **Property 8: Owned-only deletion**
    - **Validates: Requirements R8.1, R8.3, R14.4**
    - **Files/modules:** `backend/tests/test_chat_delete_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R8.1, R8.3, R14.4_
    - _Design: Correctness Properties → Property 8_

  - [x]* 2.14 Example tests — cross-account chat 403/404 (no 200-empty)
    - **Purpose:** Assert cross-account get/refine/delete → 403, missing → 404, never
      200-with-empty.
    - **Files/modules:** `backend/tests/test_chat_cross_account.py` (new)
    - _Requirements: R5.4, R5.5, R6.3, R6.4, R6.5, R8.2_
    - _Design: Error Handling (status code policy)_

  - [x] 2.15 Checkpoint — backend chat persistence builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [x] 3. Phase C — Frontend Chat Persistence

  - [x] 3.1 Add chat API endpoints/types/contract
    - **Purpose:** Expose backend chat CRUD to the frontend.
    - **Files/modules:** `frontend/src/api/ApiService.ts`, `frontend/src/api/contract.ts`,
      `frontend/src/api/types.ts`, `frontend/src/api/adapters/httpAdapter.ts`
    - **Implementation steps:**
      - Add `createChat`, `listChats`, `getChat`, `deleteChat`, optional `renameChat`
        methods + ENDPOINTS entries + types; adapter implementations reuse the injected
        `X-Account-Id` header.
    - **Acceptance criteria:**
      - Methods call the correct routes with the account header present.
    - **Tests required:** 3.4 (`*`).
    - **Dependencies:** 1.4, 2.8.
    - _Requirements: R6.1, R6.2, R8.1_
    - _Design: Components §1; Files/Modules Affected (ApiService/contract/types)_

  - [x] 3.2 `useChatLens` — durable new chat + canonical session id
    - **Purpose:** New Chat becomes backend-persisted; frontend adopts canonical id.
    - **Files/modules:** `frontend/src/hooks/useChatLens.ts`
    - **Implementation steps:**
      - `newConversation()` calls `createChat` and adopts the returned `sessionId`.
      - search/refine target the canonical `sessionId`.
      - Snapshots become a cache keyed by canonical `sessionId`.
    - **Acceptance criteria:**
      - New Chat produces a backend session; search/refine use its id.
    - **Tests required:** 3.5 (`*`).
    - **Dependencies:** 3.1.
    - _Requirements: R3.2, R7.1_
    - _Design: Frontend chat integration (newConversation creates backend session)_

  - [x] 3.3 `useChatLens` — hydrate persisted chats on select + on login
    - **Purpose:** Restore persisted conversations across refresh/login.
    - **Files/modules:** `frontend/src/hooks/useChatLens.ts`
    - **Implementation steps:**
      - `selectConversation` hydrates messages via `getChat(id)`.
      - On login, load the account's chats via `listChats` and reset in-memory slices
        first (via 1.5 reset) before hydrating.
    - **Acceptance criteria:**
      - After refresh/login, prior conversations are listed and openable.
    - **Tests required:** 3.6 (`*`).
    - **Dependencies:** 3.1, 1.3, 1.5.
    - _Requirements: R7.1, R7.3_
    - _Design: Frontend chat integration (selectConversation hydrates; on login load chats)_

  - [x]* 3.4 Frontend tests — chat adapter methods send account header
    - **Files/modules:** `frontend/src/api/chat.test.ts` (new). Fake fetch capturing headers.
    - _Requirements: R1.1, R6.1_
    - _Design: Testing Strategy (Frontend vitest)_

  - [x]* 3.5 Frontend tests — durable New Chat adopts canonical id
    - **Files/modules:** `frontend/src/hooks/useChatLens.newchat.test.ts` (new).
    - _Requirements: R3.2, R7.1_
    - _Design: Frontend chat integration_

  - [x]* 3.6 Frontend tests — hydration of persisted chats across refresh/login
    - **Files/modules:** `frontend/src/hooks/useChatLens.hydration.test.ts` (new).
    - _Requirements: R7.1, R7.3_
    - _Design: Frontend chat integration; Testing Strategy_

  - [x] 3.7 Checkpoint — frontend chat persistence builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 4. Phase D — Account-Scoped Access State

  - [ ] 4.1 Convert access-service globals to account-keyed maps
    - **Purpose:** Replace the process-global singleton with per-account state.
    - **Files/modules:** `backend/access_service.py`
    - **Implementation steps:**
      - Introduce `_states: Dict[str, dict]`, `_watchers: Dict[str, FolderWatcher]`,
        `_index_threads: Dict[str, threading.Thread]`, guarded by the existing `_lock`.
      - Keep a single shared stateless `LibraryIndexer`.
      - Leave `_scoped_roots`/`_validate_roots` UNCHANGED.
    - **Acceptance criteria:**
      - State reads/writes are keyed by `account_id`; `_scoped_roots`/`_validate_roots`
        byte-for-byte unchanged.
    - **Tests required:** 4.5 (`*`) Property 12.
    - **Dependencies:** 2.1.
    - _Requirements: R11.1_
    - _Design: Components §5 (per-account access service maps)_

  - [ ] 4.2 `get_status(account_id)` and account-scoped `/api/access/status`
    - **Purpose:** Return only the requesting account's access state.
    - **Files/modules:** `backend/access_service.py`, `backend/main.py`
    - **Implementation steps:**
      - `get_status(account_id)` returns that account's `{authorized, indexing, roots,
        indexedCount, error}` (idle default when absent).
      - Wire `/api/access/status` to pass the resolved account.
    - **Acceptance criteria:**
      - Status for A never reflects B's state.
    - **Tests required:** 4.5 (`*`), 4.6 (`*`).
    - **Dependencies:** 4.1, 1.6.
    - _Requirements: R11.4_
    - _Design: Components §5; Error Handling_

  - [ ] 4.3 `grant_access(account_id)` — server-derived roots + async start
    - **Purpose:** Grant access scoped to the account, deriving roots server-side and
      returning without waiting for indexing.
    - **Files/modules:** `backend/access_service.py`, `backend/main.py`
    - **Implementation steps:**
      - `grant_access(account_id)` derives roots from `_scoped_roots` (never caller
        paths), validates with `_validate_roots`, stores per-account state, spawns a
        per-account daemon index thread, returns immediately.
      - Wire `/api/access/grant` to pass the resolved account.
    - **Acceptance criteria:**
      - Grant response returns before indexing completes; roots come only from
        `Scoped_Roots`; caller-supplied paths ignored.
    - **Tests required:** 4.6 (`*`), 4.7 (`*`) Property 13.
    - **Dependencies:** 4.1, 1.6.
    - _Requirements: R11.2, R11.3, R11.5, R11.8, R11.9_
    - _Design: Components §5; Watcher/Async Indexing_

  - [ ] 4.4 `restore_on_startup()` and `shutdown()` per-account
    - **Purpose:** Restore each persisted account's state on startup and stop all
      watchers on shutdown.
    - **Files/modules:** `backend/access_service.py`, `backend/main.py`
    - **Implementation steps:**
      - `restore_on_startup()` iterates persisted accounts (uses Phase H loader) and
        restarts each account's watcher WITHOUT a full re-index.
      - `shutdown()` stops all watchers.
      - Wire into FastAPI startup/shutdown events.
    - **Acceptance criteria:**
      - Startup restores per-account state; shutdown stops all watchers cleanly.
    - **Tests required:** 4.6 (`*`).
    - **Dependencies:** 4.1; (full restore depends on 8.2 loader — startup wiring may no-op
      until 8.2 lands).
    - _Requirements: R12.2, R12.3_
    - _Design: Components §5; Authorized Location Persistence & Migration_

  - [ ]* 4.5 Property test — per-account access/index/watcher independence (Property 12)
    - **Property 12: Per-account access/indexing/watcher independence**
    - **Validates: Requirements R11.1, R11.4, R11.7**
    - **Files/modules:** `backend/tests/test_access_independence_pbt.py` (new). hypothesis ≥100, fakes.
    - _Requirements: R11.1, R11.4, R11.7_
    - _Design: Correctness Properties → Property 12_

  - [ ]* 4.6 Example tests — status/grant account scoping + async return
    - **Files/modules:** `backend/tests/test_access_endpoints.py` (new). TestClient + fakes.
    - _Requirements: R11.3, R11.4, R11.5_
    - _Design: Error Handling; Components §5_

  - [ ]* 4.7 Property test — server-derived scope-limited roots (Property 13)
    - **Property 13: Server-derived, scope-limited roots**
    - **Validates: Requirements R11.2, R11.8, R11.9, R15.5, R15.6**
    - **Files/modules:** `backend/tests/test_scoped_roots_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R11.2, R11.8, R11.9, R15.5, R15.6_
    - _Design: Correctness Properties → Property 13_

  - [ ] 4.8 Checkpoint — access state scoping builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 5. Phase E — Account-Scoped Chroma

  - [ ] 5.1 Chroma metadata tagging (`account_id`)
    - **Purpose:** Tag every upserted record with `account_id` from `extra_metadata`.
    - **Files/modules:** `ml/vectorstore/chroma_store.py`
    - **Implementation steps:**
      - `upsert_visual`/`upsert_text` include `"account_id"` in metadata (sourced from
        the `extra_metadata` the indexer threads).
    - **Acceptance criteria:**
      - Upserted records carry `account_id`; no fusion/ranking code touched.
    - **Tests required:** 5.10 (`*`).
    - **Dependencies:** 2.1.
    - _Requirements: R9.1_
    - _Design: Chroma Design (Option A metadata tagging); Data Models (Chroma metadata)_

  - [ ] 5.2 Account-qualified record ids
    - **Purpose:** Prevent shared path-hash `image_id` collisions across accounts.
    - **Files/modules:** `ml/vectorstore/chroma_store.py`
    - **Implementation steps:**
      - Add `visual_id(account_id, image_id)` / `text_id(account_id, image_id)` →
        `visual_<account>_<image_id>` / `text_<account>_<image_id>`; use for upsert ids.
    - **Acceptance criteria:**
      - Two accounts indexing the same file yield distinct record ids; no overwrite.
    - **Tests required:** 5.10 (`*`), 5.8 (`*`) Property 9.
    - **Dependencies:** 5.1.
    - _Requirements: R9.1_
    - _Design: Chroma Design (account-qualified record ids rationale)_

  - [ ] 5.3 `where`-filter in retriever channels (before ranking)
    - **Purpose:** Restrict each channel's candidate set to the account before fusion.
    - **Files/modules:** `ml/retrieval/retriever.py`
    - **Implementation steps:**
      - Add optional `account_id` to `_query_collection`, `search_visual`, `search_text`,
        `search_hybrid`, `search`; when present pass
        `collection.query(..., where={"account_id": account_id})` in both channels.
      - Do NOT change z-score/RRF/weighting/dedup/`[:top_k]` math.
    - **Acceptance criteria:**
      - Filter applied inside each channel query before ranking; fusion math unchanged.
    - **Tests required:** 5.8 (`*`) Property 9, 5.9 (`*`) Property 10, 5.11 (`*`) regression.
    - **Dependencies:** 5.1.
    - _Requirements: R9.2, R9.3, R9.10_
    - _Design: Chroma Design; Components §4 (Retriever/ChromaStore where filter)_

  - [ ] 5.4 `ml_retrieval.search_memories` account threading
    - **Purpose:** Forward `account_id` from the endpoint into retrieval.
    - **Files/modules:** `backend/ml_retrieval.py`, `backend/main.py`
    - **Implementation steps:**
      - `search_memories(query, account_id, top_k=5)` → `retriever.search(query,
        top_k=pool, account_id=account_id)`; unresolved account → reject + zero results.
      - Wire `/api/search` and `/api/refine` to pass the resolved account.
      - Dedup/pool math/`DEFAULT_MAX_RESULTS`/similarity logic UNCHANGED.
    - **Acceptance criteria:**
      - Account forwarded, not interpreted; retrieval math unchanged.
    - **Tests required:** 5.8 (`*`), 5.9 (`*`), 5.11 (`*`).
    - **Dependencies:** 5.3, 1.6.
    - _Requirements: R9.2, R9.4, R9.5, R9.6, R9.7, R9.10_
    - _Design: Components §3 (ml_retrieval threading)_

  - [ ] 5.5 `resolve_image_path` account gate
    - **Purpose:** Add account-tag equality check AFTER existing security checks.
    - **Files/modules:** `backend/ml_retrieval.py`
    - **Implementation steps:**
      - `resolve_image_path(image_id, account_id)`: run existing realpath/source-root/
        symlink/extension checks first, THEN require `metadata["account_id"] ==
        account_id`. Account check is additive, never a replacement.
    - **Acceptance criteria:**
      - Security checks preserved and run first; cross-account record → not served.
    - **Tests required:** 5.8 (`*`), 7-phase tasks in Phase G.
    - **Dependencies:** 5.1, 5.2.
    - _Requirements: R10.1, R10.8, R10.9, R15.5_
    - _Design: Components §3; What Remains Unchanged (security checks)_

  - [ ] 5.6 `list_memories` account scoping
    - **Purpose:** Restrict library listing candidate set to the account.
    - **Files/modules:** `backend/ml_retrieval.py`, `ml/vectorstore/chroma_store.py`
    - **Implementation steps:**
      - `list_memories(account_id, limit=200)` → `col.get(where={"account_id":
        account_id}, ...)`.
    - **Acceptance criteria:**
      - Listing returns only the account's records.
    - **Tests required:** 7-phase library tests, 5.8 (`*`).
    - **Dependencies:** 5.1.
    - _Requirements: R10.5_
    - _Design: Components §3; Chroma Design (list_memories get where=)_

  - [ ] 5.7 Account-qualified fingerprint/idempotency lookup
    - **Purpose:** Per-account incremental fingerprint state for shared files.
    - **Files/modules:** `ml/vectorstore/chroma_store.py`
    - **Implementation steps:**
      - `get_visual_by_image_id(image_id, account_id)` / `get_text_by_image_id(...)`
        reconstruct the account-qualified id (or `get(where=...)`).
    - **Acceptance criteria:**
      - Fingerprint lookup is per-account; the same file has independent state per account.
    - **Tests required:** 5.10 (`*`), 6-phase indexing tests.
    - **Dependencies:** 5.2.
    - _Requirements: R9.1_
    - _Design: Chroma Design (fingerprint idempotency account-qualified)_

  - [ ]* 5.8 Property test — cross-account isolation invariant (Property 9)
    - **Property 9: Cross-account isolation invariant**
    - **Validates: Requirements R2.5, R5.4, R6.3, R6.5, R8.2, R9.3, R10.3, R10.7, R14.1, R14.3**
    - **Files/modules:** `backend/tests/test_isolation_invariant_pbt.py` (new). hypothesis ≥100, fakes across chat/library/image/retrieval surfaces.
    - _Requirements: R2.5, R5.4, R6.3, R6.5, R8.2, R9.3, R10.3, R10.7, R14.1, R14.3_
    - _Design: Correctness Properties → Property 9_

  - [ ]* 5.9 Property test — owned, bounded, order-preserving results (Property 10)
    - **Property 10: Owned, bounded, order-preserving results**
    - **Validates: Requirements R9.2, R9.3, R9.5, R9.6, R9.7, R9.10, R14.5, R14.6, R15.1, R15.2, R15.3**
    - **Files/modules:** `backend/tests/test_results_bounded_pbt.py` (new). hypothesis ≥100, fake Retriever with deterministic ranking over mixed-account corpus.
    - _Requirements: R9.2, R9.3, R9.5, R9.6, R9.7, R9.10, R14.5, R14.6, R15.1, R15.2, R15.3_
    - _Design: Correctness Properties → Property 10_

  - [ ]* 5.10 Example tests — metadata tag + account-qualified id + no-overwrite
    - **Files/modules:** `backend/tests/test_chroma_scoping.py` (new). Uses fake ChromaStore.
    - _Requirements: R9.1_
    - _Design: Chroma Design_

  - [ ]* 5.11 Property test — truthful similarity range preserved (Property 11)
    - **Property 11: Truthful similarity range preserved**
    - **Validates: Requirements R9.8, R9.9, R15.4**
    - **Files/modules:** `backend/tests/test_similarity_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R9.8, R9.9, R15.4_
    - _Design: Correctness Properties → Property 11_

  - [ ]* 5.12 Regression test — single-account ranking/order unchanged
    - **Purpose:** Assert scoping does not reorder single-account results vs. baseline.
    - **Files/modules:** `backend/tests/test_single_account_regression.py` (new).
    - _Requirements: R15.1, R15.2, R15.3, R9.7, R9.10_
    - _Design: What Remains Intentionally Unchanged_

  - [ ] 5.13 Checkpoint — Chroma scoping builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 6. Phase F — Account-Scoped Indexing & Watcher

  - [ ] 6.1 `LibraryIndexer.index_locations(..., account_id)`
    - **Purpose:** Thread the account into indexing so records are account-tagged and
      account-qualified.
    - **Files/modules:** `ml/pipeline/indexer.py`
    - **Implementation steps:**
      - Add `account_id` param; set `extra_md[iid]["account_id"] = account_id`; use the
        account-qualified upsert id and account-qualified fingerprint lookup.
      - All other indexer logic (scan → OCR → CLIP → text → upsert, provenance,
        `IndexReport`) UNCHANGED. `scanner.py` and `local_access.py` UNCHANGED.
    - **Acceptance criteria:**
      - Indexed records carry `account_id`; incremental fingerprint per account; other
        logic unchanged.
    - **Tests required:** 6.4 (`*`).
    - **Dependencies:** 5.1, 5.2, 5.7.
    - _Requirements: R9.1, R11.7_
    - _Design: Watcher/Async Indexing (index_locations account_id)_

  - [ ] 6.2 Per-account async indexing thread + failure isolation
    - **Purpose:** Run indexing on a daemon thread per account; isolate failures.
    - **Files/modules:** `backend/access_service.py`
    - **Implementation steps:**
      - `_run_initial_index` becomes per-account; success → start that account's watcher;
        failure → set that account's `indexing="failed"`, record error, do NOT start its
        watcher; never affects another account's state.
    - **Acceptance criteria:**
      - One account's failure leaves other accounts untouched; failed account gets no watcher.
    - **Tests required:** 6.5 (`*`) Property 12, 4.6 (`*`).
    - **Dependencies:** 4.1, 4.3, 6.1.
    - _Requirements: R11.5, R11.6_
    - _Design: Watcher/Async Indexing (async daemon per account; failure isolation)_

  - [ ] 6.3 One `FolderWatcher` per account with account-bound `on_batch`
    - **Purpose:** Attribute filesystem changes unambiguously to the owning account.
    - **Files/modules:** `backend/access_service.py`
    - **Implementation steps:**
      - `_start_watcher`/`stop_watcher` per-account; construct one `FolderWatcher` keyed
        in `_watchers[account_id]` whose `on_batch(changed)` closure calls
        `indexer.index_locations(changed, account_id=<that account>)`.
      - `FolderWatcher` internals UNCHANGED.
    - **Acceptance criteria:**
      - A change indexed under account A never mutates account B's records.
    - **Tests required:** 6.5 (`*`) Property 12.
    - **Dependencies:** 6.1, 6.2.
    - _Requirements: R11.7_
    - _Design: Watcher/Async Indexing ((i) one watcher per account)_

  - [ ]* 6.4 Example test — indexer tags records + account-qualified upsert/fingerprint
    - **Files/modules:** `backend/tests/test_indexer_scoping.py` (new). Fake indexer/store.
    - _Requirements: R9.1, R11.7_
    - _Design: Watcher/Async Indexing_

  - [ ]* 6.5 Property/example test — watcher/index isolation (Property 12)
    - **Property 12: Per-account access/indexing/watcher independence** (watcher facet)
    - **Validates: Requirements R11.6, R11.7**
    - **Files/modules:** `backend/tests/test_watcher_isolation.py` (new). Fake FolderWatcher simulating batch callbacks + failure.
    - _Requirements: R11.6, R11.7_
    - _Design: Correctness Properties → Property 12; Watcher/Async Indexing_

  - [ ] 6.6 Checkpoint — indexing/watcher scoping builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 7. Phase G — Account-Scoped Library & Image Serving

  - [ ] 7.1 Account-scoped library listing endpoint
    - **Purpose:** Return only the account's images.
    - **Files/modules:** `backend/main.py`
    - **Implementation steps:**
      - `/api/library` calls `ml_retrieval.list_memories(account_id=account, limit=...)`.
    - **Acceptance criteria:**
      - Library returns only the requesting account's records.
    - **Tests required:** 7.4 (`*`).
    - **Dependencies:** 1.6, 5.6.
    - _Requirements: R10.5_
    - _Design: Isolation boundary (library listing)_

  - [ ] 7.2 Account-scoped image file serving endpoint
    - **Purpose:** Serve files only for account-owned, security-passing images.
    - **Files/modules:** `backend/main.py`
    - **Implementation steps:**
      - `/api/images/{id}/file` calls `resolve_image_path(image_id, account)`; cross-
        account or security-failing → 404 (avoid existence disclosure); missing account
        header → 401 (via resolver).
      - Preserve the recommended path of loading images through the adapter so the header
        is present; mandate the backend ownership gate regardless (flag as
        implementation-time detail; do NOT weaken backend checks).
    - **Acceptance criteria:**
      - Cross-account by id → 404; security-failing → 404; missing/invalid header → 401.
    - **Tests required:** 7.5 (`*`).
    - **Dependencies:** 1.6, 5.5.
    - _Requirements: R10.1, R10.2, R10.3, R10.4, R10.8, R10.9_
    - _Design: Error Handling (image by id → 404); flagged limitation (img src header)_

  - [ ] 7.3 Account-scoped image status endpoint
    - **Purpose:** Return status only for account-owned images; never disclose others.
    - **Files/modules:** `backend/main.py`
    - **Implementation steps:**
      - `/api/images/{id}/status` scoped by resolved account; cross-account → 404, no
        status disclosure.
    - **Acceptance criteria:**
      - Cross-account status → 404, no disclosure.
    - **Tests required:** 7.5 (`*`).
    - **Dependencies:** 1.6, 5.5.
    - _Requirements: R10.6, R10.7_
    - _Design: Error Handling; Data Models (Image.account_id deferred)_

  - [ ]* 7.4 Example test — library listing account-scoped
    - **Files/modules:** `backend/tests/test_library_scoping.py` (new). Fake store.
    - _Requirements: R10.5_
    - _Design: Isolation boundary_

  - [ ]* 7.5 Example tests — image serving/status status codes (401/404)
    - **Files/modules:** `backend/tests/test_image_serving_scoping.py` (new). TestClient + fake resolve_image_path; assert security checks still applied.
    - _Requirements: R10.1, R10.2, R10.3, R10.4, R10.6, R10.7, R10.8, R10.9_
    - _Design: Error Handling (status code policy)_

  - [ ] 7.6 Checkpoint — library/image serving scoping builds and passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 8. Phase H — authorized_locations.json Migration

  - [ ] 8.1 SQLite additive migration module
    - **Purpose:** Additive, abort-on-failure SQLite migration run at startup before serving.
    - **Files/modules:** `backend/migrations.py` (new), `backend/main.py`
    - **Implementation steps:**
      - Use `PRAGMA table_info(<table>)` to inspect columns; `ALTER TABLE ADD COLUMN
        account_id` only when missing; add `title` to `search_sessions` if missing;
        create `search_result_refs` if absent; add optional `Image.account_id`.
      - Abort on any inspect/alter failure, leaving `chatlens.db` unchanged; surface an
        error. No drop/recreate. No fabricated ownership for pre-existing rows.
      - Run at startup before serving.
    - **Acceptance criteria:**
      - Missing columns added; existing rows retained; re-run is a no-op; failure leaves
        DB unchanged.
    - **Tests required:** 8.4 (`*`) Property 15.
    - **Dependencies:** 2.2.
    - _Requirements: R13.1, R13.2, R13.3, R13.4, R13.5, R13.6_
    - _Design: Migration/Rollback (SQLite); Correctness Properties → Property 15_

  - [ ] 8.2 Account-keyed authorized-locations load/save
    - **Purpose:** Replace the global `{"roots":[...]}` file with an account-keyed store.
    - **Files/modules:** `backend/access_service.py`
    - **Implementation steps:**
      - New structure `{"accounts": {"acct-x": {"roots":[...]}}, "_legacy_unclaimed":
        {"roots":[...]}}`.
      - Helpers `_load_persisted(account_id)`, `_save_persisted(account_id, roots)`,
        `_load_all_accounts()`.
    - **Acceptance criteria:**
      - Save then load returns the same roots per account.
    - **Tests required:** 8.5 (`*`) Property 14.
    - **Dependencies:** 4.1.
    - _Requirements: R12.1_
    - _Design: Components §6; Authorized Location Persistence & Migration_

  - [ ] 8.3 Legacy authorized-locations migration (never fabricate, non-fatal)
    - **Purpose:** Migrate the legacy global file additively, preserving unattributed roots.
    - **Files/modules:** `backend/access_service.py`
    - **Implementation steps:**
      - On startup: if file already has `accounts` key → restore per account + restart
        watchers WITHOUT full re-index; if only legacy `{"roots":[...]}` → move verbatim
        into `_legacy_unclaimed` (served to nobody), never fabricate `account_id`.
      - Failure leaves the file byte-for-byte intact and is non-fatal (access reports idle).
    - **Acceptance criteria:**
      - Legacy roots preserved unattributed; failure leaves file intact + app still starts.
    - **Tests required:** 8.5 (`*`) Property 14, 8.6 (`*`).
    - **Dependencies:** 8.2, 4.4.
    - _Requirements: R12.2, R12.3, R12.4, R12.5_
    - _Design: Authorized Location Persistence & Migration; Migration/Rollback_

  - [ ]* 8.4 Property test — migration idempotence & non-destructiveness (Property 15)
    - **Property 15: Migration idempotence and non-destructiveness**
    - **Validates: Requirements R13.2, R13.3, R13.5**
    - **Files/modules:** `backend/tests/test_migration_pbt.py` (new). hypothesis ≥100 over conforming pre-migration DBs.
    - _Requirements: R13.2, R13.3, R13.5_
    - _Design: Correctness Properties → Property 15_

  - [ ]* 8.5 Property test — per-account authorization persistence round-trip (Property 14)
    - **Property 14: Per-account authorization persistence round-trip**
    - **Validates: Requirements R12.1, R12.5**
    - **Files/modules:** `backend/tests/test_authloc_persistence_pbt.py` (new). hypothesis ≥100.
    - _Requirements: R12.1, R12.5_
    - _Design: Correctness Properties → Property 14_

  - [ ]* 8.6 Example test — legacy migration preserves file + non-fatal on failure
    - **Files/modules:** `backend/tests/test_authloc_migration.py` (new).
    - _Requirements: R12.4, R12.5, R13.4_
    - _Design: Authorized Location Persistence & Migration_

  - [ ] 8.7 Checkpoint — migrations build and pass
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 9. Phase I — Full Isolation Validation (27-point checklist)

  - [ ] 9.1 Chat persistence & lifecycle isolation tests
    - **Purpose:** Verify chat persistence across login/logout/refresh and multi-chat scoping.
    - **Files/modules:** `backend/tests/test_iso_chat.py` (new),
      `frontend/src/test/iso.chat.test.ts` (new)
    - **Implementation steps (checklist points 1–6):**
      - login → chat → logout → login: chats persist (not deleted on logout).
      - simulated refresh: chats persist.
      - multiple chats persist for one account.
      - B sees only B's chats (list scoped).
      - B cannot open A's session (403).
      - B cannot modify/refine A's session (403).
      - B cannot delete A's session (403).
    - **Acceptance criteria:** all points pass with explicit 403/404 (no 200-empty).
    - **Tests required:** self (this task is tests).
    - **Dependencies:** 2.8, 3.3.
    - _Requirements: R6.3, R7.2, R7.3, R8.2, R14.3, R14.4, R16.1, R16.3_
    - _Design: Testing Strategy (required coverage 1–4)_

  - [ ] 9.2 Retrieval / library / image isolation tests
    - **Purpose:** Verify A and B cannot retrieve each other's images/records/library/status.
    - **Files/modules:** `backend/tests/test_iso_retrieval.py` (new)
    - **Implementation steps (checklist points 7–11):**
      - A/B cannot retrieve each other's images (search/refine).
      - A/B cannot list each other's library.
      - A/B cannot fetch each other's image file (404) or status (404).
      - legacy Chroma records (no `account_id`) leak to nobody.
    - **Acceptance criteria:** all cross-account retrieval yields owned-only / 404.
    - **Dependencies:** 5.4, 5.5, 5.6, 7.1, 7.2, 7.3.
    - _Requirements: R9.3, R10.3, R10.7, R13.6, R14.1, R14.6, R16.2_
    - _Design: Testing Strategy (required coverage 5, 11); Migration/Rollback (Chroma legacy)_

  - [ ] 9.3 Header rejection & account-scoped access/watcher tests
    - **Purpose:** Verify unattributed rejection and account-scoped access/index/watcher state.
    - **Files/modules:** `backend/tests/test_iso_access.py` (new)
    - **Implementation steps (checklist points 12–17):**
      - missing `X-Account-Id` → 401; malformed → 401.
      - access status/grant/indexing status account-scoped.
      - watcher-triggered changes account-scoped (batch to A never mutates B).
    - **Acceptance criteria:** all points pass.
    - **Dependencies:** 1.6, 4.2, 4.3, 6.3.
    - _Requirements: R2.2, R2.3, R11.4, R11.7, R16.4, R16.5_
    - _Design: Testing Strategy (required coverage 6–8)_

  - [ ] 9.4 Folder-policy & security-preservation tests
    - **Purpose:** Verify only the 4 folders are scanned and security checks intact.
    - **Files/modules:** `backend/tests/test_iso_folder_policy.py` (new)
    - **Implementation steps (checklist points 18–21):**
      - only Desktop/Downloads/Documents/Pictures scanned.
      - arbitrary `C:\` (and home/AppData/repo) rejected.
      - traversal/symlink protections intact in `resolve_image_path`.
      - allowed-extension eligibility intact.
    - **Acceptance criteria:** disallowed roots rejected; security checks enforced.
    - **Dependencies:** 4.3, 5.5.
    - _Requirements: R11.8, R11.9, R15.5, R15.6, R10.8, R10.9_
    - _Design: What Remains Intentionally Unchanged; Testing Strategy (coverage 9)_

  - [ ] 9.5 Retrieval-fidelity & representative-query/refinement isolation tests
    - **Purpose:** Verify preserved retrieval semantics under scoping and scenario coverage.
    - **Files/modules:** `backend/tests/test_iso_retrieval_fidelity.py` (new)
    - **Implementation steps (checklist points 22–27):**
      - `Max_Results=5` preserved; dedup unchanged; similarity real cosine 0–100.
      - single-account ranking/order unchanged vs. baseline.
      - representative queries ("CN notes about OSI", "Python login error", "confused
        guy meme", "handwritten database notes", "CN notes with a large diagram") return
        only the requesting account's results.
      - refinement sequence ("OSI" → "handwritten" → "large diagram") preserves original
        intent, accumulates clues on the same conversation, stays owned by the requester.
      - login as another account does not inherit prior frontend state (paired with a
        frontend assertion in `frontend/src/test/iso.state.test.ts`).
    - **Acceptance criteria:** all points pass; scoping reorders nothing.
    - **Dependencies:** 5.4, 5.9, 5.11, 5.12, 2.6, 3.3, 1.5.
    - _Requirements: R9.5, R9.6, R9.7, R9.8, R9.9, R15.1, R15.2, R15.3, R15.4, R16.6, R16.7_
    - _Design: Testing Strategy (required coverage 10–13); Correctness Properties 10/11_

  - [ ] 9.6 Checkpoint — full isolation validation passes
    - Ensure all tests pass, ask the user if questions arise.

---

- [ ] 10. Phase J — Final Validation

  - [ ] 10.1 Run backend test suites (existing + new)
    - **Purpose:** Confirm backend correctness and no regressions.
    - **Files/modules:** `backend/tests/**`
    - **Implementation steps:** run `pytest` (single run, no watch); confirm existing +
      new isolation/persistence/property tests pass; validate backend startup/import.
    - **Acceptance criteria:** all backend tests green; app imports and starts.
    - **Dependencies:** all backend tasks.
    - _Requirements: R15.10, R16.1–R16.8_
    - _Design: Testing Strategy_

  - [ ] 10.2 Run frontend validation (vitest + tsc + build)
    - **Purpose:** Confirm frontend correctness and type/build integrity.
    - **Files/modules:** `frontend/**`
    - **Implementation steps:** run vitest single-run, `tsc --noEmit`, and the frontend
      build; keep existing suites green.
    - **Acceptance criteria:** vitest green; tsc clean; build succeeds.
    - **Dependencies:** all frontend tasks.
    - _Requirements: R15.10_
    - _Design: Testing Strategy (Frontend vitest)_

  - [ ] 10.3 Regression verification — retrieval/API unchanged
    - **Purpose:** Verify no retrieval/API regression vs. single-account baseline.
    - **Files/modules:** `backend/tests/test_single_account_regression.py`,
      `backend/tests/test_iso_retrieval_fidelity.py`
    - **Implementation steps:** assert ranking/dedup/`Max_Results`/similarity and API
      payload shapes (`TurnResponse`, `/api/search`, `/api/refine`) unchanged.
    - **Acceptance criteria:** no regression detected.
    - **Dependencies:** 5.12, 9.5.
    - _Requirements: R9.10, R15.1, R15.2, R15.3, R15.4_
    - _Design: What Remains Intentionally Unchanged_

  - [ ] 10.4 Final implementation report
    - **Purpose:** Produce the required end-of-feature report.
    - **Files/modules:** `docs/decisions.md` (append) or spec-local report file
    - **Implementation steps:** document files changed, migrations performed, tests added,
      tests passed, known limitations (explicitly include the spoofable-header note and
      the `<img src>` header follow-up), and explicitly untouched areas (retrieval math,
      scanner/local_access, security checks, folder policy).
    - **Acceptance criteria:** report present and complete; spoofable-header limitation flagged.
    - **Dependencies:** 10.1, 10.2, 10.3.
    - _Requirements: R13.7, R15.7, R15.8, R15.9_
    - _Design: Explicitly flagged limitations / follow-ups; What Remains Intentionally Unchanged_

  - [ ] 10.5 Final checkpoint — everything green
    - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Sub-tasks marked with `*` are optional (tests) and can be skipped for a faster MVP, but
  the Phase I/J (tasks 9/10) validation tasks are NOT optional because they encode the mandated
  isolation checklist and final verification.
- Each task references specific requirement clauses (R#.#) and design sections for
  traceability.
- Property tests use `hypothesis` (backend) / `fast-check` (frontend), ≥100 iterations,
  tagged with the feature name + property number, and fake the `ml/` seam so no
  torch/CLIP/OCR models are needed.
- Account filtering is always applied BEFORE ranking/fusion/dedup; no fusion/ranking/
  dedup/similarity math is changed anywhere.
- The `X-Account-Id` header is application-level isolation, not authentication; this is
  an accepted, documented Phase-1 limitation (never "fixed" here).
- No task performs deployment, git activity, agent orchestration, or real auth.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.5", "2.1"] },
    { "id": 1, "tasks": ["1.3", "1.4", "1.6", "1.7", "2.2", "4.1", "5.1"] },
    { "id": 2, "tasks": ["1.8", "1.9", "2.3", "2.4", "4.2", "4.3", "5.2", "5.3", "5.6", "8.2"] },
    { "id": 3, "tasks": ["2.5", "2.6", "2.7", "2.9", "4.4", "4.5", "4.6", "4.7", "5.4", "5.5", "5.7", "8.1", "8.3"] },
    { "id": 4, "tasks": ["2.10", "2.11", "2.12", "2.13", "2.8", "5.8", "5.9", "5.10", "5.11", "5.12", "6.1", "8.4", "8.5", "8.6"] },
    { "id": 5, "tasks": ["2.14", "3.1", "6.2", "6.4", "7.1", "7.2", "7.3"] },
    { "id": 6, "tasks": ["3.2", "3.3", "6.3", "6.5", "7.4", "7.5"] },
    { "id": 7, "tasks": ["3.4", "3.5", "3.6", "9.1", "9.2", "9.3", "9.4"] },
    { "id": 8, "tasks": ["9.5"] },
    { "id": 9, "tasks": ["10.1", "10.2", "10.3"] },
    { "id": 10, "tasks": ["10.4"] }
  ]
}
```

---

## Requirements & Design Coverage Cross-Check

### Requirements → Task IDs

| Requirement | Task ID(s) | Notes |
| --- | --- | --- |
| R1.1 Header on every user-owned request | 1.4, 1.8 | Injected in HttpAdapter |
| R1.2 Reuse stableAccountId (no new id) | 1.2, 1.3, 1.8 | Holder set from `user.id` |
| R1.3 Stop header after logout | 1.3, 1.8 | `clearAccountId()` |
| R1.4 Clear in-memory conversation state on logout | 1.3, 1.5, 1.8 | Store reset action |
| R1.5 Preserve baseURL/Content-Type/absolutize | 1.4, 1.8 | Additive header only |
| R2.1 Resolve valid header | 1.1, 1.6, 1.7, 1.9 | resolver dependency |
| R2.2 Reject missing header (no data) | 1.1, 1.6, 1.9, 9.3 | 401 |
| R2.3 Reject malformed header (no data) | 1.1, 1.6, 1.7, 1.9, 9.3 | 401 |
| R2.4 Non-owned endpoints need no header | 1.6, 1.9 | `/health` exempt |
| R2.5 Restrict all reads/writes to resolved account | 1.6, 5.8 | via Property 9 |
| R3.1 Conversation owner = resolved account | 2.4, 2.9 | |
| R3.2 One canonical session id returned | 2.4, 2.8, 3.2 | backend-authoritative |
| R3.3 One owning account recorded | 2.4, 2.9 | |
| R3.4 Not null/anon/prev/global | 2.4, 2.9 | |
| R3.5 Persist without overwriting existing | 2.4, 2.9 | |
| R4.1 Persist user query message | 2.5, 2.10 | with created_at |
| R4.2 Persist result references | 2.5, 2.10 | |
| R4.3 Zero results → message, no refs | 2.5, 2.10 | |
| R4.4 Creation timestamp | 2.5, 2.10 | |
| R4.5 Exclude binaries & paths | 2.2, 2.5, 2.10 | enforced by table shape |
| R4.6 Same POST /api/search payload shape | 2.3, 2.8 | TurnResponse unchanged |
| R5.1 Refine appends to same owned conversation | 2.6, 2.11 | |
| R5.2 Persist clues/context | 2.6, 2.11 | |
| R5.3 No new conversation on refine | 2.6, 2.11 | |
| R5.4 Cross-account refine → 403/404, no persist | 2.6, 2.14, 5.8 | |
| R5.5 Unresolvable/nonexistent → 403/404, no persist | 2.6, 2.14 | |
| R5.6 Same POST /api/refine payload shape | 2.3, 2.8 | |
| R6.1 Chat list scoped to account | 2.7, 2.8, 3.1 | |
| R6.2 Get owned conversation (ordered) + refs + context | 2.7, 2.8 | |
| R6.3 Cross-account get → 403/404 | 2.7, 2.14, 5.8, 9.1 | |
| R6.4 Nonexistent session → 404 | 2.7, 2.14 | |
| R6.5 No 200-with-empty substitute | 2.7, 2.14, 5.8 | |
| R7.1 Frontend restores persisted chats | 3.2, 3.3, 3.6 | |
| R7.2 Logout retains chats | 9.1 | |
| R7.3 Re-login returns same set | 3.3, 9.1 | Property 7 (see gap note) |
| R7.4 Durable across process restart | 2.2, 8.1, 10.1 | integration (see gap note) |
| R8.1 Delete only owned conversation | 2.7, 2.8, 2.13 | |
| R8.2 Cross-account delete → 403/404 | 2.7, 2.14, 5.8, 9.1 | |
| R8.3 Clear only owned | 2.7, 2.13 | |
| R8.4 No indiscriminate delete-all | 2.7 | none provided |
| R9.1 Tag Chroma record with account | 5.1, 5.2, 5.7, 6.1, 6.4 | |
| R9.2 Restrict candidates before ranking | 5.3, 5.4, 5.9 | where filter |
| R9.3 Exclude other-account records | 5.3, 5.4, 5.8, 9.2 | |
| R9.4 Unresolved account → reject + 0 results | 5.4 | |
| R9.5 Dedup by canonical identity | 5.4, 5.9, 5.12 | unchanged |
| R9.6 At most Max_Results (5) | 5.4, 5.9 | unchanged |
| R9.7 Preserve ranking order | 5.4, 5.9, 5.12, 9.5 | |
| R9.8 Similarity 0–100 | 5.11, 9.5 | |
| R9.9 Similarity from real cosine | 5.11, 9.5 | |
| R9.10 Ranking/scoring/dedup unchanged | 5.3, 5.4, 5.9, 5.12, 10.3 | |
| R10.1 Verify ownership before serving | 5.5, 7.2, 7.5 | |
| R10.2 Serve owned + security-passing | 7.2, 7.5 | |
| R10.3 Cross-account image → reject | 5.5, 7.2, 7.5, 9.2 | 404 |
| R10.4 Unresolved account → reject serving | 1.6, 7.2 | 401 |
| R10.5 Library scoped to account | 5.6, 7.1, 7.4, 9.2 | |
| R10.6 Status scoped to account | 7.3, 7.5 | |
| R10.7 Cross-account status → reject, no disclose | 7.3, 7.5, 5.8, 9.2 | 404 |
| R10.8 Preserve local-folder security checks | 5.5, 7.2, 7.5, 9.4 | additive gate |
| R10.9 Security failure → reject | 5.5, 7.2, 7.5, 9.4 | 404 |
| R11.1 Per-account access state | 4.1, 4.5 | |
| R11.2 Server-derived roots | 4.3, 4.7 | |
| R11.3 Grant starts scoped indexing | 4.3, 4.6 | |
| R11.4 Status returns only account state | 4.2, 4.5, 4.6, 9.3 | |
| R11.5 Async indexing, immediate return | 4.3, 6.2, 4.6 | |
| R11.6 Fail → failed state + no watcher | 6.2, 6.5 | |
| R11.7 Watcher updates only that account | 6.1, 6.3, 6.5, 9.3 | |
| R11.8 Roots restricted to Scoped_Roots | 4.3, 4.7, 9.4 | unchanged |
| R11.9 Reject out-of-scope roots | 4.3, 4.7, 9.4 | unchanged |
| R12.1 Auth persistence keyed by account | 8.2, 8.5 | |
| R12.2 Restore each account on restart | 4.4, 8.3 | |
| R12.3 Restart watcher without full re-index | 4.4, 8.3 | |
| R12.4 Retain existing file (defined handling) | 8.3, 8.6 | |
| R12.5 Preserve unattributable data, no fabrication | 8.2, 8.3, 8.5, 8.6 | `_legacy_unclaimed` |
| R13.1 Add account_id to chat + image structures | 2.2, 8.1 | |
| R13.2 Inspect schema before change | 8.1, 8.4 | PRAGMA |
| R13.3 Add missing column, retain rows | 8.1, 8.4 | |
| R13.4 Abort on failure, leave data unchanged | 8.1, 8.6 | |
| R13.5 No unconditional drop/recreate | 8.1, 8.4 | |
| R13.6 No fabricated ownership | 8.1, 8.3, 9.2 | |
| R13.7 Document reset/migration strategy | 10.4 | docs/report |
| R14.1 Cross-account isolation invariant | 5.8, 9.1, 9.2 | Property 9 |
| R14.2 Single-owner invariant | 2.4, 2.9 | Property 3 |
| R14.3 Session read-isolation | 2.7, 5.8, 9.1 | |
| R14.4 Session delete-isolation | 2.7, 2.13, 9.1 | |
| R14.5 Bounded-results invariant | 5.9, 9.5 | |
| R14.6 Owned-results invariant | 5.9, 9.2, 9.5 | |
| R15.1 Preserve retrieval/ranking | 5.3, 5.9, 5.12, 10.3 | |
| R15.2 Preserve Max_Results | 5.4, 5.9, 5.12, 10.3 | |
| R15.3 Preserve dedup | 5.4, 5.9, 5.12, 10.3 | |
| R15.4 Preserve 0–100 similarity | 5.11, 9.5, 10.3 | |
| R15.5 Preserve security checks | 5.5, 9.4, 4.7 | |
| R15.6 Preserve folder policy | 4.3, 4.7, 9.4 | |
| R15.7 No LLM agent/orchestrator | (scope) 10.4 | not implemented — non-goal, flagged in report |
| R15.8 No real auth | (scope) 1.1, 10.4 | header bridge only; flagged |
| R15.9 No deployment/git activity | (scope) 10.4 | non-goal, flagged in report |
| R15.10 Keep existing tests green | 10.1, 10.2 | |
| R16.1 A's chats not accessible to B | 9.1 | |
| R16.2 A's library/images/results not accessible to B | 9.2 | |
| R16.3 Chat persists across refresh + logout/login | 9.1, 3.6 | |
| R16.4 Missing/invalid header rejected | 1.9, 9.3 | |
| R16.5 Cross-account → explicit error (not 200-empty) | 2.14, 9.1 | |
| R16.6 Representative queries scoped | 9.5 | |
| R16.7 Refinement sequence intent/clues/owner | 9.5 | |
| R16.8 New chat not under null/anon/prev/global; no overwrite | 2.4, 2.9, 3.2 | |

### Design sections → Task IDs

| Design section | Task ID(s) |
| --- | --- |
| Components §1 Account Identity Bridge (frontend + backend) | 1.1, 1.2, 1.3, 1.4, 1.5, 1.6 |
| Components §2 Chat persistence repository | 2.4, 2.5, 2.6, 2.7, 2.8 |
| Components §3 Retrieval bridge (`ml_retrieval`) threading | 5.4, 5.5, 5.6 |
| Components §4 Retriever/ChromaStore `where` filter | 5.1, 5.2, 5.3, 5.7 |
| Components §5 Per-account access service | 4.1, 4.2, 4.3, 4.4, 6.2, 6.3 |
| Components §6 Authorized-locations persistence | 8.2, 8.3 |
| Data Models — SQLite schema evolution | 2.2, 8.1 |
| Data Models — SearchResultRef decision (a) | 2.2, 2.5 |
| Data Models — Image.account_id deferred | 2.2, 7.3, 8.1 |
| Data Models — backend-authoritative session id | 2.4, 2.8, 3.2 |
| Chroma Design — Option A + account-qualified ids | 5.1, 5.2, 5.3, 5.6, 5.7 |
| Watcher / Async Indexing — per-account watcher | 6.1, 6.2, 6.3 |
| Authorized Location Persistence & Migration | 8.2, 8.3, 4.4 |
| Correctness Properties 1–15 | 1.7, 1.8, 2.9, 2.10, 2.11, 2.12, 2.13, 4.5, 4.7, 5.8, 5.9, 5.11, 6.5, 8.4, 8.5 |
| Error Handling — status code policy | 1.1, 2.14, 7.2, 7.3, 7.5, 9.3 |
| Testing Strategy — backend harness + fakes | 2.1 |
| Testing Strategy — required coverage 1–13 | 9.1, 9.2, 9.3, 9.4, 9.5 |
| Migration / Rollback — SQLite | 8.1, 8.4 |
| Migration / Rollback — Chroma legacy handling | 5.3, 5.6, 9.2 |
| Migration / Rollback — authorized locations | 8.2, 8.3, 8.6 |
| Risks — image_id collision / account-qualified ids | 5.2, 5.7 |
| Risks — where filter forgotten (single seam) | 5.4, 5.5, 5.6, 5.8 |
| Risks — result refs paths/binaries | 2.2, 2.5, 2.10 |
| Risks — header spoofing (documented) | 10.4 |
| Risks — frontend snapshot cache divergence | 1.5, 3.2, 3.3 |
| What Remains Intentionally Unchanged | 5.12, 9.4, 9.5, 10.3 |
| Explicitly flagged limitations / follow-ups | 7.2, 10.4 |

### Explicitly flagged elements with NO dedicated implementation task (rationale)

- **R7.4 (durability across process restart)** — no standalone *implementation* task
  beyond schema durability (2.2) + migration (8.1). Verification is folded into **10.1**
  (backend startup) and the durable SQLite storage established in 2.2/8.1. Rationale: the
  design covers this via example/integration/smoke tests, not PBT; no additional code
  is required once persistence exists.
- **R7.3 / Property 7 (logout→login set round-trip)** — validated by tests (9.1, 3.6);
  there is no separate production code task because the behavior emerges from 2.7 (list)
  + 3.3 (hydrate). Rationale: pure verification of already-built behavior.
- **R13.7 (documented reset/migration strategy)** — realized only as documentation in
  **10.4**, not code. Rationale: it is a docs deliverable, and code-level migration is
  non-destructive (8.1/8.3), so no reset is required by this design.
- **R15.7 (no LLM agent/orchestrator), R15.8 (no real auth), R15.9 (no deployment/git)**
  — **negative non-goals**; intentionally have NO implementation task. They are flagged
  in the **10.4** report as explicitly untouched. Rationale: these require *not* doing
  work; enforcing them is a review/report concern, and the spoofable-header limitation
  (R15.8-adjacent) is documented in 10.4.
- **`Image.account_id` (deferred)** — added additively in 2.2/8.1 and used for status
  scoping (7.3), but the upload path is dead/unindexed, so no ingestion-path
  implementation task exists. Rationale: authoritative served-image ownership comes
  from the Chroma `account_id` tag (5.1/5.2), per the design's deferral decision.
- **`<img src>` direct-load header carrying** — flagged in 7.2 and 10.4 as an
  implementation-time detail; the mandatory backend ownership gate is implemented (7.2)
  and never weakened. Rationale: the design defers the transport detail while requiring
  the gate, which is fully covered.
