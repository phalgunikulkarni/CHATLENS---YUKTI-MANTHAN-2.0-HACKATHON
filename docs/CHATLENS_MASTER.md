# ChatLens — Master Project Document

> ## ⚠️ IMPORTANT — READ BEFORE IMPLEMENTATION
>
> This document is the current source of truth for the ChatLens project.
> Before writing or modifying code, read this document, `docs/mvp.md`, and
> `docs/decisions.md` if it exists. Do not introduce major features or change
> agreed architecture without team approval.

## 1. What is ChatLens?

**ChatLens is an AI-powered personal visual memory search engine.**

> **You remember it. We find it.**

People accumulate screenshots, handwritten notes, receipts, documents, lecture slides, code screenshots, memes, and images from messaging platforms and devices. Later, they may remember what an image was about without remembering its filename, exact wording, date, folder, or location.

ChatLens lets users search their visual archive using **what they remember** rather than what the file is called.

## 2. The Problem

Traditional image search relies heavily on filenames, exact keywords, dates, folders, and manual scrolling.

Human memory works differently. A user may remember:

- “The screenshot where I fixed my Python login error.”
- “My handwritten CN notes with the OSI diagram.”
- “That confused guy meme.”

ChatLens bridges the gap between **human memory and machine search**.

## 3. Our Solution

ChatLens converts personal images into searchable visual memories using:

- OCR for text
- CLIP-based visual embeddings
- Semantic representations
- Available metadata
- Hybrid retrieval

Users describe a memory in natural language. ChatLens retrieves and ranks relevant images.

The complete product experience is:

> **Remember → Search → Refine → Explain → Act**

## 4. Core Product Philosophy

ChatLens is **not another photo gallery** and not simply an image-upload/search tool.

It should feel like an intelligent assistant helping users reconstruct a memory.

> **Users should not have to remember where an image is. They should only have to remember something about it.**

## 5. Target Use Cases

### Students
- Lecture slides
- Handwritten notes
- Error screenshots
- Study material
- Diagrams
- Exam preparation material

### Professionals
- Work screenshots
- Documents
- Receipts
- Technical references
- Meeting material
- Code screenshots

### Everyday users
- Receipts
- Travel images
- Memes
- Saved references
- Screenshots
- Images received through messaging platforms

## 6. Example User Journey

**User:** “Find the screenshot with the error message.”

ChatLens retrieves relevant results.

**User:** “No, I remember it was the one with the red button.”

ChatLens preserves the original context, adds the new clue, and re-runs or re-ranks retrieval rather than starting an unrelated search.

**User:** “Why this result?”

ChatLens explains the signals behind the result.

**User:** “Summarize this.”

The agent summarizes the retrieved content.

**User:** “Create a short plan from this.”

The agent generates a structured plan.

**User:** “Schedule this.”

The orchestrator proposes a calendar event or reminder and asks for confirmation before creating it.

## 7. Core System Flow

```text
                    PERSONAL SOURCES
                           |
                           v
                    IMAGE INGESTION
                           |
                           v
                +---------------------+
                |  IMAGE UNDERSTANDING|
                |                     |
                | OCR + CLIP + Meta   |
                +----------+----------+
                           |
                           v
                      SEARCH INDEX
                           ^
                           |
                    USER QUERY
                           |
                           v
                +---------------------+
                | CONVERSATIONAL LLM  |
                |  / ORCHESTRATOR     |
                | (single agent)      |
                |                     |
                | Understand intent   |
                | Maintain context    |
                | Extract clues       |
                | Formulate/update    |
                |   query             |
                | Decide when to      |
                |   trigger retrieval |
                | Interpret results   |
                | Explain / refine    |
                | Invoke actions      |
                +----------+----------+
                           |
                           v
                +---------------------+
                | RETRIEVAL ENGINE    |
                | (separate capability)|
                | OCR/text + semantic |
                | + CLIP visual +     |
                | metadata + clues    |
                | + ranking/re-ranking|
                +----------+----------+
                           |
                           v
                    RANKED RESULTS
                           |
                           v
                      ORCHESTRATOR
                           |
                 +---------+---------+
                 |                   |
                 v                   v
          WHY THIS RESULT?       USER ACTION
                                     |
                    +------------+------------+------------+
                    |            |            |            |
                    v            v            v            v
                 Summary     Roadmap     Calendar     Reminder
```

The layered ordering is: User → Conversational LLM / Orchestrator → Retrieval Engine → (OCR / semantic / visual / metadata signals) → Ranked Results → Orchestrator → Explain / Refine / Act. The agent sits around retrieval; it is not itself a search modality.

## 8. Image Understanding

Each image should produce multiple searchable signals.

### OCR
Extract text from screenshots, notes, documents, receipts, code screenshots, and lecture slides.

