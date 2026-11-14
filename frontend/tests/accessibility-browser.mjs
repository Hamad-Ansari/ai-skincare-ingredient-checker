import AxeBuilder from "@axe-core/playwright";
import { chromium, firefox, webkit } from "playwright";
import { spawn, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDirectory = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(testDirectory, "../..");
const port = Number(process.env.A11Y_PORT || 8767);
const baseURL = process.env.A11Y_BASE_URL || `http://127.0.0.1:${port}`;
const python = process.env.PYTHON || "python";
const browserName = process.env.A11Y_BROWSER || "chromium";
const browserTypes = { chromium, firefox, webkit };
const browserType = browserTypes[browserName];
if (!browserType) throw new Error(`Unsupported A11Y_BROWSER: ${browserName}`);
const reportPath = process.env.A11Y_REPORT_PATH || path.join(repoRoot, "reports/accessibility/chromium-axe.json");
const packageJson = JSON.parse(await readFile(path.join(repoRoot, "frontend/package.json"), "utf8"));
const axeCorePackage = JSON.parse(await readFile(path.join(repoRoot, "frontend/node_modules/axe-core/package.json"), "utf8"));
const testRoot = await mkdtemp(path.join(os.tmpdir(), "clarity-accessibility-"));
const databasePath = path.join(testRoot, "accessibility.sqlite3");
const serverEnv = {
  ...process.env,
  APP_ENV: "development",
  APP_SECRET_KEY: "accessibility-test-only-secret-key-1234567890",
  AUTH_EXPOSE_DEV_TOKENS: "true",
  DATABASE_URL: `sqlite:///${databasePath}`,
  PRIVATE_SCAN_STORAGE_DIR: path.join(testRoot, "private-scans"),
  LOG_LEVEL: "WARNING",
};
let server;
let browser;
let testError;
const scans = [];
const assertions = [];

function assertStep(name, passed, details = "") {
  assertions.push({ name, passed: Boolean(passed), ...(details ? { details } : {}) });
}

function gradientColors(cssValue) {
  return [...cssValue.matchAll(/rgba?\(([^)]+)\)/g)].map(([, channels]) =>
    channels.split(",").slice(0, 3).map((channel) => Number.parseFloat(channel.trim())),
  );
}

