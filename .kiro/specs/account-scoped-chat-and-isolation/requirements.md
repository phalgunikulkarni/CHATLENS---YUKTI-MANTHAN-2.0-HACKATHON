# Requirements Document

## Introduction

ChatLens today has no server-side notion of "who is asking." The backend
(`backend/main.py`) treats every request as anonymous: search/refine are stateless
passthroughs, chat/conversation state lives only in the browser (in-memory React
state, lost on refresh), local-folder access state is a single process-global
singleton persisted to one shared `backend/authorized_locations.json`, and the
Chroma vector records carry no ownership tag. In effect, the running backend
behaves as one implicit global account.

This feature ("account-scoped-chat-and-isolation", Phase 1) introduces an
**account identity bridge** and applies **application-level account scoping** to two
areas that currently leak across accounts:

- **(a) Account-scoped chat/conversation persistence** — conversations (search +
  refine turns, result references, active clues) are persisted on the backend and
  owned by an account, so they survive browser refresh and logout/login and are
  never visible to a different account.
- **(b) Per-account image / access / index isolation** — access state, indexing
  state, authorization persistence, Chroma records, image retrieval, image serving,
  library listing, and folder watchers become account-scoped, so Account A can never
  retrieve, view, or list Account B's images.

This is an **account-scoping refactor, NOT a redesign**. Existing retrieval,
ranking, dedup, similarity, and local-folder security behavior MUST be preserved
exactly. The conversational LLM/orchestrator is explicitly **out of scope**.

Authentication remains **dev-only and frontend-only**. The frontend `DevAuthService`
already derives a stable account id from the normalized email via
`stableAccountId(email) => "acct-<hex>"` (FNV-1a), stored in browser storage. Phase 1
does NOT introduce real authentication, JWT, or passwords. Instead, the frontend
transmits its existing stable account id as an `X-Account-Id` HTTP header, and the
backend resolves the owning account from that header on every request that touches
user-owned data.

### Environmental Assumption (local multi-account reality)

On the local developer machine, ChatLens may only scan Desktop, Documents,
Downloads, and Pictures under the OS user's home directory (per
`ml/filesystem/local_access.py` `default_user_scope`). Multiple ChatLens accounts on
the same machine therefore physically resolve to the **same four OS folders** and the
same underlying image files. This is **accepted and expected**. Phase 1 does NOT
attempt physical/filesystem isolation. The guarantee Phase 1 provides is strictly
**application-level isolation**: each account's indexed records, retrieval results,
library listing, image serving, chats, and access/indexing state are partitioned by
account id so that one account's application state is never exposed to another
account, even when the underlying files on disk are shared.

## Glossary

- **ChatLens_Backend**: The FastAPI application in `backend/main.py` and its
  supporting modules (`access_service`, `ml_retrieval`, `models`, `database`,
  `ingestion`). The system under specification.
- **ChatLens_Frontend**: The React application under `frontend/src` (App shell,
  stores, hooks, API adapters, auth service).
- **Account**: A logical owner of user-owned data, identified by an **Account_Id**.
- **Account_Id**: The stable identifier of the form `acct-<hex>` produced by the
  frontend `DevAuthService.stableAccountId(email)`. There is no server-side password
  or token verification in Phase 1.
- **Account_Header**: The `X-Account-Id` HTTP request header carrying the
  **Account_Id** on backend requests that touch user-owned data.
- **User_Owned_Endpoint**: Any ChatLens_Backend endpoint that reads or writes
  account-scoped data: search, refine, chat history, chat delete/clear, library
  listing, image status, image file serving, access grant, and access status.
- **Account_Resolver**: The ChatLens_Backend component that reads the
  **Account_Header** from a request and resolves the owning **Account** for that
  request.
- **Conversation**: A persisted chat owned by exactly one **Account**, consisting of
  an ordered sequence of **Chat_Messages** and associated **Search_Context** (active
  clues / intent) under one **Session_Id**.
