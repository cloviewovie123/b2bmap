"""Compare our usual pickup route with the best possible route.

Stops : the pickup sites in data/clean/sites.json, plus Fremont (start and end).
Usual : "nearest-first" -> from Fremont go to the closest unvisited stop, repeat, drive home.
Best  : solved by Google OR-Tools (a "traveling salesman" problem).
Both are judged by real driving time from OSRM, a free routing service built on OpenStreetMap.

Usage:  python scripts/optimize_route.py                      all pickup sites (also saves routes.json)
        python scripts/optimize_route.py --stops "Kim Grant Tennis,Mountain View Tennis,Furrtropolis"
                                                              only the sites you name (any pickup or dropoff)
Writes: docs/data/routes.json  (read by the map page)
        data/clean/osrm_cache.json (saved answers so we don't re-ask the server)
"""
import argparse, json, os, requests
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

OSRM = "https://router.project-osrm.org"
CACHE = "data/clean/osrm_cache.json"
cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}


def osrm(path):
    """Ask OSRM, remembering the answer on disk."""
    if path not in cache:
        r = requests.get(OSRM + path, headers={"User-Agent": "btb-map-student-project"}, timeout=60)
        r.raise_for_status()
        cache[path] = r.json()
        json.dump(cache, open(CACHE, "w"))
    return cache[path]


def coords(places):
    return ";".join(f'{p["lon"]:.6f},{p["lat"]:.6f}' for p in places)


def nearest_first(seconds):
    """Our usual method. Index 0 is Fremont."""
    order, left = [0], set(range(1, len(seconds)))
    while left:
        nxt = min(left, key=lambda j: seconds[order[-1]][j])
        order.append(nxt); left.remove(nxt)
    return order + [0]


def best_route(seconds):
    """OR-Tools: 1 vehicle, start and end at index 0."""
    n = len(seconds)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    model = pywrapcp.RoutingModel(manager)
    cb = model.RegisterTransitCallback(
        lambda i, j: int(seconds[manager.IndexToNode(i)][manager.IndexToNode(j)]))
    model.SetArcCostEvaluatorOfAllVehicles(cb)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    params.time_limit.seconds = 10  # tiny problem; this is plenty
    sol = model.SolveWithParameters(params)
    order, i = [], model.Start(0)
    while not model.IsEnd(i):
        order.append(manager.IndexToNode(i)); i = sol.Value(model.NextVar(i))
    return order + [0]


def describe(order, places, seconds, meters):
    legs = [{"from": places[a]["name"], "to": places[b]["name"],
             "minutes": round(seconds[a][b] / 60, 1), "miles": round(meters[a][b] / 1609.344, 1)}
            for a, b in zip(order, order[1:])]
    # Road shape for drawing on the map (OSRM 'route' service)
    geo = osrm(f"/route/v1/driving/{coords([places[i] for i in order])}?overview=full&geometries=geojson")
    return {"order": [places[i]["name"] for i in order], "legs": legs,
            "total_minutes": round(sum(l["minutes"] for l in legs), 1),
            "total_miles": round(sum(l["miles"] for l in legs), 1),
            "path": geo["routes"][0]["geometry"]["coordinates"]}  # [[lon, lat], ...]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stops", help="comma-separated site names, in the order you plan to drive them")
    args = ap.parse_args()

    data = json.load(open("data/clean/sites.json"))
    d = data["depot"]
    depot = {"name": "Fremont (start/end)", "lat": d["lat"], "lon": d["lon"]}
    by_name = {s["name"]: s for s in data["sites"]}
    if args.stops:
        wanted = [n.strip() for n in args.stops.split(",") if n.strip()]
        missing = [n for n in wanted if n not in by_name]
        if missing:
            raise SystemExit("Unknown site(s): " + ", ".join(missing))
        sites = [by_name[n] for n in wanted]
    else:
        sites = [s for s in data["sites"] if s["type"] == "pickup"]
    places = [depot] + [{"name": s["name"], "lat": s["lat"], "lon": s["lon"]} for s in sites]

    table = osrm(f"/table/v1/driving/{coords(places)}?annotations=duration,distance")
    seconds, meters = table["durations"], table["distances"]

    usual = describe(nearest_first(seconds), places, seconds, meters)
    best = describe(best_route(seconds), places, seconds, meters)
    results = [("USUAL (nearest-first)", usual), ("BEST (OR-Tools)", best)]
    if args.stops:   # also show the order you typed
        mine = describe(list(range(len(places))) + [0], places, seconds, meters)
        results.insert(0, ("YOUR ORDER", mine))
    saved_min = (mine if args.stops else usual)["total_minutes"] - best["total_minutes"]
    saved_mi = (mine if args.stops else usual)["total_miles"] - best["total_miles"]
    base = (mine if args.stops else usual)["total_minutes"]
    out = {"stops": len(places) - 1, "usual": usual, "best": best,
           "saved_minutes": round(saved_min, 1), "saved_miles": round(saved_mi, 1),
           "saved_percent": round(100 * saved_min / base, 1) if base else 0}
    if not args.stops:   # only the all-pickups comparison is saved for the web page
        json.dump(out, open("docs/data/routes.json", "w"))

    for label, r in results:
        print(f"\n{label}: {r['total_minutes']} min, {r['total_miles']} miles")
        for k, name in enumerate(r["order"]):
            print(f"  {k}. {name}" + (f"   (+{r['legs'][k]['minutes']} min)" if k < len(r["legs"]) else ""))
    print(f"\nBest route saves {out['saved_minutes']} min and {out['saved_miles']} miles ({out['saved_percent']}%).")

main()
