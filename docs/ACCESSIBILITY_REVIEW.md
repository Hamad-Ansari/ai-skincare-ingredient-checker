# Accessibility review — local browser, contrast, and reflow checks (2026-11-09)

**Disposition:** Source-level improvements, local Playwright/axe runs in Chromium, Firefox, and Playwright WebKit, manual review of the reported contrast targets, and representative narrow-width overflow checks are complete. This is **not** WCAG conformance evidence or accessibility sign-off. Native Safari/iOS device checks, actual browser zoom, assistive-technology, and user testing remain open.

## Source-level checks and fixes

- `frontend/index.html` contains a visible-on-focus skip link and a polite global status region. Workspace pages provide a labelled primary navigation and a programmatically focusable main landmark.
- Forms reviewed in the page templates use explicit labels or accessible names; non-informative decorative symbols are hidden from assistive technology; loading/error and consent states expose status/dialog semantics.
- Keyboard focus indicators and reduced-motion styling are present in `frontend/css/app.css`.
- SPA route changes focus the new page heading and update `document.title`, avoiding focus left on a removed navigation link after a hash-route change.
- Mobile navigation exposes `aria-expanded`, focuses its first link when opened, and restores focus to its toggle when closed by Escape or the scrim.
- Consent/delete dialogs keep keyboard focus inside the dialog, support Escape, and restore focus to their opener when dismissed.
- `frontend/tests/security-smoke.mjs` checks static security/accessibility affordances. `frontend/tests/accessibility-browser.mjs` adds axe scans, keyboard/focus checks, targeted contrast calculations, and narrow-width overflow checks.
- Contrast fixes: the dashboard welcome paragraph changed from `#66766c` (4.07:1 on the darkest gradient stop) to `var(--muted)` `#59665e`; inactive sidebar glyphs changed from `#88958b` to `var(--muted)`.
- Reflow fixes discovered at 320 CSS px: the public header actions now wrap onto their own row on very narrow screens; the one-column `.stack` grid now has an explicit shrinkable track; card-heading content can shrink and long email addresses wrap instead of forcing the settings cards wider than the viewport.

## Local cross-engine smoke

- **Run:** `npm --prefix frontend run test:a11y` with `A11Y_BROWSER` set to `chromium`, `firefox`, or `webkit`. The runner creates a temporary SQLite database, applies migrations, starts a loopback-only test server, creates an ephemeral test account, and removes its temporary database/storage on exit.
- **Versions:** Playwright 1.56.1 and `@axe-core/playwright` 4.11.0 / axe-core 4.11.4. Browsers: Chromium 141.0.7390.37, Firefox 142.0.1, and Playwright WebKit 26.0. Playwright WebKit is not the native Safari application.
- **Axe coverage:** 19 UI states per engine (57 engine/state combinations total), including public/about/auth flows, pre-auth and authenticated workspace screens, scan/history/profile/settings/onboarding/placeholders, route changes, delete-account dialog, and mobile navigation. All three engines reported zero axe violations.
- **Custom checks:** all 19 assertions passed in each engine: five keyboard/focus checks; three contrast checks; and 11 no-horizontal-overflow checks. The 320 CSS-pixel checks covered public landing/about/login, dashboard, scan, settings, and the delete-account dialog. At 640 CSS px, the landing, dashboard, scan, and settings were checked for overflow.
- **Viewport caveat:** 640 CSS px is a narrow-viewport proxy for the layout width commonly seen at 200% zoom on a 1280 CSS-pixel-wide display; it is **not** an actual browser-zoom test. The 320 CSS-pixel checks are reflow-width smoke checks, not a complete WCAG 1.4.10 audit. These width checks measure horizontal overflow; axe scans were run at the test's standard desktop viewport plus the mobile-navigation state.

## Contrast review of axe-incomplete targets

Axe continues to record incomplete `color-contrast` results because it cannot calculate contrast across the gradient/translucent/overlap cases or determine whether isolated glyphs are meaningful. The unique targets in the current reports were reviewed. Text targets pass the calculations below; glyphs are `aria-hidden` decorative marks accompanied by visible link/button text or labels. Incomplete entries are retained as incomplete rather than presented as automated passes.

Ratios use WCAG relative luminance with current CSS colors. For the dashboard gradient, the darkest stop is used as a conservative background; the browser test samples all three stops.

| Target | Foreground / surface | Minimum contrast | Review |
|---|---|---:|---|
| Public landing “Not provided” status | `#426758` on the 94%-opaque `#fffefa` card composited over black (a conservative backing) | 5.50:1 | Pass; actual artwork behind the card is lighter than the black worst case. |
| Dashboard welcome eyebrow | `#426758` on gradient stops `#e8eee6`, `#eff1e8`, `#f2eee2` | 5.37:1 | Pass. |
| Dashboard welcome heading | `#26362f` on the same gradient | 10.78:1 | Pass. |
| Dashboard welcome paragraph | `#59665e` on the same gradient | 5.11:1 | Pass after darkening; the previous `#66766c` was 4.07:1 on the darkest stop. |
| Delete-account dialog paragraph | `#51625a` on opaque `#fffefa` | 6.41:1 | Pass; the backdrop does not show through the modal surface. |
| Sidebar navigation glyphs | Inactive `#59665e` on `#f0f1ea`; active `#426758` on `#e0e9e1` | 5.30:1 / 5.11:1 | Pass; symbols are also `aria-hidden` and adjacent to visible link labels. |
| Other isolated decorative glyphs | Examples: `#426758` on `#e8efea` (5.42:1), `#426758` on `#e4eee4` (5.33:1), and `#fffefa` on `#426758` (6.28:1) | At least 5.33:1 for these checked pairs | Decorative, hidden from assistive technology, and accompanied by descriptive text or accessible control names. |

Reports: `reports/accessibility/chromium-axe.json`, `reports/accessibility/firefox-axe.json`, and `reports/accessibility/webkit-axe.json`.

## CI and remaining sign-off work

- `.github/workflows/backend-ci.yml` now runs a Chromium/Firefox/WebKit matrix and uploads one 30-day axe report artifact per engine. It removes stale local reports before each run. No hosted CI run has been observed; the matrix is configured, not remotely verified.
- Run native Safari and supported mobile-device checks; verify actual 200% browser zoom and reflow, including content not covered by the representative overflow cases.
- Use screen readers (at minimum NVDA with Firefox/Chrome and VoiceOver with Safari) to review landmarks, dynamic route changes, form errors, live updates, dialogs, OCR correction, and analysis results.
- Check target sizes, visible focus, forced-colors/high-contrast modes, reduced motion, and error identification across the UI.
- Conduct keyboard and user testing with people who use assistive technology. Review against WCAG 2.2 AA and record any exceptions and remediation owners.

The automated results are limited to the checked states, Playwright browser builds, and widths. They do not prove WCAG 2.2 AA conformance, cover every dynamic state, or replace native-device, assistive-technology, and user testing.