- **Session_Id**: The canonical identifier shared between ChatLens_Frontend and
  ChatLens_Backend that identifies a single **Conversation**.
- **Chat_Message**: A persisted turn within a **Conversation** (role, content,
  timestamp) plus, for result-producing turns, **Result_References**.
- **Result_Reference**: Persisted metadata identifying a retrieved memory within a
  **Chat_Message** (e.g. image identity and displayable result metadata). It does NOT
  include image binaries and does NOT include unnecessary filesystem paths.
- **Retrieval_Engine**: The existing `ml/` retrieval capability reached exclusively
  through `backend/ml_retrieval.py` (Chroma visual + text collections, hybrid
  ranking). Its ranking, dedup, and similarity behavior are preserved unchanged.
- **Chroma_Record**: A vector record in the Chroma visual/text collections with
  associated metadata (fingerprint, absolute_path, source_root, etc.).
- **Access_State**: Per-account authorization + indexing state currently held by the
  process-global singleton in `backend/access_service.py`
  (`authorized`, `indexing`, `roots`, `indexedCount`, `error`).
- **Authorized_Locations_Store**: The persisted authorization file(s) currently at
  `backend/authorized_locations.json`, today holding a single global `{"roots": [...]}`.
- **Folder_Watcher**: The `ml/` `FolderWatcher` that triggers incremental indexing on
  eligible filesystem changes.
- **Scoped_Roots**: The only folders ChatLens may authorize/scan — Desktop, Documents,
  Downloads, Pictures under the OS user's home — as returned by
  `LocalImageAccess.default_user_scope()`.
- **Application_Level_Isolation**: The guarantee that data owned by one **Account** is
  never returned, listed, served, read, or deleted on behalf of another **Account**,
  regardless of shared underlying files on disk.
- **Max_Results**: The existing cap of 5 distinct results per search, deduplicated by
  canonical image identity.
- **Similarity_Score**: The existing truthful integer in the range 0–100 derived from
  real per-channel cosine signals (never from the unbounded fused ranking score).

## Requirements

### Requirement 1: Account Identity Bridge (frontend transmits identity)

**User Story:** As a signed-in ChatLens user, I want the frontend to attach my stable account identity to every backend request, so that the backend can associate my data with me without introducing real authentication.

#### Acceptance Criteria

1. WHILE an Account is signed in, THE ChatLens_Frontend SHALL include the Account_Header carrying the signed-in Account_Id on every request to a User_Owned_Endpoint.
2. THE ChatLens_Frontend SHALL set the Account_Id in the Account_Header to the existing stableAccountId(email) value in the form acct-<hex> without generating a new identifier.
3. WHEN an Account logs out, THE ChatLens_Frontend SHALL stop including the previous Account_Id in the Account_Header on all subsequent requests to any User_Owned_Endpoint.
4. WHEN an Account logs out, THE ChatLens_Frontend SHALL clear in-memory conversation state so that no Chat_Message or Result_Reference belonging to the previous Account is displayed after logout.
5. WHILE an Account is signed in, THE ChatLens_Frontend SHALL preserve the existing base URL selection, result URL absolutization, and Content-Type behavior of each request while adding the Account_Header.

### Requirement 2: Account Resolution and Rejection of Unattributed Requests

**User Story:** As the ChatLens system owner, I want the backend to resolve the account from the request header and reject unattributed access to user-owned data, so that anonymous requests cannot read or modify any account's libraries, images, or chats.

#### Acceptance Criteria

