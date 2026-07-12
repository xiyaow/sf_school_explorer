# SF School Explorer

A small end-to-end data project built on [DataSF](https://data.sfgov.org)'s open
data: given any San Francisco address, find the assigned SFUSD elementary
school and nearby school options (public, private, preschool) grouped by
distance.

## Why this exists

A friend with a 2-year-old is trying to decide whether to stay in her current
rental or move, and which San Francisco neighborhoods make sense given school
options. There's no single place that answers "what school would my kid be
zoned for here, and what else is nearby?" — SFUSD publishes attendance-area
maps and a school list separately, and neither is easy to check against a
specific address. This project pulls both together.

It's also a small demonstration of a data pipeline built entirely on data San
Francisco's own city government publishes — extract, clean, model, and ship
to an actual interface — relevant context if you're wondering why this repo
exists at all.

## What it does

1. **Ingests** two DataSF datasets via the Socrata API: the citywide list of
   schools (public/private/preschool, with location and grade range) and
   SFUSD's elementary school attendance-area boundaries.
2. **Models** the data into a local SQLite database (raw → cleaned tables).
3. **Answers two questions**:
   - *Address lookup*: geocode an address, point-in-polygon match it against
     attendance-area boundaries, and list nearby schools grouped into
     0.5 / 1 / 2 mile bands (chosen because SF is only ~7.5 miles across at
     its widest — 5/10/15mi bands would just return "the whole city").
   - *Neighborhood comparison*: citywide school-density by neighborhood, and
     a side-by-side comparison across a shortlist of candidate addresses.
4. **Ships** as a Chrome extension popup — type an address, get results —
   using the same lookup logic reimplemented in JS against a static data
   export, so it works with no backend server.
5. **Optionally renders a live Google Map** of the results via a small
   GitHub Pages site (`map_site/`), which also works fully standalone (its
   own address search box, no extension required) and can additionally be
   embedded in the extension popup as an iframe — see
   [map_site/README.md](map_site/README.md) for setup. This is optional:
   without it configured, the extension still shows full text results, just
   no map.

## Data sources

- [Schools](https://data.sfgov.org/d/7e7j-59qk) — CDE's list of all SF schools (resource `7e7j-59qk`)
- [SFUSD School Attendance Areas (2024-2025)](https://data.sfgov.org/d/e6tr-sxwg) — elementary boundary polygons (resource `e6tr-sxwg`)
- Geocoding: [US Census Bureau geocoder](https://geocoding.geo.census.gov/geocoder/) (free, no API key, US addresses only) for the Python CLI/extension; `google.maps.Geocoder` for the standalone map site.

Both DataSF datasets are pulled live via the Socrata REST API
(`https://data.sfgov.org/resource/<id>.json`) — no scraping, no key required.

## Project structure

```
sf_school_explorer/
├── etl.py                    # Extract + load DataSF datasets into SQLite
├── geocode.py                 # Address -> lat/lon via Census geocoder
├── school_finder.py           # Core logic: attendance-area match + distance tiers
├── analyze.py                  # Neighborhood density + candidate-address comparison
├── export_for_extension.py     # SQLite -> static JSON/GeoJSON for extension + map_site
├── .gitignore                  # Excludes the regenerable SQLite cache
├── data/
│   └── sf_schools.db           # Local cache (created by etl.py, gitignored)
├── output/
│   ├── neighborhood_summary.csv
│   └── address_comparison.csv
├── extension/                  # Chrome extension (Manifest V3)
│   ├── manifest.json
│   ├── config.js               # <- paste your deployed map_site URL here
│   ├── popup.html / popup.css / popup.js
│   ├── shared/school-logic.js  # Point-in-polygon + distance-tier logic (JS)
│   ├── icons/
│   └── data/                   # Static export (created by export_for_extension.py)
│       ├── schools.json
│       └── attendance_areas.geojson
└── map_site/                   # Optional: GitHub Pages map (see map_site/README.md)
    ├── map.html / map.css / map.js
    ├── config.js                # <- paste your Google Maps API key here (or use secrets, see its README)
    ├── shared/school-logic.js   # Same file as extension/shared/ (copy)
    └── data/                    # Static export (same as extension/data/)
```

**Note on repos:** `map_site/` is included here as part of the full project,
but is typically also pushed to its *own* separate GitHub repo so it can be
deployed via GitHub Pages independently (Pages serves from a repo root/branch,
so keeping it separate is simpler than trying to serve a subfolder of this
repo). This repo is the one to point people at for the actual data
engineering work; the map_site repo is just the deployed artifact.

## Setup

```bash
pip install requests shapely pandas

python etl.py                    # pulls fresh data from DataSF, builds sf_schools.db
python school_finder.py "800 Sanchez St, San Francisco, CA"   # quick CLI check
python analyze.py                # neighborhood + candidate-address CSVs
python export_for_extension.py   # refresh the extension's bundled data
```

### Loading the Chrome extension

1. Open `chrome://extensions`
2. Turn on **Developer mode** (top right)
3. Click **Load unpacked** and select the `extension/` folder
4. Click the extension icon, type an address, hit Search

Because the extension declares `host_permissions` for the Census geocoder in
its manifest, it can call that API directly from the popup — a plain webpage
can't, since the geocoder doesn't send CORS headers. (DataSF's own API does
support CORS, so the school/boundary data could also be fetched live; it's
bundled as a static export instead, for speed and to keep the extension
working offline.)

### Optional: enabling the map

By default the popup works fully without a map (text results only). To add
the interactive Google Map, see [map_site/README.md](map_site/README.md) —
short version: get a free-tier Google Maps API key, deploy `map_site/` to
GitHub Pages, paste the resulting URL into `extension/config.js`.

## Example

```
$ python school_finder.py "800 Sanchez St, San Francisco, CA"

Assigned SFUSD elementary attendance area: Milk -> Harvey Milk Civil Rights Academy

-- within 0.5 mi (12 schools) --
   0.13 mi  [Public ] Mahler (Theresa S.) Children Center (Preschool, grades P-P)
   0.24 mi  [Public ] Thomas Edison Charter Academy (Elementary Schools (Public), grades K-8)
   ...
```

## Limitations

- **No quality/performance data.** DataSF doesn't publish SFUSD test scores or
  ratings — that lives with the CA Department of Education (CAASPP) or sites
  like GreatSchools. This project surfaces *options and distance*, not
  *quality*; worth pairing with those sources before making a decision.
- **No rent/price data.** DataSF doesn't publish market rent data either, so
  this doesn't directly answer the "worth moving for" question — only the
  "what schools would I have access to" half of it.
- **Attendance areas only exist for elementary schools.** SFUSD assigns
  middle and high schools through a choice process, not fixed boundaries, so
  `assigned_elementary_attendance_area` is the only guaranteed zoning result.
- **Geocoding is US-only** and occasionally fails on very new addresses or
  unusual formatting — try adding the ZIP code if a lookup comes back empty.

## If this were going into production

This runs locally against SQLite for simplicity, but the shape of a
production version would change:

- **Warehouse**: SQLite → Snowflake/BigQuery, with the transformation layer
  written as SQL models (dbt) instead of inline Python — staging tables for
  raw ingested data, mart tables for the address-lookup and neighborhood
  views.
- **Orchestration**: `etl.py` running manually → scheduled via Airflow or
  Dagster, since DataSF updates these datasets periodically.
- **Infra**: hand-run scripts → Terraform-managed warehouse/compute
  resources, so the pipeline is reproducible and version-controlled.
- **Data quality**: add basic checks (no null coordinates, no duplicate
  school IDs, attendance-area polygons that don't overlap) as dbt tests or
  a lightweight assertion layer, run on every load.
