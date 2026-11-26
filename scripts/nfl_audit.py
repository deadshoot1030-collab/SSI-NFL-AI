
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict, deque
from datetime import date
from itertools import groupby
from pathlib import Path

URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

def sigmoid(x):
    return 1 / (1 + math.exp(-max(-30, min(30, x))))

def load_games():
    req = urllib.request.Request(
        URL, headers={"User-Agent": "SSI-AI/2.0"}
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        rows = csv.DictReader(
            io.StringIO(r.read().decode("utf-8-sig"))
        )
        games = []
        for row in rows:
            try:
                d = date.fromisoformat(row["gameday"])
                h = row["home_team"]
                a = row["away_team"]
                hs = int(row["home_score"])
                aws = int(row["away_score"])
                neutral = int(row.get("location") == "Neutral")
                games.append((d, h, a, hs, aws, neutral))
            except (ValueError, TypeError, KeyError):
                continue
    return sorted(games)

def avg(values):
    return sum(values) / len(values) if values else 0

def evaluate(games, config):
    k, advantage, rate, mode = config
    elo = defaultdict(lambda: 1500.0)
    margins = defaultdict(lambda: deque(maxlen=10))
    wins = defaultdict(lambda: deque(maxlen=5))
    scored = defaultdict(lambda: deque(maxlen=10))
    allowed = defaultdict(lambda: deque(maxlen=10))
    last = {}
    weights = [0.0] * 7
    results = defaultdict(list)

    for day, group in groupby(games, key=lambda g: g[0]):
        pending = []

        for _, h, a, hs, aws, neutral in group:
            rest_h = min(21, (day-last[h]).days) if h in last else 7
            rest_a = min(21, (day-last[a]).days) if a in last else 7

            diff = elo[h] - elo[a]
            home = advantage * (1-neutral)

            pe = sigmoid(
                math.log(10) * (diff+home) / 400
            )

            x = [
                1.0-neutral,
                diff/400,
                (avg(margins[h])-avg(margins[a]))/20,
                avg(wins[h])-avg(wins[a]),
                (rest_h-rest_a)/14,
                (avg(scored[h])-avg(scored[a]))/20,
                (avg(allowed[a])-avg(allowed[h]))/20
            ]

            pl = sigmoid(sum(w*v for w, v in zip(weights, x)))

            if mode == "elo":
                p = pe
            elif mode == "adaptive":
                p = pl
            else:
                p = (pe+pl)/2

            y = 1 if hs > aws else 0 if hs < aws else 0.5

            if y != 0.5:
                if 2015 <= day.year < 2023:
                    results["validation"].append((p, y))
                elif day.year >= 2023:
                    results["test"].append((p, y))

            pending.append((h, a, hs, aws, pe, pl, x, y))

        # Learn only after all predictions for the day.
        for h, a, hs, aws, pe, pl, x, y in pending:
            delta = k*(y-pe)
            elo[h] += delta
            elo[a] -= delta

            for i in range(len(weights)):
                weights[i] += rate * (
                    (y-pl)*x[i] - 0.001*weights[i]
                )

            margins[h].append(hs-aws)
            margins[a].append(aws-hs)
            wins[h].append(y)
            wins[a].append(1-y)
            scored[h].append(hs)
            scored[a].append(aws)
            allowed[h].append(aws)
            allowed[a].append(hs)
            last[h] = day
            last[a] = day

    return results

def metrics(rows):
    n = len(rows)
    if not n:
        raise ValueError("No evaluation games")

    correct = sum(
        p != 0.5 and (p > 0.5) == bool(y)
        for p, y in rows
    )

    loss = sum(
        -math.log(max(1e-12, p if y else 1-p))
        for p, y in rows
    ) / n

    return {
        "games": n,
        "correct": correct,
        "accuracy_percent": round(100*correct/n, 4),
        "brier": round(sum((p-y)**2 for p,y in rows)/n, 6),
        "log_loss": round(loss, 6)
    }

def main():
    games = load_games()
    if len(games) < 500:
        raise ValueError("Insufficient historical data")

    history = [g for g in games if g[0].year < 2023]
    candidates = []

    for k in (10, 20, 30, 40):
        for adv in (30, 55, 80):
            for rate in (0.005, 0.02, 0.05):
                for mode in ("elo", "adaptive", "ensemble"):
                    config = (k, adv, rate, mode)
                    result = evaluate(history, config)
                    score = metrics(result["validation"])
                    candidates.append((score["log_loss"], config))

    _, best = min(candidates)

    final = metrics(evaluate(games, best)["test"])

    baseline = metrics(
        evaluate(games, (30, 30, 0.02, "elo"))["test"]
    )

    report = {
        "version": "SSI AI 2.0",
        "models_tested": len(candidates),
        "selected_model": best[3],
        "selected_k": best[0],
        "selected_home_advantage": best[1],
        "learning_rate": best[2],
        "baseline": baseline,
        "new_model": final,
        "improvement_pp": round(
            final["accuracy_percent"] -
            baseline["accuracy_percent"], 4
        ),
        "target_70_reached": final["accuracy_percent"] >= 70,
        "target_75_reached": final["accuracy_percent"] >= 75,
        "target_80_reached": final["accuracy_percent"] >= 80,
        "target_85_reached": final["accuracy_percent"] >= 85
    }

    Path("reports").mkdir(exist_ok=True)
    Path("reports/nfl_audit.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
