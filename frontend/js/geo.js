// Warn when the chosen spot is farther than this from any data
const FAR_FROM_DATA_KM = 60;

// Great-circle distance between two points, in km
export function distanceKm(lat1, lon1, lat2, lon2) {
  const rad = (d) => (d * Math.PI) / 180;
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lon2 - lon1) / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Message for when the spot is far from every place the dataset covers ("" if fine)
export function coverageNote(loc, coveragePoints) {
  if (!coveragePoints.length) return "";
  let best = Infinity;
  coveragePoints.forEach((c) => {
    best = Math.min(best, distanceKm(loc.lat, loc.lon, c.lat, c.lon));
  });
  if (best <= FAR_FROM_DATA_KM) return "";
  return "The nearest covered area is about " + Math.round(best) + " km away. You may see few or no dishes here.";
}

// The user's position via the browser, as {lat, lon}
export function getPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Your browser does not support location."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude }),
      (err) => {
        const msg = err.code === err.PERMISSION_DENIED
          ? "Location permission was denied."
          : "Could not get your location.";
        reject(new Error(msg));
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 }
    );
  });
}
