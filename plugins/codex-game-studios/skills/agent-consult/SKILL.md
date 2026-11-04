---
name: agent-consult
description: "Apply one expert role file as a focused consultation lens; use when the user names a studio role or asks for that perspective."
---

# Agent Consult

Use this skill when the user asks for a specific game-studio expert, such as a
creative director, technical director, producer, QA lead, engine specialist, or
discipline specialist.

## Workflow

1. Identify the requested expert role.
2. Read the matching file in `./agents/`.
3. Apply that role as a consultation lens for the current task.
4. If the requested role is ambiguous, choose the closest matching expert and
   state the choice.
5. If a decision is needed, present concrete options and a recommendation, but
   keep the user's decision authority explicit.

## Output

Return:
- Expert role used.
- Relevant project context reviewed.
- Recommendation or review findings.
- Next action or validation criteria.
