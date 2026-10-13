// Results area: loading skeletons, empty/error states and the result cards.
import { el } from "./dom.js";
import { updateMap } from "./map.js";

const resultsEl = document.getElementById("results");

export function showLoading() {
  resultsEl.replaceChildren();
  const grid = el("div", "grid");
  grid.style.marginTop = "34px";
  for (let i = 0; i < 3; i++) grid.appendChild(el("div", "skeleton"));
  resultsEl.appendChild(grid);
}

export function showState(message, isError) {
  updateMap([]); // nothing to plot for an empty or failed result
  resultsEl.replaceChildren();
  const box = el("div", "state" + (isError ? " error" : ""), message);
  box.style.marginTop = "34px";
  resultsEl.appendChild(box);
}

// The stored chunk looks like "Product name: X. Description: Y. Categories - Z".
// Show only the description part.
function cleanDescription(chunk) {
  if (!chunk) return "";
  let text = chunk;
  const m = chunk.match(/Description:\s*([\s\S]*?)(?:\.?\s*Categories\s*-|$)/i);
  if (m) {
    text = m[1];
  } else {
    text = chunk.replace(/^Product name:[^.]*\.\s*/i, "");
  }
  text = text.trim();
  if (/^(none|null|nan)$/i.test(text)) return "";
  return text;
}

function buildCard(p, showMatch) {
  const card = el("article", "card");

  const photo = el("div", "photo");
  const img = document.createElement("img");
  img.alt = p.product_name || "Food";
  img.loading = "lazy";
  img.src = p.image_url;
  img.addEventListener("error", () => img.remove());
  photo.appendChild(img);
  if (showMatch) photo.appendChild(el("span", "match", "Match " + Number(p.score).toFixed(3)));
  card.appendChild(photo);

  const meta = el("div", "meta");
  meta.appendChild(el("span", "cafe", p.cafe_name));
  if (p.rating !== null && p.rating !== undefined) {
    meta.appendChild(el("span", "rating", "★ " + Number(p.rating).toFixed(1)));
  }
  card.appendChild(meta);

  card.appendChild(el("h3", "", p.product_name));

  const desc = cleanDescription(p.description);
  if (desc) card.appendChild(el("p", "desc", desc));

  if (p.address) {
    const addr = el("p", "address");
    addr.appendChild(el("span", "", "📍"));
    addr.appendChild(el("span", "", p.address));
    card.appendChild(addr);
  }
  return card;
}

// opts: {label, subtitle, empty, showMatch}
export function renderResults(products, opts) {
  if (!products.length) {
    showState(opts.empty, false);
    return;
  }

  resultsEl.replaceChildren();
  updateMap(products);

  const head = el("div", "results-head");
  const left = el("div");
  left.appendChild(el("p", "label", opts.label));
  left.appendChild(el("p", "", opts.subtitle));
  head.appendChild(left);
  head.appendChild(el("span", "count", products.length + (products.length === 1 ? " food" : " foods")));
  resultsEl.appendChild(head);

  const grid = el("div", "grid");
  products.forEach((p) => grid.appendChild(buildCard(p, opts.showMatch)));
  resultsEl.appendChild(grid);
}
