---
name: studio-router
description: Natural-language entry point for Codex Game Studios. Detects intent, selects the right workflow, and routes to automation, design, production, engineering, QA, or release skills.
---

# Studio Router

Use this skill whenever the user asks Codex to help plan, design, build, review,
or organize a game project with Codex Game Studios.

## Routing Workflow

1. Inspect the project before recommending a workflow:
   - Run or emulate `./scripts/cgs-detect-stage.ps1`.
   - Check for engine files, `design/`, `docs/`, `production/`, `src/`,
     `prototypes/`, and test assets.
   - Summarize only decision-useful findings.
2. Classify the user intent:
   - New idea or vague concept: use `brainstorm`, then `setup-engine`.
   - Existing concept: use `project-stage-detect`, `map-systems`,
     `design-system`, or `create-architecture`.
   - Existing implementation: use `studio-doctor`, `automation-gate`,
     `code-review`, `tech-debt`, or `perf-profile`.
   - QA/release: use `qa-plan`, `smoke-check`, `release-checklist`,
     `launch-checklist`, or `patch-notes`.
3. Select expert references from `./agents/` when useful:
   - Creative decisions: `creative-director`, `game-designer`,
     `art-director`, `narrative-director`, `audio-director`.
   - Technical decisions: `technical-director`, `lead-programmer`,
     engine or programming specialists.
   - Delivery decisions: `producer`, `qa-lead`, `release-manager`.
4. Present the next concrete action and, when the user asked for execution,
   perform it with focused file edits and validation.

## Codex-Native Behavior

- Prefer automation scripts for repeatable checks.
- Use natural language routing instead of asking the user to memorize slash
  commands.
- Use Codex sub-agents only when the user explicitly asks for parallel agents
  or delegation.
- Keep the user in control of creative and scope decisions.

## Output

Return:
- Current project stage.
- Recommended next workflow.
- Skills or expert references used.
- Any checks run and their result.
