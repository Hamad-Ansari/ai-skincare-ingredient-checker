const API_ROOT = "/api/v1";
const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
let csrfToken = "";

export class ApiError extends Error {
  constructor(message, status, code = "request_failed", payload = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.payload = payload;
  }
}

export function setCsrfToken(value) {
  csrfToken = typeof value === "string" ? value : "";
}

export async function ensureCsrfToken({ refresh = false } = {}) {
  if (csrfToken && !refresh) return csrfToken;
  const response = await fetch(`${API_ROOT}/auth/csrf`, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new ApiError("Could not start a secure session. Please reload and try again.", response.status);
  }
  const body = await response.json();
  setCsrfToken(body.csrf_token);
  return csrfToken;
}

async function readError(response) {
  const payload = await response.json().catch(() => null);
  const detail = payload?.detail ?? payload?.error ?? payload;
  const message =
    (typeof detail === "string" && detail) ||
    detail?.message ||
    payload?.message ||
    `Request failed (${response.status}).`;
  const code = detail?.code || payload?.code || "request_failed";
  return { message, code, payload };
}

function normalizeBody(body, headers) {
  if (
    body !== null &&
    typeof body === "object" &&
    !(body instanceof FormData) &&
    !(body instanceof Blob)
  ) {
    if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    return JSON.stringify(body);
  }
  return body;
}

export async function apiRequest(path, options = {}) {
  if (typeof path !== "string" || !path.startsWith("/")) {
    throw new TypeError("API paths must be relative to the same origin.");
  }
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  let body = normalizeBody(options.body ?? null, headers);

  if (UNSAFE_METHODS.has(method)) {
    await ensureCsrfToken();
    headers.set("X-CSRF-Token", csrfToken);
  }

  const requestOptions = {
    ...options,
    method,
    body,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  };
  let response = await fetch(`${API_ROOT}${path}`, requestOptions);

  if (UNSAFE_METHODS.has(method) && response.status === 403) {
    const errorBody = await response.clone().json().catch(() => null);
    if (errorBody?.detail?.code === "csrf_failed") {
      await ensureCsrfToken({ refresh: true });
      headers.set("X-CSRF-Token", csrfToken);
      response = await fetch(`${API_ROOT}${path}`, requestOptions);
    }
  }

  if (!response.ok) {
    const error = await readError(response);
    throw new ApiError(error.message, response.status, error.code, error.payload);
  }
  return response;
}

export async function apiJSON(path, options = {}) {
  const response = await apiRequest(path, options);
  if (response.status === 204 || response.headers.get("content-length") === "0") return null;
  const contentType = response.headers.get("content-type") || "";
  return contentType.includes("application/json") ? response.json() : response.text();
}

export async function downloadFile(path, filename) {
  const response = await apiRequest(path, { method: "GET" });
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
