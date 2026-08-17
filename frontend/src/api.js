const BASE_URL = import.meta.env.VITE_API_BASE_URL;
const API_KEY = import.meta.env.VITE_API_KEY;

async function apiFetch(path, options = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "X-API-Key": API_KEY,
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${response.status}`);
  }

  return response.json();
}

export function getProducts() {
  return apiFetch("/products");
}

export function getCopy(productId) {
  return apiFetch(`/copy/${productId}`);
}

export function generateCopy(productId, force = false) {
  return apiFetch(`/generate/${productId}?force=${force}`, { method: "POST" });
}

export function getLatestEval() {
  return apiFetch("/eval/results");
}

export function runEval() {
  return apiFetch("/eval/run", { method: "POST" });
}