1. WHEN a request reaches a User_Owned_Endpoint carrying an Account_Header whose value is a syntactically valid Account_Id, THE Account_Resolver SHALL resolve the owning Account as the Account_Id carried in that Account_Header.
2. IF a request to a User_Owned_Endpoint carries no Account_Header, THEN THE ChatLens_Backend SHALL reject the request with an unauthorized error response, SHALL NOT read any Account's data, and SHALL NOT modify any Account's data.
3. IF a request to a User_Owned_Endpoint carries an Account_Header whose value does not match the Account_Id form acct-<hex>, THEN THE ChatLens_Backend SHALL reject the request with an unauthorized error response, SHALL NOT read any Account's data, and SHALL NOT modify any Account's data.
4. WHERE the requested endpoint is not a User_Owned_Endpoint, THE ChatLens_Backend SHALL process the request without requiring an Account_Header.
5. WHEN the Account_Resolver resolves an Account for a request, THE ChatLens_Backend SHALL restrict every read and every write performed for that request to data owned by the resolved Account.

### Requirement 3: Account-Scoped Conversation Creation

**User Story:** As a signed-in user, I want starting a new chat to create a conversation owned by my account with an agreed session identifier, so that my conversation is durably attributed to me and does not disturb existing conversations.

#### Acceptance Criteria

1. WHEN an Account starts a new chat, THE ChatLens_Backend SHALL create a Conversation whose owning Account_Id equals the resolved Account.
2. WHEN a Conversation is created, THE ChatLens_Backend SHALL assign exactly one Session_Id to that Conversation and SHALL return that same Session_Id to the ChatLens_Frontend as the canonical identifier for the Conversation.
3. WHEN a Conversation is created, THE ChatLens_Backend SHALL record exactly one owning Account_Id for that Conversation.
4. WHEN a Conversation is created, THE ChatLens_Backend SHALL set the owning Account_Id to the resolved Account and SHALL NOT set it to a null, anonymous, previously signed-in, or global account value.
5. WHEN a Conversation is created, THE ChatLens_Backend SHALL persist the new Conversation without modifying or overwriting any existing Conversation.

### Requirement 4: Persisting Search Turns to a Conversation

**User Story:** As a signed-in user, I want my search queries and their results recorded in my conversation, so that I can revisit what I searched and what ChatLens returned.

#### Acceptance Criteria

1. WHEN an Account submits a search on a Conversation, THE ChatLens_Backend SHALL persist the user query as a Chat_Message whose owning Account_Id equals the resolved Account and which is associated with that Conversation's Session_Id.
2. WHEN a search produces one or more results, THE ChatLens_Backend SHALL persist the associated Result_References linked to the search Chat_Message.
3. WHEN a search produces zero results, THE ChatLens_Backend SHALL persist the search Chat_Message with no associated Result_References.
4. WHEN persisting a search turn, THE ChatLens_Backend SHALL record a creation timestamp on the search Chat_Message.
5. WHEN persisting Result_References, THE ChatLens_Backend SHALL exclude image binary data and SHALL exclude filesystem paths from the persisted Result_References.
6. WHEN a search request is processed, THE ChatLens_Backend SHALL persist the search turn and SHALL return the same response payload shape currently returned by POST /api/search.

### Requirement 5: Persisting Refinement Turns to the Same Conversation

**User Story:** As a signed-in user, I want a follow-up refinement to be recorded as part of the same conversation, so that my clue history and context stay together rather than fragmenting into separate chats.

#### Acceptance Criteria

1. WHEN an Account whose Account_Id is resolved from the X-Account-Id request header submits a refinement referencing an existing Session_Id the Account owns, THE ChatLens_Backend SHALL persist the refinement as a Chat_Message appended to that same Conversation.
2. WHEN persisting a refinement turn, THE ChatLens_Backend SHALL persist, with that Chat_Message, the active clues and context semantics supplied with the turn.
3. WHEN an Account submits a refinement referencing an existing owned Session_Id, THE ChatLens_Backend SHALL NOT create a new Conversation for that refinement.
4. IF a refinement references a Session_Id owned by a different Account, THEN THE ChatLens_Backend SHALL reject the request with an authorization (HTTP 403) or not-found (HTTP 404) error and SHALL NOT persist any Chat_Message to that Conversation.
5. IF a refinement request omits a resolvable X-Account-Id or references a Session_Id that does not exist, THEN THE ChatLens_Backend SHALL reject the request with an authorization (HTTP 403) or not-found (HTTP 404) error and SHALL NOT persist any Chat_Message.
6. WHEN a refinement is successfully processed and persisted, THE ChatLens_Backend SHALL return the same result payload shape currently returned by POST /api/refine.

