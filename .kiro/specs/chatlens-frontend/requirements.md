# Requirements Document

## Introduction

ChatLens is an AI-powered personal visual memory search engine that lets users find images by describing what they remember rather than by filename or exact keywords. This specification covers the **frontend-only React web application** that delivers the ChatLens core loop: **Remember → Search → Refine → Explain → Act**.

This feature is scoped strictly to the frontend module (`frontend/`). Backend, AI, OCR, CLIP, embeddings, hybrid retrieval, ranking, and the conversational agent are owned by other team members and are consumed through an HTTP API service layer. The Frontend is loosely coupled from the Backend: all network communication passes through a single API service module.

The Frontend renders **only Backend-provided data**. It never fabricates retrieval signals, explanations, match scores, timestamps, personal history, source information, or metadata. When a field is absent from a Backend response, the Frontend omits the corresponding UI rather than inventing a placeholder value.

The API endpoints referenced in this document are a **proposed contract that requires Backend team sign-off**. They are not yet present in the repository. The Frontend is built against mocked or stubbed responses and does not depend on any endpoint being confirmed as implemented.

## Glossary

- **Frontend**: The React web application described by this specification. It runs in the browser and communicates with the Backend exclusively through the API_Service.
- **API_Service**: The single Frontend module responsible for all HTTP communication with the Backend. No other Frontend module issues network calls directly.
- **Backend**: The server-side system (owned by other team members) that provides ingestion, OCR, CLIP embeddings, hybrid retrieval, ranking, explanations, and agent responses over HTTP.
- **Search_Workspace**: The primary Frontend screen that hosts the Conversation_Panel and the Results_Panel.
- **Conversation_Panel**: The region of the Search_Workspace that displays the Session_Transcript and the natural-language search/chat input.
- **Results_Panel**: The region of the Search_Workspace that displays ranked Result_Card items, the echoed query, the result count, and the Active_Clue_Set chips.
- **Result_Card**: A single UI element representing one image returned by the Backend, showing available fields such as identifier, thumbnail, Match_Score, OCR snippet, and source/type tag.
- **Explanation_Panel**: The UI region that presents the "Why this result?" evidence for a Result_Card using Backend-provided Explanation_Signal items.
- **Explanation_Signal**: A single piece of retrieval evidence supplied by the Backend (for example, an OCR match, semantic similarity, or visual match) rendered as an icon-plus-text checklist item.
- **Match_Score**: A numeric relevance value supplied by the Backend for a Result_Card. It is supporting context and is never the sole content of an explanation.
- **Memory_Clue**: A detail a user remembers about an image (topic, appearance, content type, visual element, partial text) used as an additional retrieval signal.
- **Active_Clue_Set**: The current collection of Memory_Clue items applied to the ongoing search, displayed as removable chips.
- **Session_Transcript**: The ordered, in-memory record of user messages and agent responses for the current session.
- **Session_Id**: An identifier associated with the current conversation session, sent with search and refinement requests so the Backend can maintain context.
- **Resolved_Intent**: A Backend-provided field indicating how the Frontend should render an agent turn (for example, search, refinement, explanation, summarize, roadmap, schedule).
- **Upload_Queue**: The Frontend list of files a user has selected or dropped for ingestion, each with its own validation and Processing_Status state.
- **Processing_Status**: A Backend-provided status for an ingested image (for example, uploaded, processing, indexed, ready, failed).
- **Summary_Card**: A distinct UI element that renders a Backend-generated summary of retrieved memories.
- **Roadmap_Card**: A distinct UI element that renders a Backend-generated ordered plan of steps.
- **Schedule_Proposal**: A Backend-generated proposed set of calendar events shown to the user for review before confirmation.
- **Confirm_Dialog**: A modal dialog presenting explicit confirm and cancel controls, used before any schedule confirmation is sent.
- **Image_Detail_Drawer**: A drawer or modal that shows a full image, its OCR text, available metadata, and its Explanation_Panel.

## Requirements

### Requirement 1: Search Workspace Layout

**User Story:** As a user, I want a workspace that shows my conversation alongside my results, so that I can search and see visual memories at the same time.

#### Acceptance Criteria

1. THE Frontend SHALL display the Search_Workspace as the default screen on application load.
2. WHILE the viewport width is greater than or equal to 1024 CSS pixels, THE Search_Workspace SHALL present the Conversation_Panel and the Results_Panel in a two-pane layout.
3. WHILE the viewport width is less than 1024 CSS pixels, THE Search_Workspace SHALL present the Conversation_Panel and the Results_Panel in a single-column stacked or tabbed layout.
4. WHILE the viewport width is less than 768 CSS pixels, THE Conversation_Panel SHALL present the search/chat input as a sticky element anchored to the bottom of the viewport.

