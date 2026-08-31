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

**User:** “Find my CN notes about OSI.”

ChatLens retrieves relevant results.

**User:** “No, I remember they were handwritten and had a big diagram.”

ChatLens preserves the original context, adds the new clues, and re-runs or re-ranks retrieval.

**User:** “Why this result?”

ChatLens explains the signals behind the result.

**User:** “Summarize these notes.”

The agent summarizes the retrieved content.

**User:** “Create a 3-day revision roadmap.”

The agent generates a structured plan.

**User:** “Schedule this.”

The system proposes calendar events and asks for confirmation before creating them.

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
                | INTELLIGENT AGENT   |
                |                     |
                | Understand intent   |
                | Maintain context    |
                | Extract clues       |
                | Update query        |
                | Trigger actions     |
                +----------+----------+
                           |
                           v
                    HYBRID RETRIEVAL
                           |
                           v
                    RANKED RESULTS
                           |
                 +---------+---------+
                 |                   |
                 v                   v
          WHY THIS RESULT?       USER ACTION
                                     |
                         +-----------+-----------+
                         |           |           |
                         v           v           v
                      Summary     Roadmap     Calendar
```

## 8. Image Understanding

Each image should produce multiple searchable signals.

### OCR
Extract text from screenshots, notes, documents, receipts, code screenshots, and lecture slides.

### CLIP Visual Embeddings
Represent visual and semantic characteristics. This is particularly useful for memes, images with little text, and visually distinctive images.

### Metadata
Where available, retain source, image identifier, timestamp, file information, and other relevant metadata.

**Do not invent timestamps or personal history when unavailable.**

## 9. Hybrid Retrieval

ChatLens combines multiple retrieval signals:

- OCR/text matching
- Semantic similarity
- CLIP-based visual similarity
- Available metadata
- User-provided memory clues

Example query:

> “Find my handwritten CN notes about the OSI model.”

Possible signals:

```text
OCR          -> “OSI”, “Computer Networks”
Semantic     -> content related to CN / OSI
Visual       -> handwritten notes / diagram characteristics
Memory clues -> handwritten + notes + diagram
Metadata     -> available source/date information
```

The final ranking combines these signals rather than relying on one method.

## 10. Memory Clues

Users often remember incomplete or fuzzy details: topic, appearance, image type, visual elements, context, partial text, or approximate source.

These become additional retrieval signals.

Example:

> “Find my database notes.”

Then:

> “I remember they were handwritten.”

Then:

> “There was a large normalization diagram.”

The agent should preserve the previous intent and progressively enrich the search.

## 11. Conversational Intelligent Agent

The conversational LLM is a **core part of ChatLens**. It is not a separate chatbot beside search.

It connects:

**User conversation ↔ Retrieval ↔ Retrieved memories ↔ Actions**

The agent should:

1. Understand initial intent.
2. Convert the request into a searchable query.
3. Maintain conversation context.
4. Extract additional memory clues.
5. Update or rewrite the retrieval query.
6. Trigger retrieval/re-ranking again.
7. Interpret retrieved results.
8. Explain results.
9. Perform supported actions.

A follow-up such as “No, I remember it was handwritten” should refine the previous search rather than become an unrelated query.

## 12. Why This Result?

**“Why this result?” is a mandatory MVP feature.**

Instead of only showing a similarity score, ChatLens should provide understandable evidence, for example:

> **Why this result?**
>
> ✓ OCR matched “OSI Model”  
> ✓ Semantically related to Computer Networks  
> ✓ Visual match for handwritten notes  
> ✓ Diagram-related visual features matched

The explanation should reflect the actual signals used by retrieval.

## 13. Actions on Retrieved Memories

### Summarization
“Summarize these notes.”

The agent uses retrieved content to generate a useful summary.

### Roadmap / Plan Generation
“Create a revision roadmap from these notes.”

The agent generates an ordered plan based on retrieved material.

### Calendar
Where supported:

```text
Retrieve memories
       ↓
Generate plan
       ↓
Propose schedule
       ↓
Ask for confirmation
       ↓
Create calendar events
```

The agent should **not create calendar events without user confirmation**.

## 14. What ChatLens Is NOT

ChatLens is not intended to be:

- A conventional photo gallery
- A filename-based file browser
- A simple OCR search tool
- A basic image-upload/search application
- A standalone chatbot
- A generic autonomous agent with unrelated capabilities

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

### Future / optional
- Native Android application
- Native iOS application
- Additional source integrations
- Long-term interaction history
- Memory timeline
- Fully autonomous calendar management
- Advanced agent workflows
- Training/fine-tuning a proprietary vision model

See `docs/mvp.md` for detailed MVP success criteria.

## 16. Source and Dataset Strategy

The prototype may use supported personal source integrations, exported media, locally imported image archives, and curated datasets for development/testing.

A local dataset is acceptable for prototyping and evaluation.

However, the system should **not pretend that randomly collected images have a user's real personal history**.

Features requiring genuine personal history, such as “Find the notes I viewed before my exam,” should only be demonstrated when appropriate history data exists.

## 17. Demo Philosophy

The demo should show a story:

1. **Remember** — “Find my CN notes about OSI.”
2. **Refine** — “No, they were handwritten and had a big diagram.”
3. **Retrieve** — Relevant results appear.
4. **Explain** — “Why this result?”
5. **Act** — “Summarize these and create a 3-day revision roadmap.”
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
8. Never fabricate user history, timestamps, or personal context.
9. Test retrieval using realistic queries.
10. Keep the project demoable at every stage.

## 19. Current Product Definition

**Product:** ChatLens — AI-Powered Personal Visual Memory Search Engine

**Tagline:** You remember it. We find it.

**Core experience:** Remember → Search → Refine → Explain → Act

**Primary differentiator:** Search personal visual memories using natural-language descriptions and conversational memory clues rather than filenames or exact keywords.

**Core intelligence:** OCR + CLIP visual understanding + semantic representations + hybrid retrieval + conversational intelligent agent

**Core agent capabilities:** Search refinement + explanation + summarization + roadmap generation + supported external actions

## 20. Team Rule

Before implementing a new feature, ask:

> **Does this make ChatLens better at helping a user find, understand, or act on something they remember?**

If yes, discuss where it fits in the existing architecture.

If no, it is probably outside the current product scope.

---

**ChatLens**

> **You remember it. We find it.**
