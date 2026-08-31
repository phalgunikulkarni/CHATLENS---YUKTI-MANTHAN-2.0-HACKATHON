# ChatLens MVP

## 1. MVP Objective

ChatLens is an AI-powered personal visual memory search engine that helps users find images based on what they remember rather than what the file is called.

The MVP should provide a complete experience:

> **Remember → Search → Refine → Explain → Act**

A user should be able to describe a memory in natural language, retrieve relevant images, refine the search conversationally, understand why a result was selected, and perform useful actions on the retrieved information.

---

## 2. Core MVP Experience

The primary user flow is:

Personal Sources
→ Image Ingestion
→ Image Understanding
→ Search Index
→ Natural-Language Query
→ Hybrid Retrieval
→ Ranked Results
→ Why This Result?
→ Conversational Refinement
→ Agentic Actions

The system should feel like an intelligent memory assistant rather than a traditional image gallery or image-upload/search tool.

---

# 3. MVP Features

## 3.1 Personal Image Ingestion

ChatLens should support bringing personal images into the system through supported sources.

### MVP requirements

- Import images from the supported source/integration.
- Support a local/imported image archive as a development and fallback mechanism.
- Preserve available source information and metadata.
- Convert images into a common internal format for processing.

The core retrieval system should remain independent of the image source so that additional sources can be added later.

---

## 3.2 Image Understanding

Each image should be processed to create multiple searchable signals.

### OCR

Extract text from images such as:

- Screenshots
- Handwritten notes
- Documents
- Receipts
- Code screenshots
- Lecture slides

### CLIP Visual Embeddings

Generate visual embeddings using CLIP to represent the visual and semantic characteristics of an image.

This is particularly useful for images where OCR alone is insufficient, such as:

- Memes
- Visually distinctive screenshots
- Images with little text
- Images described by appearance

### Metadata

Store available information such as:

- Source
- Image identifier
- Timestamp, when available
- File information
- Other useful metadata

---

# 4. Hybrid Retrieval

ChatLens should not depend on a single search method.

The retrieval system combines multiple signals:

- OCR/text matching
- Semantic similarity
- CLIP-based visual similarity
- Available metadata
- User-provided memory clues

These signals are combined to rank candidate images.

### Example

User query:

> "Find my handwritten CN notes about the OSI model."

The system may use:

- OCR → "OSI", "Computer Networks", related terms
- Semantic search → meaning related to CN/OSI
- CLIP → visual similarity to handwritten notes
- Metadata → available source/date information
- Memory clues → handwritten + notes + diagram

The final results are ranked using the combined evidence.

---

# 5. Natural-Language Visual Memory Search

Users should be able to describe what they remember instead of remembering:

- File names
- Exact words
- Folder locations
- Exact dates

### Example queries

> "Find my CN notes about OSI."

> "Show me the screenshot of my Python login error."

> "Find that confused guy meme."

> "Find the handwritten database notes with a large diagram."

The system should retrieve relevant images even when the user's wording does not exactly match the text inside the image.

---

# 6. Memory Clues

Users often remember an image through incomplete or fuzzy details.

ChatLens should allow these details to become additional retrieval signals.

### Example

User:

> "Find my CN notes."

ChatLens returns results.

User:

> "No, I remember they were handwritten and had a big diagram."

The additional information becomes new search context:

- Topic → Computer Networks
- Content → OSI
- Type → Handwritten notes
- Visual clue → Large diagram

The system uses these clues to improve retrieval and re-rank the results.

This feature represents the core idea of ChatLens:

> **Search by what you remember.**

---

# 7. Conversational Intelligent Agent

The conversational LLM is a core component of ChatLens.

It should not function as a separate chatbot. It acts as the intelligent layer between the user's conversation, retrieval system, and available actions.

## Agent responsibilities

The agent should:

1. Understand the user's initial intent.
2. Convert the request into a searchable query.
3. Maintain conversation context.
4. Incorporate new memory clues.
5. Update or rewrite the retrieval query.
6. Trigger retrieval again when necessary.
7. Interpret retrieved results.
8. Explain results to the user.
9. Perform supported actions on retrieved information.

### Example

User:

> "Find my CN notes about OSI."

↓

Agent retrieves relevant results.

User:

> "No, they were handwritten."

↓

Agent maintains the original context and adds:

> handwritten notes

↓

