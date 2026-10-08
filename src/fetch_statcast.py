"""Download plate-appearance-level Statcast data (2021-2026, regular season) for steps 2-3.

One row per plate appearance: the pitch that ended it, with its actual wOBA value,
Statcast's expected wOBA on contact, and batted-ball details. Pulled from Baseball
Savant's Statcast Search in weekly windows (the search returns at most 25,000 rows per
request), trimmed to the columns used, and cached as data/raw/statcast/<season>/<week>.csv.gz.
Like the rest of data/raw/, these files are not committed.
"""

import argparse
import io
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

SEASONS = range(2021, 2027)
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "statcast"
HEADERS = {"User-Agent": "xwoba-gap-reliability (personal research project)"}
MAX_ROWS = 25_000  # Savant's per-request cap: a full response means rows were cut off
WORKERS = 3
MAX_ATTEMPTS = 4

# Every event that ends a plate appearance (Savant's search encodes "_" as "\.\.")
PA_EVENTS = [
    "single", "double", "triple", "home_run", "field_out", "strikeout", "walk",
    "intent_walk", "hit_by_pitch", "grounded_into_double_play", "force_out", "sac_fly",
    "sac_bunt", "fielders_choice", "fielders_choice_out", "double_play", "field_error",
    "strikeout_double_play", "sac_fly_double_play", "triple_play", "catcher_interf",
    "sac_bunt_double_play", "truncated_pa",
]
SEARCH_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details"
    "&player_type=batter&hfGT=R%7C&hfSea={season}%7C"
    "&game_date_gt={start}&game_date_lt={end}&hfAB={events}"
)
KEEP_COLUMNS = [
    "game_date", "game_pk", "at_bat_number", "batter", "stand", "home_team", "away_team",
    "inning_topbot", "events", "bb_type", "launch_speed", "launch_angle", "hc_x", "hc_y",
    "hit_distance_sc", "estimated_woba_using_speedangle", "woba_value", "woba_denom",
    "if_fielding_alignment", "of_fielding_alignment", "bat_speed",
]


def weeks(season: int) -> list[tuple[date, date]]:
    """Seven-day windows covering March 1 - October 10 (hfGT=R keeps regular season only)."""
    start, last = date(season, 3, 1), date(season, 10, 10)
    windows = []
    while start <= last:
        end = min(start + timedelta(days=6), last)
        windows.append((start, end))
        start = end + timedelta(days=1)
    return windows


def fetch_week(season: int, start: date, end: date, force: bool) -> str:
    path = OUT_DIR / str(season) / f"{start.isoformat()}.csv.gz"
    if path.exists() and not force:
        return f"skip  {path.name}"
    events = "%7C".join(e.replace("_", "%5C.%5C.") for e in PA_EVENTS) + "%7C"
    url = SEARCH_URL.format(season=season, start=start, end=end, events=events)
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=180)
            response.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
            if attempt == MAX_ATTEMPTS:
                raise
            time.sleep(5 * 2 ** attempt)
    text = response.content.decode("utf-8-sig")
    df = pd.read_csv(io.StringIO(text), low_memory=False) if text.strip() else pd.DataFrame()
    if len(df) >= MAX_ROWS:
        raise RuntimeError(f"{season} {start}: {len(df)} rows hit the {MAX_ROWS:,} cap; use shorter windows")
    if len(df) and not set(KEEP_COLUMNS) <= set(df.columns):
        raise RuntimeError(f"{season} {start}: missing columns {set(KEEP_COLUMNS) - set(df.columns)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    (df[KEEP_COLUMNS] if len(df) else pd.DataFrame(columns=KEEP_COLUMNS)).to_csv(
        path, index=False, compression="gzip")
    return f"saved {season} {start} ({len(df):,} PA)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download cached weeks")
    args = parser.parse_args()
    jobs = [(season, start, end) for season in SEASONS for start, end in weeks(season)]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for message in pool.map(lambda job: fetch_week(*job, args.force), jobs):
            print(message, flush=True)


if __name__ == "__main__":
    main()
