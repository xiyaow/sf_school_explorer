# SF School Explorer

This GitHub Pages site is the public map view for **SF School Explorer**. Type a
San Francisco address, and it shows:

- the assigned SFUSD elementary attendance area for that address
- the closest schools in the bundled school dataset
- school details such as address, grade range, distance, and website when the
  source data includes one

[Open the interactive map](map.html)

## Project Architecture

```text
DataSF APIs
  -> etl.py
     pulls raw school and attendance-area records into SQLite
  -> school_finder.py / shared school logic
     matches an address point to an attendance polygon and computes distances
  -> export_for_extension.py
     exports static JSON and GeoJSON files
  -> docs/
     serves the GitHub Pages map with no backend server
```

The live map is a static frontend. It loads:

- `data/schools.json` for school names, locations, grade ranges, addresses,
  school type, and website fields
- `data/attendance_areas.geojson` for SFUSD elementary attendance-area polygons
- `shared/school-logic.js` for point-in-polygon lookup and distance grouping
- Google Maps JavaScript API and Geocoding API for the map display and address
  search

Because the data is exported into static files, GitHub Pages can host the app
without a Python server or database running behind it.

## Data Sources

- [Schools](https://data.sfgov.org/d/7e7j-59qk) from DataSF, resource
  `7e7j-59qk`. This includes public, private, and preschool records with
  location fields and school attributes.
- [SFUSD School Attendance Areas (2024-2025)](https://data.sfgov.org/d/e6tr-sxwg)
  from DataSF, resource `e6tr-sxwg`. This provides elementary attendance-area
  boundary polygons.
- [Google Maps Platform](https://developers.google.com/maps/documentation)
  powers the interactive map and address geocoding on this static page.

The original Python pipeline pulls the DataSF records through the Socrata REST
API at `https://data.sfgov.org/resource/<resource-id>.json`.

## Refreshing The Published Data

From the project root, run:

```bash
python etl.py
python export_for_extension.py
```

Then commit and push the updated files under `docs/data/`. GitHub Pages will
serve the refreshed static exports after the repository updates.

## Local Testing

From the `docs/` folder:

```bash
python -m http.server 8000
```

Then open `http://localhost:8000/map.html`.

For local search to work, the Google API key used by `config.js` needs both
**Maps JavaScript API** and **Geocoding API** enabled, and the key's website
restriction should include the local test origin, for example
`http://localhost:8000/*`.
