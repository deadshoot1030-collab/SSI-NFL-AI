
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from itertools import groupby

URL = (
    "https://github.com/nflverse/nflverse-data/"
    "releases/download/schedules/games.csv"
)

def main():
    with urllib.request.urlopen(URL, timeout=120) as response:
        rows = list(csv.DictReader(
            io.TextIOWrapper(response, encoding="utf-8-sig")
        ))

    games = []

    for row in rows:
        try:
            season = int(row["season"])
            h = float(row["home_score"])
            a = float(row["away_score"])
        except (ValueError, TypeError, KeyError):
            continue

        if 1999 <= season <= 2025:
            if math.isfinite(h) and math.isfinite(a):
                games.append((
                    row["gameday"],
                    season,
                    row["home_team"],
                    row["away_team"],
                    h, a
                ))

    ratings = defaultdict(lambda: 1500.0)
    metrics = defaultdict(lambda: [0, 0, 0.0, 0.0])

    for date, group in groupby(
        sorted(games), key=lambda g: g[0]
    ):
        updates = defaultdict(float)

        for _, season, home, away, hs, aws in group:

            p = 1 / (1 + 10 ** (
                (ratings[away] - ratings[home] - 55) / 400
            ))

            y = 1 if hs > aws else 0 if hs < aws else 0.5

            if season >= 2015 and y != 0.5:
                for key in (str(season), "2015-2025"):
                    m = metrics[key]
                    m[0] += 1
                    m[1] += int((p >= 0.5) == bool(y))
                    m[2] += (p - y) ** 2
                    m[3] -= math.log(
                        max(1e-15, p if y else 1-p)
                    )

            delta = 20 * (y - p)
            updates[home] += delta
            updates[away] -= delta

        for team, delta in updates.items():
            ratings[team] += delta

    if not metrics["2015-2025"][0]:
        raise RuntimeError("No evaluation games")

    report = {
        k: {
            "games": n,
            "correct": c,
            "accuracy_percent": round(100*c/n, 2),
            "brier": b/n,
            "log_loss": l/n
        }
        for k, (n, c, b, l) in metrics.items() if n
    }

    report["target_85_reached"] = (
        report["2015-2025"]["accuracy_percent"] >= 85
    )

    with open("results.json", "w") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
