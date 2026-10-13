// Entry point: wires the modules together and loads the first results.
import { initLocationFilter, refreshCoverageNote, setLocation } from "./location.js";
import { initMap } from "./map.js";
import { initRatingFilter } from "./rating.js";
import { canSearch, initSearch, loadDefaults, runSearch } from "./search.js";

initSearch();
initRatingFilter(() => {
  if (canSearch()) runSearch();
});
initLocationFilter();
initMap({
  // Clicking the map searches around that spot
  onPick: (lat, lon) => setLocation({ lat, lon, label: "the selected spot", source: "map" }),
  onCoverageLoaded: refreshCoverageNote,
});

// Show products as soon as the page opens
loadDefaults();
