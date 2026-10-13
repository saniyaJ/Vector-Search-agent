// Minimum-rating filter (checkbox + slider).
const ratingEnabled = document.getElementById("rating-enabled");
const ratingToggle = document.getElementById("rating-toggle");
const ratingSlider = document.getElementById("rating");
const ratingValue = document.getElementById("rating-value");

// The minimum rating to send to the API, or null when the filter is off
export function getMinRating() {
  return ratingEnabled.checked ? Number(ratingSlider.value) : null;
}

function syncRatingUI() {
  const on = ratingEnabled.checked;
  ratingSlider.disabled = !on;
  ratingToggle.classList.toggle("on", on);
  ratingValue.classList.toggle("on", on);
  ratingValue.textContent = on ? "≥ " + Number(ratingSlider.value).toFixed(1) : "Any";
}

// onChange() is called when the filter should re-run the search
export function initRatingFilter(onChange) {
  ratingEnabled.addEventListener("change", () => {
    syncRatingUI();
    onChange();
  });
  ratingSlider.addEventListener("input", syncRatingUI);
  // Re-run the search once the user lets go of the slider
  ratingSlider.addEventListener("change", onChange);
  syncRatingUI();
}