### CLIP Visual Embeddings
Represent visual and semantic characteristics. This is particularly useful for memes, images with little text, and visually distinctive images.

### Metadata
Where available, retain source, image identifier, timestamp, file information, and other relevant metadata.

Image understanding and the signals it produces are part of the **retrieval engine**, a separate capability used by the orchestrator/backend. The conversational LLM does **not** perform OCR, CLIP embedding, or vector search itself; it decides how and when those signals are used.

**Never fabricate timestamps, deadlines, metadata, personal history, source information, viewing behavior, events, retrieval evidence, or previous interactions when unavailable.** All signals and explanations must be grounded in information that actually exists in available content or user input.

## 9. Hybrid Retrieval

The retrieval engine is a **separate capability** used by the orchestrator/backend. It finds and ranks relevant visual memories by combining, where applicable, multiple retrieval signals:

- OCR/text matching
- Semantic/text embeddings
- CLIP-based visual similarity
- Available metadata
- User-provided memory/query clues
- Ranking and re-ranking

The orchestrator decides how and when to use retrieval and how to interpret its results. The LLM does not perform OCR, CLIP embedding, or vector search itself.

Example query:

> “Find the screenshot of the error message with a red button.”

Possible signals:

```text
OCR          -> matched error text from the query
Semantic     -> content related to the described error
Visual       -> screenshot / red button visual characteristics
Memory clues -> error message + red button
Metadata     -> available source/date information
```

The final ranking combines these signals rather than relying on one method.

## 10. Memory Clues

Users often remember incomplete or fuzzy details: topic, appearance, image type, visual elements, context, partial text, or approximate source.

These become additional retrieval signals.

Example:

> “Find the screenshot with the error message.”

Then:

> “The one with the red button.”

Then:

> “It was on a dark background.”

Each follow-up adds or modifies clues and refines the existing search, preserving relevant prior context, rather than starting an unrelated search. The agent should preserve the previous intent and progressively enrich the search.

## 11. Conversational Intelligent Agent

The conversational LLM is a **core part of ChatLens**. It is not a separate chatbot beside search.

ChatLens uses **one** conversational intelligent agent (orchestrator). We are **not** implementing a complex multi-agent architecture.

The LLM is the **orchestration and interaction layer around the retrieval engine**. It connects:

**User conversation ↔ Retrieval engine ↔ Retrieved memories ↔ Actions**

The agent should:

1. Understand initial intent.
2. Formulate the request into a searchable query.
3. Maintain conversation context.
4. Extract and update memory clues.
5. Update or rewrite the retrieval query.
6. Decide when retrieval/re-ranking is triggered.
7. Interpret retrieved results.
8. Generate evidence-based explanations.
9. Invoke supported actions.

The LLM is **not** another retrieval modality. It does **not** replace OCR, CLIP, embeddings, vector search, or metadata retrieval — it decides how and when those signals are used and how to interpret them.

A follow-up such as “No, I remember it was the one with the red button” should refine the previous search rather than become an unrelated query.

## 12. Why This Result?

**“Why this result?” is a mandatory MVP feature.**

Instead of only showing a similarity score, ChatLens should provide understandable evidence, for example:

> **Why this result?**
>
> ✓ OCR matched relevant terms from the query  
> ✓ Semantic similarity was high  
> ✓ Visual characteristics matched the requested clue  
> ✓ Available metadata matched the query

The explanation must be grounded in **actual retrieval evidence** — the OCR/text match, semantic similarity, visual similarity, available metadata, or other signals actually used by retrieval. The system must never fabricate visual detections, metadata, personal history, retrieval signals, similarity reasons, or any evidence not actually available.

## 13. Actions on Retrieved Memories

Summarization, roadmap/plan generation, calendar actions, and reminders are **orchestration / action-layer** capabilities, not retrieval-engine capabilities.

### Summarization
“Summarize this.”

The agent uses retrieved content to generate a useful summary.

### Roadmap / Plan Generation
“Create a plan from this.”

The agent generates an ordered plan based on retrieved material.

### Reminders
The orchestrator may propose a reminder when it identifies a genuine event, task, or deadline from available content or user input.

A reminder must be based on information that actually exists in available content or user input. The system must not invent deadlines, dates, or times. Where appropriate, explicit user confirmation is required before creating a reminder.

### Calendar
Where supported:

```text
Retrieve memories
       ↓
Generate plan
       ↓
Propose schedule / reminder
       ↓
Ask for confirmation
       ↓
Create calendar event or reminder
```

The orchestrator may identify a relevant event or deadline and propose a calendar event or reminder, but it should **not create calendar events or reminders without user confirmation**. ChatLens does not autonomously manage the user's calendar.

