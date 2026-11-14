import {
  ApiError,
  apiJSON,
  apiRequest,
  downloadFile,
  ensureCsrfToken,
  setCsrfToken,
} from "./api.js";
import {
  brandLockup,
  escapeHTML,
  formatDate,
  pageHeading,
  renderShell,
  statusPill,
} from "./views.js";

const root = document.querySelector("#app-root");
const announcer = document.querySelector("#announcer");
const state = {
  user: null,
  route: { view: "home", id: null },
  loading: false,
  pageError: "",
  flash: "",
  mobileNavOpen: false,
  scansResult: null,
  profile: null,
  declarations: [],
  aiConsent: null,
  scan: null,
  analysis: null,
  analysisError: "",
  analysisBusy: false,
  selectedFile: null,
  explanations: {},
  providerChoice: {},
  modal: null,
  modalReturnFocus: null,
  authMessage: "",
  authError: "",
  authEmail: "",
  developmentToken: "",
  newAccount: false,
};

let routeSequence = 0;
let pollSequence = 0;

const AUTH_VIEWS = new Set(["login", "register", "verify", "forgot", "reset"]);
const PROTECTED_VIEWS = new Set([
  "dashboard",
  "scan",
  "history",
  "profile",
  "compare",
  "routines",
  "settings",
  "onboarding",
]);
const SKIN_TYPES = ["dry", "oily", "combination", "normal", "sensitive", "unsure"];
const DECLARATION_TYPES = ["sensitivity", "allergy", "preference", "avoid"];

const WALKTHROUGH_TRANSCRIPTS = {
  en: [
    "Welcome to Clarity Checker. This is a pre-launch walkthrough: the production ingredient and evidence library is empty, and OCR is not enabled in the current app image. This video explains the workflow, not live product results.",
    "Create an account with a unique password of at least twelve characters, verify your email, then sign in. The optional profile is for your own notes. It is not a diagnosis and is not sent to explanation providers.",
    "Choose a clear J P E G, P N G, or WebP label photo up to ten megabytes. In this build, type ingredients manually, one per line, and compare every spelling with the package. Never confirm text you have not checked.",
    "Save a draft if you want to return later. To analyze, confirm the non-empty list you reviewed, then select Analyze confirmed list. Matching is exact; unknown or ambiguous names stay unresolved. No finding is not proof of safety.",
    "Explanations are optional. OpenAI and Groq need separate consent and can explain one finding, but never change results. History lets you reopen or delete scans. Settings offers export, account deletion, and consent controls. This is educational information, not medical advice.",
  ],
  ur: [
    "کلیئرٹی چیکر میں خوش آمدید۔ یہ اجرا سے پہلے کی رہنمائی ویڈیو ہے۔ موجودہ ایپ میں حقیقی اجزاء اور شواہد کا ڈیٹا خالی ہے، اور اس ورژن میں تصویر سے متن پڑھنے کی سہولت فعال نہیں۔ یہ ویڈیو طریقۂ استعمال سمجھاتی ہے، نتائج نہیں۔",
    "اکاؤنٹ بنائیں، کم از کم بارہ حروف کا منفرد پاس ورڈ رکھیں، ای میل کی تصدیق کریں اور پھر سائن اِن کریں۔ اختیاری پروفائل صرف آپ کے ذاتی نوٹس کے لیے ہے۔ یہ تشخیص نہیں اور وضاحت فراہم کرنے والے اے آئی نظاموں کو نہیں بھیجا جاتا۔",
    "اجزاء کے لیبل کی صاف تصویر منتخب کریں، جے پی ای جی، پی این جی یا ویب پی فارمیٹ میں، اور دس میگا بائٹ سے کم رکھیں۔ اس ورژن میں اجزاء ایک ایک سطر میں خود لکھیں اور ہر ہجے پیکج سے ملائیں۔ جس متن کو خود نہ پڑھا ہو، اس کی تصدیق نہ کریں۔",
    "اگر بعد میں واپس آنا ہو تو مسودہ محفوظ کریں۔ تجزیے کے لیے اپنی خالی نہ ہونے والی فہرست کی تصدیق کریں، پھر تصدیق شدہ فہرست کا تجزیہ منتخب کریں۔ نام کا بالکل درست ملنا ضروری ہے۔ نام نہ ملے یا مبہم ہو تو کوئی اندازہ نہیں لگایا جاتا۔ نتیجہ نہ آنا حفاظت کا ثبوت نہیں۔",
    "وضاحت لینا اختیاری ہے۔ اوپن اے آئی اور گروک کے لیے الگ اجازت درکار ہے۔ وضاحت صرف ایک نتیجے کے بارے میں ہوتی ہے اور اصل نتیجہ نہیں بدلتی۔ ہسٹری میں اسکین دوبارہ کھولیں یا حذف کریں۔ سیٹنگز سے ڈیٹا برآمد، اکاؤنٹ حذف اور اجازتیں منظم کریں۔ یہ معلوماتی ٹول ہے، طبی مشورہ نہیں۔",
  ],
};

