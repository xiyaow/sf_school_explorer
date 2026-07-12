"""
school_finder.py — Given a point (or address), find:
  1. The assigned SFUSD elementary attendance-area school (if any).
  2. Nearby schools of any type (public/private/preschool/etc.), grouped
     into distance bands (default: within 0.5mi / within 1mi / within 2mi),
     sorted by distance within each band.

This is the core "useful" piece: a parent can plug in a candidate home
address and get a concrete, ranked list of school options plus their
attendance-area assignment, instead of manually cross-referencing SFUSD's
boundary maps against a list of private/preschool options.

Note on distance tiers: San Francisco is a small city — the farthest apart
any two schools in the "Schools" dataset are is ~7.6 miles. Tiers of
0.5 / 1 / 2 miles are chosen because they roughly map to "walkable",
"short drive/bike", and "cross-neighborhood" — much more useful
distinctions within SF than 5/10/15mi, which would just return
"the whole city" from almost any address.
"""
import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import Point, shape

from geocode import geocode

DB_PATH = Path(__file__).parent / "data" / "sf_schools.db"

DEFAULT_TIERS_MILES = (0.5, 1.0, 2.0)


@dataclass
class School:
    school: str
    entity_type: str
    low_grade: str
    high_grade: str
    public: bool
    street_address: str
    neighborhood: str
    website: str
    phone: str
    lat: float
    lon: float
    distance_mi: float = None


def haversine_miles(lat1, lon1, lat2, lon2) -> float:
    r = 3958.8  # earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _connect():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"{DB_PATH} not found — run etl.py first.")
    return sqlite3.connect(DB_PATH)


def find_attendance_area(lat: float, lon: float) -> dict | None:
    conn = _connect()
    pt = Point(lon, lat)  # shapely uses (x=lon, y=lat)
    cur = conn.execute("SELECT area_name, school_long_name, geometry_geojson FROM attendance_areas")
    for area_name, school_long_name, geom_json in cur.fetchall():
        poly = shape(json.loads(geom_json))
        if poly.contains(pt):
            conn.close()
            return {"area_name": area_name, "assigned_school": school_long_name}
    conn.close()
    return None


def _all_schools_with_distance(
    lat: float,
    lon: float,
    public_only: bool = False,
    entity_types: list[str] | None = None,
) -> list[School]:
    conn = _connect()
    cur = conn.execute(
        """
        SELECT school, entity_type, low_grade, high_grade, public_yesno,
               street_address, analysis_neighborhood, website, phone,
               latitude, longitude
        FROM schools
        """
    )
    results = []
    for row in cur.fetchall():
        (school, entity_type, low_grade, high_grade, public_yesno,
         street_address, neighborhood, website, phone, slat, slon) = row
        if public_only and not public_yesno:
            continue
        if entity_types and entity_type not in entity_types:
            continue
        d = haversine_miles(lat, lon, slat, slon)
        results.append(
            School(
                school=school, entity_type=entity_type, low_grade=low_grade,
                high_grade=high_grade, public=bool(public_yesno),
                street_address=street_address, neighborhood=neighborhood,
                website=website, phone=phone, lat=slat, lon=slon,
                distance_mi=round(d, 2),
            )
        )
    conn.close()
    results.sort(key=lambda s: s.distance_mi)
    return results


def nearby_schools(
    lat: float,
    lon: float,
    radius_mi: float = 1.0,
    public_only: bool = False,
    entity_types: list[str] | None = None,
    limit: int = 25,
) -> list[School]:
    all_schools = _all_schools_with_distance(lat, lon, public_only, entity_types)
    return [s for s in all_schools if s.distance_mi <= radius_mi][:limit]


def schools_by_tier(
    lat: float,
    lon: float,
    tiers_miles: tuple = DEFAULT_TIERS_MILES,
    public_only: bool = False,
    entity_types: list[str] | None = None,
) -> dict:
    all_schools = _all_schools_with_distance(lat, lon, public_only, entity_types)
    tiers = sorted(tiers_miles)
    bands = {t: [] for t in tiers}
    bands["beyond"] = []
    for s in all_schools:
        placed = False
        lower = 0.0
        for t in tiers:
            if lower < s.distance_mi <= t:
                bands[t].append(s)
                placed = True
                break
            lower = t
        if not placed:
            bands["beyond"].append(s)
    return bands


def summarize_address(address: str, tiers_miles: tuple = DEFAULT_TIERS_MILES) -> dict:
    coords = geocode(address)
    if coords is None:
        return {"address": address, "error": "Could not geocode this address."}
    lat, lon = coords
    area = find_attendance_area(lat, lon)
    tiers = schools_by_tier(lat, lon, tiers_miles=tiers_miles)
    return {
        "address": address,
        "lat": lat,
        "lon": lon,
        "assigned_elementary_attendance_area": area,
        "schools_by_tier": tiers,
    }


def _fmt_tier_label(lower: float, upper) -> str:
    if upper == "beyond":
        return f"beyond {lower} mi"
    return f"within {upper} mi" if lower == 0 else f"{lower}–{upper} mi"


if __name__ == "__main__":
    import sys

    addr = " ".join(sys.argv[1:]) or "1600 Holloway Ave, San Francisco, CA"
    result = summarize_address(addr)
    print(f"\nAddress: {result['address']}")
    if "error" in result:
        print(result["error"])
        sys.exit(1)
    print(f"Coordinates: {result['lat']:.5f}, {result['lon']:.5f}")
    area = result["assigned_elementary_attendance_area"]
    if area:
        print(f"Assigned SFUSD elementary attendance area: {area['area_name']} "
              f"-> {area['assigned_school']}")
    else:
        print("No SFUSD elementary attendance area found at this point "
              "(outside SF or outside all mapped boundaries).")

    tiers = result["schools_by_tier"]
    lower = 0.0
    tier_keys = [k for k in tiers if k != "beyond"]
    for t in tier_keys:
        label = _fmt_tier_label(lower, t)
        print(f"\n-- {label} ({len(tiers[t])} schools) --")
        for s in tiers[t]:
            kind = "Public" if s.public else "Private"
            print(f"  {s.distance_mi:>5.2f} mi  [{kind:7s}] {s.school} "
                  f"({s.entity_type}, grades {s.low_grade}-{s.high_grade})")
        lower = t
