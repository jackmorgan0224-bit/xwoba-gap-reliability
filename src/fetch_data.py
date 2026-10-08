"""Download season-level hitter data (2021-2026) from Baseball Savant and the MLB Stats API.

Every response is cached in data/raw/ so the rest of the pipeline runs offline and
reproducibly. Files that already exist are skipped; pass --force to re-download.
Raw data is not committed to the repository (MLB Advanced Media terms limit it to
personal, non-commercial use), so run this once after cloning.

Sources
- Savant custom leaderboard: PA, wOBA, xwOBA, contact quality, spray, sprint speed, bat speed
- Savant batted-ball leaderboard: pulled / straightaway / opposite-field air-ball rates
- Savant expected-stats leaderboard: an independent copy of PA / wOBA / xwOBA used only
  to cross-check the custom leaderboard
- MLB Stats API: PA by player x team (splits players who changed teams) and batting hand
- History (2015-2019): PA / AB / pitches / wOBA / xwOBA / sprint speed only, from both Savant endpoints, to rerun the
  persistence analysis on the seasons the published estimates used
"""

import argparse
import csv
import time
from pathlib import Path

import requests

SEASONS = range(2021, 2027)
HISTORY_SEASONS = range(2015, 2020)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
HEADERS = {"User-Agent": "xwoba-gap-reliability (personal research project)"}
PAUSE_SECONDS = 1.0
MAX_ATTEMPTS = 4  # retries cover the occasional dropped connection from either API

# Savant silently returns an empty column for an unknown key, so sql/02_validation.sql
# checks every one of these columns for missing values.
CUSTOM_FIELDS = [
    "pa", "ab", "pitch_count", "woba", "xwoba", "k_percent", "bb_percent",
    "barrel_batted_rate", "hard_hit_percent", "sweet_spot_percent",
    "pull_percent", "straightaway_percent", "opposite_percent",
    "groundballs_percent", "flyballs_percent", "linedrives_percent",
    "sprint_speed", "avg_swing_speed",  # full-season bat tracking begins in 2024
]
SAVANT_CUSTOM_URL = (
    "https://baseballsavant.mlb.com/leaderboard/custom"
    "?year={season}&type=batter&min=100&selections={fields}&csv=true"
)
SAVANT_BATTED_BALL_URL = (
    "https://baseballsavant.mlb.com/leaderboard/batted-ball"
    "?type=batter&season%5B%5D={season}&min=50&csv=true"
)
SAVANT_EXPECTED_URL = (
    "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
    "?type=batter&year={season}&min=1&csv=true"
)
MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1&season={season}"
# Player-level lookup. The team-level stats endpoint omits players who left a team
# midseason (found via the PA reconciliation check), so query players directly.
MLB_PEOPLE_URL = (
    "https://statsapi.mlb.com/api/v1/people?personIds={ids}"
    "&hydrate=stats(group=[hitting],type=[season],season={season})"
)
PEOPLE_BATCH_SIZE = 100


def get(url: str) -> requests.Response:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=60)
            if response.status_code < 500:
                response.raise_for_status()
                time.sleep(PAUSE_SECONDS)
                return response
            error = f"HTTP {response.status_code}"
        except (requests.ConnectionError, requests.Timeout) as exc:
            error = type(exc).__name__
        if attempt == MAX_ATTEMPTS:
            raise RuntimeError(f"{error} after {MAX_ATTEMPTS} attempts: {url}")
        wait = PAUSE_SECONDS * 2 ** attempt
        print(f"  {error}, retrying in {wait:.0f}s")
        time.sleep(wait)


def save_csv(path: Path, url: str, required_column: str, force: bool) -> None:
    """Save a CSV response, refusing anything that isn't the expected table (e.g. an HTML error page)."""
    if path.exists() and not force:
        print(f"  skip  {path.name} (cached)")
        return
    text = get(url).content.decode("utf-8-sig")
    header = text.split("\n", 1)[0]
    if f'"{required_column}"' not in header and required_column not in header.split(","):
        raise RuntimeError(f"Response from {url} is missing column {required_column!r}")
    if text.count("\n") < 2:
        raise RuntimeError(f"No data rows in response from {url}")
    path.write_text(text, encoding="utf-8", newline="")
    print(f"  saved {path.name} ({text.count(chr(10)) - 1} rows)")


def save_team_pa(season: int, force: bool) -> None:
    """One row per player x team x season, so players who changed teams are split by team."""
    path = RAW_DIR / f"statsapi_team_pa_{season}.csv"
    if path.exists() and not force:
        print(f"  skip  {path.name} (cached)")
        return
    teams = {t["id"]: t for t in get(MLB_TEAMS_URL.format(season=season)).json()["teams"]}
    with (RAW_DIR / f"savant_custom_{season}.csv").open(encoding="utf-8") as f:
        player_ids = [row["player_id"] for row in csv.DictReader(f)]

    rows = []
    for start in range(0, len(player_ids), PEOPLE_BATCH_SIZE):
        ids = ",".join(player_ids[start:start + PEOPLE_BATCH_SIZE])
        for person in get(MLB_PEOPLE_URL.format(ids=ids, season=season)).json()["people"]:
            for stat_group in person.get("stats", []):
                for split in stat_group["splits"]:
                    team_id = split.get("team", {}).get("id")
                    if team_id is None:  # the combined season-total row for multi-team players
                        continue
                    team = teams.get(team_id, {})
                    venue = team.get("venue", {})
                    rows.append({
                        "season": season,
                        "player_id": person["id"],
                        "player_name": person["fullName"],
                        "bat_side": person.get("batSide", {}).get("code"),  # current, not per-season
                        "team_id": team_id,
                        "team_abbr": team.get("abbreviation"),
                        "venue_id": venue.get("id"),
                        "venue_name": venue.get("name"),
                        "pa": split["stat"]["plateAppearances"],
                    })
    if not rows:
        raise RuntimeError(f"MLB Stats API returned no team splits for {season}")
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  saved {path.name} ({len(rows)} player-team rows for {len(player_ids)} players)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download cached files")
    args = parser.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    for season in SEASONS:
        print(f"{season}")
        save_csv(
            RAW_DIR / f"savant_custom_{season}.csv",
            SAVANT_CUSTOM_URL.format(season=season, fields=",".join(CUSTOM_FIELDS)),
            "xwoba",
            args.force,
        )
        save_csv(
            RAW_DIR / f"savant_batted_ball_{season}.csv",
            SAVANT_BATTED_BALL_URL.format(season=season),
            "pull_air_rate",
            args.force,
        )
        save_csv(
            RAW_DIR / f"savant_expected_{season}.csv",
            SAVANT_EXPECTED_URL.format(season=season),
            "est_woba",
            args.force,
        )
        save_team_pa(season, args.force)

    for season in HISTORY_SEASONS:
        print(f"{season} (history)")
        save_csv(
            RAW_DIR / f"history_custom_{season}.csv",
            SAVANT_CUSTOM_URL.format(season=season, fields="pa,ab,pitch_count,woba,xwoba,sprint_speed"),
            "xwoba",
            args.force,
        )
        save_csv(
            RAW_DIR / f"history_expected_{season}.csv",
            SAVANT_EXPECTED_URL.format(season=season),
            "est_woba",
            args.force,
        )


if __name__ == "__main__":
    main()