Retrieval is performed again.

User:

> "Yes, that's the one."

↓

User can now ask:

> "Summarize it."

or:

> "Create a 3-day revision plan."

The conversation therefore directly influences retrieval and actions.

---

# 8. Why This Result?

"Why this result?" is a mandatory MVP feature.

Users should not receive a result with only an unexplained similarity score.

ChatLens should provide understandable reasons for why an image was ranked highly.

### Example

**Why this result?**

- ✓ OCR matched "OSI Model"
- ✓ Semantically related to Computer Networks
- ✓ Visual match for handwritten notes
- ✓ Diagram detected

The exact explanation should reflect the signals actually used by the retrieval system.

The goal is to make the AI's retrieval understandable and trustworthy.

---

# 9. Actions on Retrieved Memories

ChatLens should allow users to do more than simply find an image.

Once relevant memories have been retrieved, the intelligent agent can act on them.

## 9.1 Summarization

User:

> "Summarize these notes."

The agent uses the retrieved images and extracted content to generate a concise summary.

---

## 9.2 Roadmap / Plan Generation

User:

> "Create a revision roadmap from these CN notes."

The agent analyzes the retrieved material and generates an ordered plan.

For example:

1. OSI Model
2. TCP/IP
3. Routing
4. Transport Layer
5. Practice Questions

---

## 9.3 Calendar Integration

Where supported, the agent can convert a generated roadmap into calendar events.

The intended flow is:

User request
→ Retrieve relevant memories
→ Generate plan
→ Show proposed schedule
→ Ask for confirmation
→ Create calendar events

The agent should not create calendar events without user confirmation.

Calendar integration may initially be implemented as a focused demonstration rather than a fully generalized calendar assistant.

---

# 10. MVP Success Criteria

The MVP will be considered successful when a user can complete the following workflow:

### Search

- [ ] Describe an image using natural language.
- [ ] Retrieve relevant images.
- [ ] Search across different image categories.
- [ ] Retrieve results using OCR and visual/semantic signals.

### Refine

- [ ] Add additional memory clues conversationally.
- [ ] Maintain context from previous messages.
- [ ] Re-run or re-rank retrieval using the updated query.

### Explain

- [ ] Ask "Why this result?"
- [ ] Receive understandable retrieval reasoning based on available signals.

### Act

- [ ] Summarize retrieved content.
- [ ] Generate a roadmap or structured plan.
- [ ] Offer calendar scheduling for generated plans.
- [ ] Ask for user confirmation before creating calendar events.

---

# 11. Representative MVP Test Cases

The following queries should be used to evaluate the system.

| Query | Expected behaviour |
|---|---|
| "Find my CN notes about OSI." | Retrieve relevant CN/OSI notes. |
| "Find the screenshot of my Python login error." | Retrieve relevant code/error screenshots. |
| "Find that confused guy meme." | Use visual similarity where OCR is insufficient. |
| "Find my handwritten database notes." | Combine semantic and visual signals. |
| "Find the CN notes with a large diagram." | Use topic + visual/contextual clues. |
| "No, I remember it was handwritten." | Update the previous search rather than starting an unrelated conversation. |
| "Why did you show me this?" | Explain the retrieval signals. |
| "Summarize these." | Summarize retrieved content. |
| "Create a revision roadmap." | Generate a structured plan from retrieved material. |
| "Schedule this for the next 3 days." | Propose calendar events and request confirmation. |

---

# 12. Out of Scope for Core MVP

The following features should not block the core MVP:

- Native Android application
- Native iOS application
- Large-scale multi-platform integrations
- Long-term historical interaction analysis
- Personal history inferred from externally collected datasets
- Fully autonomous calendar management
- Advanced autonomous agent workflows
- Training or fine-tuning a proprietary vision model

These can be developed if the core MVP is stable and time permits.

---

# 13. MVP Design Principle

The central principle of ChatLens is:

> **Users should not have to remember where an image is. They should only have to remember something about it.**

ChatLens transforms that memory into searchable clues, retrieves the most relevant visual memories, explains the results, and helps the user act on what they found.

### Core Product Loop

**You remember something**
→ **You describe it**
→ **ChatLens finds it**
→ **You refine the memory**
→ **ChatLens improves the results**
→ **ChatLens explains why**
→ **You act on the retrieved memory**

> **ChatLens — You remember it. We find it.**