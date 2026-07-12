"""
export_for_extension.py — Export the cleaned SQLite data to lightweight
static JSON/GeoJSON files, written to BOTH the browser extension
(extension/data/) and the GitHub Pages map site (map_site/data/) so
neither needs a live DataSF fetch at runtime.

This is the hand-off point between the Python ETL/analysis side of the
project and the JS presentation layer: run etl.py, then this script,
whenever the underlying DataSF datasets are refreshed.

Usage:
    python export_for_extension.py
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sf_schools.db"
OUTPUT_DATA_DIRS = [
    Path(__file__).parent / "extension" / "data",
    Path(__file__).parent / "map_site" / "data",
]

# ~1 meter precision is plenty for polygon boundaries at this scale; the
# source data ships 14-15 decimal places, which just bloats the bundle.
COORD_PRECISION = 6


def _round_coords(node):
    """Recursively round every coordinate pair in a GeoJSON geometry."""
    if isinstance(node, list):
        if node and isinstance(node[0], (int, float)):
            return [round(c, COORD_PRECISION) for c in node]
        return [_round_coords(child) for child in node]
    return node


def _build_schools_payload(conn: sqlite3.Connection) -> list:
    cur = conn.execute(
        """
        SELECT school, entity_type, low_grade, high_grade, public_yesno,
               street_address, street_zip, phone, website,
               analysis_neighborhood, latitude, longitude
        FROM schools
        """
    )
    schools = []
    for row in cur.fetchall():
        (school, entity_type, low_grade, high_grade, public_yesno,
         street_address, street_zip, phone, website, neighborhood, lat, lon) = row
        schools.append(
            {
                "school": school,
                "entity_type": entity_type,
                "low_grade": low_grade,
                "high_grade": high_grade,
                "public": bool(public_yesno),
                "street_address": street_address,
                "street_zip": street_zip,
                "phone": phone,
                "website": website,
                "neighborhood": neighborhood,
                "lat": lat,
                "lon": lon,
            }
        )
    return schools


def _build_attendance_areas_payload(conn: sqlite3.Connection) -> dict:
    cur = conn.execute("SELECT area_name, school_long_name, geometry_geojson FROM attendance_areas")
    features = []
    for area_name, school_long_name, geom_json in cur.fetchall():
        geometry = json.loads(geom_json)
        geometry["coordinates"] = _round_coords(geometry["coordinates"])
        features.append(
            {
                "type": "Feature",
                "properties": {"area_name": area_name, "assigned_school": school_long_name},
                "geometry": geometry,
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main():
    conn = sqlite3.connect(DB_PATH)
    schools = _build_schools_payload(conn)
    areas_fc = _build_attendance_areas_payload(conn)
    conn.close()

    schools_json = json.dumps(schools, separators=(",", ":"))
    areas_json = json.dumps(areas_fc, separators=(",", ":"))

    for out_dir in OUTPUT_DATA_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "schools.json").write_text(schools_json)
        (out_dir / "attendance_areas.geojson").write_text(areas_json)
        print(f"Exported {len(schools)} schools -> {out_dir/'schools.json'}")
        print(f"Exported {len(areas_fc['features'])} attendance areas -> {out_dir/'attendance_areas.geojson'}")


if __name__ == "__main__":
    main()
