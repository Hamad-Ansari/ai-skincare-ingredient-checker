# Product Requirements Document
## Clarity Checker — AI Skincare Ingredient Checker

**Status:** Approved product baseline; Milestones 2–5 backend/auth/profile/catalog and image/OCR intake APIs implemented locally. Live OCR evaluation, external ingredient/evidence seed, frontend, safety rules, and analysis features remain pending  
**Date:** 9 November 2026

## 1. Product vision

Help people understand cosmetic ingredient lists by converting a label image or typed list into a user-confirmed, normalized ingredient list, then presenting educational explanations and traceable evidence. The system may identify a match against ingredients or preferences the user explicitly declared.

The product must communicate uncertainty and evidence. It is not a diagnostic or treatment tool and must not guarantee product safety.

## 2. Users

- General skincare consumers seeking plain-language ingredient information.
- Users with self-declared ingredient sensitivities or preferences.
- Skincare enthusiasts comparing product ingredient lists.
- Beauty/product reviewers who need transparent, source-backed observations.

User-declared allergy/sensitivity terms are not represented as clinically verified facts. The application must not infer a condition from a photograph.

## 3. MVP capabilities

1. **Accounts:** registration, login/logout, email verification and password-reset workflows, profile settings, secure user-scoped history.
2. **Skin profile:** optional skin type, concerns, sensitivities, allergies/preferences, and current products; editable and deletable.
3. **Scanner:** accept JPEG/PNG/WebP; validate and preprocess images; perform OCR; show extracted text, uncertain tokens, and confidence metadata; allow manual correction and confirmation.
4. **Ingredient catalog:** normalize confirmed ingredient names to reviewed canonical/INCI records and aliases; preserve original text; leave ambiguous terms unresolved.
5. **Evidence and rules:** retrieve curated evidence; run deterministic, versioned, source-linked rules; distinguish user-declared matches, potential concerns, insufficient evidence, and no configured rule triggered.
6. **AI explanations:** Ollama, OpenAI, and Groq adapters. Cloud analysis requires provider-specific account-level opt-in and sends only confirmed OCR ingredient text and approved evidence excerpts—not raw images, email, or full profiles. LLM output cannot create/suppress warnings or citations.
7. **Compare:** compare two to four products/scans; show overlap, unique and unresolved ingredients, user-declared matches, and supported rule findings.
8. **Routine planner:** editable, reorderable morning/evening lists with informational checks, not prescriptions.
9. **Dashboard/history:** user-scoped scans, saved products, ingredient history, comparisons, routines, and profile.
10. **Privacy:** export/delete account data; retain uploaded photos privately until the user deletes them; disclose backup retention.
11. **Administration:** restricted, audited source ingestion, evidence review, and rule version activation.

## 4. Required pages

1. Landing page
2. Registration and login
3. Onboarding
4. Dashboard
5. Skin profile
6. Ingredient scanner
7. Analysis results
8. Ingredient details
9. Product comparison
10. Routine planner
11. Scan history
12. Account settings
13. Privacy policy
14. Terms of service

All pages must have responsive layouts and accessible navigation. Use custom CSS and vanilla JavaScript; controls must be functional, not decorative.

## 5. Out of scope for MVP

- Overall “safe/unsafe” verdict, product safety score, or unreviewed evidence letter grade.
- Diagnosis, treatment, or image-based skin-condition analysis.
- Automatic ingredient confirmation from low-confidence OCR or fuzzy name matches.
- Cloud image/multimodal OCR; raw photos are not sent to OpenAI or Groq.
- Sending user email or full skin profile to a cloud model.
- Product recommendations or instructions to start/stop a treatment.
- Subscription billing, social sharing of private scans, or guaranteed barcode catalog coverage.
- Clinical-validation or regulatory-clearance claims.

## 6. Acceptance criteria

- Each user-owned scan, product, routine, comparison, and profile is inaccessible to every other user.
- Image intake enforces server-side type, size, and pixel limits and stores files privately under generated IDs.
- Users can inspect/correct OCR output before analysis; unresolved ingredients remain visible as unresolved.
- Every finding has a tested rule/version and at least one approved evidence reference; source metadata is rendered by the server.
- An LLM outage, invalid response, or provider refusal cannot remove or add deterministic findings; a template fallback is available.
- OpenAI/Groq calls are blocked unless that provider’s account-level consent is active. Outbound payload tests prove no raw image, email, or full skin profile is sent.
- User can delete a scan and its image, export their data, and request account deletion.
- Pages target WCAG 2.2 AA; keyboard, focus, error, loading, and screen-reader status behavior are tested.
- Evaluation reports actual OCR, extraction, normalization, warning, citation, and latency results. No metrics are claimed before measurement.

## 7. Product metrics

Track scan completion/correction rates, unknown ingredient rate, OCR character error rate, ingredient precision/recall, canonical-match accuracy, per-rule false-positive/false-negative rates, citation validity/support, worker failure rate, API/worker latency, cloud provider usage/cost, user export/deletion completion, and privacy consent/revocation events.

The planned 30-label evaluation set is an initial benchmark only. It does not establish broad accuracy across all brands, languages, packaging types, or user populations.

## 8. Required disclaimer

“Clarity Checker provides educational cosmetic ingredient information. It does not diagnose skin conditions, prescribe treatment, or guarantee that a product is safe for you. Ingredient lists and automated extraction may be incomplete or inaccurate. A missing warning does not mean that a product has no risk. Consult a qualified clinician about personal health concerns.”
