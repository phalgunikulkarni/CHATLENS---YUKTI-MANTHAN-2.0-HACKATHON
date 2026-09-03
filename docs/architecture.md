# ChatLens — System Architecture

## 1. Architecture Overview

ChatLens follows a modular pipeline that connects image ingestion, image understanding, hybrid retrieval, conversational intelligence, and user actions.

There is a **single conversational LLM / orchestrator** — not a multi-agent system. The orchestrator sits between user interaction and the retrieval engine: it formulates queries, sends them to a separate retrieval engine, receives ranked results back, and then explains, refines, or acts on them. The orchestrator is not itself an OCR, CLIP, or vector-search component.

The core flow is:

> **User → Frontend → Backend → Conversational LLM/Orchestrator → Retrieval Engine → Ranked Results → Orchestrator → Actions**

The architecture should allow individual components to be improved or replaced without rewriting the entire application.

---

# 2. High-Level Architecture

```text
                         ┌──────────────┐
                         │     USER     │
                         └──────┬───────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │    React Frontend   │
                    │                     │
                    │ Search + Chat UI    │
                    │ Results + Actions   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    FastAPI Backend  │
                    │                     │
                    │ API + Orchestration │
                    └──────────┬──────────┘
                               │
                               ▼
           ┌────────────────────────────────────────┐
           │   Conversational LLM / Orchestrator      │
           │   (ONE agent — NOT multi-agent)          │
           │                                          │
           │ Intent + Context                         │
           │ Query Refinement                         │
           │ Action Selection                         │
           └───────┬──────────────────────────▲───────┘
                   │ Query                     │ Ranked Results
                   ▼                           │
          ┌──────────────────────────────────────────┐
          │           Retrieval Engine               │
          │  (separate capability — NOT the LLM)     │
          │                                          │
          │  OCR/Text  Semantic/Text  CLIP Visual    │
          │            Embeddings     Metadata       │
          └──────────┬───────────────────────────────┘
                     │
                     ▼
              Candidate Results
                     │
                     ▼
                  Re-ranking
                     │
                     ▼
               Ranked Results ──────────────────────┐
                                                     │
                              (returned to Orchestrator, above)
                                                     │
                                                     ▼
                                       ┌─────────────────────┐
                                       │     Action Layer    │
                                       │                     │
                                       │ Explain             │
                                       │ Refine              │
                                       │ Summary             │
                                       │ Roadmap / Plan      │
                                       │ Reminder            │
                                       │ Calendar Action     │
                                       └─────────────────────┘
```

Ranked results flow back to the orchestrator, which then decides whether to explain
("Why This Result?"), refine the search, or invoke an action. The LLM never acts as an
OCR/CLIP/vector-search node — it formulates queries and interprets results only.

3. Image Ingestion Layer

The ingestion layer is responsible for bringing images into ChatLens.

Initial sources

The prototype may support:

Local/imported images
Exported media
Other supported sources as integrations become available

External sources — including local folders and a planned Telegram connector/plugin
(Telegram planned, not yet implemented) — feed the SAME overall ingestion/retrieval
architecture. Local/folder access and Telegram follow the same ingestion principles, and
the system should handle incrementally-arriving content as new content becomes available.

The ingestion layer should be independent from the retrieval system.

Image Source
     ↓
Image Ingestion
     ↓
Validation
     ↓
Image Storage
     ↓
Processing
Important

Available metadata should be preserved.

The system must not invent unavailable timestamps, viewing history, or personal history.

4. Image Processing Pipeline

Each image is processed to generate searchable information.

                         IMAGE
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
            OCR           CLIP        Metadata
             │          Embedding         │
             │             │              │
             └─────────────┼──────────────┘
                           ▼
                     Image Record
4.1 OCR

OCR extracts text from images.

Useful for:

Screenshots
Handwritten notes
Documents
Receipts
Lecture slides
Code screenshots

The extracted text becomes searchable through the text/keyword retrieval layer.

4.2 CLIP Visual Embeddings

CLIP is used to generate visual embeddings.

These embeddings help represent the visual/semantic characteristics of an image.

Useful for:

Memes
Images with little text
Visually distinctive screenshots
Images described by appearance
Visual characteristics such as handwritten/document-like content

The embedding is stored in the vector search layer.

4.3 Metadata

Where available, store:

Image ID
Source
Filename/file information
Timestamp
Other relevant metadata

Metadata should only represent information that actually exists.

5. Storage Layer

ChatLens has three primary storage requirements.

5.1 Image Storage

Stores the original images.

5.2 Relational Database

Initial technology:

SQLite

Stores structured application information such as:

Image ID
OCR text
Source
Metadata
Processing status
Embedding references
Application state
5.3 Vector Store

Initial direction:

FAISS / ChromaDB

Stores and retrieves image/vector representations for similarity search.

6. Search Architecture

ChatLens uses hybrid retrieval.