### Requirement 6: Account-Scoped Chat History Retrieval

**User Story:** As a signed-in user, I want to list my past conversations and open one, so that I can continue a previous chat after refreshing or logging back in.

#### Acceptance Criteria

1. WHEN an Account whose Account_Id is resolved from the X-Account-Id request header requests its chat list, THE ChatLens_Backend SHALL return only the Conversations whose owner Account_Id equals the resolved Account_Id.
2. WHEN an Account requests a specific Session_Id whose owner Account_Id equals the resolved Account_Id, THE ChatLens_Backend SHALL return that Conversation's Chat_Messages ordered ascending by turn creation time, together with the Conversation's Result_References and persisted context.
3. IF an Account requests a Session_Id whose owner Account_Id differs from the resolved Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization (HTTP 403) or not-found (HTTP 404) error and SHALL NOT return that Conversation's content.
4. IF an Account requests a Session_Id that does not exist, THEN THE ChatLens_Backend SHALL reject the request with a not-found (HTTP 404) error.
5. THE ChatLens_Backend SHALL NOT satisfy a cross-account, non-existent, or otherwise unauthorized chat request with an HTTP 200 response containing empty content in place of an explicit authorization (HTTP 403) or not-found (HTTP 404) error.

### Requirement 7: Conversation Persistence Across Refresh and Session Change

**User Story:** As a signed-in user, I want my conversations to survive browser refresh and logout/login, so that my visual-memory searches are not lost.

#### Acceptance Criteria

1. WHEN an Account reloads the ChatLens_Frontend, THE ChatLens_Frontend SHALL request and restore the resolved Account's persisted Conversations from the ChatLens_Backend.
2. WHEN an Account logs out, THE ChatLens_Backend SHALL retain all of that Account's persisted Conversations unchanged.
3. WHEN an Account logs back in and requests its chat list, THE ChatLens_Backend SHALL return the same set of Conversations that were persisted for that Account before logout.
4. THE ChatLens_Backend SHALL store Conversations and their Chat_Messages in durable storage that survives a backend process restart, rather than only in process memory.

### Requirement 8: Account-Scoped Chat Deletion / Clearing

**User Story:** As a signed-in user, I want to delete my own conversations without affecting anyone else's, so that clearing my history is safe and scoped to me.

#### Acceptance Criteria

1. WHERE a chat delete or clear capability is provided, WHEN an Account deletes a Session_Id whose owner Account_Id equals the resolved Account_Id, THE ChatLens_Backend SHALL delete only that Conversation and SHALL leave every other Account's Conversations unchanged.
2. IF an Account attempts to delete a Session_Id whose owner Account_Id differs from the resolved Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization (HTTP 403) or not-found (HTTP 404) error and SHALL NOT delete that Conversation.
3. WHERE a clear capability is provided, WHEN an Account invokes it, THE ChatLens_Backend SHALL delete only Conversations whose owner Account_Id equals the resolved Account_Id.
4. THE ChatLens_Backend SHALL NOT provide any operation that deletes all Accounts' Conversations from durable storage indiscriminately.

### Requirement 9: Account-Tagged Index Records and Isolated Retrieval

**User Story:** As a signed-in user, I want search results drawn only from my own indexed images, so that I never see another account's memories even when we share the same folders on disk.

#### Acceptance Criteria

