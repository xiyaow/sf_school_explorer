// map.js — renders the Google Map for a searched address.
//
// Hosted on GitHub Pages (static, no backend). Works two ways:
//   1. Standalone: type an address in the search box on this page.
//      Geocoding uses google.maps.Geocoder (part of the Maps JS SDK
//      already loaded on this page) — unlike a raw fetch() to a
//      geocoding REST API, this isn't subject to browser CORS
//      restrictions, so no extension/backend is needed for this path.
//   2. Embedded: opened with ?lat=...&lon=...&address=... in the URL
//      (e.g. from the extension's iframe), which skips geocoding and
//      renders directly from the given coordinates.
//
// Either way, point-in-polygon / distance-tier logic comes from
// shared/school-logic.js — same logic as the extension popup and
// school_finder.py, so results always agree across all three surfaces.

let map;
let geocoder;
let schoolsData, attendanceAreas;
let activeMarkers = [];
let activePolygons = [];

function markerColor(school, isAssigned) {
  if (isAssigned) return "#f9a825";
  if (school.entity_type === "Preschool") return "#6a1b9a";
  return school.public ? "#256d34" : "#a45c0a";
}

function getParams() {
  const p = new URLSearchParams(window.location.search);
  const lat = parseFloat(p.get("lat"));
  const lon = parseFloat(p.get("lon"));
  const address = p.get("address") || "";
  if (Number.isNaN(lat) || Number.isNaN(lon)) return null;
  return { lat, lon, address };
}

function showError(msg) {
  const el = document.getElementById("error-banner");
  el.hidden = false;
  el.textContent = msg;
}

function clearError() {
  document.getElementById("error-banner").hidden = true;
}

function setStatus(msg, isError = false) {
  const el = document.getElementById("status");
  el.textContent = msg;
  el.className = isError ? "error" : "";
}

async function loadSchoolData() {
  if (schoolsData && attendanceAreas) return;
  const [schoolsResp, areasResp] = await Promise.all([
    fetch("data/schools.json"),
    fetch("data/attendance_areas.geojson"),
  ]);
  schoolsData = await schoolsResp.json();
  attendanceAreas = (await areasResp.json()).features;
}

function geocodeWithGoogle(address) {
  return new Promise((resolve, reject) => {
    geocoder.geocode({ address }, (results, status) => {
      if (status === "OK" && results && results[0]) {
        const loc = results[0].geometry.location;
        resolve({ lat: loc.lat(), lon: loc.lng() });
      } else {
        reject(new Error(`Couldn't find that address (${status}).`));
      }
    });
  });
}

function clearOverlays() {
  activeMarkers.forEach((m) => m.setMap(null));
  activePolygons.forEach((p) => p.setMap(null));
  activeMarkers = [];
  activePolygons = [];
}

function tierLabel(lower, upper) {
  return lower === 0 ? `Within ${upper} mi` : `${lower}–${upper} mi`;
}

function escapeHtml(str) {
  if (str == null) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function schoolCardHtml(s) {
  const kind = s.public ? "Public" : "Private";
  const badgeClass = s.public ? "public" : "private";
  return `
    <div class="school-card">
      <span class="dist">${s.distance_mi.toFixed(2)} mi</span>
      <div class="name">${escapeHtml(s.school)}<span class="badge ${badgeClass}">${kind}</span></div>
      <div class="meta">${escapeHtml(s.entity_type)} &middot; grades ${escapeHtml(s.low_grade)}-${escapeHtml(s.high_grade)}</div>
      <div class="meta">${escapeHtml(s.street_address || "")}</div>
    </div>`;
}

function renderResultsPanel(area, tiers) {
  const resultsEl = document.getElementById("results");
  let html = `<div class="assigned-box">
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
      ${list.length ? list.map(schoolCardHtml).join("") : '<div class="meta" style="color:#999;">No schools in this band.</div>'}
    </div>`;
    lower = t;
  }
  resultsEl.innerHTML = html;
}

