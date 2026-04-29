# 2026-04-29T05:56:18Z — Frank: First-Pass Token-Yield Estimate Across 26 Sources

**Agent:** Frank (Hawaiian Data Collector)  
**Agent ID:** frank-token-yield-estimate  
**Status:** Completed  
**Spawn Request:** yashasg via Coordinator Squad v0.9.1  

## Outcome

Token-yield estimate complete (no bytes fetched; based on corpus public knowledge + URL inventory).

### Estimates (Conservative / Base / Upside)

| Category | Tokens | Notes |
|----------|--------|-------|
| Raw Stage-1 Hawaiian (pre-clean, pre-dedup, pre-rights-filter) | 45M / 75M / 120M | Dominated by nūpepa OCR (~90%) via 3 overlapping routes |
| Train-eligible Stage-1 (publishable posture, no pre-1925 nūpepa) | 2.5M / 4.5M / 7M | hawwiki (~1.5–3M) + Wikisource (~0.5–1.5M) + small contributions |
| Train-eligible Stage-1 (prototype-only, nūpepa OCR included) | 30M / 50M / 80M | Post-OCR cleaning + paragraph-level LID + MinHash dedup |
| Stage-2 parallel (haw side, clean) | 1M / 2M / 3M | Bible-dominant; pipeline spec: "<50k–<10k pairs realistic" |
| Eval-only (FLORES) | ~50k | hawn_Latn dev (997) + devtest (1012) |

### Key Corpus Drivers

**Raw volume:** Ulukau/nūpepa newspapers (only source with order-of-magnitude swing; also strictest publication block)  
**Publishable Stage-1 backbone:** hawwiki dump + Wikisource  
**Stage-2 backbone:** Baibala Hemolele verse-aligned with KJV/ASV  
**Small, high-value:** FLORES (eval anchor), Tatoeba (clean parallel), Wiktionary (lexicon audit), Awaiaulu (modern register)  

### Biggest Uncertainties (Priority Order)

1. Nūpepa OCR yield rate post-cleaning (30–70% survival range) + publication ADR binding
2. Tokenizer choice (Hawaiian's ʻokina/kahakō/syllable structure; 1.3× word→token may be ±30% off)
3. NLLB Hawaiian coverage (unknown; 0–2M potential parallel tokens)
4. OHA/UH/DOE per-doc rights review pass rate (only non-Bible parallel source at scale)
5. Cross-source dedup loss (Bible editions, Wikipedia mirrors, 3× nūpepa routes)

## Pilot Plan (1–2 Days, No Bulk Fetch)

- Pull hawwiki + hawwiktionary dumps; SentencePiece token count post-WikiExtractor
- Pull Tatoeba haw export + FLORES dev/devtest; exact line + token counts
- Pull one Hawaiian Bible edition + KJV + ASV USFM; verse-aligned counts
- Inventory OPUS haw subsets via per-corpus index (line counts only)
- `internetarchive` client: enumerate `language:haw mediatype:texts`; sample 50; record OCR confidence + word counts
- Wikisource API sample: 20 pages for token density
- Output: `data-sources/pilot_token_counts.parquet` (one row per source with sample size, observed tokens, CI bands, rights posture, prototype flag)

**Goal:** Replace ±2× ranges with ±20% bands without committing to rights-questionable bulk pulls.

## Files Changed

- `.squad/agents/frank/history.md` (appended durable summary)

## Notes

- No decision file created (Coordinator directive; no team choice needed)
- Estimates grounded in public corpus knowledge + existing URL routing config
- Tightening plan is a follow-on task (Frank will execute unless redirected)
