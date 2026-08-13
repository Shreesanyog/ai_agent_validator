// Thin fetch wrapper for the AVaaS API. Reads the tenant API key from
// localStorage (set via the "Tenant" panel in the sidebar) and attaches it
// as X-API-Key on every request, per the multi-tenant auth model in
// src/avaas/api/deps.py.
const BASE = "";

export function getApiKey() {
  return localStorage.getItem("avaas_api_key") || "";
}

export function setApiKey(key) {
  localStorage.setItem("avaas_api_key", key || "");
}

export async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  const contentType = res.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await res.json() : await res.text();
  if (!res.ok) {
    const detail = typeof body === "object" && body?.detail ? body.detail : JSON.stringify(body);
    throw new Error(detail);
  }
  return body;
}