1. WHEN ChatLens_Backend indexes an image for an Account, THE ChatLens_Backend SHALL tag the resulting Chroma_Record with the resolved Account_Id.
2. WHEN an Account performs a search or refinement, THE ChatLens_Backend SHALL restrict the candidate Chroma_Records to only those tagged with the resolved Account_Id before ranking is applied.
3. THE ChatLens_Backend SHALL exclude from any Account's search or refinement results every Chroma_Record whose tagged Account_Id differs from the requesting Account's resolved Account_Id.
4. IF a search or refinement request cannot be associated with a resolved Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization error and SHALL return zero results.
5. WHEN returning search or refinement results, THE ChatLens_Backend SHALL deduplicate results by canonical image identity so that no two returned results share the same canonical image identity.
6. WHEN returning search or refinement results, THE ChatLens_Backend SHALL return at most Max_Results (5) results.
7. WHEN returning search or refinement results, THE ChatLens_Backend SHALL order the returned results using the Retrieval_Engine's existing ranking without reordering by account scoping.
8. WHEN returning a result, THE ChatLens_Backend SHALL report a Similarity_Score that is an integer or decimal value within the inclusive range 0 to 100.
9. WHEN reporting a Similarity_Score, THE ChatLens_Backend SHALL derive the score from the existing real per-channel cosine signals and SHALL NOT substitute a fabricated or placeholder value.
10. WHEN applying account scoping, THE ChatLens_Backend SHALL leave the Retrieval_Engine's ranking, scoring, and dedup logic unchanged, altering only the candidate set restricted by Account_Id.

### Requirement 10: Account-Scoped Image Serving and Library Listing

**User Story:** As a signed-in user, I want image serving and the library view limited to my own images, so that I cannot fetch or browse another account's indexed images.

#### Acceptance Criteria

1. WHEN an Account requests an image file, THE ChatLens_Backend SHALL verify that the requested image is owned by the resolved Account_Id before serving the file.
2. WHEN an Account requests an image file that is owned by the resolved Account_Id and passes the local-folder security checks, THE ChatLens_Backend SHALL serve the file.
3. IF an Account requests an image file that is owned by a different Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization or not-found error and SHALL NOT serve the file.
4. IF an image file request cannot be associated with a resolved Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization error and SHALL NOT serve the file.
5. WHEN an Account requests the library listing, THE ChatLens_Backend SHALL return only the images whose owning Account_Id equals the resolved Account_Id.
6. WHEN an Account requests image processing status, THE ChatLens_Backend SHALL return status only for images whose owning Account_Id equals the resolved Account_Id.
7. IF an Account requests image processing status for an image owned by a different Account_Id, THEN THE ChatLens_Backend SHALL reject the request with an authorization or not-found error and SHALL NOT disclose that image's status.
8. WHEN resolving an image path for serving, THE ChatLens_Backend SHALL apply the existing local-folder security checks, including realpath resolution, source-root and prefix containment, and supported-extension eligibility.
9. IF a requested image path fails any local-folder security check, THEN THE ChatLens_Backend SHALL reject the request with an authorization or not-found error and SHALL NOT serve the file.

### Requirement 11: Per-Account Access, Indexing, and Watcher State

**User Story:** As a signed-in user, I want authorizing folders and indexing to apply to my account only, so that my access state and index progress are independent of other accounts on the same machine.

#### Acceptance Criteria

1. THE ChatLens_Backend SHALL maintain a separate Access_State (authorized, indexing, roots, indexedCount, error) keyed by Account_Id rather than as a single process-global value.
2. WHEN an Account grants access, THE ChatLens_Backend SHALL derive the roots server-side from Scoped_Roots and SHALL NOT accept caller-supplied paths.
3. WHEN an Account grants access, THE ChatLens_Backend SHALL start indexing scoped to the resolved Account_Id.
4. WHEN an Account requests access status, THE ChatLens_Backend SHALL return the Access_State associated with the resolved Account_Id only.
5. WHEN indexing runs for an Account, THE ChatLens_Backend SHALL perform it asynchronously and SHALL return the access-grant response without waiting for indexing to complete.
6. IF indexing fails for an Account, THEN THE ChatLens_Backend SHALL set that Account's indexing state to a failed state, record the error in that Account's Access_State, and SHALL NOT start that Account's Folder_Watcher.
7. WHEN the Folder_Watcher detects an eligible change for an Account's authorized roots, THE ChatLens_Backend SHALL update the index for that Account_Id only.
8. THE ChatLens_Backend SHALL restrict authorizable roots to Scoped_Roots, defined as the Desktop, Documents, Downloads, and Pictures folders under the OS user's home directory.
9. IF a candidate root resolves to a path outside Scoped_Roots, THEN THE ChatLens_Backend SHALL reject that root and SHALL NOT index it.

