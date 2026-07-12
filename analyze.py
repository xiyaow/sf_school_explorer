"""
analyze.py — Two analyses aimed at the "where should I live / which school
will my toddler get" question:

  1. Citywide neighborhood summary: for every SF neighborhood, how many
     public elementary schools, private elementary schools, and preschools
     it has. A quick way to spot "school-dense" vs "school-sparse" areas.

  2. Candidate-address comparison: for a shortlist of addresses (e.g. a
     current rental vs. a few places being considered), show the assigned
     SFUSD elementary attendance area and nearby preschool/elementary
     options for each — side by side.

Edit CANDIDATE_ADDRESSES below with real addresses to compare, then run:
    python analyze.py
Outputs land in output/neighborhood_summary.csv and output/address_comparison.csv
"""
import sqlite3
from pathlib import Path

import pandas as pd

from school_finder import summarize_address

DB_PATH = Path(__file__).parent / "data" / "sf_schools.db"
OUTPUT_DIR = Path(__file__).parent / "output"

CANDIDATE_ADDRESSES = [
    "800 Sanchez St, San Francisco, CA",       # Noe Valley / Mission border
    "1600 Holloway Ave, San Francisco, CA",    # Lakeshore / SFSU area
    "600 Clement St, San Francisco, CA",       # Inner Richmond
    "3200 24th St, San Francisco, CA",         # Mission
    "100 Joost Ave, San Francisco, CA",        # Glen Park / Sunnyside
]


def neighborhood_summary() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM schools", conn)
    conn.close()

    df["category"] = df["entity_type"].apply(_categorize)
    pivot = (
        df.groupby(["analysis_neighborhood", "category"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=["Preschool", "Public Elementary", "Private Elementary", "Other"], fill_value=0)
    )
    pivot["total_schools"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total_schools", ascending=False)
    return pivot


def _categorize(entity_type: str) -> str:
    if entity_type == "Preschool":
        return "Preschool"
    if "Elementary" in entity_type and "Public" in entity_type:
        return "Public Elementary"
    if "Elementary" in entity_type and "Private" in entity_type:
        return "Private Elementary"
    return "Other"


def address_comparison(addresses: list[str]) -> pd.DataFrame:
    """Compare candidate addresses using the same 0.5 / 1 / 2 mile tiers
    the search tool (school_finder.py) uses, so the numbers here match
    what a user sees in the extension."""
    rows = []
    for addr in addresses:
        info = summarize_address(addr)
        if "error" in info:
            rows.append({"address": addr, "error": info["error"]})
            continue
        tiers = info["schools_by_tier"]
        within_half_mi = tiers[0.5]
        within_1mi = within_half_mi + tiers[1.0]  # cumulative
        preschools_1mi = [s for s in within_1mi if s.entity_type == "Preschool"]
        pub_elem_1mi = [s for s in within_1mi if "Elementary" in s.entity_type and "Public" in s.entity_type]
        priv_elem_1mi = [s for s in within_1mi if "Elementary" in s.entity_type and "Private" in s.entity_type]
        area = info["assigned_elementary_attendance_area"]
        rows.append(
            {
                "address": addr,
                "assigned_elementary_school": area["assigned_school"] if area else "N/A",
                "nearest_preschool_mi": min((s.distance_mi for s in preschools_1mi), default=None),
                "preschools_within_1mi": len(preschools_1mi),
                "public_elem_within_1mi": len(pub_elem_1mi),
                "private_elem_within_1mi": len(priv_elem_1mi),
            }
        )
    df = pd.DataFrame(rows)
    if "error" in df.columns and df["error"].isna().all():
        df = df.drop(columns=["error"])
    return df


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("=== Citywide neighborhood school-density summary (top 15) ===")
    ns = neighborhood_summary()
    print(ns.head(15).to_string())
    ns.to_csv(OUTPUT_DIR / "neighborhood_summary.csv")

    print("\n=== Candidate address comparison ===")
    comp = address_comparison(CANDIDATE_ADDRESSES)
    print(comp.to_string(index=False))
    comp.to_csv(OUTPUT_DIR / "address_comparison.csv", index=False)

    print(f"\nSaved: {OUTPUT_DIR/'neighborhood_summary.csv'}")
    print(f"Saved: {OUTPUT_DIR/'address_comparison.csv'}")


if __name__ == "__main__":
    main()
