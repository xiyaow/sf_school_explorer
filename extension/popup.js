// SF School Explorer — popup logic
//
// Data flow:
//  1. Bundled data/schools.json + data/attendance_areas.geojson (exported
//     by the Python pipeline's export_for_extension.py) are loaded once.
//  2. User types an address; we geocode it via the free US Census
//     geocoder. Extension pages with host_permissions for that host are
//     exempt from the page-level CORS restriction a plain webpage would
//     hit, so this works with no backend/proxy.
//  3. Point-in-polygon + distance-tier logic lives in shared/school-logic.js
//     (loaded before this file) so it's identical to what map_site/map.js
//     uses, and to school_finder.py on the Python side.
//  4. If config.js defines MAP_SITE_URL (your deployed GitHub Pages map),
//     an iframe embeds a live Google Map of the results.

const CENSUS_GEOCODER = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress";
const DEFAULT_ADDRESS = "800 Sanchez St, San Francisco, CA";

let schoolsData = null;
let attendanceAreas = null;

async function loadData() {
  if (schoolsData && attendanceAreas) return;
  const [schoolsResp, areasResp] = await Promise.all([
    fetch(chrome.runtime.getURL("data/schools.json")),
    fetch(chrome.runtime.getURL("data/attendance_areas.geojson")),
  ]);
  schoolsData = await schoolsResp.json();
  const areasFC = await areasResp.json();
  attendanceAreas = areasFC.features;
}

async function geocode(address) {
  const url = `${CENSUS_GEOCODER}?address=${encodeURIComponent(address)}&benchmark=Public_AR_Current&format=json`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Geocoder request failed (${resp.status})`);
  const json = await resp.json();
  const matches = json.result && json.result.addressMatches;
  if (!matches || matches.length === 0) return null;
  const { x, y } = matches[0].coordinates;
  return { lat: y, lon: x };
}

function tierLabel(lower, upper) {
  return lower === 0 ? `Within ${upper} mi` : `${lower}–${upper} mi`;
}

function schoolCardHtml(s, isAssigned = false) {
  const kind = s.public ? "Public" : "Private";
  const badgeClass = s.public ? "public" : "private";
  return `
    <div class="school-card${isAssigned ? " assigned-school" : ""}">
      <span class="dist">${s.distance_mi.toFixed(2)} mi</span>
      <div class="name">${escapeHtml(s.school)}${isAssigned ? '<span class="badge assigned">Assigned school</span>' : ""}<span class="badge ${badgeClass}">${kind}</span></div>
      <div class="meta">${escapeHtml(s.entity_type)} &middot; grades ${escapeHtml(s.low_grade)}-${escapeHtml(s.high_grade)}</div>
      <div class="meta">${escapeHtml(s.street_address || "")}</div>
      ${websiteLinkHtml(s.website)}
    </div>`;
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function websiteLinkHtml(website) {
  if (!website || website === "No Data") return "";
  const url = /^https?:\/\//i.test(website) ? website : `https://${website}`;
  try {
    const parsed = new URL(url);
    if (!/^https?:$/.test(parsed.protocol)) return "";
    return `<a class="school-website" href="${escapeHtml(parsed.href)}" target="_blank" rel="noopener">School website</a>`;
  } catch {
    return "";
  }
}

function schoolNameKey(name) {
  const genericWords = new Set(["academy", "elementary", "school", "schools", "the"]);
  return String(name || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(" ")
    .filter((word) => word && !genericWords.has(word))
    .sort()
    .join(" ");
}

function isAssignedSchool(school, area) {
  return Boolean(area) && schoolNameKey(school.school) === schoolNameKey(area.assigned_school);
}

function renderMapEmbed(address, coords) {
  const container = document.getElementById("map-embed-container");
  const siteUrl = typeof MAP_SITE_URL !== "undefined" ? MAP_SITE_URL : "";
  if (!siteUrl || siteUrl.includes("YOUR_GITHUB_USERNAME")) {
    container.innerHTML = `<div class="map-placeholder">Map view not configured yet —
      set MAP_SITE_URL in config.js once you've deployed map_site/ to GitHub Pages.</div>`;
    return;
  }
  const params = new URLSearchParams({
    lat: coords.lat,
    lon: coords.lon,
    address,
  });
  container.innerHTML = `<iframe id="map-frame" src="${siteUrl}?${params.toString()}"
    loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>`;
}

function renderResults(address, coords, area, tiers) {
  const resultsEl = document.getElementById("results");
  let html = "";

  html += `<div class="assigned-box">
    <div class="label">Assigned SFUSD elementary attendance area</div>
    ${area
      ? `${escapeHtml(area.area_name)} → ${escapeHtml(area.assigned_school)}`
      : "No elementary attendance boundary at this location (normal for middle/high schoolers, or outside SF)."}
  </div>`;

  const tierKeys = Object.keys(tiers).filter((k) => k !== "beyond").map(Number).sort((a, b) => a - b);
  let lower = 0;
  for (const t of tierKeys) {
    const list = tiers[t];
    html += `<div class="tier">
      <div class="tier-title">${tierLabel(lower, t)} (${list.length})</div>
      ${list.length ? list.map((school) => schoolCardHtml(school, isAssignedSchool(school, area))).join("") : '<div class="meta" style="color:#999;">No schools in this band.</div>'}
    </div>`;
    lower = t;
  }

  resultsEl.innerHTML = html;
  renderMapEmbed(address, coords);
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = isError ? "error" : "";
}

document.getElementById("search-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const addressInput = document.getElementById("address-input");
  const address = addressInput.value.trim() || DEFAULT_ADDRESS;
  addressInput.value = address;
  const publicOnly = document.getElementById("public-only").checked;
  const btn = document.getElementById("search-btn");
  document.getElementById("results").innerHTML = "";
  document.getElementById("map-embed-container").innerHTML = "";

  btn.disabled = true;
  setStatus("Loading school data…");
  try {
    await loadData();
    setStatus("Geocoding address…");
    const coords = await geocode(address);
    if (!coords) {
      setStatus("Couldn't find that address. Try including city and state, e.g. \"123 Main St, San Francisco, CA\".", true);
      return;
    }
    setStatus("");
    const area = findAttendanceArea(coords.lat, coords.lon, attendanceAreas);
    const tiers = schoolsByTier(coords.lat, coords.lon, schoolsData, TIERS_MILES, publicOnly);
    renderResults(address, coords, area, tiers);
  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, true);
  } finally {
    btn.disabled = false;
  }
});

// Warm the bundled data on popup open so the first search feels instant.
loadData().catch((err) => console.error("Failed to preload data", err));
