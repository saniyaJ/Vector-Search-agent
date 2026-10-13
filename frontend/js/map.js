// Leaflet map: dataset coverage (pink), current results and search area (amber/blue).
import { fetchCoverage } from "./api.js";
import { el } from "./dom.js";
import { state } from "./state.js";

let map = null;
let coverageLayer = null; // pink dots: where the dataset has data
let markerLayer = null;   // amber dots: current results, plus the search area

// onPick(lat, lon): the user clicked the map
// onCoverageLoaded(): state.coveragePoints was filled in
export function initMap({ onPick, onCoverageLoaded }) {
  if (typeof L === "undefined") return; // Leaflet failed to load; page still works without the map
  map = L.map("map", { worldCopyJump: true, scrollWheelZoom: false }).setView([50, 12], 4);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  coverageLayer = L.layerGroup().addTo(map);
  markerLayer = L.layerGroup().addTo(map);

  map.on("click", (e) => onPick(e.latlng.lat, e.latlng.lng));
  loadCoverage(onCoverageLoaded);
}

async function loadCoverage(onCoverageLoaded) {
  try {
    state.coveragePoints = await fetchCoverage();
    const bounds = [];
    state.coveragePoints.forEach((c) => {
      L.circleMarker([c.lat, c.lon], {
        radius: Math.min(3 + Math.log2(c.count + 1), 10),
        color: "#ec4899",
        weight: 0,
        fillColor: "#ec4899",
        fillOpacity: 0.55,
        interactive: false,
      }).addTo(coverageLayer);
      bounds.push([c.lat, c.lon]);
    });
    // Show the whole dataset area unless results already moved the map
    if (bounds.length && !markerLayer.getLayers().length) {
      map.fitBounds(L.latLngBounds(bounds).pad(0.15), { maxZoom: 6 });
    }
    onCoverageLoaded();
  } catch (err) {
    console.error("coverage failed", err);
  }
}

// Replace the result markers (and the search area, if a location is set)
export function updateMap(products) {
  if (!map) return;
  markerLayer.clearLayers();
  let bounds = null;
  const extend = (b) => { bounds = bounds ? bounds.extend(b) : L.latLngBounds(b); };

  const loc = state.userLoc;
  if (loc) {
    const centre = [loc.lat, loc.lon];
    const area = L.circle(centre, {
      radius: state.radiusKm * 1000,
      color: "#2563eb",
      weight: 1,
      fillColor: "#2563eb",
      fillOpacity: 0.08,
      interactive: false,
    }).addTo(markerLayer);
    L.circleMarker(centre, {
      radius: 7,
      color: "#2563eb",
      weight: 2,
      fillColor: "#2563eb",
      fillOpacity: 0.9,
    }).bindTooltip(loc.source === "me" ? "You are here" : "Search centre").addTo(markerLayer);
    extend(area.getBounds());
  }

  products.forEach((p) => {
    if (!p.location) return;
    const latlng = [p.location.lat, p.location.lon];
    const popup = el("div");
    popup.appendChild(el("div", "popup-title", p.cafe_name));
    popup.appendChild(el("div", "popup-sub", p.product_name));
    if (p.address) popup.appendChild(el("div", "popup-sub", p.address));
    L.circleMarker(latlng, {
      radius: 6,
      color: "#ffffff",
      weight: 1.5,
      fillColor: "#f59e0b",
      fillOpacity: 0.95,
    }).bindPopup(popup).bindTooltip(p.product_name + " · " + p.cafe_name).addTo(markerLayer);
    extend(latlng);
  });

  map.invalidateSize();
  if (bounds) map.fitBounds(bounds.pad(0.15), { maxZoom: 14 });
}