### Requirement 2: Natural-Language Search Input

**User Story:** As a user, I want to type what I remember about an image, so that I can find it without knowing its filename.

#### Acceptance Criteria

1. THE Conversation_Panel SHALL present a single unified input that accepts both search queries and conversational messages.
2. WHILE the search/chat input is empty, THE Conversation_Panel SHALL display example memory placeholder text.
3. WHEN a user submits a query containing at least one non-whitespace character, THE Frontend SHALL send the query to the Backend through the API_Service.
4. IF a user submits a query containing only whitespace characters, THEN THE Frontend SHALL reject the submission and SHALL NOT send a request through the API_Service.

### Requirement 3: Ranked Result Cards

**User Story:** As a user, I want to see ranked image results, so that I can identify the memory I was looking for.

#### Acceptance Criteria

1. WHEN the Backend returns search results, THE Results_Panel SHALL render one Result_Card per returned image in the order provided by the Backend.
2. THE Result_Card SHALL render only the fields supplied by the Backend for that image, including identifier, thumbnail, Match_Score, OCR snippet, and source or type tag when present.
3. IF a Backend-supplied image omits a field, THEN THE Result_Card SHALL omit the corresponding UI element for that field.
4. THE Result_Card SHALL present a "Why this result?" trigger.
5. THE Result_Card SHALL be selectable and keyboard-focusable so that a user can choose it for a summarize action.

### Requirement 4: Conversational Refinement Enriches Context

**User Story:** As a user, I want my follow-up messages to refine my previous search, so that I can add details I remember without starting over.

#### Acceptance Criteria

1. THE Conversation_Panel SHALL preserve the Session_Transcript in the order that messages and responses occur.
2. WHEN a user submits a follow-up message, THE Frontend SHALL send the message together with the Session_Id through the API_Service.
3. WHEN the Backend resolves a follow-up as a refinement, THE Frontend SHALL retain the Active_Clue_Set, add the new Memory_Clue, and re-render the Results_Panel in place.
4. WHILE a refinement request is in progress, THE Results_Panel SHALL display a visible refining indicator.
5. WHEN the Backend resolves a follow-up as a new search, THE Frontend SHALL replace the current results and reset the Active_Clue_Set.

### Requirement 5: Intent-Driven Rendering

**User Story:** As a user, I want the interface to respond correctly to what I asked, so that refinements, explanations, and actions appear in the right form.

#### Acceptance Criteria

1. WHEN an agent response includes a Resolved_Intent field, THE Frontend SHALL render the response according to the value of the Resolved_Intent field.
2. WHILE a Resolved_Intent field is present on an agent response, THE Frontend SHALL NOT infer intent from the message text.
3. IF an agent response omits the Resolved_Intent field, THEN THE Frontend SHALL render the response as an agent message and SHALL display an error state.

### Requirement 6: Active Memory Clue Chips

**User Story:** As a user, I want to see and manage the clues applied to my search, so that I can control how my results are refined.

#### Acceptance Criteria

1. WHILE the Active_Clue_Set contains at least one Memory_Clue, THE Results_Panel SHALL display each Memory_Clue as a removable chip in the results header.
2. THE Results_Panel SHALL display the echoed query and the result count in the results header.
3. WHEN a user removes a Memory_Clue chip, THE Frontend SHALL re-query through the API_Service using the updated Active_Clue_Set and the Session_Id.
4. WHILE the Active_Clue_Set is empty, THE Results_Panel SHALL display no clue chips.

### Requirement 7: Why This Result Explanation

**User Story:** As a user, I want to understand why an image was retrieved, so that I can trust the results.

#### Acceptance Criteria

1. WHEN a user activates the "Why this result?" trigger, THE Explanation_Panel SHALL render each Backend-provided Explanation_Signal as an icon-plus-text checklist item.
2. THE Explanation_Panel SHALL render only the Explanation_Signal items present in the Backend response.
3. THE Explanation_Panel SHALL NOT display a reason that is absent from the Backend payload.
4. WHERE a Match_Score is present, THE Explanation_Panel SHALL display the Match_Score as supporting context and SHALL NOT display the Match_Score as the sole content of the explanation.
5. IF the Backend response contains no Explanation_Signal items, THEN THE Explanation_Panel SHALL display an explanation-not-available state.

### Requirement 8: Image Upload and Ingestion

**User Story:** As a user, I want to add my images to ChatLens, so that they become searchable visual memories.

#### Acceptance Criteria

