# Milestone 1 — Requirements and Architecture

**Status:** Complete and approved  
**Date:** 9 November 2026

## Completed

- Reviewed the product brief and development constraints.
- Defined the PRD, MVP scope, non-goals, user journeys, pages, acceptance criteria, and product metrics.
- Produced a feasibility review and selected the initial stack with dependency pinning deferred until a clean Python 3.11 compatibility check.
- Designed system boundaries, scan lifecycle, database entities, API routes, authentication model, and threat controls.
- Created the project directory skeleton and the initial architecture/PRD documents.
- Captured approved decisions:
  - Brand: Clarity Checker; descriptor: AI Skincare Ingredient Checker.
  - Retain label photos privately until the user deletes them.
  - Include Ollama, OpenAI, and Groq provider options.
  - Require provider-specific account-level opt-in for OpenAI/Groq.
  - Cloud payload is confirmed OCR ingredient text plus approved evidence only; never the raw photo, email, or full skin profile.
  - Use deterministic source-backed rules; LLM output cannot change warnings or citations.

## Status at Milestone 1 close

At the time Milestone 1 was approved, no application code or test results existed. Milestones 2–5 have since added the backend foundation, authentication/profile/privacy APIs, ingredient/evidence catalog workflow, and image/OCR intake APIs; results and verification limits are recorded in [MILESTONE_2.md](MILESTONE_2.md) through [MILESTONE_5.md](MILESTONE_5.md). No OCR accuracy, ingredient-safety, or product-analysis results are claimed.

## Follow-on work

Milestone 5 — Image and OCR has since implemented server-side validation/size limits, safe re-encoding, a local OCR adapter with persisted job states, and correction/confirmation APIs. The separate evaluation gate remains pending a reviewed corpus, ground truth, and an available OCR engine; see [MILESTONE_5.md](MILESTONE_5.md).
