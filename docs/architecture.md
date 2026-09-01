# ChatLens — System Architecture

## 1. Architecture Overview

ChatLens follows a modular pipeline that connects image ingestion, image understanding, hybrid retrieval, conversational intelligence, and user actions.

The core flow is:

> **Image Sources → Ingestion → Processing → Search Index → Intelligent Agent → Hybrid Retrieval → Ranked Results → Actions**

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
                  ┌──────────────────────────┐
                  │   Conversational Agent   │
                  │                          │
                  │ Intent + Context         │
                  │ Query Refinement         │
                  │ Action Selection         │
                  └────────────┬─────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                 Search                 Action
                    │                     │
                    ▼                     ▼
          ┌──────────────────┐    ┌─────────────────┐
          │ Retrieval Engine │    │  Action Layer   │
          └────────┬─────────┘    │                 │
                   │              │ Summary         │
                   │              │ Roadmap         │
                   │              │ Calendar        │
                   │              └─────────────────┘
                   ▼
          ┌──────────────────────┐
          │    Hybrid Search     │
          └──────────┬───────────┘
                     │
          ┌──────────┼───────────┐
          ▼          ▼           ▼
       OCR/Text   Semantic     CLIP
        Search     Search     Visual Search
          │          │           │
          └──────────┼───────────┘
                     ▼
              Candidate Results
                     │
                     ▼
                  Re-ranking
                     │
                     ▼
               Ranked Results
                     │
                     ▼
              Why This Result?
3. Image Ingestion Layer

The ingestion layer is responsible for bringing images into ChatLens.

Initial sources

The prototype may support:

Local/imported images
Exported media
Other supported sources as integrations become available

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

Approved MVP vector store:

ChromaDB

Stores and retrieves image/vector representations for similarity search, keeping
embeddings and their metadata together. (Supersedes the earlier "FAISS / ChromaDB"
direction; see decisions.md #24.)

6. Search Architecture

ChatLens uses hybrid retrieval.

The system combines different retrieval mechanisms rather than relying on only OCR or only vector similarity.

                    USER QUERY
                         │
                         ▼
                Conversational Agent
                         │
                         ▼
                  Query Representation
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
      OCR/Text        Semantic        CLIP
       Search          Search       Visual Search
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

The intelligent agent converts the user's natural-language request into useful retrieval information.

Example:

"Find my handwritten CN notes about OSI."

Possible query signals:

Topic:
Computer Networks / OSI

Content:
Notes

Visual clue:
Handwritten

The retrieval layer uses these signals to search the visual memory index.

8. Conversational Retrieval

Conversational retrieval is one of the core architectural features.

The agent maintains relevant context across turns.

Example:

User:
Find my CN notes about OSI.
             │
             ▼
        First Retrieval
             │
             ▼
          Results

User:
No, they were handwritten.
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
There was a large diagram.
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

The conversational LLM acts as the orchestration and reasoning layer.

It connects:

User
 ↓
Agent
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
Schedule a generated plan

The agent should not become a generic unrelated chatbot.

11. Agent → Retrieval Interaction

The relationship between the agent and retrieval system is:

             User Message
                  │
                  ▼
          Intelligent Agent
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

✓ OCR matched "OSI Model"
✓ Semantically related to Computer Networks
✓ Visual characteristics matched handwritten notes
✓ Diagram-related visual signal matched

The explanation must be based on actual retrieval evidence.

13. Action Layer

Actions operate on retrieved memories.

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

13.3 Calendar Integration

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

The system should not create external calendar events without confirmation.

14. End-to-End Example
USER
 │
 │ "Find my handwritten CN notes about OSI."
 ▼
FRONTEND
 │
 ▼
BACKEND
 │
 ▼
INTELLIGENT AGENT
 │
 │ Understand intent
 ▼
HYBRID RETRIEVAL
 ├── OCR
 ├── Semantic
 └── CLIP
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
     "No, there was a large diagram."
              │
              ▼
       AGENT UPDATES CONTEXT
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
       "Schedule it."
              │
              ▼
       CONFIRMATION
              │
              ▼
       CALENDAR
15. Component Responsibilities
Component	Responsibility
React Frontend	User interface, search, conversation, results, actions
FastAPI Backend	API, orchestration, validation, application logic
Ingestion	Import and validate images
OCR	Extract text
CLIP	Generate visual embeddings
Database	Store structured image/application information
Vector Store	Store and retrieve embeddings
Retrieval Engine	Execute hybrid search
Ranking Layer	Combine retrieval signals
Intelligent Agent	Understand intent, maintain context, refine queries, select actions
Action Layer	Summary, roadmap and calendar workflows
Explanation Layer	Produce grounded retrieval explanations
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

The exact structure can evolve as implementation progresses.

17. Technology Mapping
Layer	Initial Technology
Frontend	React
Backend	Python + FastAPI
OCR	PaddleOCR / Tesseract
Visual Embeddings	CLIP
Vector Search	ChromaDB
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
Agent / Orchestration
   ↕
Retrieval
   ↕
Processing
   ↕
Storage

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

The most important relationship in ChatLens is:

             CONVERSATION
                   ↕
           INTELLIGENT AGENT
                   ↕
              RETRIEVAL
                   ↕
          VISUAL MEMORY INDEX

The agent does not replace retrieval.

Retrieval does not replace the agent.

Together:

The agent understands what the user remembers; the retrieval system finds the visual memories that best match it.
