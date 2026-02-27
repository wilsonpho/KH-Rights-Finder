# Skill: Backend Ticket Skeleton (KH Rights Finder)

You are implementing ONE backend ticket only. Do not modify frontend files.

## Guardrails (non-negotiable)
- Cambodia authoritative sources are Tier A; never infer missing fields.
- If a value is not present in source/snapshot: set null and add parse_warnings.
- Always persist raw_text and snapshot reference.
- Include tests for backend logic changes.
- Include Alembic migration for any DB schema change.
- Keep backwards compatibility for existing rows.

## Output Format (must follow)
1) Assumptions (max 5 bullets)
2) Files to change (explicit list)
3) Plan (max 8 bullets)
4) Implementation details
   - DB migration notes
   - Model/schema notes
   - Worker notes
   - API notes
5) Tests to add/run (exact commands)
6) Manual verification steps (SQL query + one sample mark)

## Stop conditions
If the ticket requires frontend changes or unclear requirements, STOP and ask a single clarification question.
