---
name: "adr"
description: "Write a structured, neutral and concise Architecture Decision Record (ADR)."
---

# Skill: Architecture Decision Record (ADR)

## Invocation

```
/adr <decision title>
```

Example: `/adr Migration to PostgreSQL for feedback storage`

## Objective

Produce a factual, neutral and concise ADR (200-400 lines max) in `docs/adr/`.

## Workflow

1. **Identify the next number**: list `docs/adr/*.md`, take the next highest number.
2. **Explore the context**: read source files and existing ADRs related to the topic.
3. **Write the ADR** following the template below.
4. **Create the file**: `docs/adr/<NNN>-<slug>.md`

## Writing rules

### Tone and style
- Neutral and factual. No promotional language.
- No emojis.
- Short sentences. Avoid superlatives.
- Write in English (project language).

### Size constraints
- **200-400 lines maximum.**
- No complete implementation code blocks (describe what to do, not the exact code).
- No content that belongs in CHANGELOG, README or CLAUDE.md.
- Tests are referenced by path, not inline.

### Content
- Describe the problem, not the desired solution.
- List at least 2 options with factual pros/cons.
- Never decide: the ADR presents options, the team decides.
- Default status is "Proposed". Only change to "Accepted" when the team has made its decision.
- The Decision, Architecture, Implementation and Consequences sections are only filled after team validation.
- Include a rollback strategy if applicable.

## Template

```markdown
# ADR <NNN>: <Title>

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX
**Deciders:** Team Mondi

---

## Context

[Factual description of the current state and the problem to solve.
Include relevant technical and business constraints.]

---

## Options considered

### Option A: <Name>

<Description in 2-3 sentences.>

| | |
|---|---|
| Pros | ... |
| Cons | ... |
| Complexity | Trivial / Low / Medium / High |

### Option B: <Name>

<Same>

### Option C: <Name> (if applicable)

<Same. Indicate why rejected if applicable.>

---

## Decision

> To be completed by the team after discussion.

---

## References

- [Title](link or path)
```

## Anti-patterns

- Do not include CHANGELOG or user documentation sections.
- Do not copy-paste complete source code into the ADR.
- Do not include open-ended "next steps" (the implementation covers that need).
- Do not use subjective wording ("excellent", "perfect", "best choice").
- Do not add future revision notes unless a specific date is defined.
