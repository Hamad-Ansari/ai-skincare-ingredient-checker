# Production data and review intake

**Status:** The owner reports that a source packet is ready and a qualified reviewer is confirmed. A workspace check found no source packet or reviewer evidence under `data/private/`; the seed manifest remains empty. Rights documents, reviewer qualifications/scope, and written approval have not been supplied or reviewed. Do not populate the production seed or enable real ingredient findings until intake is complete and each source's terms have been reviewed. Use [`PRODUCTION_REVIEW_WORKSHEET.md`](PRODUCTION_REVIEW_WORKSHEET.md) to prepare one restricted record per source and reviewer decision.

A public URL or “open data” label alone is not sufficient evidence of permission for this product's storage, transformations, display, excerpting, or redistribution. No production source or evaluation corpus is currently approved.

## For each source/data package, provide

1. **Source identity:** publisher/author, title, canonical URL or licensed delivery location, version/release, retrieval date, checksum, and any account/access restrictions.
2. **Rights evidence:** license/contract/permission text, who granted it, effective/expiry dates, permitted territories, and whether commercial use, modification, storage, derived records, public display, and redistribution are allowed.
3. **Attribution and excerpt rules:** required credit, citation format, limits on excerpts/quotes, whether paraphrase/derived facts can be displayed, and any notice or link requirements.
4. **Data dictionary:** field meanings, units, encoding, ingredient naming/INCI conventions, language/locale, missing-value rules, and source-specific caveats.
5. **Scope and provenance:** which records/ingredients the package covers, how records map to canonical ingredient identifiers, known gaps/ambiguities, and how an operator can trace every imported row back to its source record.
6. **Qualified review:** reviewer name/role/qualifications and review scope; row/rule/evidence approval decisions; conflicts/limitations; date and version reviewed; and any signed approval or review memo. Do not provide unnecessary personal details.
7. **Evaluation set, if supplied:** documented rights for evaluation use; ground-truth labels and annotation instructions; adjudication process and disagreements; separation from training/development examples; and privacy review for every image or text sample.

## Recommended handoff layout

Keep licensed source packets and real evaluation material out of Git and out of public reports. Use a restricted private transfer approved by the owner/operator; do not paste personal scan photos, user data, or credentials into this repository or public issues.

```text
data/private/source-packets/<source-id>/
  source-metadata.json       # provenance, terms, permitted uses, attribution, checksum
  rights/                    # license/contract/permission evidence; restricted access
  import-manifest.json       # format accepted by the reviewed admin import workflow
  reviewer-approval.md       # signed/versioned source, row, rule, and evidence decisions

data/private/evaluation/<evaluation-id>/
  evaluation-manifest.json   # rights, scope, labels, protocol, adjudication, metrics plan
  labels/                    # private, access-controlled annotations and ground truth
```

The paths above are illustrative. `data/private/` is Git-ignored; verify the ignore rules and backup/data-retention policy before placing files there. Keep a separate access-controlled original and checksum; import only approved material.

## Review gates before activation

- Legal/privacy review confirms the exact intended uses and attribution for each source and evaluation asset.
- A qualified skincare/domain reviewer approves ingredient normalization, each evidence mapping, each deterministic rule and its conditions, and each user-facing claim. A technical import approval is not a clinical or safety endorsement.
- The operator records reviewer/version/date in the source registry and each relevant review note; rights changes and review expiry have an owner and process.
- Evaluation protocol defines representative cases, ground truth, denominators, handling of ambiguous labels, adjudication, and pass/fail thresholds before results are examined.
- Measurements report OCR character/word error, ingredient extraction/normalization precision and recall, rule/citation support, failure cases, and uncertainty. Synthetic fixtures are excluded from production-quality claims.
- No “no match,” “no finding,” or empty rule result is represented as proof that a product is safe.

## Owner handoff needed

Provide the source packet(s), rights evidence, proposed deployment use/territory, and qualified reviewer's scope through an approved private channel. Once received, the next work is a rights review, data mapping, staged import, row/rule/evidence review, and a versioned evaluation report. Until those materials and approvals exist, keep `data/seed/ingredient_seed_manifest.json` empty and do not claim the product is validated for real-world use.
