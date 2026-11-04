---
name: studio-doctor
description: "Check plugin and project health, then summarize structural, workflow, and release-readiness issues."
---

# Studio Doctor

Use this skill when the user asks to check, validate, audit, or diagnose a
Codex Game Studios project or plugin installation.

## Workflow

1. Run `./scripts/cgs-doctor.ps1` from the repository root.
2. If the user is checking a game project, also run:
   - `./scripts/cgs-detect-stage.ps1`
   - `./scripts/cgs-validate-project.ps1`
3. Summarize findings by severity:
   - Blocking: invalid JSON, missing plugin manifest, missing skills, broken
     attribution, or leaked local paths.
   - Warning: missing docs, incomplete production artifacts, missing tests.
   - Info: project stage and recommended next workflow.
4. Offer the next Codex Game Studios action through `studio-router`.

## Output

Keep output concise:
- Overall verdict.
- Blocking issues.
- Warnings.
- Recommended next step.
