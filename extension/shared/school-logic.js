// school-logic.js — shared point-in-polygon / distance-tier logic.
//
// Used by BOTH the extension popup (popup.js) and the GitHub Pages map
// site (map_site/map.js). Kept as one file, copied into both places,
// so the two surfaces never silently disagree on a result (they did,
// briefly, during development — a distance-rounding boundary case gave
// different tier counts in Python vs. JS until both sides rounded to 2
// decimal places before binning. Same fix applies here: round early).
//
// Mirrors the Python implementation in school_finder.py exactly.

const TIERS_MILES = [0.5, 1.0, 2.0];

function haversineMiles(lat1, lon1, lat2, lon2) {
  const r = 3958.8;
  const toRad = (d) => (d * Math.PI) / 180;
  const dphi = toRad(lat2 - lat1);
  const dlambda = toRad(lon2 - lon1);
  const a =
    Math.sin(dphi / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dlambda / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

// Ray-casting point-in-polygon for a single ring (array of [lon, lat] pairs).
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const intersects = ((yi > lat) !== (yj > lat)) &&
      (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi);
    if (intersects) inside = !inside;
  }
  return inside;
}

// geometry.coordinates for MultiPolygon: [ [ [ring...], [hole...] ], ... ]
function pointInMultiPolygon(lon, lat, coordinates) {
  for (const polygon of coordinates) {
    const [exterior, ...holes] = polygon;
    if (!pointInRing(lon, lat, exterior)) continue;
    const inHole = holes.some((hole) => pointInRing(lon, lat, hole));
    if (!inHole) return true;
  }
  return false;
}

function findAttendanceArea(lat, lon, attendanceAreas) {
  for (const feature of attendanceAreas) {
    if (pointInMultiPolygon(lon, lat, feature.geometry.coordinates)) {
      return feature.properties; // { area_name, assigned_school }
    }
  }
  return null;
}

function schoolsByTier(lat, lon, schoolsData, tiersMiles = TIERS_MILES, publicOnly = false) {
  const withDist = schoolsData
    .filter((s) => !publicOnly || s.public)
    .map((s) => ({
      ...s,
      // Round BEFORE binning so this always agrees with the Python side.
      distance_mi: Math.round(haversineMiles(lat, lon, s.lat, s.lon) * 100) / 100,
    }))
    .sort((a, b) => a.distance_mi - b.distance_mi);

  const tiers = [...tiersMiles].sort((a, b) => a - b);
  const bands = {};
  tiers.forEach((t) => (bands[t] = []));
  bands.beyond = [];

  for (const s of withDist) {
    let lower = 0;
    let placed = false;
    for (const t of tiers) {
      if (s.distance_mi > lower && s.distance_mi <= t) {
        bands[t].push(s);
        placed = true;
        break;
      }
      lower = t;
    }
    if (!placed) bands.beyond.push(s);
  }
  return bands;
}
