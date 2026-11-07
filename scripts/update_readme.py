"""
Update the stats in README.md (and optionally the GitHub repo description)
from the project's data files, so the numbers never go out of date.

What it reads:
  docs/data/sites.json   - every site, its type, balls, and visits
  docs/data/routes.json  - the usual route vs. the optimized route

What it writes:
  README.md - only the part between the STATS:START and STATS:END markers.

Usage (run from the project folder):
  python scripts/update_readme.py                  # update README.md only
  python scripts/update_readme.py --github         # also update the GitHub description
                                                   # (needs the GitHub CLI "gh", logged in)

Run it after clean_data.py / optimize_route.py whenever the data changes.
"""

import argparse
import json
import subprocess
from datetime import datetime

README = "README.md"
SITES = "docs/data/sites.json"
ROUTES = "docs/data/routes.json"
REPO = "cloviewovie123/b2bmap"
START = "<!-- STATS:START"
END = "<!-- STATS:END -->"


def month_year(date_text):
    """Turn '2026-09-20' into 'Sep 2026'."""
    return datetime.strptime(date_text, "%Y-%m-%d").strftime("%b %Y")


def compute_stats():
    """Add up the numbers we show in the README."""
    with open(SITES) as f:
        sites = json.load(f)["sites"]
    with open(ROUTES) as f:
        routes = json.load(f)

    pickups = [s for s in sites if s["type"] == "pickup"]
    dropoffs = [s for s in sites if s["type"] == "dropoff"]
    dates = sorted(v["date"] for s in sites for v in s["visits"])

    usual_mi = routes["usual"]["total_miles"]
    best_mi = routes["best"]["total_miles"]
    saved_min = routes["usual"]["total_minutes"] - routes["best"]["total_minutes"]

    return {
        "balls": sum(s["total_balls"] for s in sites),
        "sites": len(sites),
        "pickups": len(pickups),
        "dropoffs": len(dropoffs),
        "visits": sum(s["num_visits"] for s in sites),
        "first": month_year(dates[0]),
        "last": month_year(dates[-1]),
        "usual_mi": usual_mi,
        "best_mi": best_mi,
        "percent": round((usual_mi - best_mi) / usual_mi * 100),
        "saved_min": round(saved_min),
    }


def stats_table(st):
    """Build the markdown table that goes in the README."""
    return "\n".join([
        "| | |",
        "|---|---|",
        f"| 🎾 **Balls moved** | {st['balls']:,} |",
        f"| 📍 **Sites mapped** | {st['sites']} ({st['pickups']} pickup clubs, {st['dropoffs']} dropoff partners) |",
        f"| 🗓️ **Visits logged** | {st['visits']}, from {st['first']} to {st['last']} |",
        f"| 🚗 **Pickup run** | {st['usual_mi']} mi → **{st['best_mi']} mi** with the optimized route "
        f"(**−{st['percent']}%**, about {st['saved_min']} min saved) |",
    ])


def description(st):
    """One-line description for the GitHub 'About' box (max 350 characters)."""
    thousands = st["balls"] // 1000
    return (f"Interactive map + route optimizer for Bin to Better's Bay Area tennis ball "
            f"recycling network: {thousands}K+ balls, {st['sites']} sites, "
            f"{st['percent']}% shorter pickup runs.")


def update_readme(table):
    """Replace only the text between the two markers; leave the rest alone."""
    with open(README, encoding="utf-8") as f:
        text = f.read()

    start = text.index(START)
    start = text.index("\n", start) + 1  # keep the START marker line itself
    end = text.index(END)

    new_text = text[:start] + table + "\n" + text[end:]
    changed = new_text != text
    if changed:
        with open(README, "w", encoding="utf-8") as f:
            f.write(new_text)
    return changed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--github", action="store_true",
                        help="also update the GitHub repo description with gh")
    args = parser.parse_args()

    st = compute_stats()
    changed = update_readme(stats_table(st))
    print("README.md updated." if changed else "README.md already up to date.")

    desc = description(st)
    print("Description:", desc)
    if args.github:
        subprocess.run(["gh", "repo", "edit", REPO, "--description", desc], check=True)
        print("GitHub description updated.")


if __name__ == "__main__":
    main()