The Retrieval Engine is a **separate capability** from the orchestrator. It combines
OCR/text, semantic/text embeddings, CLIP visual embeddings, metadata, and memory/query
clues to produce ranked results via ranking/re-ranking. It relies on more than only OCR
or only vector similarity.

The "Conversational Agent" shown above the query is the **single orchestrator**: it
formulates the query and interprets the results. It is not itself a retrieval modality.

                    USER QUERY
                         │
                         ▼
             Conversational Agent (Orchestrator)
                         │
                         ▼
                  Query Representation
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      OCR/Text        Semantic        CLIP
       Search        Embeddings     Visual Search
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Candidate Results
                         │
                         ▼
                      Re-ranking
                         │
                         ▼
                   Ranked Results
7. Query Processing

The intelligent agent (single orchestrator) converts the user's natural-language request into useful retrieval information.

Example:

"Find the screenshot with the error message."

Possible query signals:

Topic:
Error message

Content:
Screenshot

Visual clue:
On-screen text / dialog

The retrieval layer uses these signals to search the visual memory index.

8. Conversational Retrieval

Conversational retrieval is one of the core architectural features.

The single orchestrator maintains relevant context across turns.

Example:

User:
Find the screenshot with the error message.
             │
             ▼
        First Retrieval
             │
             ▼
          Results

User:
No, the one with the red button.
             │
             ▼
      Update Context
             │
             ▼
       Re-query / Re-rank
             │
             ▼
      Improved Results

User:
It also had a stack trace.
             │
             ▼
      Update Context Again
             │
             ▼
       Re-query / Re-rank

The original intent should not be discarded when a user adds a new clue.

9. Retrieval and Ranking

Each retrieval method produces candidate results.

The ranking layer combines available signals.

Conceptually:

Final Score =
    Text Relevance
  + Semantic Similarity
  + Visual Similarity
  + Metadata Relevance
  + Memory Clue Relevance

The exact weighting can be tuned during implementation and testing.

The ranking system should retain enough information to explain the result.

10. Intelligent Agent

The conversational LLM acts as the orchestration and reasoning layer. It is a **single orchestrator — not a multi-agent system**, and it does not perform OCR, CLIP, or vector search itself.

It connects:

User
 ↓
Orchestrator
 ├── Search
 ├── Refine Search
 ├── Explain
 └── Act

The agent determines what the user is trying to do.

Possible intents include:

Search for a memory
Refine an existing search
Ask why a result was selected
Summarize retrieved content
Generate a roadmap
Create a reminder
Schedule a generated plan

Its possible actions include Summarize, Roadmap/Plan, Reminder, and Calendar Action.
These are action-layer capabilities, not retrieval-engine functions.

The agent should not become a generic unrelated chatbot.

11. Agent → Retrieval Interaction

The relationship between the single orchestrator and the separate retrieval engine is:

             User Message
                  │
                  ▼
     Intelligent Agent (Orchestrator)
                  │
          Understand Intent
                  │
          Extract Memory Clues
                  │
                  ▼
            Search Query
                  │
                  ▼
          Hybrid Retrieval
                  │
                  ▼
            Ranked Results
                  │
                  ▼
          Agent Interprets
                  │
                  ▼
             User Response

For conversational refinement:

Previous Context
       +
New User Clue
       ↓
Updated Agent Context
       ↓
Updated Query
       ↓
Retrieval Again
12. "Why This Result?" Architecture

The retrieval system should expose the signals that contributed to ranking.

                 Retrieved Image
                       │
             ┌─────────┼─────────┐
             ▼         ▼         ▼
           OCR       Semantic    CLIP
          Signal      Signal    Signal
             │         │         │
             └─────────┼─────────┘
                       ▼
                  Rank / Score
                       │
                       ▼
              Explanation Data
                       │
                       ▼
               Why This Result?

Example:

Why this result?

✓ OCR matched "error"
✓ Semantically related to the query text
✓ Visual characteristics matched an on-screen dialog
✓ Metadata matched the requested source

The explanation must be based on ACTUAL retrieval evidence/signals exposed by the
retrieval engine. It must never fabricate visual detections, metadata, personal history,
retrieval signals, or similarity reasons that retrieval did not actually produce.

13. Action Layer

Actions operate on retrieved memories. They belong to the orchestration/action layer,
not the retrieval engine.

13.1 Summarization
Retrieved Images
       ↓
OCR / Extracted Content
       ↓
Agent / LLM
       ↓
Summary

The user can ask:

"Summarize these notes."

13.2 Roadmap Generation
Retrieved Content
       ↓
Content Understanding
       ↓
Agent / LLM
       ↓
Structured Roadmap

Example:

"Create a 3-day revision plan from these notes."

13.3 Reminder

A reminder must be grounded in a genuine event, task, or deadline found in available
content or provided by user input.

Retrieved Content / User Input
       ↓
Identify Genuine Event / Task / Deadline
       ↓
Propose Reminder
       ↓
User Confirmation
       ↓
Reminder Created

The system must never invent dates or times, and it requires explicit user confirmation
where appropriate before creating a reminder.

