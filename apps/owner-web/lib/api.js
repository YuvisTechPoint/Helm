const DEV_API = "http://127.0.0.1:8000";

/** Browser uses Next proxy (/api → backend). SSR hits the API directly. */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (typeof window !== "undefined" ? "/api" : DEV_API);

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

function apiHeaders(extra = {}) {
  const headers = { ...extra };
  if (API_KEY) headers["x-api-key"] = API_KEY;
  return headers;
}

/** Treat workflow fallbacks and normal 2xx payloads as success. */
export function apiOk(data) {
  if (!data || data.offline) return false;
  if (data.error) {
    return (
      data.result != null ||
      data.fallback === "sync" ||
      data.mode === "in_process" ||
      data.started === true ||
      data.status === "ok" ||
      data.finished_at != null
    );
  }
  return true;
}

export async function apiGet(path) {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store", headers: apiHeaders() });
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      const detail = typeof data.detail === "string" ? data.detail : null;
      return { error: detail || `API returned ${response.status}`, status: response.status };
    }
    return await response.json();
  } catch {
    return {
      error: "Cannot reach API. Start the backend with: python run_api.py",
      offline: true,
    };
  }
}

export async function apiRequest(method, path, body) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method,
      headers: apiHeaders(body ? { "content-type": "application/json" } : {}),
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = typeof data.detail === "string" ? data.detail : null;
      return { error: detail || `API returned ${response.status}`, status: response.status, offline: response.status === 0 };
    }
    return data;
  } catch {
    return { error: "Cannot reach API. Start the backend with: python run_api.py", offline: true };
  }
}

export function apiPost(path, body) {
  return apiRequest("POST", path, body);
}

export function apiDelete(path) {
  return apiRequest("DELETE", path);
}

export function formatCents(cents) {
  if (cents == null) return "—";
  return `₹${(cents / 100).toLocaleString("en-IN", { minimumFractionDigits: 0 })}`;
}

export function formatNumber(n) {
  if (n == null) return "—";
  return Number(n).toLocaleString();
}
