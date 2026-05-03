# Linus — Stage-2 HK statutes Round 8 extension

## Legal/TOS check

- Host for 1869/1859/1846 is the same as the already-processed 1897 pair: `archive.org`.
- Existing IA ToS snapshot inherited: `data/raw/hawaiian-kingdom-statutes-paired-imprints/20260501/_tos/ia_terms.html`, snapshot id `ia_terms`, fetched `2026-05-01T21:14:22Z`, sha256 `4bbba9062696abf26a594e0c9fb3e84101cf05321f557b9d8baf862f863ada7b`.
- Rights status: public domain for the legal text (pre-1929 public-domain term + sovereign-edicts doctrine for government legal edicts). IA ToS governs hosted scan/OCR bytes.
- No live fetch was performed in Round 8; only already-local raw OCR and manifests were inspected.

## Editions added to source registry / adapter pins

- 1869 Penal Code: EN `https://archive.org/details/esrp475081650`; HAW `https://archive.org/details/esrp468790723`; status `blocked-content-mismatch` because HAW OCR filename is `1850.002_djvu.txt` and prior sampling found mismatched content. Dry-run parsed 38 EN sections / 2 HAW sections / 1 common / 0 emitted.
- 1859 Civil Code: EN `https://archive.org/details/civilcodehawaii00armsgoog`; HAW `https://archive.org/details/hekumukanawaiam00hawagoog`; status `in-progress-dryrun-only` pending manual Pauku range mapping. Dry-run parsed 195 EN sections / 80 HAW sections / 21 common / 0 emitted.
- 1846 Statute Laws: EN `https://archive.org/details/statutelawshism00ricogoog`; HAW `https://archive.org/details/kanawaiikauiaek00ricogoog`; status `in-progress-dryrun-only` pending act/chapter segmentation because section numbers repeat across acts. Dry-run parsed 633 EN section markers / 36 HAW markers / 0 common / 0 emitted.

## Shipped

- `scripts/325_build_hk_statutes_candidates.py` is now edition-parameterized (`--edition 1897|1869|1859|1846`).
- `--execute` remains allowed only for 1897; non-1897 editions are dry-run/inventory only until alignment blockers are cleared.
- Added `data-sources/hk-statutes/source_registry.json` with license/TOS, source URLs, access timestamps, raw sha256 values, and edition status.
- Added stdlib unittest with mocked HTTP layer to verify User-Agent/rate-limit behavior without live network.
