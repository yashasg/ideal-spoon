# Orchestration Log: danny-remove-data-release-wording

**Timestamp:** 2026-04-29T05:06:20Z  
**Agent:** Danny (Lead)  
**Spawn ID:** danny-remove-data-release-wording  
**Requested by:** yashasg  
**Topic:** Remove release wording from docs/data-pipeline.md

## Directive

User: "docs still mentioned 'release'; project is prototype-only — strip it."

## Outcome

✅ **docs/data-pipeline.md rewritten to prototype-only scope.**

- Replaced "Prototype vs Release" two-column section with single-column "Prototype scope" table.
- Removed `release_eligible` field from manifest schemas (Stage 1 and Stage 2).
- Status banner reworded to "public sharing … is out of scope."
- Reframed source-table phrases: release-eligibility language → license-posture / FLORES-200-inclusion language.
- CI guard clarified: "refuse external publication" (publication itself out of scope).
- **Verification:** `rg -i release docs/data-pipeline.md` returns **zero matches**.

## Files Modified

- `docs/data-pipeline.md` — released-scope references stripped; prototype-only guardrails preserved (provenance, manifests, contamination guards, cultural sensitivity, licensing posture).
- `.squad/agents/danny/history.md` — entry 66 appended: "data-pipeline.md release-language sweep (2026-04-29)".

## Pattern Applied

When collapsing dual-posture (prototype-vs-release) framing under explicit prototype-only directive:
- Prefer removing release-hypothetical language entirely over preserving "if we ever pivoted" scaffolding.
- Preserve engineering gates and guard machinery; reframe as prototype-only fixtures.

## Related Decisions

- Existing ADR: "Prototype scope" (formerly "prototype-vs-release split" in `.squad/decisions.md`).
- No new team decision; applies existing prototype-scope direction.

## Status

**Ready to commit.** Staged: `.squad/agents/danny/history.md`.