function routeFromHash() {
  const path = window.location.hash.replace(/^#\/?/, "");
  if (!path) return { view: "home", id: null };
  const [view = "home", rawId = ""] = path.split("/");
  let id = null;
  try {
    id = rawId ? decodeURIComponent(rawId) : null;
  } catch {
    id = null;
  }
  return { view, id };
}

function go(view, id = null) {
  const hash = `#/${view}${id ? `/${encodeURIComponent(id)}` : ""}`;
  state.mobileNavOpen = false;
  if (window.location.hash === hash) {
    void loadRoute();
  } else {
    window.location.hash = hash;
  }
}

function toast(message, kind = "success") {
  const region = document.querySelector("#toast-region");
  if (!region) return;
  const item = document.createElement("div");
  item.className = `toast ${kind === "error" ? "error" : ""}`;
  item.textContent = message;
  region.replaceChildren(item);
  if (announcer) announcer.textContent = message;
  window.setTimeout(() => {
    if (item.isConnected) item.remove();
  }, 4500);
}

function setFormFeedback(form, message, kind = "error") {
  const output = form?.querySelector("[data-form-message]");
  if (!output) {
    toast(message, kind === "error" ? "error" : "success");
    return;
  }
  output.textContent = message;
  output.className = kind === "error" ? "form-error" : "form-success";
  output.setAttribute("role", kind === "error" ? "alert" : "status");
}

function focusPageContent() {
  const main = root?.querySelector("#main-content");
  const heading = main?.querySelector("h1, h2");
  if (heading) {
    heading.tabIndex = -1;
    heading.focus();
    document.title = `${heading.textContent.trim()} — Clarity Checker`;
  } else {
    main?.focus();
    document.title = "Clarity Checker";
  }
}

function focusMobileNavigation(open) {
  window.setTimeout(() => {
    const selector = open ? "#app-sidebar .primary-nav a" : ".mobile-menu-button";
    root?.querySelector(selector)?.focus();
  }, 0);
}

function captureModalReturnFocus(element) {
  if (!element) return;
  state.modalReturnFocus = {
    action: element.dataset.action || "",
    id: element.dataset.id || "",
  };
}

function restoreModalReturnFocus(target = state.modalReturnFocus) {
  state.modalReturnFocus = null;
  window.setTimeout(() => {
    const candidate = target
      ? [...(root?.querySelectorAll("[data-action]") || [])].find(
          (element) => element.dataset.action === target.action && (element.dataset.id || "") === target.id,
        )
      : null;
    if (candidate) candidate.focus();
    else focusPageContent();
  }, 0);
}

function pageErrorCard() {
  return state.pageError
    ? `<div class="notice warning" role="alert"><strong>We couldn't load this view.</strong>${escapeHTML(state.pageError)}<div class="form-actions"><button class="button button-secondary button-small" type="button" data-action="retry-load">Try again</button></div></div>`
    : "";
}

function publicHeader() {
  return `<header class="public-header"><a href="#/" class="brand-home" aria-label="Clarity Checker home">${brandLockup()}</a><nav class="public-actions" aria-label="Account"><a class="button button-quiet" href="#/about">How it works</a><a class="button button-secondary" href="#/login">Sign in</a><a class="button button-primary" href="#/register">Create account</a></nav></header>`;
}

function publicFooter() {
  return `<footer class="public-footer"><span>© Clarity Checker · Educational information, not medical advice.</span><a href="#/about">About &amp; safety</a></footer><div id="toast-region" class="toast-region" role="status" aria-live="polite" aria-atomic="true"></div>`;
}

function renderWalkthroughCard(language) {
  const isUrdu = language === "ur";
  const otherLanguage = isUrdu ? "en" : "ur";
  const audioLabel = isUrdu ? "Urdu narration" : "English narration";
  const titleId = `walkthrough-${language}-title`;
  const descriptionId = `walkthrough-${language}-description`;
  const videoPath = `/static/assets/clarity-walkthrough-${language}.mp4`;
  const webmPath = `/static/assets/clarity-walkthrough-${language}.webm`;
  const posterPath = `/static/assets/clarity-walkthrough-poster${isUrdu ? "-ur" : ""}.jpg`;
  const transcriptPath = `/static/assets/clarity-walkthrough-transcript-${language}.txt`;
  const primaryCaptionPath = `/static/assets/clarity-walkthrough-${language}.vtt`;
  const translatedCaptionPath = `/static/assets/clarity-walkthrough-${language}-${otherLanguage}.vtt`;
  const transcript = WALKTHROUGH_TRANSCRIPTS[language]
    .map((paragraph) => `<p>${escapeHTML(paragraph)}</p>`)
    .join("");

  return `<article class="walkthrough-card" aria-labelledby="${titleId}">
    <div class="walkthrough-card-heading"><div><p class="eyebrow">${isUrdu ? "اردو آواز" : "ENGLISH AUDIO"}</p><h3 id="${titleId}">${audioLabel}</h3></div><span class="walkthrough-duration">Masculine voice · ${isUrdu ? "1 min 52 sec" : "1 min 22 sec"}</span></div>
    <figure class="walkthrough-figure">
      <video class="walkthrough-video" controls playsinline preload="metadata" poster="${posterPath}" aria-labelledby="${titleId}" aria-describedby="${descriptionId}">
        <source src="${videoPath}" type="video/mp4" />
        <source src="${webmPath}" type="video/webm" />
        <track kind="captions" src="${primaryCaptionPath}" srclang="${language}" label="${isUrdu ? "Urdu" : "English"} captions" default />
        <track kind="captions" src="${translatedCaptionPath}" srclang="${otherLanguage}" label="${isUrdu ? "English" : "Urdu"} captions" />
        <p>Your browser cannot play this video. <a href="${videoPath}" download>Download MP4</a> or <a href="${webmPath}" download>download WebM</a>.</p>
      </video>
      <figcaption id="${descriptionId}" class="walkthrough-caption">Choose captions with the CC menu. The secondary track is a translated caption track.</figcaption>
    </figure>
    <details class="walkthrough-transcript"><summary>Read the ${isUrdu ? "Urdu" : "English"} transcript</summary><div class="walkthrough-transcript-copy" lang="${language}" ${isUrdu ? 'dir="rtl"' : ""}>${transcript}</div></details>
    <nav class="walkthrough-downloads" aria-label="${audioLabel} video, transcript and captions">
      <a href="${videoPath}" download>Download MP4</a>
      <a href="${webmPath}" download>Download WebM</a>
      <a href="${transcriptPath}" download>Download transcript</a>
      <a href="${primaryCaptionPath}" download>Download ${isUrdu ? "Urdu" : "English"} captions</a>
      <a href="${translatedCaptionPath}" download>Download ${isUrdu ? "English" : "Urdu"} captions</a>
    </nav>
  </article>`;
}

function renderWalkthroughSection() {
  return `<section class="walkthrough-section" id="walkthrough" aria-labelledby="walkthrough-heading">
    <div class="walkthrough-intro"><p class="eyebrow">BILINGUAL WALKTHROUGH</p><h2 id="walkthrough-heading">See how the current app works.</h2><p>Choose English or Urdu narration, then use the video’s CC menu to select either language’s captions. Full transcripts are available below each video.</p></div>
    <div class="walkthrough-status" role="note"><span class="walkthrough-status-mark" aria-hidden="true">i</span><p><strong>Pre-launch prototype, not live product coverage.</strong> The production ingredient and evidence corpus is empty, OCR is unavailable in the current app image, and Compare/Routines are not connected yet. The application interface is English; Urdu is provided for this walkthrough. Screens shown are illustrative.</p></div>
    <p class="walkthrough-provider-note"><strong>Optional explanation providers, if configured:</strong> Ollama uses an operator-managed local endpoint; OpenAI and Groq are cloud providers and require separate consent. Explanations can only supplement an existing finding and cannot change it.</p>
    <div class="walkthrough-grid">${renderWalkthroughCard("en")}${renderWalkthroughCard("ur")}</div>
  </section>`;
}

function renderLanding() {
  return `<div class="public-page">
    ${publicHeader()}
    ${state.authMessage ? `<div class="flash-banner" role="status">${escapeHTML(state.authMessage)}</div>` : ""}
    <main id="main-content" class="public-main" tabindex="-1">
      <section class="landing-hero">
        <div class="landing-copy">
          <p class="eyebrow">A little more clarity, one label at a time</p>
          <h1>Skincare, <em>made clearer.</em></h1>
          <p class="lead">Explore the label-review workflow. Ingredient text is entered manually in this pre-launch build; production ingredient and evidence data is not yet available.</p>
          <div class="button-row"><a class="button button-primary" href="#/register">Create your private space <span aria-hidden="true">↗</span></a><a class="button button-secondary" href="#/about">Explore how it works</a></div>
          <div class="landing-footnote"><span class="tiny-leaf" aria-hidden="true">✳</span><span>Every scan starts with your review. A missing finding is not proof that a product is safe.</span></div>
        </div>
        <div class="hero-art" aria-hidden="true">
          <div class="hero-orbit"></div><div class="hero-sun"></div><div class="hero-leaf"></div><div class="hero-leaf leaf-two"></div>
          <div class="hero-card"><div class="hero-card-top"><div><div class="hero-card-label">Illustrative scan flow</div><h3>Your ingredient list</h3></div><span class="status-pill tone-neutral"><span class="status-dot"></span>Review first</span></div>
            <div class="hero-card-line"><span>Production data</span><span>Not populated</span></div><div class="hero-card-line"><span>Current image</span><span>Manual entry</span></div><div class="hero-card-line"><span>Safety score</span><span>Not provided</span></div>
            <div class="hero-card-note">Findings are limited to reviewed rules and sources. They are not a personal safety verdict.</div>
          </div>
        </div>
      </section>
      ${renderWalkthroughSection()}
      <section class="landing-principles" aria-label="How Clarity Checker works">
        <article class="principle"><span class="principle-number">01 / Review</span><h2>You stay in control</h2><p>Ingredient entry is manual in this build. Review every line and confirm only what you have checked.</p></article>
        <article class="principle"><span class="principle-number">02 / Trace</span><h2>Evidence matters</h2><p>When reviewed data is configured, deterministic findings can link to their supporting sources.</p></article>
        <article class="principle"><span class="principle-number">03 / Understand</span><h2>Know the limits</h2><p>No score, diagnosis, or guarantee. Explanations are optional and never change findings.</p></article>
      </section>
      <section class="landing-safety"><span class="tiny-leaf" aria-hidden="true">✳</span><div><strong>Information for understanding—not a verdict.</strong><p>Clarity Checker is an educational ingredient-reference tool. It cannot assess your individual health or guarantee compatibility. Review the <a href="#/about">About &amp; safety</a> notes before you begin.</p></div></section>
    </main>
    ${publicFooter()}
  </div>`;
}

function renderPublicAbout() {
  return `<div class="public-page">${publicHeader()}<main id="main-content" class="public-main" tabindex="-1">
    <section class="policy-copy" style="max-width:860px;padding:42px 3% 70px">
      <p class="eyebrow">Our approach</p><h1 style="font:500 clamp(2.7rem,7vw,4.6rem)/1.03 Georgia,serif;letter-spacing:-.04em;margin:0">Useful context, without false certainty.</h1>
      <p style="max-width:700px;color:var(--muted);font-size:1.05rem;line-height:1.7">Clarity Checker helps people review cosmetic ingredient labels and inspect source-linked educational notes. It does not determine whether a product is safe for you.</p>
      ${renderWalkthroughSection()}
      <h2>How a scan works</h2><ol><li>Upload a label image. The backend validates and stores a private, metadata-stripped copy.</li><li>In the current image, OCR is unavailable, so you enter and review ingredient text manually. In a build with OCR enabled, its output remains unconfirmed until you check it.</li><li>Rules are deterministic and versioned. Citations come from current, reviewed database records; if evidence or rule state changes, the analysis can become stale.</li></ol>
      <h2>Optional explanations</h2><p>You may request a short explanation of one current finding. It cannot add, remove, change, or cite a warning. OpenAI and Groq require current, provider-specific consent. Only one confirmed ingredient, its finding, and currently approved evidence text may be sent. Source URLs, images, email, full scans, and profile/skin data are excluded. Generated text is not stored and may be incomplete or inaccurate.</p>
      <h2>Important limits</h2><p>No finding is not evidence of safety. OCR can make mistakes; ingredient names can be ambiguous; the configured rule set and evidence corpus may be incomplete. This service does not diagnose, prescribe, or replace professional medical advice.</p>
      <h2>Privacy controls</h2><p>Scans are scoped to your account. You can review scan history, delete individual scans and retained photos, export account data, and revoke provider-specific cloud consent. Uploaded photos remain private until deletion.</p>
      <section class="creator-card" aria-labelledby="creator-heading"><p class="eyebrow">ABOUT THE CREATOR</p><h2 id="creator-heading">Hi, I’m Hammad Zahid.</h2><p>I’m building Clarity Checker to make skincare ingredient labels easier to review, with source-linked educational notes and clear limits. The project is designed to support careful human review—not provide a personal safety verdict.</p><nav class="social-links" aria-label="Hammad Zahid on social media"><a class="social-link" href="https://www.facebook.com/hammad.zahid.9484" target="_blank" rel="me noopener noreferrer">Facebook <span aria-hidden="true">↗</span></a><a class="social-link" href="https://www.linkedin.com/in/hammad-zahid-xyz/" target="_blank" rel="me noopener noreferrer">LinkedIn <span aria-hidden="true">↗</span></a><a class="social-link" href="https://github.com/Hamad-Ansari" target="_blank" rel="me noopener noreferrer">GitHub <span aria-hidden="true">↗</span></a></nav></section>
      <div class="notice warning"><strong>Current prototype scope</strong><p>The production ingredient and evidence corpus is empty. Compare and routine features are not available yet. No live provider quality or clinical safety evaluation is claimed.</p></div>
      <div class="form-actions"><a class="button button-primary" href="#/register">Create an account</a><a class="button button-quiet" href="#/">Back home</a></div>
    </section>
  </main>${publicFooter()}</div>`;
}

function authStatus() {
  const message = state.authMessage
    ? `<div class="notice info" role="status">${escapeHTML(state.authMessage)}${state.developmentToken ? `<p><strong>Development-only token:</strong> <code>${escapeHTML(state.developmentToken)}</code></p>` : ""}</div>`
    : "";
  const error = state.authError ? `<p class="form-error" role="alert">${escapeHTML(state.authError)}</p>` : "";
  return `${message}${error}`;
}

function renderAuthPage(view) {
  const titles = {
    login: ["Welcome back", "Sign in to your private workspace."],
    register: ["Start with clarity", "Create a private account to save and review your scans."],
    verify: ["Verify your email", "Use the one-time token from your email, or request it again."],
    forgot: ["Reset your password", "We'll send instructions if an account matches that address."],
    reset: ["Choose a new password", "Use the one-time reset token you received."],
  };
  const [title, subtitle] = titles[view] || titles.login;
  let form = "";
  if (view === "login") {
    form = `<form data-form="login">
      <div class="field"><label for="login-email">Email address</label><input id="login-email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escapeHTML(state.authEmail)}" /></div>
      <div class="field"><label for="login-password">Password</label><input id="login-password" name="password" type="password" autocomplete="current-password" required minlength="1" maxlength="128" /></div>
      <div data-form-message aria-live="polite"></div><button class="button button-primary" type="submit" style="width:100%;margin-top:20px">Sign in</button>
    </form><div class="auth-links"><a href="#/forgot">Forgot password?</a><a href="#/verify">Need a verification token?</a></div>`;
  } else if (view === "register") {
    form = `<form data-form="register">
      <div class="field"><label for="register-email">Email address</label><input id="register-email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escapeHTML(state.authEmail)}" /></div>
      <div class="field"><label for="register-password">Create a password</label><input id="register-password" name="password" type="password" autocomplete="new-password" required minlength="12" maxlength="128" aria-describedby="password-help" /><small class="field-help" id="password-help">Use at least 12 characters. Keep it private and unique.</small></div>
      <div data-form-message aria-live="polite"></div><button class="button button-primary" type="submit" style="width:100%;margin-top:20px">Create account</button>
      <p class="field-help" style="margin-top:14px">By creating an account, you understand this is an educational tool, not a medical service.</p>
    </form><div class="auth-links"><a href="#/login">Already have an account? Sign in</a></div>`;
  } else if (view === "verify") {
    form = `<form data-form="verify-email">
      <div class="field"><label for="verify-token">One-time verification token</label><input id="verify-token" name="token" type="text" autocomplete="one-time-code" required minlength="20" maxlength="200" value="${escapeHTML(state.developmentToken)}" /><small class="field-help">Tokens are single-use. In local development only, the API may return a test token.</small></div>
      <div data-form-message aria-live="polite"></div><button class="button button-primary" type="submit" style="width:100%;margin-top:18px">Verify email</button>
    </form>
    <hr class="card-divider" /><form data-form="request-verification"><div class="field"><label for="verification-email">Request another token</label><input id="verification-email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escapeHTML(state.authEmail)}" /></div><div data-form-message aria-live="polite"></div><button class="button button-secondary" type="submit" style="margin-top:14px">Send instructions</button></form>
    <div class="auth-links"><a href="#/login">Back to sign in</a></div>`;
  } else if (view === "forgot") {
    form = `<form data-form="request-reset"><div class="field"><label for="reset-email">Email address</label><input id="reset-email" name="email" type="email" autocomplete="email" required maxlength="254" value="${escapeHTML(state.authEmail)}" /></div><div data-form-message aria-live="polite"></div><button class="button button-primary" type="submit" style="width:100%;margin-top:18px">Request reset instructions</button></form><div class="auth-links"><a href="#/reset">I already have a reset token</a><a href="#/login">Back to sign in</a></div>`;
  } else {
    form = `<form data-form="confirm-reset"><div class="field"><label for="reset-token">One-time reset token</label><input id="reset-token" name="token" type="text" autocomplete="one-time-code" required minlength="20" maxlength="200" value="${escapeHTML(state.developmentToken)}" /></div><div class="field"><label for="new-password">New password</label><input id="new-password" name="new_password" type="password" autocomplete="new-password" required minlength="12" maxlength="128" /></div><div data-form-message aria-live="polite"></div><button class="button button-primary" type="submit" style="width:100%;margin-top:18px">Update password</button></form><div class="auth-links"><a href="#/forgot">Request a token</a><a href="#/login">Back to sign in</a></div>`;
  }
  return `<div class="public-page">${publicHeader()}<main id="main-content" class="public-main" tabindex="-1"><section class="auth-layout"><div class="auth-aside"><a href="#/" aria-label="Clarity Checker home">${brandLockup()}</a><p class="eyebrow" style="margin-top:54px">YOUR LABEL, YOUR REVIEW</p><h1>${escapeHTML(title)}.</h1><p>Ingredient notes should come with context, clear limits, and the room to make your own decisions.</p><a class="text-button" href="#/about">Read about our approach →</a></div><section class="auth-card" aria-labelledby="auth-title"><h2 id="auth-title">${escapeHTML(title)}</h2><p>${escapeHTML(subtitle)}</p>${authStatus()}${form}</section></section></main>${publicFooter()}</div>`;
}

function scanStatus(scan) {
  const labels = {
    queued: ["Queued", "neutral"],
    extracting: ["Reading label", "blue"],
    needs_confirmation: ["Review needed", "caution"],
    confirmed: ["Confirmed", "good"],
    failed: ["Needs attention", "alert"],
  };
  const [label, tone] = labels[scan?.status] || ["Unknown", "neutral"];
  return { label, tone };
}

function statusTag(scan) {
  const { label, tone } = scanStatus(scan);
  return statusPill(label, tone);
}

function scanName(scan) {
  return `Label scan · ${formatDate(scan?.created_at)}`;
}

function scanRow(scan, options = {}) {
  const id = escapeHTML(scan.id);
  return `<div class="scan-row">
    <div class="scan-row-title"><strong>${escapeHTML(scanName(scan))}</strong><small>${escapeHTML(scan.ocr_status === "unavailable" ? "OCR unavailable · manual entry is possible" : `Updated ${formatDate(scan.updated_at, { time: true })}`)}${scan.photo_available ? " · private photo retained" : ""}</small></div>
    ${statusTag(scan)}
    <div class="scan-row-actions"><button class="button button-secondary button-small" type="button" data-action="resume-scan" data-id="${id}">${options.history ? "Open" : "Review"}</button>${options.history ? `<button class="button button-quiet button-small" type="button" data-action="open-delete-scan" data-id="${id}">Delete</button>` : ""}</div>
  </div>`;
}

function renderDashboard() {
  const results = state.scansResult;
  const items = results?.items || [];
  const latest = items[0];
  const confirmed = items.filter((item) => item.status === "confirmed").length;
  const loading = state.loading && !results;
  const recent = items.slice(0, 5).map((item) => scanRow(item)).join("");
  const actions = `<button class="button button-primary" type="button" data-route="scan">＋ New scan</button>`;
  return `${pageHeading("YOUR OVERVIEW", "A calmer way to review.", "Your ingredient scans and source-linked notes, all in one private place.", actions)}${pageErrorCard()}
    <section class="welcome-panel"><div><p class="eyebrow">WELCOME TO YOUR SPACE</p><h2>${escapeHTML(state.user?.display_name || "A little more clarity")}</h2><p>Start with a label photo, then take a moment to review the ingredient list before analysis.</p></div><div class="welcome-actions"><button class="button button-primary" type="button" data-route="scan">Scan a label <span aria-hidden="true">↗</span></button></div></section>
    <section class="metric-grid" aria-label="Scan summary"><article class="metric-card"><div class="metric-top"><span>Total scans</span><span class="metric-icon" aria-hidden="true">◷</span></div><strong class="metric-value">${loading ? "—" : escapeHTML(results?.total ?? 0)}</strong><small class="metric-note">Saved to your private history</small></article><article class="metric-card"><div class="metric-top"><span>Confirmed in recent scans</span><span class="metric-icon" aria-hidden="true">✓</span></div><strong class="metric-value">${loading ? "—" : escapeHTML(confirmed)}</strong><small class="metric-note">Among the newest scans loaded</small></article><article class="metric-card"><div class="metric-top"><span>Most recent</span><span class="metric-icon" aria-hidden="true">⌁</span></div><strong class="metric-value" style="font-size:1.1rem;margin-top:20px">${loading ? "Loading…" : latest ? escapeHTML(formatDate(latest.created_at)) : "Not yet"}</strong><small class="metric-note">${latest ? escapeHTML(scanStatus(latest).label) : "Your first scan can start here"}</small></article></section>
    <section class="card"><div class="card-heading"><div><h2>Recent scans</h2><p>Review a draft or return to a confirmed analysis.</p></div><a class="button button-quiet button-small" href="#/history">View history →</a></div>
      ${loading ? `<div class="empty-state" style="margin-top:18px"><div class="spinner" aria-label="Loading"></div><p style="margin-top:12px">Loading your scans…</p></div>` : recent ? `<div class="scan-list">${recent}</div>` : `<div class="empty-state" style="margin-top:18px"><div class="empty-mark" aria-hidden="true">＋</div><h3>Your first scan starts here</h3><p>Upload a label image and review the ingredient draft before analysis. The production evidence set is still being built.</p><button class="button button-primary" type="button" data-route="scan">Start a scan</button></div>`}
    </section>
    <div class="notice" style="margin-top:18px"><strong>A note about findings</strong>Configured findings are educational and limited to reviewed rules. No finding is not proof of safety; there is no product safety score.</div>`;
}

function renderUploadPage() {
  return `${pageHeading("NEW SCAN", "Start with the label.", "Upload a clear photo, then enter the ingredient text manually. OCR is unavailable in this app image.")}${pageErrorCard()}
    <div class="grid-2"><section class="card"><form data-form="upload">
      <div class="upload-zone" id="upload-zone"><div><span class="upload-icon" aria-hidden="true">↥</span><h2>Choose a label photo</h2><p>JPEG, PNG, or WebP · maximum 10 MB</p><input class="sr-only" id="scan-file" name="image" type="file" accept="image/jpeg,image/png,image/webp" aria-label="Choose a skincare label photo" /><button class="button button-secondary" type="button" data-action="pick-file">Browse files</button><div id="selected-file" class="file-summary" hidden><span class="metric-icon" aria-hidden="true">▧</span><div><strong id="selected-file-name"></strong><small id="selected-file-size"></small></div></div></div></div>
      <div data-form-message aria-live="polite"></div><div class="form-actions"><button class="button button-primary" type="submit">Upload label photo <span aria-hidden="true">→</span></button></div>
      <p class="field-help" style="margin-top:13px">Your image is validated and stored privately. It is not sent to a cloud LLM.</p>
    </form></section><section class="card"><div class="card-heading"><div><p class="eyebrow">THREE SIMPLE STEPS</p><h2>Review before you rely.</h2></div></div><div class="step-list"><div class="step-item"><span class="step-number">1</span><div><h3>Enter the label text</h3><p>OCR is unavailable in the current app image. Type the ingredients manually.</p></div></div><div class="step-item"><span class="step-number">2</span><div><h3>Check each item</h3><p>Compare spelling with the package and enter one ingredient per line.</p></div></div><div class="step-item"><span class="step-number">3</span><div><h3>Confirm, then analyze</h3><p>Only the non-empty list you explicitly confirm reaches analysis.</p></div></div></div></section></div>
    <div class="notice warning" style="margin-top:18px"><strong>Not a safety verdict</strong>Results reflect only the configured rule set and current evidence. A missing finding does not mean a product is safe for you.</div>`;
}

function renderTokenChips(tokens = []) {
  const visible = tokens.slice(0, 36);
  if (!visible.length) return "";
  return `<div class="token-list" aria-label="Sample OCR words">${visible.map((token) => `<span class="token-chip">${escapeHTML(token.text)}${token.confidence !== null && token.confidence !== undefined ? `<small>${escapeHTML(Math.round(token.confidence))}%</small>` : ""}</span>`).join("")}${tokens.length > visible.length ? `<span class="token-chip">+${tokens.length - visible.length} more</span>` : ""}</div>`;
}

function renderCitation(citation) {
  const source = citation.source || {};
  const rawUrl = source.canonical_url || "";
  let safeLink = "";
  try {
    const parsed = new URL(rawUrl);
    if (["https:", "http:"].includes(parsed.protocol) && !parsed.username && !parsed.password) {
      safeLink = `<a href="${escapeHTML(parsed.href)}" target="_blank" rel="noopener noreferrer">${escapeHTML(source.title || "View source")} ↗</a>`;
    }
  } catch {
    safeLink = "";
  }
  return `<article class="citation"><p>${escapeHTML(citation.summary || "")}</p>${citation.excerpt ? `<p style="margin-top:8px"><strong>Permitted excerpt:</strong> “${escapeHTML(citation.excerpt)}”</p>` : ""}${safeLink}<small>${escapeHTML(source.publisher || "Source")}${source.license_name ? ` · ${escapeHTML(source.license_name)}` : ""}${citation.locator ? ` · ${escapeHTML(citation.locator)}` : ""}</small></article>`;
}

function renderFinding(finding) {
  const explanation = state.explanations[finding.id];
  const selectedProvider = state.providerChoice[finding.id] || "ollama";
  const severityTone = finding.severity === "caution" ? "alert" : finding.severity === "notice" ? "caution" : "blue";
  const explanationHtml = explanation?.loading
    ? `<div class="explanation-panel"><div class="scan-progress"><span class="spinner" aria-hidden="true"></span><span>Preparing your supplemental explanation…</span></div></div>`
    : explanation?.data
      ? `<div class="explanation-panel"><div class="pill-row">${statusPill(explanation.data.status === "generated" ? "Supplemental explanation" : "Deterministic fallback", explanation.data.status === "generated" ? "blue" : "neutral")}</div><p>${escapeHTML(explanation.data.explanation)}</p><small class="field-help">${escapeHTML(explanation.data.notice)} ${escapeHTML(explanation.data.disclaimer)}</small></div>`
      : explanation?.error
        ? `<div class="notice warning" style="margin-top:14px">${escapeHTML(explanation.error)}</div>`
        : "";
  return `<article class="finding-card"><div class="finding-top"><div><span class="status-pill tone-${severityTone}"><span class="status-dot"></span>${escapeHTML(finding.severity)}</span><h3 class="finding-title">${escapeHTML(finding.title)}</h3><p class="finding-message"><strong>${escapeHTML(finding.ingredient_name)}:</strong> ${escapeHTML(finding.message)}</p></div><span class="quiet-label">Rule ${escapeHTML(finding.rule_version)}</span></div>
    <div class="citation-list">${(finding.citations || []).map(renderCitation).join("")}</div>
    <div class="form-actions" style="margin-top:16px"><label class="sr-only" for="provider-${escapeHTML(finding.id)}">Choose an explanation provider</label><select id="provider-${escapeHTML(finding.id)}" data-provider-for="${escapeHTML(finding.id)}" aria-label="Choose an explanation provider"><option value="ollama" ${selectedProvider === "ollama" ? "selected" : ""}>Ollama · local</option><option value="openai" ${selectedProvider === "openai" ? "selected" : ""}>OpenAI · cloud consent</option><option value="groq" ${selectedProvider === "groq" ? "selected" : ""}>Groq · cloud consent</option></select><button class="button button-secondary button-small" type="button" data-action="explain-finding" data-id="${escapeHTML(finding.id)}" ${explanation?.loading ? "disabled" : ""}>Explain this finding</button></div>${explanationHtml}
  </article>`;
}

function renderAnalysis(analysis) {
  if (!analysis) return "";
  const statusText = {
    completed: "Analysis complete",
    no_active_rules: "No active rules",
    needs_review: "Review needed",
    stale: "Analysis needs an update",
  }[analysis.status] || "Analysis status";
  const tone = analysis.status === "stale" ? "caution" : analysis.status === "completed" ? "good" : "neutral";
  const findings = (analysis.findings || []).map(renderFinding).join("");
  const emptyTitle = analysis.status === "stale"
    ? "Rerun to see current results"
    : analysis.status === "needs_review"
      ? "Review the unresolved names"
      : analysis.status === "no_active_rules"
        ? "No active rules to check"
        : "No configured findings";
  const emptyText = analysis.status === "stale"
    ? "Current source, rule, or catalog state has changed. The prior findings are withheld until you rerun."
    : analysis.status === "needs_review"
      ? "One or more ingredient names could not be resolved exactly. No guessed finding was added."
      : "This is not evidence that the product is safe. Results are limited to the reviewed rules currently available.";
  const ingredientRows = (analysis.ingredients || []).map((item) => {
    const result = item.resolution || {};
    const label = result.status || "unresolved";
    const pillTone = label === "resolved" ? "good" : label === "ambiguous" ? "caution" : "neutral";
    const canonicalName = result.ingredient?.name;
    return `<li><strong>${escapeHTML(item.input_text)}</strong><span>${statusPill(label, pillTone)}${canonicalName ? ` <small>${escapeHTML(canonicalName)}</small>` : ""}</span></li>`;
  }).join("");
  return `<section class="card stack" style="margin-top:20px"><div class="card-heading"><div><p class="eyebrow">DETERMINISTIC ANALYSIS</p><h2>Your reviewed results</h2></div>${statusPill(statusText, tone)}</div>
    <div class="analysis-summary"><p>${escapeHTML(analysis.notice || "")} ${escapeHTML(analysis.disclaimer || "")}</p>${analysis.status === "stale" ? `<button class="button button-primary button-small" type="button" data-action="run-analysis">Refresh analysis</button>` : ""}</div>
    ${analysis.unresolved_count ? `<div class="notice info"><strong>${escapeHTML(analysis.unresolved_count)} ingredient${analysis.unresolved_count === 1 ? "" : "s"} need more information</strong>Unresolved or ambiguous names do not trigger guessed findings.</div>` : ""}
    ${findings ? `<div class="finding-list">${findings}</div>` : `<div class="empty-state"><div class="empty-mark" aria-hidden="true">${analysis.status === "stale" ? "↻" : "○"}</div><h3>${escapeHTML(emptyTitle)}</h3><p>${escapeHTML(emptyText)}</p>${analysis.status === "stale" ? `<button class="button button-primary" type="button" data-action="run-analysis">Run analysis again</button>` : ""}</div>`}
    <details><summary class="text-button">Show how each ingredient resolved</summary><ul class="resolution-list">${ingredientRows}</ul></details>
  </section>`;
}

function renderScanDetail() {
  const scan = state.scan;
  if (state.loading && !scan) {
    return `${pageHeading("SCAN REVIEW", "Loading scan…", "Retrieving your private scan state.")}${loadingCard()}`;
  }
  if (!scan) {
    return `${pageHeading("SCAN REVIEW", "Scan not available", "This scan may have been deleted or is not available to this account.")}${pageErrorCard()}<button class="button button-primary" type="button" data-route="history">Back to history</button>`;
  }
  const { label, tone } = scanStatus(scan);
  const OCR_LABELS = { queued: "Queued", running: "Reading", succeeded: "Text available", unavailable: "OCR unavailable", failed: "OCR needs attention" };
  const ocrLabel = OCR_LABELS[scan.ocr_status] || scan.ocr_status;
  const ocrNotice = scan.ocr_status === "unavailable"
    ? `<div class="notice warning"><strong>Text recognition isn't available here.</strong>You can still enter the ingredient list manually. OCR unavailability does not prevent review.</div>`
    : scan.ocr_status === "failed"
      ? `<div class="notice warning"><strong>Text recognition could not finish.</strong>You can still enter the ingredient list manually. ${escapeHTML(scan.ocr_error_code || "")}</div>`
      : "";
  const review = scan.status === "needs_confirmation" ? `<section class="card stack"><div class="card-heading"><div><p class="eyebrow">YOUR REVIEW IS REQUIRED</p><h2>Correct the ingredient draft</h2><p>OCR text is not a confirmed ingredient list. The app does not guess ingredient boundaries.</p></div>${statusPill(label, tone)}</div>
      ${ocrNotice}
      <details><summary class="text-button">View raw OCR text <span class="quiet-label">· unconfirmed</span></summary>${scan.ocr_text ? `<pre class="ocr-text">${escapeHTML(scan.ocr_text.slice(0, 20000))}${scan.ocr_text.length > 20000 ? "… (preview truncated)" : ""}</pre>` : `<p class="field-help">No OCR text was returned. Enter ingredients manually below.</p>`}${renderTokenChips(scan.ocr_tokens || [])}</details>
      <form data-form="ingredient-review"><div class="field"><label for="ingredient-draft">One ingredient per line</label><textarea id="ingredient-draft" name="items" rows="10" placeholder="Example:&#10;Water&#10;Glycerin&#10;…" aria-describedby="ingredient-help">${escapeHTML((scan.ingredients || []).map((item) => item.text).join("\n"))}</textarea><small class="field-help" id="ingredient-help">Edit spelling, add or remove items, and keep one ingredient on each line. Empty lines are ignored; maximum 300 items.</small></div>
        <label class="checkbox-row" style="margin-top:15px"><input type="checkbox" name="confirmAccepted" /><span>I have reviewed and corrected this list. I understand OCR can be wrong.</span></label>
        <div data-form-message aria-live="polite"></div><div class="form-actions"><button class="button button-secondary" name="mode" value="draft" type="submit">Save draft</button><button class="button button-primary" name="mode" value="confirm" type="submit">Save &amp; confirm ingredients</button></div></form>
    </section>` : "";
  const confirmed = scan.status === "confirmed" ? `<section class="card stack"><div class="card-heading"><div><p class="eyebrow">CONFIRMED INPUT</p><h2>Ingredient list reviewed</h2><p>Analysis uses only this confirmed list and the current reviewed rule set.</p></div>${statusPill(label, tone)}</div>
      <ol class="confirmed-list">${(scan.ingredients || []).map((item) => `<li>${escapeHTML(item.text)} <span class="status-pill tone-good"><span class="status-dot"></span>confirmed</span></li>`).join("")}</ol>
      ${state.analysisError ? `<div class="notice warning" role="alert">${escapeHTML(state.analysisError)}</div>` : ""}
      ${state.analysisBusy ? `<div class="scan-progress"><span class="spinner" aria-hidden="true"></span><span>Running deterministic analysis…</span></div>` : ""}
      ${!state.analysis && !state.analysisBusy ? `<div class="notice info"><strong>Ready when you are</strong>Analysis checks the confirmed names against exact ingredient records and the configured deterministic rules.</div><button class="button button-primary" type="button" data-action="run-analysis">Analyze confirmed list</button>` : ""}
      ${renderAnalysis(state.analysis)}
    </section>` : "";
  const waiting = ["queued", "extracting"].includes(scan.status) ? `<section class="card"><div class="scan-progress"><span class="spinner" aria-hidden="true"></span><div><strong>${escapeHTML(label)}</strong><p style="margin:5px 0 0;color:var(--muted);font-size:.84rem">${escapeHTML(ocrLabel)} · We'll keep checking for the review draft.</p></div></div><p class="field-help" style="margin-top:14px">If this page remains here after a minute, return to history and reopen the scan. The local OCR runner is not durable across server restarts.</p></section>` : "";
  const failed = scan.status === "failed" ? `<div class="notice warning"><strong>This scan needs attention.</strong>Return to history or create a new scan. The original image remains private until deletion.</div>` : "";
  return `${pageHeading("SCAN REVIEW", scanName(scan), `Created ${formatDate(scan.created_at, { time: true })}`, `<a class="button button-secondary button-small" href="#/history">← History</a>`)}${pageErrorCard()}<div class="stack">${waiting}${review}${confirmed}${failed}</div>`;
}

function loadingCard() {
  return `<section class="card"><div class="scan-progress"><span class="spinner" aria-hidden="true"></span><span>Loading your private data…</span></div></section>`;
}

function renderHistory() {
  const results = state.scansResult;
  const items = results?.items || [];
  return `${pageHeading("YOUR SCANS", "Scan history.", "Return to a draft, inspect a confirmed scan, or delete a scan and its retained photo.", `<button class="button button-primary" type="button" data-route="scan">＋ New scan</button>`)}${pageErrorCard()}
    <section class="card"><div class="card-heading"><div><h2>${state.loading && !results ? "Loading history…" : `${escapeHTML(results?.total ?? 0)} scan${results?.total === 1 ? "" : "s"}`}</h2><p>Your scan list is visible only to your account.</p></div></div>
      ${state.loading && !results ? loadingCard() : items.length ? `<div class="scan-list">${items.map((item) => scanRow(item, { history: true })).join("")}</div>${results.total > items.length ? `<p class="field-help" style="margin-top:14px">Showing the newest ${items.length} of ${results.total} scans. Older pages are not yet available in this interface.</p>` : ""}` : `<div class="empty-state" style="margin-top:18px"><div class="empty-mark" aria-hidden="true">◷</div><h3>No scans yet</h3><p>Your private scan history will appear here after you upload a label.</p><button class="button button-primary" type="button" data-route="scan">Create your first scan</button></div>`}
    </section>`;
}

function renderProfile() {
  const profile = state.profile || { skin_type: null, concerns: [], locale: "" };
  const displayName = state.user?.display_name || "";
  const declarations = state.declarations || [];
  return `${pageHeading("YOUR PROFILE", "Your notes, your terms.", "These are optional self-reported preferences. They are not clinically verified and are not sent to explanation providers.")}${pageErrorCard()}
    <div class="profile-header"><span class="profile-avatar" aria-hidden="true">${escapeHTML((displayName || state.user?.email || "C").slice(0, 1).toUpperCase())}</span><div><h2>${escapeHTML(displayName || "Your profile")}</h2><p>${escapeHTML(state.user?.email || "")} · User-reported information</p></div></div>
    <div class="grid-2"><section class="card"><div class="card-heading"><div><h2>Account display</h2><p>Shown only in your private workspace.</p></div></div><form data-form="display-name" style="margin-top:20px"><div class="field"><label for="display-name">Display name</label><input id="display-name" name="display_name" type="text" maxlength="120" value="${escapeHTML(displayName)}" autocomplete="nickname" /></div><div data-form-message aria-live="polite"></div><div class="form-actions"><button class="button button-primary" type="submit">Save display name</button></div></form></section>
    <section class="card"><div class="card-heading"><div><h2>Optional profile</h2><p>Stored as user-reported context, never a diagnosis.</p></div></div><form data-form="profile" style="margin-top:20px"><div class="form-grid"><div class="field"><label for="skin-type">Skin type (optional)</label><select id="skin-type" name="skin_type"><option value="">Prefer not to say</option>${SKIN_TYPES.map((value) => `<option value="${value}" ${profile.skin_type === value ? "selected" : ""}>${escapeHTML(value[0].toUpperCase() + value.slice(1))}</option>`).join("")}</select></div><div class="field"><label for="locale">Locale (optional)</label><input id="locale" name="locale" maxlength="20" placeholder="e.g. en-PK" value="${escapeHTML(profile.locale || "")}" /></div></div><div class="field"><label for="concerns">Concerns (optional, one per line)</label><textarea id="concerns" name="concerns" rows="4" placeholder="For your own notes">${escapeHTML((profile.concerns || []).join("\n"))}</textarea><small class="field-help">Up to 10 notes. These are not sent to LLM providers.</small></div><div data-form-message aria-live="polite"></div><div class="form-actions"><button class="button button-primary" type="submit">Save profile</button></div></form></section></div>
    <section class="card" style="margin-top:18px"><div class="card-heading"><div><h2>Declared ingredient terms</h2><p>Personal notes you choose to track. These labels are self-reported, not medically verified.</p></div></div>
      <form data-form="declaration" class="form-grid" style="margin-top:20px;align-items:end"><div class="field"><label for="declared-term">Ingredient or term</label><input id="declared-term" name="term" required maxlength="200" placeholder="e.g. an ingredient name" /></div><div class="field"><label for="declaration-type">How would you like to label it?</label><select id="declaration-type" name="declaration_type" required>${DECLARATION_TYPES.map((value) => `<option value="${value}">${escapeHTML(value[0].toUpperCase() + value.slice(1))}</option>`).join("")}</select></div><div data-form-message aria-live="polite" class="form-grid-message"></div><div class="form-actions" style="margin-top:0"><button class="button button-secondary" type="submit">Add term</button></div></form>
      ${declarations.length ? `<div class="declaration-list">${declarations.map((item) => `<div class="declaration-row"><div><strong>${escapeHTML(item.term)}</strong><small>${escapeHTML(item.declaration_type)} · user-reported</small></div><button class="button button-quiet button-small" type="button" data-action="delete-declaration" data-id="${escapeHTML(item.id)}" aria-label="Delete ${escapeHTML(item.term)}">Remove</button></div>`).join("")}</div>` : `<div class="empty-state" style="margin-top:16px"><div class="empty-mark" aria-hidden="true">＋</div><h3>No declared terms</h3><p>You can add a term if you want to keep a personal note. This does not make it a verified allergy.</p></div>`}
    </section>`;
}

function renderConsentRow(provider, consent) {
  const enabled = Boolean(consent?.enabled);
  const name = provider === "openai" ? "OpenAI" : "Groq";
  return `<div class="consent-row"><div><strong>${name}</strong><p>${enabled ? "Current consent is enabled. It applies only when you explicitly request this provider." : "Not enabled. No cloud explanation will be sent for this provider."}${consent?.granted_at ? ` · Updated ${escapeHTML(formatDate(consent.granted_at))}` : ""}</p></div>
    ${enabled ? `<button class="button button-secondary button-small switch-button" type="button" data-action="revoke-consent" data-provider="${provider}">Revoke consent</button>` : `<form data-form="consent-grant" data-provider="${provider}"><label class="checkbox-row"><input type="checkbox" name="accepted" required /><span>I have read the disclosure above and agree to use ${name} for explanations I request.</span></label><div data-form-message aria-live="polite"></div><button class="button button-secondary button-small switch-button" type="submit" style="margin-top:9px">Enable ${name}</button></form>`}
  </div>`;
}

function renderSettings() {
  const consent = state.aiConsent;
  const providerRows = (consent?.providers || []).map((item) => renderConsentRow(item.provider, item)).join("");
  return `${pageHeading("SETTINGS & PRIVACY", "Your choices stay yours.", "Manage optional cloud explanation consent, export your account data, or remove your account.")}${pageErrorCard()}
    <div class="stack"><section class="card"><div class="card-heading"><div><p class="eyebrow">OPTIONAL AI EXPLANATIONS</p><h2>Cloud-provider consent</h2><p>Consent is separate for each provider. Granting consent does not send a request; you must still ask for an explanation.</p></div></div>
      ${consent ? `<div class="notice info" style="margin-top:17px"><strong>Current disclosure · ${escapeHTML(consent.current_disclosure_version)}</strong>${escapeHTML(consent.disclosure_text)}</div><div style="margin-top:8px">${providerRows}</div>` : state.loading ? `<div style="margin-top:18px">${loadingCard()}</div>` : `<div class="notice warning" style="margin-top:17px">Consent status is not available. Try loading this page again.</div>`}
      <p class="field-help">Ollama is an operator-configured local endpoint and does not use cloud consent. Provider keys are configured server-side; this screen never collects them.</p>
    </section>
    <section class="card"><div class="card-heading"><div><p class="eyebrow">YOUR DATA</p><h2>Export or delete</h2><p>Exports include your account, profile, declarations, scans, and analysis history.</p></div></div><div class="form-actions"><button class="button button-secondary" type="button" data-action="download-export">Download account export</button><button class="button button-danger" type="button" data-action="open-delete-account">Delete account</button></div><p class="field-help">Deleting your account removes its scans and private photos. Make an export first if you want a copy.</p></section>
    <section class="card"><div class="card-heading"><div><h2>Signed in as</h2><p>${escapeHTML(state.user?.email || "")}</p></div><button class="button button-secondary button-small" type="button" data-action="logout">Sign out</button></div><div class="card-divider"></div><a href="#/about">About, privacy and safety notes →</a></section></div>`;
}

function renderOnboarding() {
  const profile = state.profile || { skin_type: null, concerns: [], locale: "" };
  return `${pageHeading("A SOFT START", "A profile is optional.", "Add only the notes you want to keep. Everything here is user-reported, and you can change or delete it later.")}${pageErrorCard()}
    <section class="card" style="max-width:720px"><p class="eyebrow">YOUR NOTES</p><h2 style="font:500 1.6rem Georgia,serif;margin:0 0 8px">What would you like to remember?</h2><p class="page-description" style="margin:0 0 21px">You can skip this step. Your skin profile is not sent to explanation providers.</p><form data-form="onboarding"><div class="form-grid"><div class="field"><label for="onboarding-skin-type">Skin type (optional)</label><select id="onboarding-skin-type" name="skin_type"><option value="">Prefer not to say</option>${SKIN_TYPES.map((value) => `<option value="${value}" ${profile.skin_type === value ? "selected" : ""}>${escapeHTML(value[0].toUpperCase() + value.slice(1))}</option>`).join("")}</select></div><div class="field"><label for="onboarding-locale">Locale (optional)</label><input id="onboarding-locale" name="locale" maxlength="20" placeholder="e.g. en-PK" value="${escapeHTML(profile.locale || "")}" /></div></div><div class="field"><label for="onboarding-concerns">Concerns (optional, one per line)</label><textarea id="onboarding-concerns" name="concerns" rows="4">${escapeHTML((profile.concerns || []).join("\n"))}</textarea></div><div data-form-message aria-live="polite"></div><div class="form-actions"><button class="button button-primary" type="submit">Save and continue</button><button class="button button-quiet" type="button" data-action="skip-onboarding">Skip for now</button></div></form><p class="field-help">This is not a medical profile or diagnosis.</p></section>`;
}

function renderRoadmapPage(kind) {
  const isCompare = kind === "compare";
  const title = isCompare ? "Compare, when the foundations are ready." : "Routines, at your own pace.";
  const desc = isCompare
    ? "A future view will help you review shared and unique ingredients across saved scans without turning the result into a safety score."
    : "A future routine planner will help you organize products without prescribing what you should use.";
  return `${pageHeading(isCompare ? "COMPARE" : "ROUTINES", title, desc)}
    <section class="card" style="max-width:780px"><div class="empty-state"><div class="empty-mark" aria-hidden="true">${isCompare ? "⇄" : "◌"}</div><h3>This feature is not connected to an API yet</h3><p>The current backend does not save comparisons or routines. This screen does not create or store mock data. You can still manage your scans and review confirmed ingredient findings.</p><div class="button-row" style="justify-content:center"><button class="button button-primary" type="button" data-route="scan">Start a scan</button><button class="button button-secondary" type="button" data-route="history">View scan history</button></div></div></section>`;
}

function renderAbout() {
  return `${pageHeading("ABOUT & SAFETY", "Context, not certainty.", "What Clarity Checker can do today—and what it cannot claim.")}
    <div class="policy-copy"><div class="notice warning"><strong>Educational information only</strong>Clarity Checker does not diagnose, prescribe, or guarantee that a product is safe for an individual. “No configured rule triggered” is not proof of safety.</div>
      <h2>Review is part of the process</h2><p>OCR is unavailable in the current app image, so enter ingredient text manually. In a build with OCR enabled, its output can omit, insert, or alter text and remains unconfirmed. Ingredient boundaries are not guessed; review and confirm the list before analysis. Ambiguous and unresolved terms do not trigger guessed findings.</p>
      <h2>What findings mean</h2><p>Findings come from a deterministic, versioned rule set. Source details and citations are validated by the server against currently approved records and reuse rights. The current production ingredient and evidence corpus is empty, so no real-world coverage or safety conclusion is claimed.</p>
      <h2>Optional explanations</h2><p>Generated prose is supplemental, may be incomplete or inaccurate, and cannot change a finding or supply a citation. OpenAI and Groq require current provider-specific consent. A request includes only one confirmed ingredient, its current finding, and approved evidence summaries/permitted excerpts. Images, email, full scans, profile/skin data, and source URLs are excluded. Generated prose is not stored.</p>
      <h2>Your privacy controls</h2><p>Scan history is scoped to your account. Retained photos remain private until you delete the scan or account. You can export account data, delete scans, and revoke cloud-provider consent in Settings &amp; privacy. API credentials are never collected in this interface.</p>
      <h2>Prototype notice</h2><p>This project does not yet provide comparison or routine APIs, and its formal legal and support materials are not complete. Do not use the prototype for urgent or personal medical decisions.</p>
      <div class="form-actions"><a class="button button-secondary" href="#/settings">Settings &amp; privacy</a><a class="button button-primary" href="#/scan">Start a scan</a></div>
    </div>`;
}

function renderPage() {
  if (state.loading && ["dashboard", "history", "profile", "settings", "onboarding"].includes(state.route.view)) {
    const title = { dashboard: "Overview", history: "Scan history", profile: "My profile", settings: "Settings & privacy", onboarding: "Your profile" }[state.route.view];
    return `${pageHeading("PRIVATE WORKSPACE", title, "Loading your account data…")}${loadingCard()}`;
  }
  switch (state.route.view) {
    case "dashboard": return renderDashboard();
    case "scan": return state.route.id ? renderScanDetail() : renderUploadPage();
    case "history": return renderHistory();
    case "profile": return renderProfile();
    case "settings": return renderSettings();
    case "compare": return renderRoadmapPage("compare");
    case "routines": return renderRoadmapPage("routines");
    case "onboarding": return renderOnboarding();
    case "about": return renderAbout();
    default: return renderDashboard();
  }
}

function renderModal() {
  const modal = state.modal;
  if (!modal) return "";
  if (modal.type === "explanation-consent") {
    const providerName = modal.provider === "openai" ? "OpenAI" : "Groq";
    return `<div class="modal-backdrop" data-action="backdrop-close"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1"><p class="eyebrow">ONE-TIME CONSENT</p><h2 id="modal-title">Before using ${providerName}</h2><p>${escapeHTML(modal.disclosure || "Review the current cloud explanation disclosure before continuing.")}</p><form data-form="explanation-consent" data-provider="${escapeHTML(modal.provider)}" data-finding="${escapeHTML(modal.findingId)}"><label class="checkbox-row"><input type="checkbox" name="accepted" required /><span>I have read this disclosure and agree to send the described text to ${providerName} when I request the explanation below.</span></label><div data-form-message aria-live="polite"></div><div class="modal-actions"><button class="button button-quiet" type="button" data-action="close-modal">Cancel</button><button class="button button-primary" type="submit">Agree and request explanation</button></div></form></section></div>`;
  }
  if (modal.type === "delete-scan") {
    return `<div class="modal-backdrop" data-action="backdrop-close"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1"><p class="eyebrow">DELETE SCAN</p><h2 id="modal-title">Remove this scan?</h2><p>The scan, analysis history, and retained private photo will be deleted. This cannot be undone.</p><form data-form="delete-scan" data-id="${escapeHTML(modal.scanId)}"><div data-form-message aria-live="polite"></div><div class="modal-actions"><button class="button button-secondary" type="button" data-action="close-modal">Keep scan</button><button class="button button-danger" type="submit">Delete scan</button></div></form></section></div>`;
  }
  if (modal.type === "delete-account") {
    return `<div class="modal-backdrop" data-action="backdrop-close"><section class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1"><p class="eyebrow">ACCOUNT DELETION</p><h2 id="modal-title">Delete your account?</h2><p>This permanently removes your account, saved scans, analysis history, declarations, and private scan photos.</p><form data-form="delete-account"><div class="field"><label for="delete-password">Confirm your password</label><input id="delete-password" name="password" type="password" autocomplete="current-password" required maxlength="128" /></div><label class="checkbox-row" style="margin-top:14px"><input type="checkbox" name="understood" required /><span>I understand that account deletion cannot be undone.</span></label><div data-form-message aria-live="polite"></div><div class="modal-actions"><button class="button button-secondary" type="button" data-action="close-modal">Cancel</button><button class="button button-danger" type="submit">Delete account</button></div></form></section></div>`;
  }
  return "";
}

function render() {
  if (!root) return;
  if (!state.user) {
    if (state.route.view === "home") root.innerHTML = renderLanding();
    else if (state.route.view === "about") root.innerHTML = renderPublicAbout();
    else if (AUTH_VIEWS.has(state.route.view)) root.innerHTML = renderAuthPage(state.route.view);
    else root.innerHTML = renderLanding();
    return;
  }
  const active = state.route.view === "scan" ? "scan" : state.route.view;
  const content = `${renderPage()}${renderModal()}`;
  root.innerHTML = renderShell({
    user: state.user,
    active,
    content,
    flash: state.flash,
    mobileNavOpen: state.mobileNavOpen,
  });
  if (state.modal) {
    window.setTimeout(() => root.querySelector("[role=dialog]")?.focus(), 0);
  }
}

async function loadRoute() {
  const sequence = ++routeSequence;
  const nextRoute = routeFromHash();
  const routeChanged = nextRoute.view !== state.route.view || nextRoute.id !== state.route.id;
  state.route = nextRoute;
  state.pageError = "";
  state.flash = "";
  const view = state.route.view;
  if (state.user && (view === "home" || AUTH_VIEWS.has(view))) {
    if (view === "verify") {
      state.user = null;
      setCsrfToken("");
    } else {
      go("dashboard");
      return;
    }
  }
  if (!state.user && PROTECTED_VIEWS.has(view)) {
    state.authMessage = "Sign in to access your private workspace.";
    go("login");
    return;
  }
  if (!state.user && !AUTH_VIEWS.has(view) && view !== "home" && view !== "about") {
    go("home");
    return;
  }
  state.mobileNavOpen = false;
  state.loading = Boolean(state.user && ["dashboard", "history", "profile", "settings", "onboarding", "scan"].includes(view));
  if (view === "scan" && !state.route.id) {
    state.loading = false;
    state.scan = null;
    state.analysis = null;
    state.analysisError = "";
    state.explanations = {};
    state.selectedFile = null;
  } else if (view === "scan" && state.route.id) {
    state.scan = null;
    state.analysis = null;
    state.analysisError = "";
    state.explanations = {};
  }
  render();
  if (!state.user) {
    if (routeChanged) focusPageContent();
    return;
  }
  try {
    if (["dashboard", "history"].includes(view)) {
      state.scansResult = await apiJSON("/scans?limit=100&offset=0");
    } else if (view === "profile") {
      const [user, profile, declarations] = await Promise.all([
        apiJSON("/users/me"),
        apiJSON("/users/me/profile"),
        apiJSON("/users/me/declared-ingredients?limit=200&offset=0"),
      ]);
      if (sequence !== routeSequence) return;
      state.user = user;
      state.profile = profile;
      state.declarations = declarations;
    } else if (view === "settings") {
      const [user, consent] = await Promise.all([
        apiJSON("/users/me"),
        apiJSON("/users/me/ai-consents"),
      ]);
      if (sequence !== routeSequence) return;
      state.user = user;
      state.aiConsent = consent;
    } else if (view === "onboarding") {
      try {
        state.profile = await apiJSON("/users/me/profile");
      } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 404) throw error;
        state.profile = { skin_type: null, concerns: [], locale: "" };
      }
    } else if (view === "scan" && state.route.id) {
      const scanId = state.route.id;
      state.scan = await apiJSON(`/scans/${encodeURIComponent(scanId)}`);
      state.analysis = null;
      state.analysisError = "";
      if (state.scan.status === "confirmed") {
        try {
          state.analysis = await apiJSON(`/scans/${encodeURIComponent(scanId)}/analysis`);
        } catch (error) {
          if (!(error instanceof ApiError) || error.status !== 404) throw error;
        }
      }
    }
  } catch (error) {
    if (sequence !== routeSequence) return;
    if (error instanceof ApiError && error.status === 401) {
      state.user = null;
      state.authMessage = "Your session may have expired. Please sign in again.";
      setCsrfToken("");
      go("login");
      return;
    }
    state.pageError = error instanceof Error ? error.message : "The request could not be completed.";
    if (view === "scan" && state.route.id) state.scan = null;
  }
  if (sequence !== routeSequence) return;
  state.loading = false;
  render();
  if (routeChanged) focusPageContent();
  if (view === "scan" && state.route.id && state.scan && ["queued", "extracting"].includes(state.scan.status)) {
    void pollScan(state.route.id, sequence);
  }
}

