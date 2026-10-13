// Location filter UI: Anywhere / Near me / radius dropdown (the map click calls setLocation too).
import { coverageNote, getPosition } from "./geo.js";
import { hasQuery, loadDefaults, runSearch } from "./search.js";
import { state } from "./state.js";

const anywhereBtn = document.getElementById("loc-anywhere");
const nearBtn = document.getElementById("loc-near");
const radiusSelect = document.getElementById("radius");
const nearStatus = document.getElementById("near-status");
const mapHint = document.getElementById("map-hint");

function setNearStatus(text, isError) {
  nearStatus.textContent = text;
  nearStatus.classList.toggle("error", Boolean(isError));
}

function syncLocationUI() {
  const loc = state.userLoc;
  anywhereBtn.classList.toggle("active", !loc);
  nearBtn.classList.toggle("active", Boolean(loc && loc.source === "me"));
  radiusSelect.hidden = !loc;
  radiusSelect.value = String(state.radiusKm);
  mapHint.textContent = loc
    ? "Searching within " + state.radiusKm + " km of " + loc.label + ". Amber points are your results."
    : "Amber points are your current results; pink dots show the wider dataset. Click the map to search near a spot.";
}

// loc: {lat, lon, label, source} or null for "Anywhere". Updates the UI and re-runs the search.
export function setLocation(loc) {
  state.userLoc = loc;
  setNearStatus(loc ? coverageNote(loc, state.coveragePoints) : "", false);
  syncLocationUI();
  if (loc) runSearch();
  // Back to the normal search, or the default list if nothing was searched
  else if (hasQuery()) runSearch();
  else loadDefaults();
}

// Called once the coverage data arrives, so the "far from data" note can appear
export function refreshCoverageNote() {
  if (state.userLoc) setNearStatus(coverageNote(state.userLoc, state.coveragePoints), false);
}

export function initLocationFilter() {
  anywhereBtn.addEventListener("click", () => {
    if (state.userLoc) setLocation(null);
  });

  nearBtn.addEventListener("click", async () => {
    nearBtn.disabled = true;
    nearBtn.textContent = "Locating…";
    setNearStatus("", false);
    try {
      const pos = await getPosition();
      setLocation({ lat: pos.lat, lon: pos.lon, label: "you", source: "me" });
    } catch (err) {
      setNearStatus(err.message, true);
    } finally {
      nearBtn.disabled = false;
      nearBtn.textContent = "📍 Near me";
    }
  });

  radiusSelect.addEventListener("change", () => {
    state.radiusKm = Number(radiusSelect.value);
    syncLocationUI();
    if (state.userLoc) runSearch();
  });

  syncLocationUI();
}