### Requirement 12: Per-Account Authorization Persistence (Safe Migration of the Global File)

**User Story:** As the ChatLens system owner, I want per-account authorization persistence introduced without destroying the existing global authorization file, so that no existing dev state is silently lost.

#### Acceptance Criteria

1. THE ChatLens_Backend SHALL persist authorization state keyed by Account_Id rather than in a single shared Authorized_Locations_Store acting as one global account.
2. WHEN the ChatLens_Backend restarts, THE ChatLens_Backend SHALL restore each Account's persisted authorization state.
3. WHEN the ChatLens_Backend restarts and an Account has valid persisted roots, THE ChatLens_Backend SHALL restart that Account's Folder_Watcher without performing a full re-index.
4. WHEN introducing per-account authorization persistence, THE ChatLens_Backend SHALL retain the contents of the existing backend/authorized_locations.json and SHALL NOT delete or overwrite it in a way that discards its contents without a defined handling path.
5. IF existing global authorization data cannot be safely attributed to a specific Account_Id, THEN THE ChatLens_Backend SHALL preserve that data unattributed and SHALL NOT fabricate an owning Account_Id for it.

### Requirement 13: Safe Data Migration and Schema Evolution

**User Story:** As the ChatLens system owner, I want account ownership added to existing data without blindly recreating the databases, so that recoverable dev data is preserved and unattributable data is not given a fabricated owner.

#### Acceptance Criteria

1. THE ChatLens_Backend SHALL add an Account_Id ownership field to the persisted chat data structures and to the persisted image data structures.
2. WHEN evolving the SQLite schema, THE ChatLens_Backend SHALL inspect the existing schema to determine whether the Account_Id columns already exist before applying any change.
3. WHEN the existing schema is missing an Account_Id column, THE ChatLens_Backend SHALL add that column while retaining all existing rows that already conform to the pre-migration schema.
4. IF inspecting the existing schema or applying a schema change fails, THEN THE ChatLens_Backend SHALL abort the migration, leave the existing chatlens.db, chroma_db, and authorized_locations.json data unchanged, and surface an error indicating the migration did not complete.
5. THE ChatLens_Backend SHALL NOT unconditionally delete or recreate chatlens.db, chroma_db, or authorized_locations.json as part of introducing account scoping.
6. IF existing chat, image, or index data cannot be safely attributed to a specific Account, THEN THE ChatLens_Backend SHALL NOT assign any Account_Id to that data.
7. WHERE existing dev data cannot be safely attributed and a reset of the local dev data is unavoidable, THE ChatLens_Backend documentation SHALL describe the reset/migration strategy explicitly before the reset is applied.

### Requirement 14: Cross-Account Isolation Invariants (Correctness Properties)

**User Story:** As the ChatLens system owner, I want testable isolation invariants, so that cross-account leakage can be verified by property-based tests across chats, library, image serving, and retrieval.

#### Acceptance Criteria