async function pollScan(scanId, routeId) {
  const pollId = ++pollSequence;
  for (let attempt = 0; attempt < 30; attempt += 1) {
    await new Promise((resolve) => window.setTimeout(resolve, 1400));
    if (pollId !== pollSequence || routeId !== routeSequence || state.route.id !== scanId) return;
    try {
      state.scan = await apiJSON(`/scans/${encodeURIComponent(scanId)}`);
      render();
      if (!["queued", "extracting"].includes(state.scan.status)) return;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        state.user = null;
        setCsrfToken("");
        state.authMessage = "Your session may have expired. Please sign in again.";
        go("login");
        return;
      }
      state.pageError = error instanceof Error ? error.message : "Could not refresh the scan status.";
      render();
      return;
    }
  }
  if (pollId === pollSequence && routeId === routeSequence) {
    toast("The scan is still processing. You can check it again from history.", "error");
  }
}

function parseLines(value, maxItems = 300) {
  const items = String(value || "").split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
  if (items.length > maxItems) throw new Error(`Please use no more than ${maxItems} lines.`);
  if (items.some((item) => item.length > 300)) throw new Error("Each ingredient must be 300 characters or fewer.");
  return items;
}

function providerConsent(provider) {
  return state.aiConsent?.providers?.find((item) => item.provider === provider) || null;
}

