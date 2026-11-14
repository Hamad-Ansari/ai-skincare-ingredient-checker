export function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[character];
  });
}

export function formatDate(value, options = {}) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: options.time ? "short" : undefined,
  }).format(date);
}

function navItem(route, label, symbol, active) {
  const selected = active === route || (route === "scan" && active === "scan");
  return `<a class="nav-link ${selected ? "is-active" : ""}" href="#/${route}" data-route="${route}" ${selected ? 'aria-current="page"' : ""}>
    <span class="nav-symbol" aria-hidden="true">${symbol}</span><span>${label}</span>
  </a>`;
}

export function brandLockup(compact = false) {
  return `<span class="brand-lockup ${compact ? "brand-compact" : ""}">
    <span class="brand-mark" aria-hidden="true">C</span>
    <span class="brand-copy"><strong>clarity</strong><small>SKINCARE, MADE CLEARER</small></span>
  </span>`;
}

export function renderShell({ user, active, content, flash = "", mobileNavOpen = false }) {
  const displayName = user?.display_name || user?.email?.split("@")[0] || "Your space";
  const initials = displayName
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("") || "C";
  const scanActive = active === "scan";
  const nav = [
    navItem("dashboard", "Overview", "⌂", active),
    navItem("scan", "New scan", "+", scanActive ? "scan" : active),
    navItem("history", "Scan history", "◷", active),
    navItem("profile", "My profile", "◎", active),
    navItem("compare", "Compare", "⇄", active),
    navItem("routines", "Routines", "◌", active),
    navItem("settings", "Settings & privacy", "⚙", active),
    navItem("about", "About & safety", "i", active),
  ].join("");
  return `<div class="workspace">
    <aside class="sidebar ${mobileNavOpen ? "sidebar-open" : ""}" id="app-sidebar" aria-label="Workspace navigation">
      <a class="brand-home" href="#/dashboard" data-route="dashboard" aria-label="Clarity Checker overview">${brandLockup()}</a>
      <div class="sidebar-label">YOUR WORKSPACE</div>
      <nav class="primary-nav" aria-label="Primary">${nav}</nav>
      <div class="sidebar-bottom">
        <div class="sidebar-note"><span class="tiny-leaf" aria-hidden="true">✳</span><p>Clear notes, not medical advice.</p></div>
        <button type="button" class="account-chip" data-route="settings">
          <span class="avatar" aria-hidden="true">${escapeHTML(initials)}</span>
          <span class="account-meta"><strong>${escapeHTML(displayName)}</strong><small>${escapeHTML(user?.email || "")}</small></span>
          <span class="account-more" aria-hidden="true">···</span>
        </button>
      </div>
    </aside>
    <div class="main-column">
      <header class="workspace-topbar">
        <button class="icon-button mobile-menu-button" type="button" data-action="toggle-nav" aria-label="Toggle navigation" aria-expanded="${mobileNavOpen}" aria-controls="app-sidebar"><span aria-hidden="true">☰</span></button>
        <a class="mobile-brand" href="#/dashboard" data-route="dashboard">${brandLockup(true)}</a>
        <div class="topbar-right"><span class="quiet-label">Private workspace</span><span class="privacy-dot" aria-hidden="true"></span></div>
      </header>
      ${flash ? `<div class="flash-banner" role="status">${escapeHTML(flash)}</div>` : ""}
      <main id="main-content" class="page-content" tabindex="-1">${content}</main>
      <footer class="app-footer"><span>Clarity Checker</span><span>Educational information · not a safety guarantee</span><a href="#/about" data-route="about">How we handle findings</a></footer>
    </div>
    <div class="nav-scrim ${mobileNavOpen ? "is-visible" : ""}" data-action="close-nav" aria-hidden="true"></div>
    <div id="toast-region" class="toast-region" role="status" aria-live="polite" aria-atomic="true"></div>
  </div>`;
}

export function pageHeading(kicker, title, description = "", actions = "") {
  return `<div class="page-heading"><div><p class="eyebrow">${escapeHTML(kicker)}</p><h1>${escapeHTML(title)}</h1>${description ? `<p class="page-description">${escapeHTML(description)}</p>` : ""}</div>${actions ? `<div class="heading-actions">${actions}</div>` : ""}</div>`;
}

export function statusPill(label, tone = "neutral") {
  return `<span class="status-pill tone-${escapeHTML(tone)}"><span class="status-dot" aria-hidden="true"></span>${escapeHTML(label)}</span>`;
}
