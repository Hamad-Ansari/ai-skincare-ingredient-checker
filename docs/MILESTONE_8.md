# Milestone 8 — Frontend Modules

**Status:** First-pass responsive vanilla-JavaScript interface implemented and locally verified against the current backend APIs. This is not a formal WCAG audit, usability study, production deployment, or claim that deferred APIs are available.  
**Verification date:** 9 November 2026  
**Database migration:** None.  
**Dependency changes:** None.  
**Scope:** Landing/auth/onboarding, dashboard, profile, scan review/results, scan history, settings/privacy, legal/safety information, and honest compare/routine placeholders.

## Delivered

### Same-origin application shell

- FastAPI serves `GET /` and local frontend assets under `/static/`, after the API routes are registered. The app uses vanilla HTML, CSS, and JavaScript ES modules; no frontend build step or third-party CDN is required.
- Browser API requests use relative `/api/v1/...` paths, the same-origin session cookie, and the signed CSRF header. CSRF tokens are held in JavaScript memory only; no session, password, scan, or consent data is placed in `localStorage`.
- Server-provided user, OCR, citation, and model strings are escaped before rendering. The generated explanation remains plain supplemental text; citations link only to server-returned validated source URLs.

### Screens and working controls

- **Landing / about & safety:** explains the review-first scan flow, limitations, privacy controls, optional cloud explanation boundaries, and the absence of a safety score.
- **Account flows:** register, login, email verification/resend, password-reset request/confirmation, and a short optional onboarding step. Local-only verification/reset tokens are shown only when the backend is configured to return its development token.
- **Dashboard / history:** current-user scan count and recent scans, resumable scan states, pagination boundary messaging, and confirmed delete flows for scan history and retained photos.
- **Profile:** display name, optional user-reported skin type/concern notes/locale, and declared ingredient terms with self-reported labels and remove controls.
- **Scanner / results:** JPEG/PNG/WebP selection and drag/drop, upload progress/polling, OCR state and confidence-token preview, editable one-item-per-line ingredient draft, explicit review checkbox, separate save/confirm actions, deterministic analysis, current SQL-validated citations, and optional per-finding Ollama/OpenAI/Groq explanation requests. The UI never auto-splits OCR into ingredient candidates.
- **Settings & privacy:** current provider disclosure/status, explicit separate OpenAI/Groq opt-in and revocation, JSON account export, sign-out, and password-confirmed account deletion.
- **Compare / routines:** route and visual shell are present, but the current backend has no comparison or routine endpoints. The UI states this clearly and does not store fabricated/mock results.

### Responsive and accessibility foundations

- Desktop sidebar and mobile navigation; responsive card/forms/layouts at narrower viewport sizes.
- Semantic headings/landmarks, skip link, visible keyboard focus, labeled inputs, status/live regions, confirmation dialogs with Escape handling and a focus trap, and reduced-motion CSS support.
- No external fonts, scripts, stylesheets, or image dependencies; decorative artwork is CSS/system-font based.

## Verification

- Full backend suite: **78 passed**.
- Ruff format and lint: passed.
- Node syntax checks for `frontend/js/app.js`, `frontend/js/api.js`, and `frontend/js/views.js`: passed.
- Integration tests verify the root shell and same-origin CSS/JS assets are served, API routes remain reachable, and the app does not use `localStorage` for session state.
- No migration, dependency, provider call, or live data corpus was added.

## Not verified / not included

- Formal WCAG 2.2 AA audit, screen-reader/device testing, browser matrix, Windows visual review, user testing, or production performance assessment.
- Comparison and routine persistence/API behavior; product catalog search; frontend administrative tooling.
- Live OCR accuracy, populated evidence/rules, live LLM provider compatibility/quality, or medical/safety performance. In this environment Tesseract is not installed; the interface supports manual ingredient correction when OCR is unavailable.
- Formal legal/terms/privacy counsel review and production deployment/security headers beyond the existing API's current middleware.

M8 is a frontend foundation. Do not present the compare/routine placeholders, empty production corpus, or absence of findings as an available product assessment or proof of safety.