async function getConsentDisclosure() {
  if (!state.aiConsent) state.aiConsent = await apiJSON("/users/me/ai-consents");
  return state.aiConsent;
}

async function requestExplanation(findingId, provider, consentAlreadyGranted = false) {
  const scanId = state.route.id || state.scan?.id;
  if (!scanId) return;
  if (["openai", "groq"].includes(provider) && !consentAlreadyGranted) {
    const consent = await getConsentDisclosure();
    const providerState = providerConsent(provider);
    if (!providerState?.enabled) {
      state.modal = {
        type: "explanation-consent",
        provider,
        findingId,
        disclosure: consent.disclosure_text,
      };
      render();
      return;
    }
  }
  state.explanations[findingId] = { loading: true };
  render();
  try {
    const data = await apiJSON(`/scans/${encodeURIComponent(scanId)}/analysis/findings/${encodeURIComponent(findingId)}/explanation`, {
      method: "POST",
      body: { provider },
    });
    state.explanations[findingId] = { data };
  } catch (error) {
    state.explanations[findingId] = { error: error instanceof Error ? error.message : "The explanation could not be generated." };
  }
  render();
}

async function grantConsent(provider, form, pendingExplanation = null) {
  const accepted = form.elements.accepted?.checked;
  if (!accepted) throw new Error("Please confirm that you have read the disclosure.");
  const consent = await getConsentDisclosure();
  const result = await apiJSON(`/users/me/ai-consents/${encodeURIComponent(provider)}`, {
    method: "POST",
    body: { disclosure_version: consent.current_disclosure_version, accepted: true },
  });
  if (state.aiConsent?.providers) {
    state.aiConsent.providers = state.aiConsent.providers.map((item) => item.provider === provider ? result : item);
  }
  const returnFocus = state.modalReturnFocus;
  state.modal = null;
  state.modalReturnFocus = null;
  render();
  if (pendingExplanation) {
    await requestExplanation(pendingExplanation, provider, true);
    restoreModalReturnFocus(returnFocus);
  } else {
    restoreModalReturnFocus(returnFocus);
    toast(`${provider === "openai" ? "OpenAI" : "Groq"} consent saved. No explanation was sent yet.`);
  }
}

