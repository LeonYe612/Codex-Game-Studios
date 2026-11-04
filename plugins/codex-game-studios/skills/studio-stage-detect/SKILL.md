---
name: studio-stage-detect
description: Detects a game project's current stage and recommends the next Codex Game Studios workflow.
---

# Studio Stage Detect

Use this skill when the user asks where their game project stands, what is
missing, or what to do next.

## Workflow

1. Run `./scripts/cgs-detect-stage.ps1`.
2. Interpret the result:
   - Empty or no concept: recommend `brainstorm`.
   - Concept without engine: recommend `setup-engine`.
   - GDDs without architecture: recommend `create-architecture`.
   - Architecture without stories: recommend `create-epics` and
     `create-stories`.
   - Stories without sprint plan: recommend `sprint-plan`.
   - Implementation in progress: recommend `automation-gate`, `dev-story`,
     `smoke-check`, or `code-review`.
3. Use relevant expert references from `./agents/` if the recommendation depends
   on design, technical, production, QA, or release concerns.

## Output

Return the detected stage, evidence, gaps, and one recommended next action.
