# map_site — GitHub Pages map for SF School Explorer

A static page that renders search results (assigned SFUSD elementary school
+ nearby schools) on an interactive Google Map. It works standalone (type
an address right on the page — geocoding uses `google.maps.Geocoder`, part
of the Maps JS SDK, which isn't subject to the CORS restriction a raw API
call would hit from a plain webpage) and can also be embedded in the
extension's popup via iframe, passing `?lat=&lon=&address=` in the URL.

## Deploy it (two options for the API key)

Either way, first: get a Google Maps JavaScript API key at
console.cloud.google.com -> create/select a project -> APIs & Services ->
Library -> enable **Maps JavaScript API** -> Credentials -> Create API key.
Then **restrict it**: Credentials -> click the key -> Application
restrictions -> Websites -> `https://YOUR_GITHUB_USERNAME.github.io/*`, and
API restrictions -> limit to Maps JavaScript API only. This restriction is
the real protection here — the key is client-side JS, so it's visible to
anyone who checks the live page's source no matter which option below you
pick; the restriction is what stops someone else from using it.

**Option A — simple (key committed to the repo):**

1. Paste your key into `config.js`, replacing `YOUR_API_KEY_HERE`.
2. Push `map_site/` to a GitHub repo, enable Pages (Settings -> Pages ->
   Deploy from a branch -> `main` / root).
3. Copy the resulting `<pages-url>/map.html` into `../extension/config.js`
   (`MAP_SITE_URL`) if you're using it with the extension.

**Option B — key kept out of git history (GitHub Actions + secret):**

1. Don't touch `config.js` — leave it as the committed placeholder.
2. In the repo: Settings -> Secrets and variables -> Actions -> New
   repository secret. Name it `GOOGLE_MAPS_API_KEY`, paste your key as the
   value.
3. In the repo: Settings -> Pages -> Source -> **GitHub Actions** (not
   "Deploy from a branch").
4. Push `map_site/` including the `.github/workflows/deploy-pages.yml`
   file included here. On push to `main`, the workflow generates `config.js`
   from `config.template.js` + the secret, and deploys it — the filled-in
   `config.js` never gets committed (it's gitignored).
5. For local testing, copy `config.template.js` to `config.js` yourself and
   paste your key in — it won't be committed since `config.js` is
   gitignored.

## Refreshing the data

`schools.json` / `attendance_areas.geojson` in `data/` are static exports —
rerun `python export_for_extension.py` from the project root whenever you
refresh `etl.py`'s data, then push the updated `map_site/data/*` files.

## Using it standalone

`map.html` also works on its own (not just inside the extension's iframe):
`map.html?lat=37.7563&lon=-122.4302&address=800+Sanchez+St` — useful for
testing or sharing a direct link to one result.