function renderModalClosed() {
  const returnFocus = state.modalReturnFocus;
  state.modal = null;
  state.modalReturnFocus = null;
  render();
  restoreModalReturnFocus(returnFocus);
}

async function handleAction(actionElement) {
  const action = actionElement.dataset.action;
  const id = actionElement.dataset.id;
  if (action === "toggle-nav") {
    state.mobileNavOpen = !state.mobileNavOpen;
    render();
    focusMobileNavigation(state.mobileNavOpen);
  } else if (action === "close-nav") {
    state.mobileNavOpen = false;
    render();
    focusMobileNavigation(false);
  } else if (action === "close-modal") {
    renderModalClosed();
  } else if (action === "pick-file") {
    root.querySelector("#scan-file")?.click();
  } else if (action === "resume-scan") {
    go("scan", id);
  } else if (action === "open-delete-scan") {
    captureModalReturnFocus(actionElement);
    state.modal = { type: "delete-scan", scanId: id };
    render();
  } else if (action === "open-delete-account") {
    captureModalReturnFocus(actionElement);
    state.modal = { type: "delete-account" };
    render();
  } else if (action === "run-analysis") {
    await runAnalysis();
  } else if (action === "explain-finding") {
    const provider = document.getElementById(`provider-${id}`)?.value || "ollama";
    state.providerChoice[id] = provider;
    captureModalReturnFocus(actionElement);
    await requestExplanation(id, provider);
    if (!state.modal) restoreModalReturnFocus();
  } else if (action === "download-export") {
    try {
      await downloadFile("/privacy/export", "clarity-checker-export.json");
      toast("Your account export has been downloaded.");
    } catch (error) {
      toast(error.message || "Could not download the export.", "error");
    }
  } else if (action === "logout") {
    try {
      await apiJSON("/auth/logout", { method: "POST" });
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) toast(error.message || "Could not sign out.", "error");
    }
    setCsrfToken("");
    state.user = null;
    state.aiConsent = null;
    state.scansResult = null;
    state.authMessage = "You have signed out.";
    go("home");
  } else if (action === "revoke-consent") {
    const provider = actionElement.dataset.provider;
    try {
      const result = await apiJSON(`/users/me/ai-consents/${encodeURIComponent(provider)}`, { method: "DELETE" });
      if (state.aiConsent?.providers) state.aiConsent.providers = state.aiConsent.providers.map((item) => item.provider === provider ? result : item);
      render();
      toast(`${provider === "openai" ? "OpenAI" : "Groq"} consent revoked.`);
    } catch (error) {
      toast(error.message || "Could not revoke consent.", "error");
    }
  } else if (action === "delete-declaration") {
    try {
      await apiJSON(`/users/me/declared-ingredients/${encodeURIComponent(id)}`, { method: "DELETE" });
      state.declarations = state.declarations.filter((item) => item.id !== id);
      render();
      toast("The declared term was removed.");
    } catch (error) {
      toast(error.message || "Could not remove the term.", "error");
    }
  } else if (action === "skip-onboarding") {
    go("dashboard");
  } else if (action === "retry-load") {
    void loadRoute();
  }
}

