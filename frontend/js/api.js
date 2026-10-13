// Backend (FastAPI) calls. Every function throws on failure; use errorMessage() to show it.
import { API_BASE } from "./config.js";

const SEARCH_URL = API_BASE + "/search";
const DEFAULT_URL = API_BASE + "/default-products";
const LOCATIONS_URL = API_BASE + "/locations";

const NETWORK_MSG = "Could not reach the API at " + API_BASE + ". Make sure the FastAPI server is running.";

// A failed fetch() (server down, CORS, offline) rejects with a TypeError
export function errorMessage(err) {
  return err instanceof TypeError ? NETWORK_MSG : err.message;
}

// Build an Error from a non-OK response, using FastAPI's `detail` when present
async function responseError(res) {
  let detail = "Request failed (" + res.status + ")";
  try {
    const err = await res.json();
    if (typeof err.detail === "string") detail = err.detail;
    else if (Array.isArray(err.detail) && err.detail[0] && err.detail[0].msg) detail = err.detail[0].msg;
  } catch (_) {
    // Body was not JSON; keep the generic message
  }
  return new Error(detail);
}

// POST /search. `body`: {query, rating?, lat?, lon?, radius_km?}
export async function searchProducts(body) {
  const res = await fetch(SEARCH_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await responseError(res);
  return res.json();
}

// GET /default-products: one dish per restaurant
export async function fetchDefaultProducts() {
  const res = await fetch(DEFAULT_URL);
  if (!res.ok) throw await responseError(res);
  return res.json();
}

// GET /locations: where the dataset has data, as [{lat, lon, count}]
export async function fetchCoverage() {
  const res = await fetch(LOCATIONS_URL);
  if (!res.ok) throw await responseError(res);
  const data = await res.json();
  return data.points || [];
}
