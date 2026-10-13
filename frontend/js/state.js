// Shared mutable UI state. Modules import this object and read/write its fields.
export const state = {
  // Incremented on every request; a response is dropped if a newer request started
  requestId: 0,
  // Search radius in km (used when a location filter is on)
  radiusKm: 10,
  // {lat, lon, label, source: "me" | "map"} while a location filter is on, else null
  userLoc: null,
  // [{lat, lon, count}] from GET /locations
  coveragePoints: [],
};