async function runAnalysis() {
  if (!state.scan?.id || state.analysisBusy) return;
  state.analysisBusy = true;
  state.analysisError = "";
  render();
  try {
    state.analysis = await apiJSON(`/scans/${encodeURIComponent(state.scan.id)}/analysis`, { method: "POST" });
    state.explanations = {};
  } catch (error) {
    state.analysisError = error instanceof Error ? error.message : "Analysis could not be completed.";
  } finally {
    state.analysisBusy = false;
    render();
  }
}

function updateFileSummary(file) {
  const container = root.querySelector("#selected-file");
  const name = root.querySelector("#selected-file-name");
  const size = root.querySelector("#selected-file-size");
  if (!container || !name || !size) return;
  if (!file) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  name.textContent = file.name || "Selected image";
  size.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB · ready to upload`;
}

function updateFileSelection(file) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) {
    state.selectedFile = null;
    const input = root.querySelector("#scan-file");
    if (input) input.value = "";
    updateFileSummary(null);
    toast("That file is larger than 10 MB. Choose a smaller image.", "error");
    return;
  }
  state.selectedFile = file;
  updateFileSummary(file);
}

function safeResponseMessage(error) {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "The request could not be completed.";
}

async function handleSubmit(event) {
  const form = event.target.closest("form[data-form]");
  if (!form) return;
  event.preventDefault();
  const submitter = event.submitter;
  if (submitter) submitter.disabled = true;
  const data = new FormData(form);
  const kind = form.dataset.form;
  try {
    if (kind === "login") {
      const result = await apiJSON("/auth/login", {
        method: "POST",
        body: { email: data.get("email"), password: data.get("password") },
      });
      setCsrfToken(result.csrf_token);
      state.user = result.user;
      state.authError = "";
      state.authMessage = "";
      state.developmentToken = "";
      if (state.newAccount) {
        state.newAccount = false;
        go("onboarding");
      } else {
        go("dashboard");
      }
    } else if (kind === "register") {
      const email = String(data.get("email") || "").trim();
      const result = await apiJSON("/auth/register", {
        method: "POST",
        body: { email, password: data.get("password") },
      });
      state.authEmail = email;
      state.authMessage = result.message || "If the address is available, verification instructions will be sent.";
      state.authError = "";
      state.developmentToken = result.dev_verification_token || "";
      state.newAccount = true;
      go("verify");
    } else if (kind === "verify-email") {
      await apiJSON("/auth/verify-email", { method: "POST", body: { token: data.get("token") } });
      state.authEmail = state.authEmail || "";
      state.authMessage = "Email verified. Sign in to continue.";
      state.authError = "";
      state.developmentToken = "";
      state.newAccount = true;
      go("login");
    } else if (kind === "request-verification") {
      const email = String(data.get("email") || "").trim();
      const result = await apiJSON("/auth/verification/request", { method: "POST", body: { email } });
      state.authEmail = email;
      state.authMessage = result.message || "If verification is required, instructions will be sent.";
      state.developmentToken = result.dev_token || "";
      state.authError = "";
      render();
    } else if (kind === "request-reset") {
      const email = String(data.get("email") || "").trim();
      const result = await apiJSON("/auth/password-reset/request", { method: "POST", body: { email } });
      state.authEmail = email;
      state.authMessage = result.message || "If the account matches, reset instructions will be sent.";
      state.developmentToken = result.dev_token || "";
      state.authError = "";
      if (result.dev_token) go("reset");
      else render();
    } else if (kind === "confirm-reset") {
      await apiJSON("/auth/password-reset/confirm", {
        method: "POST",
        body: { token: data.get("token"), new_password: data.get("new_password") },
      });
      state.authMessage = "Your password was updated. Sign in with the new password.";
      state.developmentToken = "";
      state.authError = "";
      go("login");
    } else if (kind === "upload") {
      const file = state.selectedFile || form.elements.image.files?.[0];
      if (!file) throw new Error("Choose one label photo before uploading.");
      const body = new FormData();
      body.append("image", file, file.name);
      const scan = await apiJSON("/scans", { method: "POST", body });
      state.selectedFile = null;
      state.scan = scan;
      state.analysis = null;
      go("scan", scan.id);
    } else if (kind === "ingredient-review") {
      const items = parseLines(data.get("items"));
      const mode = submitter?.value || "draft";
      if (mode === "confirm" && !form.elements.confirmAccepted.checked) {
        throw new Error("Confirm that you have reviewed the list before continuing.");
      }
      if (mode === "confirm" && !items.length) throw new Error("Add at least one ingredient before confirming.");
      let scan = await apiJSON(`/scans/${encodeURIComponent(state.scan.id)}/ingredients`, {
        method: "PATCH",
        body: { items },
      });
      if (mode === "confirm") {
        scan = await apiJSON(`/scans/${encodeURIComponent(state.scan.id)}/confirm`, {
          method: "POST",
          body: { accepted: true },
        });
        state.analysis = null;
        state.analysisError = "";
        toast("Ingredient list confirmed. Run analysis when you're ready.");
      } else {
        toast("Draft saved. It is still unconfirmed.");
      }
      state.scan = scan;
      render();
    } else if (kind === "display-name") {
      state.user = await apiJSON("/users/me", {
        method: "PATCH",
        body: { display_name: String(data.get("display_name") || "").trim() || null },
      });
      render();
      toast("Display name saved.");
    } else if (kind === "profile") {
      const concerns = parseLines(data.get("concerns"), 10);
      state.profile = await apiJSON("/users/me/profile", {
        method: "PATCH",
        body: {
          skin_type: String(data.get("skin_type") || "") || null,
          locale: String(data.get("locale") || "").trim() || null,
          concerns,
        },
      });
      render();
      toast("Your user-reported profile was saved.");
    } else if (kind === "declaration") {
      const result = await apiJSON("/users/me/declared-ingredients", {
        method: "POST",
        body: { term: String(data.get("term") || "").trim(), declaration_type: data.get("declaration_type") },
      });
      state.declarations = [...state.declarations, result];
      render();
      toast("Your declared term was added.");
    } else if (kind === "consent-grant") {
      await grantConsent(form.dataset.provider, form);
    } else if (kind === "explanation-consent") {
      await grantConsent(form.dataset.provider, form, form.dataset.finding);
    } else if (kind === "delete-scan") {
      await apiJSON(`/scans/${encodeURIComponent(form.dataset.id)}`, { method: "DELETE" });
      state.modal = null;
      state.modalReturnFocus = null;
      toast("Scan and retained photo deleted.");
      if (state.route.id === form.dataset.id) go("history");
      else {
        state.scansResult = await apiJSON("/scans?limit=100&offset=0");
        render();
      }
    } else if (kind === "delete-account") {
      if (!form.elements.understood.checked) throw new Error("Confirm that you understand account deletion is permanent.");
      await apiJSON("/users/me", { method: "DELETE", body: { password: data.get("password") } });
      setCsrfToken("");
      state.user = null;
      state.modal = null;
      state.modalReturnFocus = null;
      state.aiConsent = null;
      state.scansResult = null;
      state.authMessage = "Your account deletion request is complete.";
      go("home");
    } else if (kind === "onboarding") {
      const concerns = parseLines(data.get("concerns"), 10);
      state.profile = await apiJSON("/users/me/profile", {
        method: "PATCH",
        body: {
          skin_type: String(data.get("skin_type") || "") || null,
          locale: String(data.get("locale") || "").trim() || null,
          concerns,
        },
      });
      go("dashboard");
      toast("Your optional profile is ready.");
    }
  } catch (error) {
    setFormFeedback(form, safeResponseMessage(error), "error");
    if (error instanceof ApiError && error.status === 401 && state.user) {
      state.user = null;
      setCsrfToken("");
      state.authMessage = "Your session may have expired. Please sign in again.";
      go("login");
    }
  } finally {
    if (submitter?.isConnected) submitter.disabled = false;
  }
}

function onClick(event) {
  const routeButton = event.target.closest("[data-route]");
  if (routeButton && routeButton.tagName !== "A") {
    event.preventDefault();
    go(routeButton.dataset.route);
    return;
  }
  const actionElement = event.target.closest("[data-action]");
  if (!actionElement) return;
  if (actionElement.dataset.action === "backdrop-close") {
    if (event.target !== actionElement) return;
    event.preventDefault();
    renderModalClosed();
    return;
  }
  event.preventDefault();
  void handleAction(actionElement);
}

function onKeyDown(event) {
  if (event.key === "Escape") {
    if (state.modal) {
      renderModalClosed();
      return;
    }
    if (state.mobileNavOpen) {
      state.mobileNavOpen = false;
      render();
      focusMobileNavigation(false);
      return;
    }
  }
  const dialog = root.querySelector("[role=dialog]");
  if (event.key !== "Tab" || !dialog) return;
  const focusable = [...dialog.querySelectorAll('button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]')];
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (!dialog.contains(document.activeElement)) {
    event.preventDefault();
    (event.shiftKey ? last : first).focus();
    return;
  }
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function onChange(event) {
  const target = event.target;
  if (target?.id === "scan-file") {
    updateFileSelection(target.files?.[0]);
  } else if (target?.matches("[data-provider-for]")) {
    state.providerChoice[target.dataset.providerFor] = target.value;
  }
}

function onDragOver(event) {
  const zone = event.target.closest("#upload-zone");
  if (!zone) return;
  event.preventDefault();
  zone.classList.add("is-dragging");
}

function onDragLeave(event) {
  const zone = event.target.closest("#upload-zone");
  if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove("is-dragging");
}

function onDrop(event) {
  const zone = event.target.closest("#upload-zone");
  if (!zone) return;
  event.preventDefault();
  zone.classList.remove("is-dragging");
  const file = event.dataTransfer?.files?.[0];
  if (file) updateFileSelection(file);
}

root.addEventListener("click", onClick);
root.addEventListener("submit", (event) => void handleSubmit(event));
root.addEventListener("change", onChange);
root.addEventListener("dragover", onDragOver);
root.addEventListener("dragleave", onDragLeave);
root.addEventListener("drop", onDrop);
root.addEventListener("keydown", onKeyDown);
window.addEventListener("hashchange", () => void loadRoute());

async function initialize() {
  try {
    await ensureCsrfToken();
  } catch {
    // Public pages still render; a later write will show a safe connection error.
  }
  try {
    state.user = await apiJSON("/users/me");
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) {
      state.pageError = safeResponseMessage(error);
    }
  }
  await loadRoute();
}

void initialize();