async function renderForCoords(lat, lon, address, publicOnly = false) {
  clearError();
  clearOverlays();
  await loadSchoolData();

  map.setCenter({ lat, lng: lon });
  map.setZoom(15);

  const bounds = new google.maps.LatLngBounds();

  const addressMarker = new google.maps.Marker({
    position: { lat, lng: lon },
    map,
    title: address || "Searched address",
    icon: {
      path: google.maps.SymbolPath.CIRCLE,
      scale: 8,
      fillColor: "#1565c0",
      fillOpacity: 1,
      strokeColor: "#fff",
      strokeWeight: 2,
    },
  });
  activeMarkers.push(addressMarker);
  bounds.extend(addressMarker.getPosition());

  const area = findAttendanceArea(lat, lon, attendanceAreas);
  const areaFeature = attendanceAreas.find(
    (f) => area && f.properties.area_name === area.area_name
  );
  if (areaFeature) {
    for (const polygon of areaFeature.geometry.coordinates) {
      const [exterior] = polygon;
      const path = exterior.map(([plon, plat]) => ({ lat: plat, lng: plon }));
      const poly = new google.maps.Polygon({
        paths: path,
        strokeColor: "#f9a825",
        strokeOpacity: 0.9,
        strokeWeight: 2,
        fillColor: "#f9a825",
        fillOpacity: 0.12,
        map,
      });
      activePolygons.push(poly);
      path.forEach((pt) => bounds.extend(pt));
    }
  }

  const tiers = schoolsByTier(lat, lon, schoolsData, TIERS_MILES, publicOnly);
  const toPlot = [...tiers[0.5], ...tiers[1.0]];

  const infoWindow = new google.maps.InfoWindow();
  for (const school of toPlot) {
    const isAssigned = area && school.school === area.assigned_school;
    const marker = new google.maps.Marker({
      position: { lat: school.lat, lng: school.lon },
      map,
      title: school.school,
      icon: {
        path: google.maps.SymbolPath.CIRCLE,
        scale: isAssigned ? 9 : 6,
        fillColor: markerColor(school, isAssigned),
        fillOpacity: 1,
        strokeColor: "#fff",
        strokeWeight: 1.5,
      },
    });
    marker.addListener("click", () => {
      infoWindow.setContent(`
        <div style="font-size:13px;max-width:220px;">
          <strong>${school.school}</strong><br>
          ${school.entity_type} &middot; grades ${school.low_grade}-${school.high_grade}<br>
          ${school.public ? "Public" : "Private"} &middot; ${school.distance_mi.toFixed(2)} mi away<br>
          ${school.street_address || ""}
        </div>`);
      infoWindow.open(map, marker);
    });
    activeMarkers.push(marker);
    bounds.extend(marker.getPosition());
  }

  map.fitBounds(bounds);
  renderResultsPanel(area, tiers);
}

async function handleSearch(address, publicOnly) {
  if (!address) return;
  const btn = document.getElementById("search-btn");
  btn.disabled = true;
  setStatus("Geocoding address…");
  try {
    const coords = await geocodeWithGoogle(address);
    setStatus("");
    await renderForCoords(coords.lat, coords.lon, address, publicOnly);
  } catch (err) {
    console.error(err);
    setStatus(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

async function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: 37.7749, lng: -122.4194 },
    zoom: 12,
  });
  geocoder = new google.maps.Geocoder();

  document.getElementById("search-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const address = document.getElementById("address-input").value.trim();
    const publicOnly = document.getElementById("public-only").checked;
    handleSearch(address, publicOnly);
  });

  // If opened with ?lat=&lon= (e.g. from the extension's iframe), skip
  // geocoding and render directly.
  const params = getParams();
  if (params) {
    document.getElementById("address-input").value = params.address || "";
    await loadSchoolData();
    renderForCoords(params.lat, params.lon, params.address, false);
  }
}
