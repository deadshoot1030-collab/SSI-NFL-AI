
import csv
import io
import json
import math
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

URL = "https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv"

def load_games():
    request = urllib.request.Request(
        URL, headers={"User-Agent": "SSI-NFL-AI/1.0"}
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read(25_000_001)

    if len(data) > 25_000_000:
        raise ValueError("CSV is too large")

    games = []
    reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))

    for row in reader:
        try:
            home = row["home_team"].strip()
            away = row["away_team"].strip()
            hs = int(row["home_score"])
            aws = int(row["away_score"])
            day = date.fromisoformat(
                (row.get("gameday") or row.get("date") or "")[:10]
            )
            if home and away and home != away and min(hs, aws) >= 0:
                games.append((day, home, away, hs, aws))
        except (ValueError, TypeError, KeyError):
            continue

    return sorted(games)

def evaluate(games, k=20, home_adv=55, score_from=None):
    ratings = defaultdict(lambda: 1500.0)
    groups = defaultdict(list)

    for game in games:
        groups[game[0]].append(game)

    correct = 0
    count = 0
    brier = 0.0
    log_loss = 0.0

    for day, group in sorted(groups.items()):
        predictions = []

        for _, home, away, hs, aws in group:
            p = 1 / (
                1 + 10 ** (
                    (ratings[away] - ratings[home] - home_adv) / 400
                )
            )
            predictions.append((home, away, hs, aws, p))

        for home, away, hs, aws, p in predictions:
            if score_from is not None and day < score_from:
                continue
            if hs == aws:
                continue

            y = int(hs > aws)
            count += 1
            if p != 0.5 and (p > 0.5) == bool(y):
                correct += 1

            brier += (p - y) ** 2
            safe_p = max(1e-9, min(1 - 1e-9, p))
            log_loss -= y * math.log(safe_p) + (
                1 - y
            ) * math.log(1 - safe_p)

        for home, away, hs, aws, p in predictions:
            outcome = 1 if hs > aws else 0 if hs < aws else 0.5
            delta = k * (outcome - p)
            ratings[home] += delta
            ratings[away] -= delta

    if count == 0:
        raise ValueError("No games to evaluate")

    return {
        "games": count,
        "accuracy": round(correct / count, 5),
        "brier": round(brier / count, 5),
        "log_loss": round(log_loss / count, 5),
    }

def main():
    games = load_games()
    if len(games) < 500:
        raise ValueError("Insufficient historical games")

    training = [g for g in games if g[0].year < 2023]
    if len(training) < 200:
        raise ValueError("Insufficient training games")

    candidates = []

    for k in (10, 20, 30, 40):
        for advantage in (30, 55, 80):
            result = evaluate(
                training, k, advantage, date(2015, 1, 1)
            )
            candidates.append(
                (result["log_loss"], k, advantage)
            )

    _, best_k, best_advantage = min(candidates)

    result = evaluate(
        games, best_k, best_advantage, date(2023, 1, 1)
    )

    report = {
        "model": "NFL Elo",
        "training_period": "Before 2023",
        "holdout_period": "2023 onward",
        "selected_k": best_k,
        "selected_home_advantage": best_advantage,
        **result,
    }

    Path("reports").mkdir(exist_ok=True)
    Path("reports/nfl_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
