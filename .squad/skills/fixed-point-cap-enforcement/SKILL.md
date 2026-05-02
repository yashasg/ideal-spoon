---
name: "fixed-point-cap-enforcement"
description: "Enforce simultaneous fractional caps (e.g., source-share limits) against the FINAL artifact, not a stale reference denominator."
domain: "data-pipeline"
confidence: "high"
source: "earned (Stage 2 review-pass; two prior owners locked out for cap-denominator drift)"
---

## Context

When a dataset must satisfy multiple share caps simultaneously
(e.g., "Bible <= 30% of train tokens" AND "legal-register <= 15% of
train tokens"), the obvious greedy approach — cap each source against
the current denominator, then cap the next — produces an artifact
whose final shares VIOLATE the caps. The fix is twofold:

1. Compute targets via the closed-form fixed-point.
2. Verify shares directly from the emitted artifact and drop the tail
   until the artifact-measured shares pass.

## Patterns

### Closed-form for two caps

For sources X with cap `x_max` and Y with cap `y_max`, total
`T = N + X + Y` where N is uncapped base tokens:

```
X_max = x_max * N / (1 - x_max - y_max)
Y_max = y_max * N / (1 - x_max - y_max)
```

For 30%/15% caps: `X = 6N/11`, `Y = 3N/11`, `T = 20N/11`.

### Deterministic subsampling

Sort pool by `sha256_pair` ascending. Greedy-add rows until next
row would exceed target. Reproducible, no randomness.

### Artifact verification loop

After selection, re-read the emitted rows; recompute shares; if a
share exceeds its cap by rounding, pop the highest-`sha256_pair` row
of that source and re-verify. Loop until all caps hold on the
artifact itself.

## Examples

- `scripts/333_build_reviewed_manifest_final_capped.py`
- `.squad/decisions/inbox/danny-review-pass-final-cap.md`

## Anti-Patterns

- **Cap against `T_target` (the goal, e.g. 80k rows) rather than
  actual final tokens.** Linus did this. Result: Bible 91.9% of train.
- **Cap source A first, then cap source B; assume A's share holds.**
  Basher did this. After B was capped, the denominator shrank and A's
  actual share rose from 30% to 64.8%.
- **Trust the report your script prints.** Always re-read the file.
- **Use a "reference denominator" that won't appear in the shipped
  artifact.** If the reader of your dataset can't recompute the caps
  from the file alone, your cap isn't enforced.