function relativeLuminance(rgb) {
  const [red, green, blue] = rgb.map((channel) => {
    const value = channel / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

function contrastRatio(first, second) {
  const values = [relativeLuminance(first), relativeLuminance(second)].sort((a, b) => b - a);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

function parseCssRgba(cssColor) {
  const match = cssColor.match(/rgba?\(([^)]+)\)/);
  if (!match) throw new Error(`Could not parse computed color: ${cssColor}`);
  const channels = match[1].split(",").map((channel) => Number.parseFloat(channel.trim()));
  return { rgb: channels.slice(0, 3), alpha: channels[3] ?? 1 };
}

function parseCssRgb(cssColor) {
  return parseCssRgba(cssColor).rgb;
}

async function waitForServer(child) {
  const deadline = Date.now() + 30_000;
  let lastError;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`Test server exited with code ${child.exitCode}`);
    try {
      const response = await fetch(`${baseURL}/health/live`);
      if (response.ok) return;
      lastError = new Error(`Health endpoint returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${baseURL}/health/live: ${lastError}`);
}

async function scanPage(page, state) {
  await page.waitForSelector("#main-content h1", { timeout: 10_000 });
  await page.waitForTimeout(150);
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const summarizeNode = (node) => ({
    target: node.target,
    summary: node.failureSummary,
    html: node.html.slice(0, 350),
  });
  scans.push({
    state,
    url: page.url(),
    title: await page.title(),
    violationCount: result.violations.length,
    incompleteCount: result.incomplete.length,
    violations: result.violations.map((item) => ({
      id: item.id,
      impact: item.impact,
      description: item.description,
      help: item.help,
      helpUrl: item.helpUrl,
      nodes: item.nodes.map(summarizeNode),
    })),
    incomplete: result.incomplete.map((item) => ({
      id: item.id,
      impact: item.impact,
      help: item.help,
      helpUrl: item.helpUrl,
      nodes: item.nodes.map(summarizeNode),
    })),
  });
}

async function navigate(page, route, state) {
  await page.goto(`${baseURL}/#/${route}`, { waitUntil: "domcontentloaded" });
  await scanPage(page, state);
}

async function checkReflow(page, route, label, width) {
  await page.setViewportSize({ width, height: 900 });
  await page.goto(`${baseURL}/#/${route}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#main-content h1", { timeout: 10_000 });
  await page.waitForTimeout(100);
  const dimensions = await page.evaluate(() => {
    const viewport = document.documentElement.clientWidth;
    const offenders = [...document.body.querySelectorAll("*")]
      .map((element) => {
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return {
          element,
          right: rect.right,
          left: rect.left,
          width: rect.width,
          display: style.display,
          visibility: style.visibility,
          position: style.position,
          text: (element.innerText || "").replace(/\\s+/g, " ").slice(0, 70),
          parents: (() => {
            const parents = [];
            let parent = element.parentElement;
            while (parent && parents.length < 4) {
              const parentRect = parent.getBoundingClientRect();
              const parentStyle = getComputedStyle(parent);
              parents.push({
                tag: parent.tagName.toLowerCase(),
                className: typeof parent.className === "string" ? parent.className : "",
                left: parentRect.left,
                right: parentRect.right,
                width: parentRect.width,
                scrollWidth: parent.scrollWidth,
                clientWidth: parent.clientWidth,
                display: parentStyle.display,
                gridTemplateColumns: parentStyle.gridTemplateColumns,
                minWidth: parentStyle.minWidth,
              });
              parent = parent.parentElement;
            }
            return parents;
          })(),
        };
      })
      .filter((item) => item.width > 0 && item.right > viewport + 1 && item.display !== "none" && item.visibility !== "hidden" && item.position !== "fixed")
      .sort((a, b) => b.right - a.right)
      .slice(0, 6)
      .map(({ element, ...item }) => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === "string" ? element.className : "",
        ...item,
      }));
    return {
      viewport,
      document: document.documentElement.scrollWidth,
      body: document.body.scrollWidth,
      offenders,
    };
  });
  const passed = dimensions.document <= dimensions.viewport + 1 && dimensions.body <= dimensions.viewport + 1;
  const detail = `viewport ${dimensions.viewport}px; document ${dimensions.document}px; body ${dimensions.body}px${passed ? "" : `; offenders ${JSON.stringify(dimensions.offenders)}`}`;
  assertStep(`no horizontal overflow on ${label} at ${width}px CSS width`, passed, detail);
}

try {
  await rm(reportPath, { force: true });
  const migration = spawnSync(
    python,
    ["-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
    { cwd: repoRoot, env: serverEnv, encoding: "utf8" },
  );
  if (migration.error || migration.status !== 0) {
    throw new Error(`Alembic setup failed: ${migration.error || migration.stderr || migration.status}`);
  }

  server = spawn(
    python,
    ["-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", String(port)],
    { cwd: repoRoot, env: serverEnv, stdio: "ignore" },
  );
  await waitForServer(server);

  browser = await browserType.launch({
    headless: true,
    ...(browserName === "chromium" ? { args: ["--no-sandbox"] } : {}),
  });
  const context = await browser.newContext({ viewport: { width: 1365, height: 900 } });
  const page = await context.newPage();

  await page.goto(`${baseURL}/`, { waitUntil: "domcontentloaded" });
  await scanPage(page, "public-landing-desktop");
  const landingCardColors = await page.locator(".hero-card").evaluate((card) => {
    const status = card.querySelector(".hero-card-line:nth-child(4) > span:nth-child(2)");
    return {
      foreground: getComputedStyle(status).color,
      background: getComputedStyle(card).backgroundColor,
    };
  });
  const landingForeground = parseCssRgb(landingCardColors.foreground);
  const landingSurface = parseCssRgba(landingCardColors.background);
  const darkestCardBacking = landingSurface.rgb.map((channel) => channel * landingSurface.alpha);
  const landingCardRatio = contrastRatio(landingForeground, darkestCardBacking);
  assertStep(
    "landing status text meets 4.5:1 over a conservative translucent-card backing",
    landingCardRatio >= 4.5,
    `${landingCardRatio.toFixed(2)}:1 when the 94% opaque card is composited over black`,
  );

  await page.keyboard.press("Tab");
  const skipLinkFocused = await page.evaluate(() => document.activeElement?.classList.contains("skip-link"));
  assertStep("first keyboard Tab focuses skip link", skipLinkFocused);

  await checkReflow(page, "", "public landing (200% desktop-width proxy)", 640);
  await checkReflow(page, "", "public landing (WCAG reflow-width proxy)", 320);
  await checkReflow(page, "about", "about page", 320);
  await checkReflow(page, "login", "login form", 320);
  await page.setViewportSize({ width: 1365, height: 900 });

  for (const [route, state] of [
    ["about", "public-about-desktop"],
    ["login", "login-desktop"],
    ["register", "register-desktop"],
    ["forgot", "password-reset-request-desktop"],
  ]) {
    await navigate(page, route, state);
  }

  // Create an isolated test account via the API, then test the actual browser login form.
  const email = `a11y-${Date.now()}@example.com`;
  const password = "A11y-Test-Only-Password-123!";
  const csrfResponse = await context.request.get(`${baseURL}/api/v1/auth/csrf`);
  if (!csrfResponse.ok()) throw new Error(`CSRF bootstrap failed: ${csrfResponse.status()}`);
  const csrf = (await csrfResponse.json()).csrf_token;
  const headers = { Origin: baseURL, "X-CSRF-Token": csrf };
  const registration = await context.request.post(`${baseURL}/api/v1/auth/register`, {
    data: { email, password },
    headers,
  });
  if (registration.status() !== 202) {
    throw new Error(`Test registration failed: ${registration.status()} ${(await registration.text()).slice(0, 300)}`);
  }
  const registrationBody = await registration.json();
  if (!registrationBody.dev_verification_token) {
    throw new Error("The local accessibility test server did not expose its verification token.");
  }
  const verification = await context.request.post(`${baseURL}/api/v1/auth/verify-email`, {
    data: { token: registrationBody.dev_verification_token },
    headers,
  });
  if (verification.status() !== 204) throw new Error(`Test email verification failed: ${verification.status()}`);

  await navigate(page, "login", "login-before-auth");
  await page.getByLabel("Email address").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByRole("heading", { name: "A calmer way to review." }).waitFor({ timeout: 15_000 });
  await scanPage(page, "workspace-dashboard-desktop");

  // Axe cannot infer colors behind a gradient; compare every rendered stop for the dashboard copy.
  const welcomeColors = await page.locator(".welcome-panel").evaluate((panel) => ({
    backgroundImage: getComputedStyle(panel).backgroundImage,
    eyebrow: getComputedStyle(panel.querySelector(".eyebrow")).color,
    heading: getComputedStyle(panel.querySelector("h2")).color,
    body: getComputedStyle(panel.querySelector("p:not(.eyebrow)")).color,
  }));
  const stops = gradientColors(welcomeColors.backgroundImage);
  if (stops.length < 2) throw new Error("Welcome panel gradient did not expose parseable color stops.");
  const contrastByText = Object.fromEntries(
    Object.entries(welcomeColors)
      .filter(([key]) => key !== "backgroundImage")
      .map(([key, color]) => [key, stops.map((background) => contrastRatio(parseCssRgb(color), background))]),
  );
  const minimumWelcomeContrast = Math.min(...Object.values(contrastByText).flat());
  assertStep(
    "dashboard welcome text meets 4.5:1 at every gradient stop",
    Object.values(contrastByText).flat().every((ratio) => ratio >= 4.5),
    `minimum ${minimumWelcomeContrast.toFixed(2)}:1; eyebrow ${Math.min(...contrastByText.eyebrow).toFixed(2)}:1, heading ${Math.min(...contrastByText.heading).toFixed(2)}:1, body ${Math.min(...contrastByText.body).toFixed(2)}:1`,
  );

  for (const [width, widthLabel] of [[640, "200% desktop-width proxy"], [320, "320px reflow-width proxy"]]) {
    for (const route of ["dashboard", "scan", "settings"]) {
      await checkReflow(page, route, `${route} (${widthLabel})`, width);
    }
  }
  await page.getByRole("button", { name: "Delete account" }).click();
  const narrowDialog = page.getByRole("dialog", { name: "Delete your account?" });
  await narrowDialog.waitFor({ state: "visible" });
  const narrowDialogDimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  const narrowDialogFits = narrowDialogDimensions.document <= narrowDialogDimensions.viewport + 1 && narrowDialogDimensions.body <= narrowDialogDimensions.viewport + 1;
  assertStep(
    "delete-account dialog has no horizontal overflow at 320px CSS width",
    narrowDialogFits,
    `viewport ${narrowDialogDimensions.viewport}px; document ${narrowDialogDimensions.document}px; body ${narrowDialogDimensions.body}px`,
  );
  await narrowDialog.getByRole("button", { name: "Cancel" }).click();
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  await page.setViewportSize({ width: 1365, height: 900 });

  for (const [route, state] of [
    ["scan", "scan-upload-desktop"],
    ["history", "scan-history-desktop"],
    ["profile", "profile-desktop"],
    ["settings", "settings-desktop"],
    ["onboarding", "onboarding-desktop"],
    ["compare", "compare-placeholder-desktop"],
    ["routines", "routines-placeholder-desktop"],
  ]) {
    await navigate(page, route, state);
  }

  // SPA route transitions must move focus to the new heading and update the title.
  await navigate(page, "dashboard", "workspace-dashboard-focus-check");
  await page.getByRole("link", { name: "Settings & privacy" }).click();
  await page.getByRole("heading", { name: "Your choices stay yours." }).waitFor({ timeout: 10_000 });
  const routeHeadingFocused = await page.evaluate(() => document.activeElement?.matches("#main-content h1"));
  const routeTitleUpdated = (await page.title()).startsWith("Your choices stay yours.");
  assertStep("route transition focuses heading and updates title", routeHeadingFocused && routeTitleUpdated);
  await scanPage(page, "settings-route-focus-check");

  // Check dialog semantics, containment, keyboard wrapping, Escape, and return focus.
  await page.getByRole("button", { name: "Delete account" }).click();
  const dialog = page.getByRole("dialog", { name: "Delete your account?" });
  await dialog.waitFor({ state: "visible" });
  await page.waitForFunction(() => document.querySelector('[role="dialog"]')?.contains(document.activeElement) === true);
  const initialDialogFocus = await page.evaluate(() => document.querySelector('[role="dialog"]')?.contains(document.activeElement) === true);
  await page.getByLabel("Confirm your password").focus();
  await page.keyboard.press("Shift+Tab");
  const shiftTabWrapped = await dialog.getByRole("button", { name: "Delete account" }).evaluate((element) => element === document.activeElement);
  await page.keyboard.press("Tab");
  const tabWrapped = await page.getByLabel("Confirm your password").evaluate((element) => element === document.activeElement);
  assertStep("dialog receives initial focus and traps Tab/Shift+Tab", initialDialogFocus && shiftTabWrapped && tabWrapped);
  await scanPage(page, "settings-delete-account-dialog");
  const dialogTextColors = await dialog.locator("p:nth-child(3)").evaluate((element) => ({
    foreground: getComputedStyle(element).color,
    background: getComputedStyle(element.closest(".modal")).backgroundColor,
  }));
  const dialogForeground = parseCssRgb(dialogTextColors.foreground);
  const dialogSurface = parseCssRgba(dialogTextColors.background);
  const dialogRatio = contrastRatio(dialogForeground, dialogSurface.rgb);
  assertStep(
    "delete-dialog body text meets 4.5:1 against the opaque dialog surface",
    dialogSurface.alpha === 1 && dialogRatio >= 4.5,
    `${dialogRatio.toFixed(2)}:1 on the modal surface`,
  );
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector('[role="dialog"]'));
  await page.waitForFunction(() => document.activeElement?.dataset?.action === "open-delete-account");
  const modalReturnFocus = await page.evaluate(() => document.activeElement?.dataset?.action === "open-delete-account");
  assertStep("Escape closes dialog and restores opener focus", modalReturnFocus);

  // Mobile navigation state and focus management at a 390px viewport.
  await page.setViewportSize({ width: 390, height: 844 });
  const menuButton = page.getByRole("button", { name: "Toggle navigation" });
  await menuButton.click();
  await page.waitForFunction(() => document.querySelector("#app-sidebar")?.classList.contains("sidebar-open"));
  await page.waitForFunction(() => document.activeElement?.matches("#app-sidebar .primary-nav a"));
  const mobileMenuFocusMoved = await page.evaluate(() => document.activeElement?.matches("#app-sidebar .primary-nav a"));
  const expanded = await menuButton.getAttribute("aria-expanded");
  await scanPage(page, "settings-mobile-navigation-open");
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => !document.querySelector("#app-sidebar")?.classList.contains("sidebar-open"));
  await page.waitForFunction(() => document.activeElement?.matches(".mobile-menu-button"));
  const collapsed = await menuButton.getAttribute("aria-expanded");
  assertStep("mobile menu exposes state, moves focus, and restores focus on Escape", expanded === "true" && collapsed === "false" && mobileMenuFocusMoved);
  await scanPage(page, "settings-mobile-navigation-closed");

  const report = {
    scanner: "axe-core via @axe-core/playwright",
    axePlaywrightVersion: packageJson.devDependencies["@axe-core/playwright"],
    axeCoreVersion: axeCorePackage.version,
    playwrightVersion: packageJson.devDependencies.playwright,
    browserEngine: browserName,
    browser: `${browserName[0].toUpperCase()}${browserName.slice(1)} ${browser.version()}`,
    tags: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
    note: "Automated scan only; not a WCAG conformance audit or assistive-technology user test.",
    assertions,
    scans,
  };
  await mkdir(path.dirname(reportPath), { recursive: true });
  await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);

  const violationCount = scans.reduce((total, scan) => total + scan.violationCount, 0);
  const failedAssertions = assertions.filter((assertion) => !assertion.passed);
  console.log(JSON.stringify({
    browser: report.browser,
    reportPath,
    statesScanned: scans.length,
    violationCount,
    incompleteCount: scans.reduce((total, scan) => total + scan.incompleteCount, 0),
    assertions,
  }, null, 2));
  if (violationCount || failedAssertions.length) process.exitCode = 1;
} catch (error) {
  testError = error;
} finally {
  if (browser) await browser.close();
  if (server && server.exitCode === null) {
    server.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => server.once("exit", resolve)),
      new Promise((resolve) => setTimeout(() => {
        server.kill("SIGKILL");
        resolve();
      }, 5_000)),
    ]);
  }
  await rm(testRoot, { recursive: true, force: true });
}

if (testError) {
  console.error(testError);
  process.exitCode = 1;
}
