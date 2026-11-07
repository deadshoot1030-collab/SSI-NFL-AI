# SSI NFL AI — Android v0.2

Android project (Kotlin, min SDK 26). Import completed games CSV or download one from a direct HTTPS CSV URL. Required columns: `home_team,away_team,home_score,away_score`; optional `date` in YYYY-MM-DD format. With dates, rows are sorted chronologically; without dates, CSV must be oldest first. For same-date games, the backtest follows input order, so cross-game same-day leakage is possible if games are not ordered by kickoff time. Data must contain only games completed before any live prediction.

Elo model: base 1500, home advantage 55 Elo, K=20. Backtest uses first 20 games as warmup, then predicts each subsequent game before updating Elo. Accuracy, Brier score and log loss are displayed. Ties are treated as 0.5 for scoring, but accuracy counts no tie as a correct winner prediction. The two displayed probabilities represent an Elo binary approximation, not calibrated 3-way probabilities.

**Limitations:** no verified historical dataset included; no claimed 85% accuracy; no automated NFL API; no APK included. Downloading a direct CSV link is not an automatic NFL data feed. For building, open project in Android Studio with Android SDK 35 and JDK 17, then Build > Build APK(s). Internet access is needed for Gradle dependencies and CSV download. No data is sent to a model server.


## Version 0.3 / APK build
GitHub Actions workflow `.github/workflows/android-apk.yml` builds a debug APK. Push this repository to GitHub, open Actions → Build Android APK → Run workflow, then download the `SSI-NFL-AI-debug-apk` artifact. Unzip it to get `app-debug.apk`. Android may require permission to install from the selected app.

The URL field is prefilled with the nflverse schedules CSV (CC BY 4.0). Source: https://github.com/nflverse/nflverse-data. Data is not bundled; requires internet access. This baseline is not validated to reach 85% accuracy.


## Version 0.4 validation notes
Backtesting now excludes tied games from binary winner metrics and predicts every game on a given date before observing any result from that date. This avoids within-day leakage. No historical accuracy number is claimed without running a real dataset. Android APK is built by GitHub Actions, not included in this archive.
