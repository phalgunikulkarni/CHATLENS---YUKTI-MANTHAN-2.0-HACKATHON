# ChatLens — AI Development Instructions

> **These instructions apply to AI coding assistants working in this repository.**

## 1. Read Project Context First

Before making code changes, read:

1. `docs/CHATLENS_MASTER.md`
2. `docs/mvp.md`
3. `docs/decisions.md` if it exists

These define the product vision, MVP scope, architecture decisions, and team agreements.

Do not implement based only on an isolated prompt.

## 2. Core Product

ChatLens is an **AI-powered personal visual memory search engine**.

Core experience:

> **Remember → Search → Refine → Explain → Act**

Users search by describing what they remember about an image rather than by filename or exact keywords.

## 3. Core MVP

The MVP includes:

- Image ingestion
- OCR
- CLIP visual embeddings
- Semantic/text representations
- Hybrid retrieval
- Natural-language search
- Ranked results
- Memory Clues
- Conversational intelligent agent
- Context-aware query refinement
- Re-retrieval/re-ranking after conversational refinement
- “Why this result?”
- Summarization
- Roadmap/plan generation

Calendar integration is an important extension and must use user confirmation before creating events.

## 4. Intelligent Agent Behavior

The conversational LLM is part of the retrieval system, not an unrelated chatbot.

The agent should:

- Understand user intent.
- Preserve relevant conversation context.
- Extract new memory clues.
- Update/rewrite search queries.
- Trigger retrieval or re-ranking when appropriate.
- Explain retrieved results.
- Perform supported actions on retrieved memories.

A follow-up such as “No, I remember it was handwritten” should refine the previous search rather than discard the original context.

## 5. Retrieval Principles

Where applicable, retrieval should consider:

- OCR/text
- Semantic similarity
- CLIP visual similarity
- Metadata
- Memory clues

Do not assume OCR alone is sufficient.

Do not assume vector similarity alone is sufficient.

Do not invent metadata or personal history that is unavailable.

## 6. “Why This Result?”

This is a mandatory MVP capability.

Use evidence from actual retrieval signals.

Good explanations:
- OCR matched relevant terms.
- Semantic similarity was high.
- Visual characteristics matched the requested clue.
- Available metadata matched the query.

Bad explanations:
- Inventing a reason never used by retrieval.
- Claiming a visual feature was detected when it was not.
- Showing a meaningless similarity percentage as the only explanation.

## 7. Engineering Rules

- Prefer simple implementations that can be demonstrated reliably.
- Avoid unnecessary frameworks or infrastructure.
- Do not add dependencies without justification.
- Keep modules loosely coupled.
- Preserve existing interfaces unless change is necessary.
- Handle errors explicitly.
- Keep configuration in environment variables where appropriate.
- Never commit secrets, API keys, passwords, or credentials.
- Keep large datasets and generated artifacts out of Git unless required.

## 8. Scope Control

Do not independently introduce major features outside the agreed MVP.

Examples:
- New source integrations
- Native mobile applications
- Face recognition
- Long-term personal behavior modeling
- Autonomous calendar management
- Complex multi-agent systems
- Model training/fine-tuning
- Unrelated AI features

If a feature seems valuable but is outside scope, **suggest it to the team instead of silently implementing it.**

## 9. Data Integrity

Never fabricate:

- User timestamps
- Personal history
- Previous interactions
- Viewing behavior
- Source information
- Events that did not occur

For development/demo datasets, clearly distinguish synthetic or curated data from genuine user history.

## 10. Testing

When modifying retrieval or agent behavior, test realistic queries such as:

- “Find my CN notes about OSI.”
- “Find the screenshot of my Python login error.”
- “Find that confused guy meme.”
- “Find my handwritten database notes.”
- “Find the CN notes with a large diagram.”

Also test conversational refinement:

```text
User:
Find my CN notes about OSI.

User:
No, I remember they were handwritten.

User:
There was a large diagram.
```

Verify that the system preserves the original intent and improves retrieval using the new clues.

## 11. Integration Discipline

Before changing an API or data structure:

1. Check existing consumers.
2. Identify affected modules.
3. Make the change compatible where possible.
4. Inform the team if a breaking change is required.

Do not build against imaginary or undocumented APIs.

## 12. Documentation

Update documentation when making a significant architectural or product decision.

Relevant documentation:

```text
docs/
├── CHATLENS_MASTER.md
├── mvp.md
├── architecture.md
└── decisions.md
```

Do not silently change the product definition inside code.

## 13. Working Style

When asked to implement something:

1. Understand the existing repository.
2. Read relevant documentation.
3. Inspect existing code before creating replacements.
4. Identify the smallest implementation that satisfies the requirement.
5. Implement it.
6. Test it.
7. Report what changed and any blockers.

Prioritize:

> **Working → Testable → Simple → Polished**

rather than:

> **Complex → Over-engineered → Unfinished**

## 14. Final Principle

Every implementation should strengthen the core ChatLens promise:

> **The user remembers something. ChatLens helps them find it, understand why it was found, refine the search conversationally, and act on the recovered memory.**
