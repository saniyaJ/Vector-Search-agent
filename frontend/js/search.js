// Search box, example chips, and the two data loads (search / default products).
import { errorMessage, fetchDefaultProducts, searchProducts } from "./api.js";
import { getMinRating } from "./rating.js";
import { renderResults, showLoading, showState } from "./render.js";
import { state } from "./state.js";

const EXAMPLES = ["sushi", "pizza", "vegan salad", "burger", "ramen", "dessert"];
// Query used when a location is set but the search box is empty
const NEAR_ME_DEFAULT_QUERY = "food";

const form = document.getElementById("search-form");
const queryInput = document.getElementById("query");
const submitBtn = document.getElementById("submit");
const examplesEl = document.getElementById("examples");

export function hasQuery() {
  return Boolean(queryInput.value.trim());
}

// A search can run with a typed query, or with just a location filter
export function canSearch() {
  return hasQuery() || Boolean(state.userLoc);
}

export function initSearch() {
  EXAMPLES.forEach((text) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip";
    b.textContent = text;
    b.addEventListener("click", () => {
      queryInput.value = text;
      runSearch();
    });
    examplesEl.appendChild(b);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    runSearch();
  });
}

export async function runSearch() {
  const typed = queryInput.value.trim();
  const loc = state.userLoc;
  if (!typed && !loc) {
    queryInput.focus();
    return;
  }

  const body = { query: typed || NEAR_ME_DEFAULT_QUERY };
  const rating = getMinRating();
  if (rating !== null) body.rating = rating;
  if (loc) {
    body.lat = loc.lat;
    body.lon = loc.lon;
    body.radius_km = state.radiusKm;
  }

  const myId = ++state.requestId;
  submitBtn.disabled = true;
  showLoading();

  try {
    const products = await searchProducts(body);
    if (myId !== state.requestId) return; // a newer search has started
    renderResults(products, {
      label: "Results",
      subtitle: (typed ? "Top matches for “" + typed + "”" : "Foods near " + (loc ? loc.label : "you"))
        + (loc ? " within " + state.radiusKm + " km" : ""),
      empty: "No foods found" + (typed ? " for “" + typed + "”" : "")
        + (loc ? " within " + state.radiusKm + " km of " + loc.label : "")
        + ". Try a different search or relax the filters.",
      showMatch: true,
    });
  } catch (err) {
    if (myId !== state.requestId) return;
    showState(errorMessage(err), true);
  } finally {
    if (myId === state.requestId) submitBtn.disabled = false;
  }
}

// Default products (one per restaurant), loaded when the page opens
export async function loadDefaults() {
  const myId = ++state.requestId;
  showLoading();
  try {
    const products = await fetchDefaultProducts();
    if (myId !== state.requestId) return; // the user already started a search
    renderResults(products, {
      label: "Explore",
      subtitle: "One dish from each restaurant",
      empty: "No foods to show yet.",
      showMatch: false, // the score is relative to a generic query, so it would be misleading here
    });
  } catch (err) {
    if (myId !== state.requestId) return;
    showState(errorMessage(err), true);
  }
}
