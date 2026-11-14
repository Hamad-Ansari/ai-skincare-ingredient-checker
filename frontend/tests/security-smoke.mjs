import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { escapeHTML, renderShell } from "../js/views.js";

const payload = `\"><img src=x onerror=alert(1)>`;
const escaped = escapeHTML(payload);
assert.equal(escaped, "&quot;&gt;&lt;img src=x onerror=alert(1)&gt;");

const shell = renderShell({
  user: { display_name: payload, email: "user@example.invalid" },
  active: "dashboard",
  content: "<p>Trusted application markup</p>",
});
assert.equal(shell.includes(payload), false, "account data must not render as executable markup");
assert.equal(shell.includes(escaped), true, "account data should be HTML-escaped");

const appSource = await readFile(new URL("../js/app.js", import.meta.url), "utf8");
const apiSource = await readFile(new URL("../js/api.js", import.meta.url), "utf8");
const html = await readFile(new URL("../index.html", import.meta.url), "utf8");
const css = await readFile(new URL("../css/app.css", import.meta.url), "utf8");

assert.doesNotMatch(appSource, /localStorage|sessionStorage/, "private state must not use browser storage");
assert.match(apiSource, /credentials:\s*"same-origin"/, "API calls must use same-origin credentials");
assert.match(apiSource, /const API_ROOT = "\/api\/v1"/, "API calls must remain same-origin");
assert.doesNotMatch(html, /https?:\/\//, "HTML must not depend on external origins");
assert.doesNotMatch(css, /@import|https?:\/\//, "CSS must not depend on external origins");
assert.match(html, /class="skip-link" href="#main-content"/, "the document must provide a skip link");
assert.match(shell, /<nav class="primary-nav" aria-label="Primary">/, "workspace navigation must be labelled");
assert.match(shell, /aria-expanded="false"/, "the collapsed mobile navigation state must be exposed");
assert.match(appSource, /function focusMobileNavigation\(open\)/, "mobile navigation changes must manage focus");
assert.match(shell, /<main id="main-content" class="page-content" tabindex="-1">/, "the main region must be programmatically focusable");
assert.match(appSource, /heading\.tabIndex = -1;\s*heading\.focus\(\)/, "route changes must move focus to the page heading");
assert.match(appSource, /restoreModalReturnFocus/, "closing a modal must restore focus");
assert.match(appSource, /dialog\.contains\(document\.activeElement\)/, "the modal tab loop must keep focus inside the dialog");
assert.match(appSource, /aria-modal="true"/, "confirmation dialogs must expose modal semantics");

console.log("Frontend security/accessibility static smoke checks passed.");
