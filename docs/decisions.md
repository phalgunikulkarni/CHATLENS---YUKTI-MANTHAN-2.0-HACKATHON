# ChatLens — Project Decisions

This document records the major product and implementation decisions agreed upon by the ChatLens team.

> **Purpose:** Keep the entire team and all AI coding assistants aligned on what we have decided to build.

If a major decision changes, update this document and inform the team before implementation proceeds.

---

# 1. Product Definition

### Decision
ChatLens is an **AI-powered personal visual memory search engine**.

### Core idea

> **You remember it. We find it.**

The user should be able to describe what they remember about an image instead of remembering its filename, exact text, folder, or location.

---

# 2. Core Product Experience

### Decision
The main ChatLens experience is:

> **Remember → Search → Refine → Explain → Act**

The product should not stop after finding an image.

The user should be able to:

1. Describe what they remember.
2. Find relevant images.
3. Add additional memory clues.
4. Get improved results.
5. Understand why a result was selected.
6. Perform useful actions on the retrieved content.

---

# 3. ChatLens Is Not Another Google Lens

### Decision
ChatLens should not be positioned as a conventional image-upload or reverse-image-search product.

### Reason
If the user simply uploads an image and asks for visually similar images, the experience becomes too similar to existing visual search tools.

Our focus is:

> **Finding something from the user's existing visual archive based on what they remember about it.**

The user should not need to provide the exact image they are looking for.

---

# 4. Conversational AI Is Core MVP

### Decision
The conversational LLM is a **core component of the MVP**.

It is not a separate chatbot placed beside the search system.

ChatLens uses **one** conversational intelligent agent (orchestrator). We are **not** implementing a complex multi-agent architecture.

The conversational LLM is the **orchestration and interaction layer around the retrieval engine**. It is responsible for:

- Understanding user intent.
- Maintaining relevant conversation context.
- Extracting and updating memory clues.
- Formulating retrieval queries.
- Refining previous searches.
- Deciding when retrieval / re-ranking is triggered.
- Interpreting results.
- Generating evidence-based explanations.
- Invoking supported actions.

The LLM is **not** another retrieval modality. It does **not** replace OCR, CLIP, embeddings, vector search, or metadata retrieval — it decides how and when those signals are used and how to interpret them.

It acts as the intelligent layer connecting:

