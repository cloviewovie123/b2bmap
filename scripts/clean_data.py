"""Clean the raw CSVs and attach map coordinates to every site.

Reads : data/raw/*.csv                (never modified)
Writes: data/clean/sites.json         one entry per site (totals + visit history)
        data/clean/visits.csv         one row per visit (no personal info)
        data/clean/geocode_cache.json saved lookups so we don't re-ask the server
Personal info (Contact # column and volunteer names) is NOT copied anywhere.
"""
import csv, json, time, os
from datetime import datetime
import requests

RAW = "data/raw"
CLEAN = "data/clean"
FILES = {
    "pickup":  ("Bounce Back Resource Sheet - Past Pickups (1).csv", "Center"),
    "dropoff": ("Bounce Back Resource Sheet - Past Dropoffs.csv", "Dropoff location"),
}

# Different spellings of the same place -> one official name.
ALIASES = {
    "Allie's Doggy Daycamp": "Allie's Doggie Day Camp",
    "City of SJ Animal Care Services": "San Jose Animal Shelter",  # same building, 2750 Monterey Rd
}

# Where each site is. 'q' is what we ask the map service; 'conf' says how sure we are.
# high = street address confirmed, medium = address from a weaker source, low = only the city.
SITES = {
    "A Pet Villa Dog Boarding and Grooming": ("1205 Laurelwood Rd, Santa Clara, CA", "high"),
    "Allie's Doggie Day Camp": ("562 N 20th St, San Jose, CA", "high"),
    "Blacow Elementary": ("Blacow Elementary School, Fremont, CA", "high"),
    "Brier Elementary": ("Brier Elementary School, Fremont, CA", "high"),
    "Bringhurst Elementary": ("Bringhurst Elementary School, Fremont, CA", "high"),
    "Cupertino Hills Swim & Racquet Club": ("22090 Rae Ln, Cupertino, CA", "high"),
    "Downtown Dogs": ("Downtown Dogs, 734 S 1st St, San Jose, CA", "high"),
    "Forest Park Elementary": ("Forest Park Elementary School, Fremont, CA", "high"),
    "Furrtropolis": ("902 S Bascom Ave, San Jose, CA", "high"),
    "Girly's Pet Sitting": ("East Palo Alto, CA", "low"),  # home-based, no public street address
    "Gomes Elementary": ("John M Gomes Elementary School, Fremont, CA", "high"),
    "Grimmer Elementary": ("E M Grimmer Elementary School, Fremont, CA", "high"),
    "Humane Society Silicon Valley": ("901 Ames Ave, Milpitas, CA", "high"),
    "Irvington High School": ("Irvington High School, Fremont, CA", "high"),
    "Kim Grant Tennis": ("3005 Middlefield Rd, Palo Alto, CA", "high"),
    "Kona Kai Swim & Racquet Club": ("680 Hubbard Ave, Santa Clara, CA", "high"),
    "Lifetime Activities Cupertino": ("21111 Stevens Creek Blvd, Cupertino, CA", "high"),
    "Lifetime Activities Sunnyvale": ("755 S Mathilda Ave, Sunnyvale, CA", "high"),
    "Love Second Chances": ("7601 Kilrush Ave, Dublin, CA", "medium"),  # nonprofit's registered address
    "Lucky Buddies Pet Sitting": ("404 N 13th St, San Jose, CA", "low"),  # review-site address; map shows a different business there, so likely wrong
    "Mission Hills Swim & Racquet Club": ("10 E Las Palmas Ave, Fremont, CA", "high"),
    "Mission San Jose Elementary": ("Mission San Jose Elementary School, Fremont, CA", "high"),
    "Mission Valley Elementary": ("Mission Valley Elementary School, Fremont, CA", "high"),
    "Mountain View Tennis": ("685 Cuesta Dr, Mountain View, CA", "high"),
    "Norcal Tennis Academy": ("6200 Buena Vista Dr, Newark, CA", "medium"),  # also lists a San Jose site
    "Oliveira Elementary": ("Oliveira Elementary School, Fremont, CA", "high"),
    "Red Rover Pet Resort": ("334 Turquoise St, Milpitas, CA", "high"),
    "San Jose Animal Shelter": ("2750 Monterey Rd, San Jose, CA", "high"),
    "Silicon Valley Animal Control Authority": ("3370 Thomas Rd, Santa Clara, CA", "high"),
    "University Club Palo Alto": ("3277 Miranda Ave, Palo Alto, CA", "high"),
    "Vallejo Mill Elementary": ("Vallejo Mill Elementary School, Fremont, CA", "high"),
    "Walters Middle School": ("Walters Middle School, Fremont, CA", "high"),
}
# Trip start/end (approximate center of Fremont).
DEPOT = {"name": "Fremont (start/end)", "lat": 37.5485, "lon": -121.9886}


def geocode(query, cache):
    if query in cache:
        return cache[query]
    r = requests.get("https://nominatim.openstreetmap.org/search",
                     params={"q": query, "format": "json", "limit": 1},
                     headers={"User-Agent": "btb-map-student-project"}, timeout=30).json()
    time.sleep(1.1)  # Nominatim's rule: at most 1 request per second
    cache[query] = ({"lat": float(r[0]["lat"]), "lon": float(r[0]["lon"]), "found": r[0]["display_name"]}
                    if r else None)
    return cache[query]


def main():
    os.makedirs(CLEAN, exist_ok=True)
    cache_path = f"{CLEAN}/geocode_cache.json"
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}

    visits = []
    for kind, (fname, col) in FILES.items():
        for row in csv.DictReader(open(f"{RAW}/{fname}", encoding="utf-8")):
            site = ALIASES.get(row[col].strip(), row[col].strip())
            date = datetime.strptime(row["Date"].strip(), "%m/%d/%Y").date().isoformat()
            visits.append({"site": site, "type": kind, "date": date,
                           "balls": int(row["Ball Count"]), "notes": row["Notes"].strip()})

    sites = {}
    for v in visits:
        key = (v["site"], v["type"])  # a place could in theory be both; keep them separate
        s = sites.setdefault(key, {"name": v["site"], "type": v["type"], "total_balls": 0, "visits": []})
        s["total_balls"] += v["balls"]
        s["visits"].append({"date": v["date"], "balls": v["balls"], "notes": v["notes"]})

    out = []
    for s in sites.values():
        q, conf = SITES[s["name"]]
        g = geocode(q, cache)
        if not g:
            print("COULD NOT FIND:", s["name"], "|", q); continue
        s.update(lat=g["lat"], lon=g["lon"], confidence=conf, matched_as=g["found"][:90])
        s["visits"].sort(key=lambda x: x["date"], reverse=True)
        s["num_visits"] = len(s["visits"]); s["last_visit"] = s["visits"][0]["date"]
        out.append(s)
    out.sort(key=lambda s: (s["type"], -s["total_balls"]))

    json.dump(cache, open(cache_path, "w"), indent=1)
    json.dump({"depot": DEPOT, "sites": out}, open(f"{CLEAN}/sites.json", "w"), indent=1)
    with open(f"{CLEAN}/visits.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["site", "type", "date", "balls", "notes"])
        w.writeheader(); w.writerows(sorted(visits, key=lambda v: (v["type"], v["site"], v["date"])))
    for s in out:
        print(f'{s["type"]:8} {s["total_balls"]:6} {s["confidence"]:6} {s["name"]:42} {s["lat"]:.4f},{s["lon"]:.4f}  {s["matched_as"][:50]}')

main()