## 14. What ChatLens Is NOT

ChatLens is not intended to be:

- A conventional photo gallery
- A filename-based file browser
- A simple OCR search tool
- A basic image-upload/search application
- A standalone chatbot
- A generic autonomous agent with unrelated capabilities

We are also deliberately **not** implementing complex multi-agent systems, autonomous calendar management, face recognition, model training/fine-tuning, or unrelated AI features.

Its differentiator is:

> **Visual memory retrieval + conversational refinement + explainability + useful actions**

## 15. MVP Boundary

The MVP is centered on:

> **Find → Refine → Explain → Act**

### Must-have
- Personal image ingestion
- OCR
- CLIP visual embeddings
- Semantic/text search
- Hybrid retrieval
- Natural-language search
- Ranked results
- Memory Clues
- Conversational intelligent agent
- Updated-query retrieval/re-ranking
- “Why this result?”
- Summarization
- Roadmap/plan generation

### Important extension
- Calendar integration with user confirmation
- Reminders as a planned orchestrated action (with user confirmation where appropriate)

### Future / optional
- Native Android application
- Native iOS application
- Additional source integrations
- Telegram as a planned external source/input via a plugin/connector (planned, not yet implemented)
- Long-term interaction history
- Memory timeline
- Fully autonomous calendar management
- Advanced agent workflows
- Training/fine-tuning a proprietary vision model

See `docs/mvp.md` for detailed MVP success criteria.

## 16. Source and Dataset Strategy

The prototype may use supported personal source integrations, exported media, locally imported image archives, and curated datasets for development/testing.

Local photo/folder access is an input/**source** mechanism for accessing and searching the user's visual memories. It is not the core product experience, and ChatLens should not be described as an image-upload workflow/tool.

External sources can provide additional visual memories. **Telegram is a planned source/input** via a Telegram plugin/connector (planned, not yet implemented). It would supply available images and associated metadata to the same ingestion/retrieval architecture, following the same overall ingestion and retrieval principles, and content arriving from such sources is handled incrementally as it becomes available.

A local dataset is acceptable for prototyping and evaluation.

However, the system should **not pretend that randomly collected images have a user's real personal history**.

Features requiring genuine personal history, such as “Find the notes I viewed before my exam,” should only be demonstrated when appropriate history data exists.

## 17. Demo Philosophy

The demo should show a story:

1. **Remember** — “Find the screenshot with the error message.”
2. **Refine** — “No, it was the one with the red button.”
3. **Retrieve** — Relevant results appear.
4. **Explain** — “Why this result?”
5. **Act** — “Summarize this and create a short plan.”
6. **Optional** — “Schedule it.”

This demonstrates:

> **You remember it. We find it. We help you use it.**

## 18. Development Principles

1. Build the core retrieval loop before optional features.
2. Prefer simple, reliable implementations over unnecessary complexity.
3. Keep ingestion, processing, retrieval, agent, and frontend modules separable.
4. Keep interfaces between modules clear.
5. Do not introduce major architecture changes without team discussion.
6. Do not build features merely because an AI model can technically perform them.
7. Every AI feature should contribute to the visual-memory workflow.
8. Never fabricate timestamps, deadlines, metadata, personal history, source information, viewing behavior, events, retrieval evidence, or previous interactions; ground everything in actually-available information.
9. Test retrieval using realistic queries.
10. Keep the project demoable at every stage.

## 19. Current Product Definition

**Product:** ChatLens — AI-Powered Personal Visual Memory Search Engine

**Tagline:** You remember it. We find it.

**Core experience:** Remember → Search → Refine → Explain → Act

**Primary differentiator:** Search personal visual memories using natural-language descriptions and conversational memory clues rather than filenames or exact keywords.

**Core intelligence:** A separate retrieval engine (OCR + CLIP visual understanding + semantic representations + metadata + hybrid retrieval/ranking) coordinated by a **single conversational intelligent agent (orchestrator)** that surrounds it. The orchestrator is the interaction/orchestration layer; it is not another retrieval modality and does not replace OCR, CLIP, embeddings, vector search, or metadata retrieval. ChatLens is **not** a complex multi-agent system.

**Core agent (orchestration / action-layer) capabilities:** Search refinement + evidence-based explanation + summarization + roadmap/plan generation + confirmation-based calendar actions + confirmation-based reminders. Summarization, roadmap/plan generation, calendar actions, and reminders belong to the action layer, not the retrieval engine.

## 20. Team Rule

Before implementing a new feature, ask:

> **Does this make ChatLens better at helping a user find, understand, or act on something they remember?**

If yes, discuss where it fits in the existing architecture.

If no, it is probably outside the current product scope.

---

**ChatLens**

> **You remember it. We find it.**