```text
User Conversation
        ↕
Intelligent Agent (single orchestrator)
        ↕
Retrieval Engine
        ↕
Retrieved Memories
        ↕
Actions
5. Conversational Refinement
Decision

The agent must use conversation context to improve retrieval.

A follow-up message should add or modify memory clues and refine the existing search, preserving relevant prior context, rather than starting an unrelated search.

Example:

User:
Find the screenshot with the error message.

ChatLens:
[Results]

User:
The one with the red button.

ChatLens:
[Refined results]

The new message should update the previous search context, rather than being treated as an unrelated query.

Reason

This is one of the most important parts of the visual-memory concept.

People often remember an image through several incomplete clues rather than one perfect description.

6. Hybrid Retrieval
Decision

ChatLens will use hybrid retrieval.

The retrieval engine is a **separate capability** used by the orchestrator/backend. It is responsible for finding and ranking relevant visual memories using, where applicable:

OCR/text matching
Semantic/text embeddings
CLIP visual similarity
Available metadata
User-provided memory / query clues
Ranking and re-ranking

The orchestrator decides how and when to use retrieval and how to interpret its results. The LLM does not perform OCR, CLIP embedding, or vector search itself.

Reason

Different image types require different signals.

For example:

OCR is useful for screenshots, notes and documents.
Visual embeddings are useful for memes and images with little text.
Semantic search helps when the user's wording differs from the text inside the image.
Metadata can provide additional filtering where available.

No single retrieval method should be treated as sufficient for every image type.

7. CLIP for Visual Understanding
Decision

CLIP is the initial approach for generating visual embeddings.

Reason

It provides a practical way to capture visual/semantic similarity without requiring the team to train a vision model from scratch during the hackathon.

CLIP is used alongside OCR and other retrieval signals, not as a replacement for them.

8. OCR + Visual Embeddings
Decision

OCR and visual embeddings are complementary.

OCR answers approximately:

What text is present in the image?

Visual embeddings help capture:

What does the image visually/semantically represent?

This combination is important for supporting:

Screenshots
Handwritten notes
Documents
Receipts
Lecture slides
Code screenshots
Memes
Images with little text
9. "Why This Result?" Is Mandatory
Decision

"Why this result?" is a must-have MVP feature.

Users should be able to ask why ChatLens selected a particular image.

Example:

Why this result?

✓ OCR matched relevant terms from the query
✓ Semantic similarity was high
✓ Visual characteristics matched the requested clue
✓ Available metadata matched the query
Important rule

The explanation must be grounded in **actual retrieval evidence** — the OCR/text match, semantic similarity, visual similarity, available metadata, or other signals actually used.

The system must never fabricate visual detections, metadata, personal history, retrieval signals, similarity reasons, or any evidence not actually available. It must not invent an explanation simply because it sounds convincing.

10. Summarization Is an MVP Agent Action
Decision

The agent should be able to summarize retrieved content.

Summarization belongs to the orchestration / action layer, not the retrieval engine.

Example:

"Summarize these notes."

The agent uses the retrieved images/content and generates a useful summary.

Reason

Finding a memory should lead to a useful action rather than ending at image retrieval.

11. Roadmap / Plan Generation
Decision

The agent should be able to create a structured roadmap or plan from retrieved content.

Roadmap/plan generation belongs to the orchestration / action layer, not the retrieval engine.

Example:

"Create a 3-day revision roadmap from these notes."

The agent can analyze the retrieved study material and generate an ordered plan.

Reason

This demonstrates that ChatLens can turn recovered visual memories into actionable information.

12. Calendar Integration
Decision

Calendar integration is an important extension of the agent workflow.

The intended flow is:

Retrieve memories
       ↓
Generate roadmap
       ↓
Propose schedule
       ↓
Ask user for confirmation
       ↓
Create calendar events
Calendar actions belong to the orchestration / action layer, not the retrieval engine. The orchestrator may identify a relevant event or deadline, propose a calendar event, or propose a reminder.

Important rule

Explicit user confirmation is required before creating a calendar event or reminder where appropriate. The agent should not create calendar events without user confirmation.

ChatLens does not autonomously manage the user's calendar.

Calendar integration should not compromise the core retrieval MVP if implementation time becomes limited.

13. Local Dataset for Prototype
Decision

A locally collected/imported dataset can be used for the hackathon prototype.

The dataset may contain images collected from different sources or contributors.

Local photo / folder access is an input **source** mechanism for accessing and searching the user's visual memories. It is not the core product experience, and ChatLens should not be described as an image-upload workflow/tool.

Reason

Direct integration with every personal source is not necessary to prove the core visual-memory retrieval concept.

The ingestion architecture should remain flexible enough to support additional sources later.

14. No Fake Personal History
Decision

We will not fabricate personal history to demonstrate memory-based features.

For example, a random dataset cannot truthfully answer:

"Find the CN notes I used for studying before my exam."

unless actual history information exists.

We can use:

Image content
OCR
Visual embeddings
Available metadata
Current conversation context

But we should never fabricate:

Timestamps
Deadlines
Metadata
Personal history
Source information
Viewing behavior
Usage history
Events
Retrieval evidence
Previous interactions

All explanations and actions must be grounded in information that actually exists in available content or user input.

Reason

The dataset may not contain genuine personal-history information.

15. Web App First
Decision

The primary hackathon implementation will be a web application.

Reason

The hackathon team and mentor have identified a web app as the preferred initial platform.

16. Mobile Application Is Optional
Decision

Android/iOS implementation is optional and should only be attempted after the core web MVP is functional.

Reason

The core product must be demonstrated first.

Mobile development should never delay the primary retrieval + agent experience.

17. Core MVP Priority
Decision

The team should prioritize the following order:

1. Image ingestion
        ↓
2. OCR + CLIP processing
        ↓
3. Search index
        ↓
4. Basic retrieval
        ↓
5. Hybrid retrieval
        ↓
6. Natural-language search
        ↓
7. Conversational refinement
        ↓
8. Why This Result?
        ↓
9. Summarization
        ↓
10. Roadmap generation
        ↓
11. Calendar integration
        ↓
12. UI polish / WOW factors

The exact implementation order can change based on technical dependencies, but optional features should not be built before the core retrieval loop works.

18. MVP Success Criteria

The MVP should successfully demonstrate:

Find

User describes an image using natural language.

Refine

User adds new clues conversationally.

Explain

User asks why a result was selected.

Act

User asks the agent to summarize or create a roadmap from the retrieved content.

Optional external action

User confirms a proposed schedule and calendar events are created.

The key demonstration is:

The system understands the user's memory, not just the image's filename.

19. Agent Scope
Decision

ChatLens uses a **single** intelligent agent (orchestrator) focused on ChatLens's core workflow. We are not building a complex multi-agent system.

Core agent (orchestration / action layer) capabilities:

Understand search intent
Refine searches
Maintain conversational context
Trigger retrieval and re-ranking
Explain results
Summarize retrieved content
Generate roadmaps
Propose calendar actions
Propose reminders

Summarization, roadmap/plan generation, calendar actions, and reminders belong to the orchestration / action layer, not the retrieval engine.

We will not turn ChatLens into a general-purpose autonomous AI agent during the hackathon.

We are deliberately **not** implementing: complex multi-agent systems, autonomous calendar management, face recognition, model training/fine-tuning, or unrelated AI features. The architecture stays simple, modular, testable, and hackathon-suitable.

20. No Unnecessary Model Training
Decision

We will prefer existing/open-source models and APIs where practical instead of training a proprietary vision model from scratch.

Reason

The hackathon goal is to demonstrate the product and retrieval experience, not to spend the majority of development time training infrastructure.

21. Documentation as Source of Truth
Decision

The repository documentation will be used to keep all team members and AI coding assistants aligned.

docs/
├── CHATLENS_MASTER.md
├── mvp.md
├── architecture.md
└── decisions.md

Additionally:

AGENTS.md

contains instructions for AI coding assistants.

Responsibilities

CHATLENS_MASTER.md
→ Overall product vision and complete understanding of ChatLens.

mvp.md
→ What must work for the MVP.

architecture.md
→ How the system is structured technically.

decisions.md
→ Important decisions and the reasoning behind them.

AGENTS.md
→ Instructions for Kiro and other AI coding assistants working on the repository.

22. Team Alignment Rule

Before implementing a major feature or changing the agreed architecture:

Check the documentation.
Discuss the change with the team.
Update the relevant documentation if the decision changes.
Then implement it.

No individual developer or AI coding assistant should silently redefine the product.

23. Guiding Question

For every new feature, ask:

Does this help the user find, understand, or act on something they remember?

If yes, it may fit ChatLens.

If no, it is probably outside the current scope.

24. External Sources / Telegram
Decision

External sources can provide additional visual memories.

Telegram is a **planned** source/input via a Telegram plugin/connector (planned, not yet implemented).

The Telegram integration should supply available images and associated metadata to the ChatLens ingestion/retrieval system, following the same overall ingestion and retrieval principles rather than a separate retrieval architecture.

The system should handle data arriving from such sources incrementally, as new content becomes available.

25. Reminders
Decision

Reminders are an orchestrated capability.

If the system identifies a genuine event, task, or deadline from available content or user input, the orchestrator may propose or schedule a reminder.

A reminder must be based on information that actually exists in available content or user input. The system must not invent deadlines, dates, or times.

Where confirmation is required, explicit user confirmation must be obtained before creating the reminder.

26. Mock/Dummy Frontend Retrieval Is Temporary
Decision

Any existing mock/dummy retrieval implementation in the frontend is temporary UI/demo behavior only.

It is **not** the actual retrieval architecture and must not be treated as the source of truth.

The final system uses the real ML retrieval engine through the backend/orchestration architecture. The frontend mock must not be documented as a real retrieval pipeline.

27. Implementation Direction
Decision

The current direction distinguishes CURRENT, PLANNED, and FUTURE work (planned features are not claimed as implemented):

1. Stabilize frontend UX for local visual-memory access.
2. Connect the backend to the real ML retrieval engine.
3. Test frontend → backend → real retrieval → results.
4. Add/complete conversational orchestration and context-aware refinement.
5. Add evidence-based "Why this result?" explanations.
6. Add supported orchestrated actions: summarization, roadmap/plan generation, calendar actions, reminders.
7. Add Telegram as an external source/plugin when implemented.
8. Perform complete end-to-end testing.

Final Product Definition

ChatLens

You remember it. We find it.

The product combines:

Visual Memory Retrieval + Conversational Refinement + Explainability + Intelligent Actions

The goal is not simply to search images.

The goal is to make a user's scattered visual archive feel like an intelligent extension of their memory.


**This version is better for your team** than the earlier one because it records the decisions you guys actually made in our discussion, especially the important ones: **not Google Lens, conversational retrieval, CLIP + OCR, “Why this result?”, agent actions, calendar confirmation, local dataset limitations, and web-first/mobile-optional.**

I'd put this at:

```text
ChatLens/
└── docs/
    └── decisions.md