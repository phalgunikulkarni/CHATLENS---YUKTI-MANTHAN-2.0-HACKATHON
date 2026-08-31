# ChatLens

### AI-Powered Personal Visual Memory Search Engine

> **You remember it. We find it.**

---

## What is ChatLens?

We remember what was in an image.  
We just don't remember which image.

People accumulate thousands of screenshots, handwritten notes, receipts, documents, lecture slides, code snippets, memes, and other images.

Weeks or months later, finding one specific image becomes frustrating because traditional search expects us to remember:

- A filename
- Exact words
- A date
- A folder
- Where the image was saved

But that's not how we usually remember things.

We remember **what the image was about**.

ChatLens turns this idea into an AI-powered visual memory search engine.

Instead of searching:

> `IMG_20260417_1832.png`

users can simply ask:

> **"Find my handwritten CN notes about OSI."**

or:

> **"Find the screenshot where I fixed my Python login error."**

or:

> **"Show me the restaurant receipt from my Bangalore trip."**

---

# Why ChatLens?

Traditional image search asks:

> **"What is the file called?"**

ChatLens asks:

> **"What do you remember about it?"**

The system combines multiple signals to understand an image:

```text
                IMAGE
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
       OCR       CLIP    Metadata
        │       Visual       │
        │     Embedding      │
        └─────────┼──────────┘
                  ▼
             Visual Memory
                  │
                  ▼
          Hybrid Retrieval
                  │
                  ▼
           Ranked Results

Core Features
🔍 Natural-Language Search

Search personal images using descriptions instead of filenames or exact keywords.

"Find my handwritten DBMS notes about normalization."

🧠 Hybrid Visual Retrieval

Combines:

OCR/text search
Semantic similarity
CLIP visual similarity
Available metadata
User-provided memory clues

This allows ChatLens to work across different types of visual content.

💬 Conversational Search

Users can progressively add clues instead of creating a perfect query.

Find my CN notes about OSI.

        ↓

No, they were handwritten.

        ↓

There was a large diagram.

        ↓

Improved results

The intelligent agent updates the search using the conversation context.

❓ Why This Result?

Users can ask why a particular image was retrieved.

For example:

Why this result?

✓ OCR matched "OSI Model"
✓ Semantic similarity matched Computer Networks
✓ Visual signal matched handwritten notes
✓ Diagram-related visual signal matched

The explanation is based on actual retrieval signals.

✨ Intelligent Actions

Once relevant memories are found, the conversational agent can work with them.

Users can ask:

"Summarize these notes."

or:

"Create a 3-day revision roadmap."

The roadmap can optionally be converted into a proposed calendar schedule.

Calendar events require user confirmation before creation.

How It Works
┌──────────────────┐
│   Image Sources  │
└────────┬─────────┘
         ↓
┌──────────────────┐
│    Ingestion     │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ OCR + CLIP +     │
│ Metadata         │
└────────┬─────────┘
         ↓
┌──────────────────┐
│  Search Index    │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Intelligent      │
│ Agent            │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Hybrid Retrieval │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Ranked Results   │
└────────┬─────────┘
         ↓
┌──────────────────┐
│ Explain /        │
│ Summarize / Plan │
└──────────────────┘
Technology
Component	Technology
Frontend	React
Backend	Python + FastAPI
OCR	PaddleOCR / Tesseract
Visual Embeddings	CLIP
Vector Search	FAISS / ChromaDB
Database	SQLite
Image Processing	Python / OpenCV
Intelligent Agent	Conversational LLM
Version Control	Git + GitHub

These are the initial technology choices and may evolve during implementation.

MVP

The MVP focuses on proving the complete visual-memory workflow.

Must Work
Image ingestion
OCR processing
CLIP visual embeddings
Hybrid retrieval
Natural-language search
Conversational query refinement
Why This Result?
Conversational summarization
Roadmap generation
Optional
Calendar integration
Additional image sources
Android/iOS application
Additional WOW features

The web application is the primary platform for the hackathon.

Example User Journey
User
 │
 │ "Find my handwritten CN notes about OSI."
 ▼
ChatLens
 │
 ▼
Relevant Images
 │
 │ "No, there was a large diagram."
 ▼
ChatLens
 │
 ▼
Refined Results
 │
 │ "Why this result?"
 ▼
Explanation
 │
 │ "Summarize these."
 ▼
Summary
 │
 │ "Make a 3-day revision plan."
 ▼
Roadmap
 │
 │ "Schedule it."
 ▼
Proposed Calendar
 │
 │ Confirm
 ▼
Calendar Events
Project Structure
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
Documentation

Before starting implementation, read the project documentation in this order:

1. docs/CHATLENS_MASTER.md

Complete product vision and project definition.

2. docs/mvp.md

Defines the MVP and success criteria.

3. docs/architecture.md

Explains the technical architecture and component relationships.

4. docs/decisions.md

Records decisions already agreed upon by the team.

5. AGENTS.md

Instructions for Kiro and AI coding assistants working on the repository.

All contributors should read these files before making major implementation decisions.

Development Principles
1. Build the core first

Get the complete retrieval loop working before adding optional features.

2. Keep components modular

Frontend, backend, processing, retrieval, and agent logic should remain separated.

3. Don't fake personal history

If actual timestamps or usage history are unavailable, the system must not invent them.

4. Explain actual retrieval

"Why this result?" must be based on real retrieval signals.

5. Keep the agent within scope

The conversational agent exists to help users find, understand, and act on their visual memories.

6. Document major decisions

If an architectural or product decision changes, update docs/decisions.md.

The Vision

Thousands of forgotten screenshots and images shouldn't have to remain digital clutter.

ChatLens aims to turn them into an intelligent, searchable extension of memory.

Search by what you remember, not by what the file is called.

ChatLens
You remember it. We find it.

### Your repo documentation now has a very clean hierarchy

```text
                         CHATLENS
                            │
              ┌─────────────┴─────────────┐
              │                           │
          README.md                 AGENTS.md
       "Quick overview"          "AI instructions"
              │
              ▼
        docs/CHATLENS_MASTER.md
          "What are we building?"
              │
        ┌─────┴──────┐
        ▼            ▼
     mvp.md    architecture.md
   "What?"       "How?"
        │            │
        └─────┬──────┘
              ▼
        decisions.md
      "Why this way?"