1. FOR ALL pairs of distinct Accounts A and B and any persisted chat, image, or index data item owned by A, THE ChatLens_Backend SHALL NOT return, list, serve, or read that item on behalf of B via chat retrieval, library listing, image serving, or search/refine retrieval (cross-account isolation invariant).
2. FOR ALL persisted Conversations, THE ChatLens_Backend SHALL record exactly one owning Account_Id (single-owner invariant).
3. FOR ALL Session_Ids owned by Account A, THE ChatLens_Backend SHALL NOT allow Account B to read the corresponding Conversation (session read-isolation invariant).
4. FOR ALL Session_Ids owned by Account A, THE ChatLens_Backend SHALL NOT allow Account B to delete the corresponding Conversation (session delete-isolation invariant).
5. FOR ALL sets of search results returned to an Account, the number of distinct results SHALL be at most Max_Results (bounded-results invariant).
6. FOR ALL images contained in search results returned to an Account, each returned image SHALL be owned by that Account (owned-results invariant).

### Requirement 15: Preservation of Existing Behavior and Explicit Non-Goals

**User Story:** As the ChatLens team, I want this refactor to preserve existing behavior and stay within Phase 1 scope, so that account scoping does not regress retrieval or pull in unrelated work.

#### Acceptance Criteria

1. THE ChatLens_Backend SHALL preserve the existing retrieval and ranking behavior of the Retrieval_Engine unchanged.
2. THE ChatLens_Backend SHALL preserve the existing Max_Results cap unchanged.
3. THE ChatLens_Backend SHALL preserve the existing canonical dedup behavior unchanged.
4. THE ChatLens_Backend SHALL preserve the existing truthful 0-100 Similarity_Score derived from real cosine signals unchanged.
5. THE ChatLens_Backend SHALL preserve the existing local-folder security checks (realpath/prefix containment and supported-extension eligibility) unchanged.
6. THE ChatLens_Backend SHALL preserve the existing Desktop/Documents/Downloads/Pictures-only scanning constraint unchanged.
7. THE ChatLens_Backend SHALL NOT introduce an LLM agent or orchestrator as part of this feature.
8. THE ChatLens_Backend SHALL NOT introduce real authentication (JWT or passwords) as part of this feature.
9. THE ChatLens_Backend SHALL NOT introduce deployment work or git commit/push activity as part of this feature.
10. THE ChatLens_Frontend and ChatLens_Backend SHALL keep the existing automated tests passing after this feature is implemented.

### Requirement 16: Regression and Isolation Test Coverage

**User Story:** As the ChatLens team, I want new isolation and chat-persistence tests plus coverage of the representative query scenarios, so that both the new scoping and the preserved retrieval behavior are verified.

#### Acceptance Criteria

1. THE ChatLens test suite SHALL include a test verifying that Account A's chats are not accessible to Account B.
2. THE ChatLens test suite SHALL include a test verifying that Account A's library listing, served images, and retrieval results are not accessible to Account B.
3. THE ChatLens test suite SHALL include a test verifying that a Conversation created by an Account persists across a simulated refresh and a simulated logout/login and is restored for that Account.
4. THE ChatLens test suite SHALL include a test verifying that a request to a User_Owned_Endpoint without a valid Account_Header is rejected with an explicit error and no owned data is returned.
5. THE ChatLens test suite SHALL include a test verifying that a cross-account chat or image request is rejected with an explicit authorization or not-found error rather than a 200-with-empty-body response.
6. THE ChatLens test suite SHALL exercise the representative retrieval scenarios - "Find my CN notes about OSI", "Find the screenshot of my Python login error", "Find that confused guy meme", "Find my handwritten database notes", "Find the CN notes with a large diagram" - and verify results remain scoped to the requesting Account.
7. THE ChatLens test suite SHALL exercise the conversational refinement sequence ("Find my CN notes about OSI" -> "No, I remember they were handwritten" -> "There was a large diagram") and verify that the original intent is preserved, that clues accumulate on the same Conversation, and that the Conversation stays owned by the requesting Account.
8. THE ChatLens test suite SHALL include a test verifying that a new chat is not created under a null, anonymous, previous, or global account and does not overwrite an existing Conversation.
