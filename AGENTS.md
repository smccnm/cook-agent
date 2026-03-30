# Repository Instructions

## Commit Discipline

- After any meaningful fix, feature completion, or verified refactor, commit immediately.
- Do not leave validated code changes uncommitted while waiting for the user to remind you.
- If a change is split into multiple coherent steps, commit each step once its tests or verification pass.
- Only delay a commit when:
  - the user explicitly says not to commit
  - the change is still failing verification
  - the change is blocked and incomplete

## Verification Before Commit

- Run the most relevant tests or verification commands before each commit.
- Summarize what was verified in the user-facing response.

## Scope

- Prefer small, focused commits with clear messages.
- Do not bundle unrelated cleanup into the same commit.