13.4 Calendar Integration

Calendar scheduling follows a confirmation-based workflow.

Retrieved Content
       ↓
Generate Roadmap
       ↓
Generate Proposed Schedule
       ↓
User Confirmation
       ↓
Calendar API
       ↓
Calendar Events

The orchestrator proposes an event or reminder and requires explicit confirmation. The
system should not create external calendar events without confirmation and does not
autonomously manage the calendar.

These actions belong to the orchestration/action layer, not the retrieval engine.

14. End-to-End Example
USER
 │
 │ "Find the screenshot with the error message."
 ▼
FRONTEND
 │
 ▼
BACKEND
 │
 ▼
INTELLIGENT AGENT (ORCHESTRATOR)
 │
 │ Understand intent
 ▼
RETRIEVAL ENGINE
 ├── OCR/Text
 ├── Semantic/Text Embeddings
 ├── CLIP Visual
 └── Metadata
 │
 ▼
RANKING
 │
 ▼
RESULTS
 │
 ├── Why this result?
 │
 │
 └── User:
     "No, the one with the red button."
              │
              ▼
       ORCHESTRATOR UPDATES CONTEXT
              │
              ▼
       RETRIEVAL AGAIN
              │
              ▼
       IMPROVED RESULTS
              │
              ▼
       User:
       "Summarize these."
              │
              ▼
           SUMMARY
              │
              ▼
       User:
       "Make a 3-day plan."
              │
              ▼
           ROADMAP
              │
              ▼
       User:
       "Remind me about step 1 tomorrow."
              │
              ▼
       PROPOSED REMINDER
              │
              ▼
       CONFIRMATION
              │
              ▼
         REMINDER CREATED
              │
              ▼
       User:
       "Schedule it."
              │
              ▼
       CONFIRMATION
              │
              ▼
       CALENDAR

The orchestrator only proposes reminders/events; scheduling is never autonomous.
15. Component Responsibilities
Component	Responsibility
React Frontend	User interface, search, conversation, results, actions
FastAPI Backend	API, orchestration, validation, application logic
Ingestion	Import and validate images
OCR	Extract text
CLIP	Generate visual embeddings
Database	Store structured image/application information
Vector Store	Store and retrieve embeddings
Retrieval Engine	Separate retrieval capability: execute hybrid search
Ranking Layer	Separate retrieval capability: combine retrieval signals
Intelligent Agent	Single orchestrator: understand intent, maintain context, refine queries, interpret results, select/invoke actions
Action Layer	Summary, roadmap, reminder and calendar workflows
Explanation Layer	Produce grounded retrieval explanations

Note: any mock/dummy frontend retrieval, if present, is temporary demo UI only and is NOT the real retrieval engine.
16. Suggested Repository Structure
ChatLens/
│
├── README.md
├── AGENTS.md
│
├── frontend/
│
├── backend/
│
├── ai/
│   ├── ingestion/
│   ├── ocr/
│   ├── embeddings/
│   ├── retrieval/
│   ├── agent/
│   └── actions/
│
├── data/
│
├── tests/
│
└── docs/
    ├── CHATLENS_MASTER.md
    ├── mvp.md
    ├── architecture.md
    └── decisions.md

Telegram and local-folder sources feed `ai/ingestion/`.

The exact structure can evolve as implementation progresses.

17. Technology Mapping
Layer	Initial Technology
Frontend	React
Backend	Python + FastAPI
OCR	PaddleOCR / Tesseract
Visual Embeddings	CLIP
Vector Search	FAISS / ChromaDB
Database	SQLite
Image Processing	Python / OpenCV
Intelligent Agent	Conversational LLM
Version Control	Git + GitHub

Technology choices can be refined during implementation. Major changes should be recorded in decisions.md.

18. Parallel Development Boundaries

Since multiple team members are implementing different components, the architecture should maintain clear boundaries.

Suggested ownership areas:

Frontend
   ↕
Backend API
   ↕
Agent / Orchestration (single orchestrator)
   ↕
Retrieval (separate retrieval engine)
   ↕
Processing
   ↕
Storage

The single orchestrator does not replace the separate retrieval engine, and the retrieval
engine does not replace the orchestrator.

Changes to shared interfaces should be communicated to the team before implementation.

19. Architecture Priorities

The architecture should prioritize:

Working end-to-end retrieval
Reliable hybrid search
Conversational refinement
Explainability
Agent actions
UI polish
Optional integrations

Avoid building complex infrastructure before the core retrieval loop works.

20. Core Architectural Principle

The most important relationship in ChatLens is a **single orchestrator around a separate retrieval engine**:

             CONVERSATION
                   ↕
     INTELLIGENT AGENT (single orchestrator)
                   ↕
       RETRIEVAL ENGINE (separate capability)
                   ↕
          VISUAL MEMORY INDEX

The agent does not replace retrieval.

Retrieval does not replace the agent.

Together:

The agent understands what the user remembers; the retrieval system finds the visual memories that best match it.
