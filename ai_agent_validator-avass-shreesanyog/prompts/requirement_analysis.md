# Requirement & Use Case Analysis Engine prompt (Phase 1)

Used by `backend/app/services/analysis.py` (`SYSTEM`).

Enforces source priority: explicit business requirements/acceptance criteria >
supplied documents > explicit use case > agent documentation > agent description
> system prompt > tool schemas > other context. Conflicts are reported as a
`requirement_gap`, never silently resolved.

Every requirement is classified `EXPLICIT` / `DERIVED` / `INFERRED` / `UNKNOWN`.
INFERRED is never authoritative — a `cancel_order` tool existing does not mean
cancellation is business-permitted.

**Guardrail beyond the prompt**: `_enforce_source_discipline()` deterministically
re-verifies every `EXPLICIT` claim by term overlap against the actual supplied
source text, and downgrades untraceable claims to `DERIVED` with a
`_source_reclassified` marker. The model's own label is never trusted on its own.

See the full output JSON contract in `analysis.py`.