1. THE Frontend SHALL present a drag-and-drop dropzone and a file picker for adding images.
2. THE Upload_Queue SHALL accept multiple files in a single selection or drop.
3. WHEN a user adds files, THE Frontend SHALL validate each file's type and size on the client before sending.
4. IF a file fails client-side validation, THEN THE Frontend SHALL reject that file with a message and SHALL continue processing the remaining valid files.
5. WHEN a file passes client-side validation, THE Frontend SHALL send the file to the Backend ingestion endpoint through the API_Service.
6. THE Frontend SHALL NOT perform OCR or CLIP embedding on images.

### Requirement 9: Processing and Loading States

**User Story:** As a user, I want to see what the system is doing, so that I know whether to wait or act.

#### Acceptance Criteria

1. WHEN the Backend reports a Processing_Status for an image, THE Frontend SHALL display that Processing_Status.
2. WHILE an image Processing_Status is uploaded, processing, or indexed, THE Frontend SHALL display a processing indicator for that image.
3. WHILE an image Processing_Status is ready, THE Frontend SHALL display a ready indicator for that image.
4. WHILE a retrieval request is in progress, THE Results_Panel SHALL display skeleton Result_Card placeholders.
5. WHILE an agent turn is in progress, THE Conversation_Panel SHALL display an in-progress indicator.

### Requirement 10: Empty States

**User Story:** As a user, I want helpful guidance when there is nothing to show, so that I know how to get started.

#### Acceptance Criteria

1. WHILE no query has been submitted in the session, THE Results_Panel SHALL display an onboarding empty state that includes example queries.
2. WHEN the Backend returns zero results for a query, THE Results_Panel SHALL display a no-results state that suggests adding a Memory_Clue.
3. WHILE the Upload_Queue contains no files, THE Frontend SHALL display an empty upload-queue state.

### Requirement 11: Error States and Retry

**User Story:** As a user, I want to recover from errors, so that a failed request does not block my work.

#### Acceptance Criteria

1. IF a retrieval request fails, THEN THE Results_Panel SHALL display a retrieval error state with a retry control.
2. IF an upload request fails for a file, THEN THE Frontend SHALL display an upload error state for that file with a retry control.
3. IF an action request fails, THEN THE Frontend SHALL display an action error state with a retry control.
4. WHEN a user activates a retry control, THE Frontend SHALL resend the failed request through the API_Service.
5. IF the Backend reports a Processing_Status of failed for an image, THEN THE Frontend SHALL display a processing-failed state for that image with a retry control.
6. WHILE the browser reports the network as offline, THE Frontend SHALL display an offline indicator.

### Requirement 12: Summarization Action

**User Story:** As a user, I want to summarize retrieved memories, so that I can quickly understand their content.

#### Acceptance Criteria

1. WHEN the Backend returns a summary, THE Frontend SHALL render the summary in a distinct Summary_Card.
2. THE Summary_Card SHALL indicate which memories were used by displaying the Backend-provided response identifiers.
3. WHEN a user requests a summary of selected Result_Card items, THE Frontend SHALL send the selected image identifiers together with the Session_Id through the API_Service.

### Requirement 13: Roadmap Generation

**User Story:** As a user, I want to turn retrieved notes into a plan, so that I can act on what I found.

#### Acceptance Criteria

1. WHEN the Backend returns a roadmap, THE Frontend SHALL render the roadmap steps as an ordered list in a Roadmap_Card.
2. THE Roadmap_Card SHALL render only the steps supplied by the Backend.
3. THE Roadmap_Card SHALL present a "Schedule this" control that opens a Schedule_Proposal.

### Requirement 14: Schedule Proposal Requires Confirmation

**User Story:** As a user, I want to confirm before any calendar events are created, so that nothing is scheduled without my approval.

#### Acceptance Criteria

1. WHEN a user activates the "Schedule this" control, THE Frontend SHALL request a Schedule_Proposal through the API_Service and SHALL display a preview of the proposed events.
2. THE Frontend SHALL present a Confirm_Dialog with an explicit confirm control and an explicit cancel control.
3. WHEN a user activates the cancel control, THE Confirm_Dialog SHALL close and THE Frontend SHALL send no schedule confirmation.
4. WHEN a user activates the confirm control, THE Frontend SHALL send a schedule confirmation through the API_Service.
5. THE Frontend SHALL NOT send a schedule confirmation until a user activates the confirm control.

### Requirement 15: In-Session Transcript Only

**User Story:** As a user, I want my conversation to support refinement during my session, so that follow-ups work without long-term tracking of my activity.

#### Acceptance Criteria

