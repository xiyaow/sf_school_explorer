"""
etl.py — Extract, transform, load pipeline for SF school data.

Sources (SF open data portal, Socrata API, no key required):
  - "Schools" dataset (all SF schools, incl. public/private/preschool)
    https://data.sfgov.org/d/7e7j-59qk
  - "SFUSD School Attendance Areas (2024-2025)" (elementary attendance boundaries)
    https://data.sfgov.org/d/e6tr-sxwg

Loads both into a local SQLite database (data/sf_schools.db) so downstream
steps (geocoding, lookup, analysis, mapping) don't need network access.

Usage:
    python etl.py
"""
import json
import sqlite3
import sys
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "sf_schools.db"

SCHOOLS_URL = "https://data.sfgov.org/resource/7e7j-59qk.json"
ATTENDANCE_AREAS_URL = "https://data.sfgov.org/resource/e6tr-sxwg.json"


def fetch_all(url: str, limit: int = 1000) -> list[dict]:
    """Fetch all rows from a Socrata resource (small datasets, single page)."""
    resp = requests.get(url, params={"$limit": limit}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_schools(conn: sqlite3.Connection) -> int:
    rows = fetch_all(SCHOOLS_URL)
    conn.execute("DROP TABLE IF EXISTS schools")
    conn.execute(
        """
        CREATE TABLE schools (
            cds_code TEXT PRIMARY KEY,
            school TEXT,
            district TEXT,
            status TEXT,
            entity_type TEXT,
            educational_program_type TEXT,
            low_grade TEXT,
            high_grade TEXT,
            public_yesno INTEGER,
            charter_yesno INTEGER,
            street_address TEXT,
            street_zip TEXT,
            phone TEXT,
            website TEXT,
            analysis_neighborhood TEXT,
            supervisor_district TEXT,
            latitude REAL,
            longitude REAL
        )
        """
    )
    n = 0
    for r in rows:
        if r.get("status") != "Active":
            continue  # skip pending/not-yet-open schools
        try:
            lat = float(r["latitude"])
            lon = float(r["longitude"])
        except (KeyError, ValueError, TypeError):
            continue  # skip rows we can't place on a map
        conn.execute(
            """
            INSERT OR REPLACE INTO schools VALUES
            (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                r.get("cds_code"),
                r.get("school"),
                r.get("district"),
                r.get("status"),
                r.get("entity_type"),
                r.get("educational_program_type"),
                r.get("low_grade"),
                r.get("high_grade"),
                1 if r.get("public_yesno") else 0,
                1 if r.get("charter_yesno") else 0,
                r.get("street_address"),
                r.get("street_zip"),
                r.get("phone"),
                r.get("website"),
                r.get("analysis_neighborhood"),
                r.get("supervisor_district"),
                lat,
                lon,
            ),
        )
        n += 1
    conn.commit()
    return n


def load_attendance_areas(conn: sqlite3.Connection) -> int:
    rows = fetch_all(ATTENDANCE_AREAS_URL)
    conn.execute("DROP TABLE IF EXISTS attendance_areas")
    conn.execute(
        """
        CREATE TABLE attendance_areas (
            objectid TEXT PRIMARY KEY,
            area_name TEXT,
            school_long_name TEXT,
            geometry_geojson TEXT
        )
        """
    )
    n = 0
    for r in rows:
        geom = r.get("the_geom")
        if not geom:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO attendance_areas VALUES (?,?,?,?)",
            (
                r.get("objectid_1"),
                r.get("aaname"),
                r.get("sch_lng_na"),
                json.dumps(geom),
            ),
        )
        n += 1
    conn.commit()
    return n


def main():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    n_schools = load_schools(conn)
    n_areas = load_attendance_areas(conn)
    conn.close()
    print(f"Loaded {n_schools} active schools -> {DB_PATH}")
    print(f"Loaded {n_areas} elementary attendance areas -> {DB_PATH}")


if __name__ == "__main__":
    sys.exit(main())
