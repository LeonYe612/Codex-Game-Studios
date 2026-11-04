# Codex-Native Design

Codex Game Studios is not a 1:1 clone of Claude Code Game Studios. It keeps the
source material, but adapts the workflow to Codex strengths.

## Why Not Copy Claude Agents Directly?

Claude Code uses `.claude/agents/*.md` as first-class agent definitions. Codex
plugins currently expose skills, plugin metadata, scripts, and supporting
instruction bundles, but do not use the same `.claude/agents` registration
mechanism.

Instead of pretending the systems are identical, this port treats the 49 studio
roles as expert references. Codex skills can read and apply them as consultation
lenses through `agent-consult`, `studio-router`, and related workflows.

## Codex-Native Workflow

Codex Game Studios emphasizes:

- Natural-language routing through `studio-router`
- Repeatable automation through PowerShell scripts
- Quality gates through `automation-gate`
- Stage detection through `studio-stage-detect`
- Expert consultation through `agent-consult`

This means a user can say "check my game project" or "help me design a combat
system" and Codex can choose the workflow, inspect the project, run checks, and
apply relevant expert references.

## Hooks Strategy

The original Claude project includes session and tool lifecycle hooks. Codex
does not need the same hook model for the core experience. This port keeps a
valid `hooks.json` advisory file and moves practical validation into scripts
that Codex can run on demand.

The gate scripts are PowerShell 7 scripts and require `pwsh`. Codex skills can
still follow their workflows without PowerShell when a check can be emulated
from the repository contents.

Recommended gates:

- `plugins/codex-game-studios/scripts/cgs-doctor.ps1` for plugin and repository health
- `plugins/codex-game-studios/scripts/cgs-detect-stage.ps1` for project stage detection
- `plugins/codex-game-studios/scripts/cgs-validate-project.ps1` for project artifact validation

## Multi-Agent Use

If a Codex environment supports multi-agent work, `studio-router` can use the
expert references to decide which perspectives are useful. Actual delegation
still follows Codex's available agent types and current user permission model.