1. THE Frontend SHALL retain the Session_Transcript in memory for the duration of the session to support refinement.
2. THE Frontend SHALL NOT persist the Session_Transcript beyond the session.
3. WHEN the session ends, THE Frontend SHALL discard the Session_Transcript.

### Requirement 16: Image Detail View

**User Story:** As a user, I want to inspect a single memory in detail, so that I can read its text and metadata.

#### Acceptance Criteria

1. WHEN a user opens a Result_Card for detail, THE Image_Detail_Drawer SHALL display the full image, the OCR text, the available metadata, and the Explanation_Panel.
2. THE Image_Detail_Drawer SHALL render only the metadata fields supplied by the Backend.
3. IF a metadata field is absent from the Backend response, THEN THE Image_Detail_Drawer SHALL omit the corresponding UI element.
4. WHILE the viewport width is less than 768 CSS pixels, THE Image_Detail_Drawer SHALL display in full-screen.

### Requirement 17: Proposed API Contract and Mock Operation

**User Story:** As a developer, I want a single documented API boundary that can run against mocks, so that the Frontend progresses independently of Backend readiness.

#### Acceptance Criteria

1. THE API_Service SHALL be the only Frontend module that issues HTTP calls to the Backend.
2. THE API_Service SHALL document each endpoint as a proposed contract that requires Backend team sign-off.
3. WHERE no live Backend is configured, THE API_Service SHALL operate against stubbed responses.
4. THE Frontend SHALL NOT depend on any Backend endpoint being confirmed as implemented.
5. THE API_Service SHALL define the proposed endpoints: POST /api/search, POST /api/refine (or POST /api/search with a Session_Id), GET /api/results/{id}/explanation (or an embedded explanation), POST /api/actions/summarize, POST /api/actions/roadmap, POST /api/actions/schedule/propose, POST /api/actions/schedule/confirm, POST /api/images, and GET /api/images/{id}/status.

### Requirement 18: Data Integrity

**User Story:** As a user, I want to trust that what I see reflects real data, so that ChatLens does not mislead me.

#### Acceptance Criteria

1. THE Frontend SHALL render retrieval signals, Match_Score values, timestamps, source information, and metadata only when present in the Backend response.
2. IF a field is absent from a Backend response, THEN THE Frontend SHALL omit the field and SHALL NOT display a placeholder value.
3. THE Frontend SHALL NOT generate image descriptions, personal history, or retrieval reasons that are not supplied by the Backend.

### Requirement 19: Responsive Presentation

**User Story:** As a user, I want ChatLens to work across screen sizes, so that I can use it on desktop and smaller devices.

#### Acceptance Criteria

1. WHILE the viewport width is greater than or equal to 1024 CSS pixels, THE Search_Workspace SHALL present a two-pane layout.
2. WHILE the viewport width is less than 1024 CSS pixels, THE Search_Workspace SHALL present a single-column layout.
3. WHILE the viewport width is less than 768 CSS pixels, THE Frontend SHALL render interactive touch targets at a minimum size of 44 by 44 CSS pixels.

### Requirement 20: Accessibility

**User Story:** As a user who relies on assistive technology, I want ChatLens to be operable and understandable, so that I can search my memories.

#### Acceptance Criteria

1. THE Frontend SHALL support keyboard navigation across the search/chat input, the Result_Card items, and the Image_Detail_Drawer.
2. THE Frontend SHALL display a visible focus indicator on the currently focused element.
3. THE Conversation_Panel SHALL expose the Session_Transcript with an ARIA log role and SHALL announce agent responses through a live region.
4. WHILE the Confirm_Dialog is open, THE Frontend SHALL trap keyboard focus within the Confirm_Dialog.
5. THE Frontend SHALL derive image alt text from Backend-provided OCR or metadata, and WHERE such text is absent, THE Frontend SHALL provide a meaningful non-fabricated fallback.
6. THE Explanation_Panel SHALL convey each Explanation_Signal through both an icon and text rather than color alone.

### Requirement 21: Module Structure and Build Tooling

**User Story:** As a developer, I want a clear frontend module structure, so that the Frontend stays loosely coupled and maintainable.

#### Acceptance Criteria

1. THE Frontend SHALL reside in a `frontend/` module that is separate from the Backend.
2. THE Frontend SHALL organize source code into `api`, `components`, `features`, `state`, `hooks`, `pages`, `styles`, and `utils` folders.
3. THE Frontend SHALL manage application state using React Context with useReducer or a lightweight store, organized into conversation, results, ingestion, actions, and ui slices.
4. THE Frontend SHALL NOT introduce a heavyweight application framework beyond React and its build tooling.
