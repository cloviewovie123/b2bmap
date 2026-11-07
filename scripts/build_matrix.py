"""Build the driving-time table the web page uses for the route planner.

GitHub Pages can't run Python, so the page can't ask OR-Tools for a route live.
Instead we measure the real driving time and distance between EVERY pair of places
once (Fremont + all sites), save them in docs/data/matrix.json, and the page uses
that table to compare routes for whatever stops you click.

Run again whenever sites.json changes:   .venv/Scripts/python scripts/build_matrix.py
"""
import json, requests

data = json.load(open("data/clean/sites.json"))
d = data["depot"]
places = [{"name": d["name"], "lat": d["lat"], "lon": d["lon"]}] + \
         [{"name": s["name"], "lat": s["lat"], "lon": s["lon"], "type": s["type"]} for s in data["sites"]]
names = [p["name"] for p in places]
assert len(names) == len(set(names)), "site names must be unique"

coords = ";".join(f'{p["lon"]:.6f},{p["lat"]:.6f}' for p in places)
r = requests.get(f"https://router.project-osrm.org/table/v1/driving/{coords}",
                 params={"annotations": "duration,distance"},
                 headers={"User-Agent": "btb-map-student-project"}, timeout=120)
r.raise_for_status()
t = r.json()
assert t["code"] == "Ok", t

out = {"names": names,
       "seconds": [[round(x) for x in row] for row in t["durations"]],
       "meters": [[round(x) for x in row] for row in t["distances"]]}
json.dump(out, open("docs/data/matrix.json", "w"), separators=(",", ":"))
print(f"Saved {len(names)} x {len(names)} table to docs/data/matrix.json")
