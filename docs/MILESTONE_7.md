# Milestone 7 — On-Demand LLM Explanations

**Status:** Implemented and locally verified with provider calls mocked; no live LLM calls or explanation-quality claims.  
**Verification date:** 9 November 2026  
**Database migration:** None; M7 adds no persisted explanation data or schema changes.  
**Scope:** Explicit, provider-selected supplemental prose for one current deterministic finding, with provider-specific cloud consent and deterministic fallback.

## Delivered

### Owner-scoped explanation endpoint

`POST /api/v1/scans/{scan_id}/analysis/findings/{finding_id}/explanation` accepts only a provider choice:

```json
{"provider": "ollama"}
```

Supported values are `ollama`, `openai`, and `groq`. The caller cannot submit an arbitrary prompt, model name, context, citation, or conversation history. The route requires an authenticated owner, a scan explicitly confirmed with every scan entry confirmed, a completed current deterministic analysis, and a finding in that analysis. Missing or cross-user scans/findings are not exposed; stale analysis is rejected until rerun.

The generated response is returned for that request only and is not stored. It contains the finding ID, selected provider, `generated` or `fallback` status, explanation, notice, and educational disclaimer; it does not contain model-supplied citation fields. The deterministic analysis response remains the authority for findings and SQL-validated citations.

### Provider isolation and bounded output

- Ollama Chat, OpenAI Chat Completions, and Groq Chat Completions have separate adapters. The caller explicitly selects one; unconfigured, failing, invalid, refused, or incomplete responses use the reviewed deterministic rule message. There is no automatic provider switching.
- Requests are non-streaming and bounded by a configured timeout, context/response size limits, and output token limits. Provider credentials and model identifiers come only from server settings, never from request data.
- Providers receive a strict one-field JSON Schema contract. The response parser rejects additional fields, malformed/oversized output, links, and markup. This is structural validation only—not fact-checking; generated prose may still be incomplete or inaccurate.
- No tools, browser/network access, arbitrary user instructions, or conversation history are supplied to the model. Prompt-injection text in the supplied fields is treated as untrusted data by the fixed system instruction.
- Link-bearing context is rejected before provider I/O. Citation URLs and provenance are not prompt fields; trusted citation text is loaded and validated by the existing server-side analysis path.

### Minimal context and cloud consent

The provider payload is limited to one confirmed ingredient string, its canonical name, that current deterministic finding's title/message/severity, and up to three currently approved evidence summaries plus excerpts only where reproduction is permitted. It excludes raw images, email addresses, full scans or other scan ingredients, user profile/skin/sensitivity data, source URLs, and user-supplied prompts/history. Generated prose cannot create, remove, strengthen, weaken, or cite a deterministic warning.

OpenAI and Groq calls require current, provider-specific consent for the current disclosure version. The disclosure version is now `clarity-cloud-consent-v2`; a previous-version consent is not sufficient and must be renewed. Ollama is an operator-configured local/private endpoint and does not use cloud-provider consent. Consent can be inspected, granted, and revoked through:

- `GET /api/v1/users/me/ai-consents` — returns the current disclosure text/version and per-provider status.
- `POST /api/v1/users/me/ai-consents/{provider}` with `{"disclosure_version":"<current version>","accepted":true}` — grant OpenAI or Groq consent.
- `DELETE /api/v1/users/me/ai-consents/{provider}` — revoke only the selected provider's consent.

All state-changing calls use the application's authenticated session, CSRF protections, and Origin checks as configured. No provider key is accepted from or exposed to the browser.

### Configuration

All explanation settings are optional. In `.env`, configure only the provider(s) intended to be offered:

- `OLLAMA_BASE_URL` and `OLLAMA_CHAT_MODEL` for the private Ollama chat endpoint (the model setting is blank by default).
- `OPENAI_API_KEY` and `OPENAI_CHAT_MODEL` for OpenAI.
- `GROQ_API_KEY` and `GROQ_CHAT_MODEL` for Groq.
- `LLM_TIMEOUT_SECONDS` (default 30; bounded to 1–120 seconds).

Cloud keys remain server-side secrets. Without the selected provider's required settings, the endpoint returns deterministic rule text and identifies the response as `fallback`. A cloud request without current consent is rejected before provider construction/network access. No provider credentials, real model calls, or provider-retention behavior were tested in M7.

The endpoint uses an in-memory limit of 10 explanation requests per user per hour per application process. This limiter does not coordinate multiple workers; production deployments need a shared limiter/quotas before scaling horizontally.

## Verification

- Focused provider/config/analysis/auth tests: **35 passed**.
- Full backend suite: **76 passed**.
- Ruff format check and lint: passed.
- Unit tests use mocked transports and cover Ollama/OpenAI/Groq request contracts, no tools, provider selection/configuration, minimal payload boundaries, strict output validation, invalid/citation-inventing responses, response-size limits, and URL-bearing context rejected before any network call.
- Integration tests use synthetic-only database/evidence fixtures and mocked providers. They cover missing and revoked cloud consent, explicit provider choice, payload boundaries, generated and deterministic fallback responses, unconfigured providers, stale findings, scan confirmation, and cross-user access.
- No live provider call, production data, human review, clinical evaluation, or generated-explanation fact/quality evaluation was performed. No database migration or dependency was added.

## Not verified / not included

- Live Ollama/OpenAI/Groq connectivity, model-specific structured-output behavior, provider retention/abuse-monitoring terms, cost, latency, and explanation quality.
- A production UI/consent workflow, source/evidence corpus, or broad medical/domain evaluation.
- Any model-generated warning, recommendation, safety score, or trusted citation. Absence of findings remains no evidence of safety; generated text is supplemental and may be incomplete or inaccurate.
- The existing production source, ingredient, evidence, and rules corpus remains empty. All analysis tests use synthetic fixtures; no real provider credentials or scan content were sent externally.
