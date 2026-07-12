"""
geocode.py — Turn a street address into (lat, lon) using the US Census
Bureau's free public geocoder (no API key required, US addresses only).

Docs: https://geocoding.geo.census.gov/geocoder/
"""
import requests

CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def geocode(address: str) -> tuple[float, float] | None:
    """Return (lat, lon) for a US street address, or None if no match."""
    resp = requests.get(
        CENSUS_GEOCODER_URL,
        params={"address": address, "benchmark": "Public_AR_Current", "format": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json()["result"]["addressMatches"]
    if not matches:
        return None
    coords = matches[0]["coordinates"]
    return coords["y"], coords["x"]  # lat, lon


if __name__ == "__main__":
    import sys

    addr = " ".join(sys.argv[1:]) or "1600 Holloway Ave, San Francisco, CA"
    result = geocode(addr)
    print(f"{addr} -> {result}")
