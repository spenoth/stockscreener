# AI Harness Prompt Cheat Sheet

> **Important:** Each step below must be executed in a **new, separate chat window (chat session)**.
> This ensures that each agent remains unbiased and provides an independent opinion, code, or review —
> completely isolated from the context and decisions of the previous steps.
> Think of each chat session as a separate individual agent.

---

## Step 1 — Discovery Agent

**Goal:** Understand the problem space and gather requirements before any design decisions are made.

**Open a new chat session and use this prompt:**

```
Act as a Discovery Agent.
I want to build a stock screening application.

Do NOT design the solution.
Instead:
- Understand what problem I want to solve
- Identify requirements
- Identify missing information
- Identify risks
- Ask follow-up questions

Your output should be a structured Discovery Report.
```

The AI will ask follow-up questions until it has enough information to produce a comprehensive Discovery Report.

**📄 Save the result as:** `quant-db/ai-harness/buisness-requirements.md`

---

## Step 2 — Planning Agent

**Goal:** Turn the discovery output into a structured development roadmap with incremental milestones.

**Open a new chat session and use this prompt:**

```
You are acting as a Planning Agent.
I have completed the discovery phase.
The project requirements are described in the attached file: buisness-requirements.md

Your task is NOT to generate code.

Create a development roadmap:
- Break the system into small, deliverable features
- For each feature provide:
  - Business goal
  - Dependencies
  - Acceptance criteria
  - Estimated complexity
  - Recommended implementation order
- Focus on delivering value incrementally

Output format:
- Roadmap
- Milestones
- Implementation waves
```

**📄 Save the result as:** `quant-db/ai-harness/development-roadmap.md`

---

## Step 3 — Specification Planner

**Goal:** Break down a specific wave into concrete, independently implementable features.

**Open a new chat session and use this prompt:**

```
You are acting as a Specification Planner.

I have already completed:
- business-requirements.md (attached)
- development-roadmap.md (attached)

Focus only on: Wave 1 — Solid Foundation (Backend Data Layer)

Your task:
Break Wave 1 into concrete implementation features.

Each feature must:
- Be independently implementable
- Have clear acceptance criteria
- Be completable within a few days
- Provide measurable progress

For each feature provide:
- Feature name
- Purpose
- Dependencies
- Acceptance criteria
- Implementation priority

Do NOT generate code.
Do NOT generate architecture.
Only create feature specifications.
```

**📄 Save the result as:** `quant-db/ai-harness/specs/wave1-feature-specifications.md`

---

## Step 4 — Specification Agent (In-Depth)

**Goal:** Produce a detailed functional specification for each feature identified in Step 3.

**Open a new chat session and use this prompt:**

```
You are acting as a Specification Agent.

Context (attach the following files):
- business-requirements.md
- development-roadmap.md
- wave1-feature-specifications.md

Feature focus: Wave 1 — Solid Foundation (Backend Data Layer)

Create a detailed functional and tehnical specification. Include:
- Purpose
- Scope
- Inputs
- Outputs
- Business Rules
- Data Requirements
- Error Handling
- Acceptance Criteria
- Out of Scope
- Open Questions

Do NOT generate code.
Do NOT generate implementation details.
```

**📄 Save the result as:** `quant-db/ai-harness/indepth-specs/wave1-backend-data-layer.md`

---

## Step 5 — Code Generation Agent

**Goal:** Generate implementation code based on the approved functional specification.

**Open a new chat session**, attach the relevant in-depth spec file, and ask the agent to implement the feature according to the specification.

**📄 Save generated code into the appropriate source files.**

---

## Step 6 — Code Review Agent

**Goal:** Independently review the generated code for quality, correctness, and alignment with specifications.

**Open a new chat session**, attach both the in-depth spec and the generated code, and ask the agent to perform a thorough code review.

The reviewer has no knowledge of the previous sessions — it will provide a fresh, unbiased assessment.

**📄 Document review findings and apply fixes as needed.**

---

> **Workflow Summary**
>
> | Step | Agent | Input | Output |
> |------|-------|-------|--------|
> | 1 | Discovery Agent | Your idea | `buisness-requirements.md` |
> | 2 | Planning Agent | requirements | `development-roadmap.md` |
> | 3 | Specification Planner | roadmap | `wave1-feature-specifications.md` |
> | 4 | Specification Agent | feature specs | `indepth-specs/*.md` |
> | 5 | Code Generation Agent | in-depth spec | source code |
> | 6 | Code Review Agent | spec + code | review findings |
