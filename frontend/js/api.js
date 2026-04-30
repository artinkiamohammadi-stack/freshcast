/**
 * api.js — Thin wrapper around fetch() for all FreshCast API calls.
 *
 * Why a wrapper? Centralises the base URL and error handling so
 * the rest of the code never has to repeat try/catch boilerplate.
 *
 * The API is served at /api (Nginx proxies /api/* → http://api:8000).
 */

// When served by Nginx (port 80), API calls go to /api (Nginx strips the prefix).
// When served directly by FastAPI (port 8000), no prefix is needed.
const API_BASE = (window.location.port === '80' || window.location.port === '') ? '/api' : '';

/**
 * Core fetch helper — throws on HTTP errors, returns parsed JSON.
 */
async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/** GET /products — returns array of { product_id, name, category, shelf_life_days, unit } */
async function fetchProducts() {
  return apiFetch('/products');
}

/**
 * GET /products/{id}/history?days=N
 * Returns { product_id, history: [{ sale_date, units_sold, price }] }
 */
async function fetchHistory(productId, days = 90) {
  return apiFetch(`/products/${encodeURIComponent(productId)}/history?days=${days}`);
}

/**
 * GET /forecast/{id}?days=N
 * Returns { product_id, forecasts: [{ forecast_date, predicted_units, confidence_low, confidence_high }] }
 */
async function fetchForecast(productId, days = 7) {
  return apiFetch(`/forecast/${encodeURIComponent(productId)}?days=${days}`);
}

/**
 * POST /retrain
 * Returns { status, model_version, trained_at, mae, rmse, n_products }
 */
async function postRetrain() {
  return apiFetch('/retrain', { method: 'POST' });
}

/** GET /model-info */
async function fetchModelInfo() {
  return apiFetch('/model-info');
}

/** GET /health */
async function fetchHealth() {
  return apiFetch('/health');
}
