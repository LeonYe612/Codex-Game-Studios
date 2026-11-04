---
name: automation-gate
description: Runs Codex-native quality gates for game design, production artifacts, source layout, assets, tests, and release readiness.
---

# Automation Gate

Use this skill when the user asks for a quality gate, readiness check, validation
pass, pre-commit review, pre-release check, or project safety scan.

## Workflow

1. Run `./scripts/cgs-validate-project.ps1`.
2. Run `./scripts/cgs-doctor.ps1` if plugin or repository health is in scope.
3. Review detected issues against the current project stage.
4. Classify results:
   - Pass: no blocking issues.
   - Concerns: warnings exist but work can continue.
   - Blocked: missing required artifacts, invalid JSON, leaked paths, or
     structurally broken plugin files.
5. Recommend the smallest next fix.

## Output

Start with one verdict:

```text
AUTOMATION-GATE: PASS
AUTOMATION-GATE: CONCERNS
AUTOMATION-GATE: BLOCKED
```

Then list blocking issues, warnings, and next action.
