"""
Baseball Analysis Engine
MLB Stats API + Baseball Savant + Open-Meteo weather
No API keys required - all free public endpoints
"""

import requests
import json
from datetime import datetime, date
from typing import Optional
import time

MLB_API = "https://statsapi.mlb.com/api/v1"
MLB_API_V1_1 = "https://statsapi.mlb.com/api/v1.1"
SAVANT_API = "https://baseballsavant.mlb.com"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"

HEADERS = {"User-Agent": "PropStats/1.0 Baseball Analysis"}

# MLB venue coordinates for weather lookup
VENUE_COORDS = {
    2:    ("Oriole Park at Camden Yards", 39.2838, -76.6217),
    3:    ("Fenway Park", 42.3467, -71.0972),
    4:    ("Guaranteed Rate Field", 41.8300, -87.6339),
    6:    ("Great American Ball Park", 39.0979, -84.5082),
    5:    ("Progressive Field", 41.4962, -81.6852),
    2394: ("Minute Maid Park", 29.7573, -95.3555),
    17:   ("Comerica Park", 42.3390, -83.0485),
    7:    ("Kauffman Stadium", 39.0516, -94.4803),
    32:   ("American Family Field", 43.0280, -87.9712),
    27:   ("Target Field", 44.9817, -93.2781),
    1:    ("Yankee Stadium", 40.8296, -73.9262),
    3289: ("Citi Field", 40.7571, -73.8458),
    2681: ("Citizens Bank Park", 39.9056, -75.1665),
    31:   ("PNC Park", 40.4469, -80.0057),
    3309: ("Nationals Park", 38.8730, -77.0074),
    4705: ("Truist Park", 33.8908, -84.4678),
    14:   ("Wrigley Field", 41.9484, -87.6553),
    2889: ("Busch Stadium", 38.6226, -90.1928),
    2680: ("Chase Field", 33.4455, -112.0667),
    19:   ("Coors Field", 39.7559, -104.9942),
    22:   ("Dodger Stadium", 34.0739, -118.2400),
    2395: ("Oracle Park", 37.7786, -122.3893),
    2406: ("Petco Park", 32.7073, -117.1566),
    5325: ("Globe Life Field", 32.7473, -97.0845),
    2500: ("Angel Stadium", 33.8003, -117.8827),
    680:  ("T-Mobile Park", 47.5914, -122.3325),
    4169: ("loanDepot park", 25.7781, -80.2197),
    12:   ("Tropicana Field", 27.7683, -82.6534),
    14536: ("Rogers Centre", 43.6414, -79.3894),
}

PARK_FACTORS = {
    "Coors Field": {"run": 1.20, "hr": 1.27, "hit": 1.12, "description": "Extreme hitter's park (altitude)"},
    "Great American Ball Park": {"run": 1.13, "hr": 1.22, "hit": 1.05, "description": "Hitter-friendly"},
    "Fenway Park": {"run": 1.08, "hr": 1.04, "hit": 1.07, "description": "Slight hitter's park (Green Monster)"},
    "Wrigley Field": {"run": 1.05, "hr": 1.07, "hit": 1.04, "description": "Hitter-friendly (wind dependent)"},
    "Yankee Stadium": {"run": 1.06, "hr": 1.19, "hit": 1.02, "description": "HR-friendly short porches"},
    "Globe Life Field": {"run": 0.94, "hr": 0.91, "hit": 0.97, "description": "Pitcher-friendly (dome)"},
    "Tropicana Field": {"run": 0.90, "hr": 0.85, "hit": 0.92, "description": "Pitcher's park (dome)"},
    "Oracle Park": {"run": 0.88, "hr": 0.74, "hit": 0.95, "description": "Strong pitcher's park"},
    "T-Mobile Park": {"run": 0.93, "hr": 0.91, "hit": 0.95, "description": "Pitcher-friendly"},
    "Petco Park": {"run": 0.94, "hr": 0.88, "hit": 0.95, "description": "Pitcher-friendly"},
    "Dodger Stadium": {"run": 0.95, "hr": 0.92, "hit": 0.97, "description": "Slight pitcher's park"},
    "loanDepot park": {"run": 0.93, "hr": 0.87, "hit": 0.95, "description": "Pitcher-friendly (dome/retractable)"},
    "Minute Maid Park": {"run": 1.04, "hr": 1.08, "hit": 1.01, "description": "Slight hitter's park"},
    "Target Field": {"run": 0.97, "hr": 0.94, "hit": 0.98, "description": "Neutral-slight pitcher"},
    "Progressive Field": {"run": 0.96, "hr": 0.93, "hit": 0.97, "description": "Neutral"},
    "PNC Park": {"run": 0.95, "hr": 0.94, "hit": 0.96, "description": "Slight pitcher's park"},
    "Guaranteed Rate Field": {"run": 1.04, "hr": 1.08, "hit": 1.01, "description": "Slight hitter's park"},
    "Busch Stadium": {"run": 0.96, "hr": 0.92, "hit": 0.97, "description": "Slight pitcher's park"},
    "Oriole Park at Camden Yards": {"run": 1.05, "hr": 1.08, "hit": 1.02, "description": "Hitter-friendly"},
    "Citizens Bank Park": {"run": 1.07, "hr": 1.14, "hit": 1.03, "description": "HR-friendly"},
    "Citi Field": {"run": 0.96, "hr": 0.92, "hit": 0.97, "description": "Slight pitcher's park"},
    "Nationals Park": {"run": 1.01, "hr": 1.03, "hit": 1.00, "description": "Neutral"},
    "Truist Park": {"run": 0.98, "hr": 0.98, "hit": 0.99, "description": "Neutral"},
    "American Family Field": {"run": 1.02, "hr": 1.04, "hit": 1.00, "description": "Slight hitter's (retractable)"},
    "Chase Field": {"run": 1.05, "hr": 1.06, "hit": 1.02, "description": "Hitter-friendly (retractable/heat)"},
    "Kauffman Stadium": {"run": 0.97, "hr": 0.93, "hit": 0.98, "description": "Slight pitcher's park"},
    "Comerica Park": {"run": 0.95, "hr": 0.89, "hit": 0.96, "description": "Pitcher-friendly"},
    "Angel Stadium": {"run": 0.97, "hr": 0.95, "hit": 0.97, "description": "Neutral"},
    "Rogers Centre": {"run": 1.01, "hr": 1.03, "hit": 1.00, "description": "Neutral (dome/turf)"},
}

PITCH_TYPE_NAMES = {
    "FF": "4-Seam Fastball", "SI": "Sinker", "FC": "Cutter", "FS": "Splitter",
    "SL": "Slider", "CU": "Curveball", "KC": "Knuckle-Curve", "CH": "Changeup",
    "FO": "Forkball", "KN": "Knuckleball", "SC": "Screwball", "EP": "Eephus",
    "CS": "Slow Curve", "ST": "Sweeper", "SV": "Slurve", "FA": "Fastball",
    "IN": "Intentional Ball", "PO": "Pitch Out",
}

def _get(url: str, params: dict = None, retries: int = 2) -> Optional[dict]:
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries - 1:
                time.sleep(0.5)
    return None


def get_today_games(game_date: str = None) -> list:
    """Get all MLB games for a given date (default today)."""
    if not game_date:
        game_date = date.today().strftime("%Y-%m-%d")

    data = _get(f"{MLB_API}/schedule", {
        "sportId": 1,
        "date": game_date,
        "hydrate": "probablePitcher(note),linescore,team,venue,broadcasts,weather"
    })
    if not data:
        return []

    games = []
    for game_date_entry in data.get("dates", []):
        for g in game_date_entry.get("games", []):
            venue = g.get("venue", {})
            status = g.get("status", {})
            away_team = g.get("teams", {}).get("away", {})
            home_team = g.get("teams", {}).get("home", {})
            away_pitcher = away_team.get("probablePitcher", {})
            home_pitcher = home_team.get("probablePitcher", {})

            games.append({
                "game_pk": g.get("gamePk"),
                "game_date": g.get("officialDate"),
                "game_time": g.get("gameDate", ""),
                "status": status.get("detailedState", "Scheduled"),
                "status_code": status.get("statusCode", "S"),
                "venue_id": venue.get("id"),
                "venue_name": venue.get("name", "Unknown"),
                "away": {
                    "team_id": away_team.get("team", {}).get("id"),
                    "team_name": away_team.get("team", {}).get("name", ""),
                    "team_abbr": away_team.get("team", {}).get("abbreviation", ""),
                    "record": f"{away_team.get('leagueRecord', {}).get('wins', 0)}-{away_team.get('leagueRecord', {}).get('losses', 0)}",
                    "probable_pitcher": {
                        "id": away_pitcher.get("id"),
                        "name": away_pitcher.get("fullName", "TBD"),
                        "note": away_pitcher.get("note", ""),
                    } if away_pitcher else {"id": None, "name": "TBD", "note": ""},
                },
                "home": {
                    "team_id": home_team.get("team", {}).get("id"),
                    "team_name": home_team.get("team", {}).get("name", ""),
                    "team_abbr": home_team.get("team", {}).get("abbreviation", ""),
                    "record": f"{home_team.get('leagueRecord', {}).get('wins', 0)}-{home_team.get('leagueRecord', {}).get('losses', 0)}",
                    "probable_pitcher": {
                        "id": home_pitcher.get("id"),
                        "name": home_pitcher.get("fullName", "TBD"),
                        "note": home_pitcher.get("note", ""),
                    } if home_pitcher else {"id": None, "name": "TBD", "note": ""},
                },
                "broadcasts": [b.get("name") for b in g.get("broadcasts", [])],
            })
    return games


def get_pitcher_season_stats(pitcher_id: int, season: int = None) -> dict:
    if not season:
        season = datetime.now().year
    data = _get(f"{MLB_API}/people/{pitcher_id}", {
        "hydrate": f"stats(group=[pitching],type=[season,seasonAdvanced],season={season})"
    })
    if not data:
        return {}

    person = data.get("people", [{}])[0]
    stats_list = person.get("stats", [])

    basic = {}
    advanced = {}
    for s in stats_list:
        splits = s.get("splits", [{}])
        if not splits:
            continue
        stat_data = splits[0].get("stat", {})
        if s.get("type", {}).get("displayName") == "season":
            basic = stat_data
        elif s.get("type", {}).get("displayName") == "seasonAdvanced":
            advanced = stat_data

    return {
        "name": person.get("fullName", ""),
        "number": person.get("primaryNumber", ""),
        "bats": person.get("batSide", {}).get("code", ""),
        "throws": person.get("pitchHand", {}).get("code", ""),
        "age": person.get("currentAge"),
        "team": person.get("currentTeam", {}).get("name", ""),
        "position": person.get("primaryPosition", {}).get("abbreviation", ""),
        "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{pitcher_id}/headshot/67/current",
        "season": season,
        "stats": {
            "era": basic.get("era", "-"),
            "whip": basic.get("whip", "-"),
            "wins": basic.get("wins", 0),
            "losses": basic.get("losses", 0),
            "saves": basic.get("saves", 0),
            "games": basic.get("gamesPlayed", 0),
            "games_started": basic.get("gamesStarted", 0),
            "innings_pitched": basic.get("inningsPitched", "0.0"),
            "strikeouts": basic.get("strikeOuts", 0),
            "walks": basic.get("baseOnBalls", 0),
            "hits": basic.get("hits", 0),
            "home_runs": basic.get("homeRuns", 0),
            "k9": basic.get("strikeoutsPer9Inn", "-"),
            "bb9": basic.get("walksPer9Inn", "-"),
            "hr9": basic.get("homeRunsPer9", "-"),
            "k_pct": advanced.get("strikeoutPercentage", "-"),
            "bb_pct": advanced.get("walkPercentage", "-"),
            "k_bb": advanced.get("strikeoutWalkRatio", "-"),
            "fip": advanced.get("fieldingIndependentPitching", "-"),
            "avg": basic.get("avg", "-"),
            "obp": basic.get("obp", "-"),
            "slg": basic.get("slg", "-"),
            "ops": basic.get("ops", "-"),
            "babip": advanced.get("babip", "-"),
            "lob_pct": advanced.get("lobPercentage", "-"),
            "ground_ball_pct": advanced.get("groundOutsToAirouts", "-"),
            "pitch_count": basic.get("numberOfPitches", 0),
        }
    }


def get_pitcher_splits(pitcher_id: int, season: int = None) -> dict:
    if not season:
        season = datetime.now().year
    data = _get(f"{MLB_API}/people/{pitcher_id}/stats", {
        "stats": "statSplits",
        "group": "pitching",
        "season": season,
        "sportId": 1,
    })
    if not data:
        return {}

    splits = {}
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            split_type = split.get("split", {}).get("description", "")
            stat = split.get("stat", {})
            if split_type in ("vs. Left", "vs. Right", "Home", "Away"):
                splits[split_type] = {
                    "era": stat.get("era", "-"),
                    "avg": stat.get("avg", "-"),
                    "ops": stat.get("ops", "-"),
                    "whip": stat.get("whip", "-"),
                    "k9": stat.get("strikeoutsPer9Inn", "-"),
                    "bb9": stat.get("walksPer9Inn", "-"),
                    "ip": stat.get("inningsPitched", "0.0"),
                    "hr": stat.get("homeRuns", 0),
                }
    return splits


def get_pitcher_recent_starts(pitcher_id: int, season: int = None, limit: int = 7) -> list:
    if not season:
        season = datetime.now().year
    data = _get(f"{MLB_API}/people/{pitcher_id}/stats", {
        "stats": "gameLog",
        "group": "pitching",
        "season": season,
        "sportId": 1,
    })
    if not data:
        return []

    starts = []
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            stat = split.get("stat", {})
            if stat.get("gamesStarted", 0) == 0 and stat.get("inningsPitched", "0.0") == "0.0":
                continue
            game = split.get("game", {})
            team = split.get("team", {})
            opponent = split.get("opponent", {})
            starts.append({
                "date": split.get("date", ""),
                "opponent": opponent.get("abbreviation", ""),
                "opponent_name": opponent.get("name", ""),
                "home_away": split.get("isHome", False),
                "result": stat.get("wins", 0) and "W" or stat.get("losses", 0) and "L" or "-",
                "ip": stat.get("inningsPitched", "0.0"),
                "h": stat.get("hits", 0),
                "r": stat.get("runs", 0),
                "er": stat.get("earnedRuns", 0),
                "bb": stat.get("baseOnBalls", 0),
                "k": stat.get("strikeOuts", 0),
                "hr": stat.get("homeRuns", 0),
                "pitches": stat.get("numberOfPitches", 0),
                "strikes": stat.get("strikes", 0),
                "era_for_game": _game_era(stat),
            })

    return sorted(starts, key=lambda x: x["date"], reverse=True)[:limit]


def _game_era(stat: dict) -> str:
    er = stat.get("earnedRuns", 0) or 0
    ip_str = stat.get("inningsPitched", "0.0") or "0.0"
    try:
        parts = str(ip_str).split(".")
        full_inn = int(parts[0])
        thirds = int(parts[1]) if len(parts) > 1 else 0
        total_thirds = full_inn * 3 + thirds
        if total_thirds == 0:
            return "-"
        era = (er / total_thirds) * 27
        return f"{era:.2f}"
    except:
        return "-"


def get_pitch_arsenal(pitcher_id: int, season: int = None) -> list:
    if not season:
        season = datetime.now().year

    data = _get(f"{MLB_API}/people/{pitcher_id}/stats", {
        "stats": "pitchArsenal",
        "group": "pitching",
        "season": season,
        "sportId": 1,
    })
    if not data:
        return []

    arsenal = []
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            stat = split.get("stat", {})
            pitch_code = stat.get("type", {}).get("code", "")
            arsenal.append({
                "pitch_type": pitch_code,
                "pitch_name": PITCH_TYPE_NAMES.get(pitch_code, stat.get("type", {}).get("description", pitch_code)),
                "usage_pct": round(float(stat.get("percentage", 0) or 0), 1),
                "avg_velocity": round(float(stat.get("averageSpeed", 0) or 0), 1),
                "avg_spin": stat.get("spinRate"),
                "whiff_pct": round(float(stat.get("whiffPercentage", 0) or 0), 1),
                "put_away_pct": round(float(stat.get("putAwayPercentage", 0) or 0), 1),
                "hard_hit_pct": stat.get("hardHitPercentage"),
                "batting_avg": stat.get("battingAverage", "-"),
                "slg": stat.get("sluggingPercentage", "-"),
            })

    return sorted(arsenal, key=lambda x: x["usage_pct"], reverse=True)


def get_batter_season_stats(batter_id: int, season: int = None) -> dict:
    if not season:
        season = datetime.now().year
    data = _get(f"{MLB_API}/people/{batter_id}", {
        "hydrate": f"stats(group=[hitting],type=[season,seasonAdvanced],season={season})"
    })
    if not data:
        return {}

    person = data.get("people", [{}])[0]
    stats_list = person.get("stats", [])

    basic = {}
    advanced = {}
    for s in stats_list:
        splits = s.get("splits", [{}])
        if not splits:
            continue
        stat_data = splits[0].get("stat", {})
        if s.get("type", {}).get("displayName") == "season":
            basic = stat_data
        elif s.get("type", {}).get("displayName") == "seasonAdvanced":
            advanced = stat_data

    return {
        "name": person.get("fullName", ""),
        "number": person.get("primaryNumber", ""),
        "bats": person.get("batSide", {}).get("code", ""),
        "throws": person.get("pitchHand", {}).get("code", ""),
        "age": person.get("currentAge"),
        "team": person.get("currentTeam", {}).get("name", ""),
        "position": person.get("primaryPosition", {}).get("abbreviation", ""),
        "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{batter_id}/headshot/67/current",
        "season": season,
        "stats": {
            "avg": basic.get("avg", ".000"),
            "obp": basic.get("obp", ".000"),
            "slg": basic.get("slg", ".000"),
            "ops": basic.get("ops", ".000"),
            "pa": basic.get("plateAppearances", 0),
            "ab": basic.get("atBats", 0),
            "hits": basic.get("hits", 0),
            "doubles": basic.get("doubles", 0),
            "triples": basic.get("triples", 0),
            "hr": basic.get("homeRuns", 0),
            "rbi": basic.get("rbi", 0),
            "runs": basic.get("runs", 0),
            "bb": basic.get("baseOnBalls", 0),
            "k": basic.get("strikeOuts", 0),
            "sb": basic.get("stolenBases", 0),
            "k_pct": advanced.get("strikeoutPercentage", "-"),
            "bb_pct": advanced.get("walkPercentage", "-"),
            "iso": advanced.get("isolatedPower", "-"),
            "babip": advanced.get("babip", "-"),
            "woba": advanced.get("woba", "-"),
            "wrc_plus": advanced.get("wRCPlus", "-"),
            "hard_hit_pct": advanced.get("hardHitPercentage", "-"),
            "barrel_pct": advanced.get("barrelBatted", "-"),
            "exit_velocity": advanced.get("avgHitSpeed", "-"),
            "launch_angle": advanced.get("avgHitAngle", "-"),
        }
    }


def get_batter_splits(batter_id: int, season: int = None) -> dict:
    if not season:
        season = datetime.now().year
    data = _get(f"{MLB_API}/people/{batter_id}/stats", {
        "stats": "statSplits",
        "group": "hitting",
        "season": season,
        "sportId": 1,
    })
    if not data:
        return {}

    splits = {}
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            split_type = split.get("split", {}).get("description", "")
            stat = split.get("stat", {})
            if split_type in ("vs. Left", "vs. Right", "Home", "Away", "Last 7 days", "Last 14 days", "Last 30 days"):
                splits[split_type] = {
                    "avg": stat.get("avg", ".000"),
                    "obp": stat.get("obp", ".000"),
                    "slg": stat.get("slg", ".000"),
                    "ops": stat.get("ops", ".000"),
                    "pa": stat.get("plateAppearances", 0),
                    "hr": stat.get("homeRuns", 0),
                    "k": stat.get("strikeOuts", 0),
                    "bb": stat.get("baseOnBalls", 0),
                }
    return splits


def get_batter_vs_pitcher(batter_id: int, pitcher_id: int, season: int = None) -> dict:
    """Career and recent H2H stats between batter and pitcher."""
    career_data = _get(f"{MLB_API}/people/{batter_id}/stats", {
        "stats": "vsPlayer",
        "group": "hitting",
        "opposingPlayerId": pitcher_id,
        "sportId": 1,
    })

    season_data = None
    if season:
        season_data = _get(f"{MLB_API}/people/{batter_id}/stats", {
            "stats": "vsPlayerTotal",
            "group": "hitting",
            "opposingPlayerId": pitcher_id,
            "season": season,
            "sportId": 1,
        })

    def parse_splits(data):
        if not data:
            return []
        results = []
        for entry in data.get("stats", []):
            for split in entry.get("splits", []):
                stat = split.get("stat", {})
                results.append({
                    "season": split.get("season", "career"),
                    "pa": stat.get("plateAppearances", 0),
                    "ab": stat.get("atBats", 0),
                    "hits": stat.get("hits", 0),
                    "doubles": stat.get("doubles", 0),
                    "triples": stat.get("triples", 0),
                    "hr": stat.get("homeRuns", 0),
                    "rbi": stat.get("rbi", 0),
                    "bb": stat.get("baseOnBalls", 0),
                    "k": stat.get("strikeOuts", 0),
                    "avg": stat.get("avg", ".000"),
                    "obp": stat.get("obp", ".000"),
                    "slg": stat.get("slg", ".000"),
                    "ops": stat.get("ops", ".000"),
                })
        return results

    career = parse_splits(career_data)
    current = parse_splits(season_data)

    if not career and not current:
        return {"career": [], "season": [], "summary": "No H2H history found"}

    career_summary = {}
    if career:
        career_summary = career[0] if len(career) == 1 else _aggregate_splits(career)

    return {
        "career": career,
        "season": current,
        "career_summary": career_summary,
        "summary": _h2h_summary(career_summary),
    }


def _aggregate_splits(splits: list) -> dict:
    if not splits:
        return {}
    total_ab = sum(s.get("ab", 0) for s in splits)
    total_hits = sum(s.get("hits", 0) for s in splits)
    total_pa = sum(s.get("pa", 0) for s in splits)
    total_bb = sum(s.get("bb", 0) for s in splits)
    total_hr = sum(s.get("hr", 0) for s in splits)
    total_k = sum(s.get("k", 0) for s in splits)
    total_2b = sum(s.get("doubles", 0) for s in splits)
    total_3b = sum(s.get("triples", 0) for s in splits)
    total_rbi = sum(s.get("rbi", 0) for s in splits)

    avg = f".{int(total_hits/total_ab*1000):03d}" if total_ab > 0 else ".000"
    obp_num = total_hits + total_bb
    obp = f".{int(obp_num/total_pa*1000):03d}" if total_pa > 0 else ".000"
    tb = total_hits + total_2b + 2*total_3b + 3*total_hr
    slg = f".{int(tb/total_ab*1000):03d}" if total_ab > 0 else ".000"

    return {
        "pa": total_pa, "ab": total_ab, "hits": total_hits, "doubles": total_2b,
        "triples": total_3b, "hr": total_hr, "rbi": total_rbi, "bb": total_bb,
        "k": total_k, "avg": avg, "obp": obp, "slg": slg,
        "ops": f"{float(obp)+float(slg):.3f}",
    }


def _h2h_summary(stats: dict) -> str:
    if not stats:
        return "No historical matchup data"
    pa = stats.get("pa", 0)
    avg = stats.get("avg", ".000")
    hr = stats.get("hr", 0)
    k = stats.get("k", 0)
    ops = stats.get("ops", ".000")
    if pa < 5:
        return f"Limited history ({pa} PA)"
    try:
        avg_val = float(avg)
        ops_val = float(ops)
        k_pct = (k / pa * 100) if pa > 0 else 0
        if avg_val >= 0.350 or ops_val >= 1.000:
            edge = "Strong batter advantage"
        elif avg_val >= 0.280 or ops_val >= 0.800:
            edge = "Slight batter advantage"
        elif avg_val <= 0.150 or ops_val <= 0.500:
            edge = "Strong pitcher dominance"
        elif avg_val <= 0.200 or ops_val <= 0.600:
            edge = "Pitcher advantage"
        else:
            edge = "Even matchup"
        return f"{edge} — {pa} PA, {avg} AVG, {hr} HR, {ops} OPS, {k_pct:.0f}% K-rate"
    except:
        return f"{pa} PA, {avg} AVG, {hr} HR"


def get_team_lineup(game_pk: int, team_side: str = "home") -> list:
    """Get confirmed or probable lineup from boxscore."""
    data = _get(f"{MLB_API}/game/{game_pk}/boxscore")
    if not data:
        return []

    team_data = data.get("teams", {}).get(team_side, {})
    batting_order = team_data.get("battingOrder", [])
    players = team_data.get("players", {})

    lineup = []
    for i, player_id in enumerate(batting_order):
        key = f"ID{player_id}"
        p = players.get(key, {})
        person = p.get("person", {})
        pos = p.get("position", {})
        stats = p.get("seasonStats", {}).get("batting", {})
        lineup.append({
            "order": i + 1,
            "player_id": player_id,
            "name": person.get("fullName", ""),
            "position": pos.get("abbreviation", ""),
            "bats": p.get("batSide", {}).get("code", ""),
            "season_avg": stats.get("avg", ".000"),
            "season_ops": stats.get("ops", ".000"),
            "season_hr": stats.get("homeRuns", 0),
        })
    return lineup


def get_game_lineups(game_pk: int) -> dict:
    data = _get(f"{MLB_API}/game/{game_pk}/boxscore")
    if not data:
        return {"home": [], "away": []}
    return {
        "home": get_team_lineup(game_pk, "home"),
        "away": get_team_lineup(game_pk, "away"),
    }


def get_projected_lineup(team_id: int, season: int = None, exclude_date: str = None) -> list:
    """Fetch team's most recent completed game lineup as a projected proxy."""
    if not season:
        season = datetime.now().year
    end_date = exclude_date or date.today().strftime("%Y-%m-%d")
    data = _get(f"{MLB_API}/schedule", {
        "teamId": team_id,
        "startDate": f"{season}-03-01",
        "endDate": end_date,
        "sportId": 1,
        "gameType": "R",
    })
    if not data:
        return []

    recent_pk = None
    team_side = "away"
    for date_entry in sorted(data.get("dates", []), key=lambda x: x.get("date", ""), reverse=True):
        for g in date_entry.get("games", []):
            if g.get("status", {}).get("detailedState") == "Final":
                recent_pk = g.get("gamePk")
                away_id = g.get("teams", {}).get("away", {}).get("team", {}).get("id")
                team_side = "away" if away_id == team_id else "home"
                break
        if recent_pk:
            break

    if not recent_pk:
        return []

    bs = _get(f"{MLB_API}/game/{recent_pk}/boxscore")
    if not bs:
        return []

    team_data = bs.get("teams", {}).get(team_side, {})
    lineup = _extract_lineup(team_data)
    for p in lineup:
        p["projected"] = True
    return lineup


def get_weather_for_venue(venue_id: int, game_date: str, game_time: str = None) -> dict:
    """Get weather forecast for a venue using Open-Meteo API."""
    venue_info = None
    for vid, info in VENUE_COORDS.items():
        if vid == venue_id:
            venue_info = info
            break

    if not venue_info:
        return {"available": False, "note": "Indoor/dome venue or coordinates unavailable"}

    name, lat, lon = venue_info

    INDOOR_VENUES = ["Globe Life Field", "Tropicana Field", "loanDepot park",
                     "Rogers Centre", "American Family Field", "Chase Field", "Minute Maid Park"]

    is_retractable = name in ["American Family Field", "Chase Field", "Minute Maid Park", "loanDepot park"]
    is_dome = name in ["Globe Life Field", "Tropicana Field", "Rogers Centre"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation_probability,cloud_cover,weather_code",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "forecast_days": 3,
        "timezone": "auto",
    }

    data = _get(WEATHER_API, params)
    if not data:
        return {"available": False, "note": "Weather API unavailable"}

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    target_hour = 18
    if game_time:
        try:
            gt = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
            target_hour = gt.hour
        except:
            pass

    best_idx = 0
    best_diff = float("inf")
    for i, t in enumerate(times):
        try:
            dt = datetime.fromisoformat(t)
            if dt.strftime("%Y-%m-%d") == game_date:
                diff = abs(dt.hour - target_hour)
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
        except:
            continue

    def safe_get(arr, idx):
        try:
            return arr[idx] if idx < len(arr) else None
        except:
            return None

    temp = safe_get(hourly.get("temperature_2m", []), best_idx)
    humidity = safe_get(hourly.get("relative_humidity_2m", []), best_idx)
    wind_speed = safe_get(hourly.get("wind_speed_10m", []), best_idx)
    wind_dir = safe_get(hourly.get("wind_direction_10m", []), best_idx)
    precip_prob = safe_get(hourly.get("precipitation_probability", []), best_idx)
    cloud_cover = safe_get(hourly.get("cloud_cover", []), best_idx)
    weather_code = safe_get(hourly.get("weather_code", []), best_idx)

    wind_cardinal = _degrees_to_cardinal(wind_dir) if wind_dir is not None else "N/A"
    weather_desc = _wmo_code_to_desc(weather_code)

    impact = _weather_impact(temp, wind_speed, wind_dir, precip_prob, is_dome)

    return {
        "available": True,
        "venue_name": name,
        "is_dome": is_dome,
        "is_retractable": is_retractable,
        "temperature": temp,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction_degrees": wind_dir,
        "wind_direction": wind_cardinal,
        "precipitation_probability": precip_prob,
        "cloud_cover": cloud_cover,
        "conditions": weather_desc,
        "impact": impact,
    }


def _degrees_to_cardinal(deg: float) -> str:
    if deg is None:
        return "N/A"
    dirs = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
            "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return dirs[idx]


def _wmo_code_to_desc(code) -> str:
    if code is None:
        return "Unknown"
    mapping = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Icy fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Heavy drizzle", 61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Light snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Rain showers",
        81: "Moderate rain showers", 82: "Violent rain showers", 95: "Thunderstorm",
        96: "Thunderstorm with hail", 99: "Severe thunderstorm",
    }
    return mapping.get(int(code), f"Code {code}")


def _weather_impact(temp, wind_speed, wind_dir, precip_prob, is_dome) -> dict:
    if is_dome:
        return {"offense": "neutral", "hr": "neutral", "note": "Indoor venue — weather irrelevant", "score": 0}

    score = 0
    notes = []

    if temp is not None:
        if temp >= 85:
            score += 1.5
            notes.append(f"Hot ({temp}°F) boosts offense/HR")
        elif temp >= 75:
            score += 0.8
            notes.append(f"Warm ({temp}°F) slightly favors offense")
        elif temp <= 45:
            score -= 1.5
            notes.append(f"Cold ({temp}°F) suppresses offense/HR")
        elif temp <= 55:
            score -= 0.8
            notes.append(f"Cool ({temp}°F) slight pitcher advantage")

    if wind_speed is not None and wind_dir is not None:
        if wind_speed >= 15:
            blowing_out = wind_dir in range(180, 360) or wind_dir < 45
            if blowing_out and wind_speed >= 20:
                score += 2.0
                notes.append(f"Wind blowing OUT {wind_speed}mph {_degrees_to_cardinal(wind_dir)} — big HR boost")
            elif blowing_out:
                score += 1.0
                notes.append(f"Wind blowing out {wind_speed}mph — HR-friendly")
            else:
                score -= 1.0
                notes.append(f"Wind blowing IN {wind_speed}mph — suppresses HR")
        elif wind_speed >= 10:
            notes.append(f"Moderate wind {wind_speed}mph {_degrees_to_cardinal(wind_dir)}")

    if precip_prob is not None and precip_prob >= 50:
        score -= 1.0
        notes.append(f"{precip_prob}% rain chance — potential delay risk")
    elif precip_prob is not None and precip_prob >= 30:
        notes.append(f"{precip_prob}% rain chance — monitor")

    if score >= 2.0:
        offense_label = "Strong Hitter Boost"
        hr_label = "Very HR-Friendly"
    elif score >= 1.0:
        offense_label = "Hitter-Friendly"
        hr_label = "HR-Friendly"
    elif score <= -2.0:
        offense_label = "Strong Pitcher Boost"
        hr_label = "HR-Suppressing"
    elif score <= -1.0:
        offense_label = "Pitcher-Friendly"
        hr_label = "HR-Suppressing"
    else:
        offense_label = "Neutral"
        hr_label = "Neutral"

    return {
        "offense": offense_label,
        "hr": hr_label,
        "score": round(score, 1),
        "note": " | ".join(notes) if notes else "Neutral conditions",
    }


def get_ballpark_factors(venue_name: str) -> dict:
    for park_name, factors in PARK_FACTORS.items():
        if park_name.lower() in venue_name.lower() or venue_name.lower() in park_name.lower():
            return {"venue": venue_name, **factors}
    return {"venue": venue_name, "run": 1.00, "hr": 1.00, "hit": 1.00, "description": "Neutral (data unavailable)"}


def search_mlb_players(query: str, player_type: str = "all") -> list:
    data = _get(f"{MLB_API}/sports/1/players", {
        "season": datetime.now().year,
        "gameType": "R",
    })
    if not data:
        return []

    query_lower = query.lower()
    all_players = data.get("people", [])
    matches = [p for p in all_players if query_lower in p.get("fullName", "").lower()][:20]

    results = []
    for p in matches:
        pos = p.get("primaryPosition", {}).get("abbreviation", "")
        pos_type = p.get("primaryPosition", {}).get("type", "")
        if player_type == "pitcher" and pos not in ("SP", "RP", "P"):
            continue
        if player_type == "batter" and pos in ("SP", "RP", "P"):
            continue
        results.append({
            "id": p.get("id"),
            "name": p.get("fullName", ""),
            "team": p.get("currentTeam", {}).get("name", ""),
            "team_abbr": p.get("currentTeam", {}).get("abbreviation", ""),
            "position": pos,
            "position_type": pos_type,
            "bats": p.get("batSide", {}).get("code", ""),
            "throws": p.get("pitchHand", {}).get("code", ""),
            "number": p.get("primaryNumber", ""),
            "headshot": f"https://img.mlbstatic.com/mlb-photos/image/upload/d_people:generic:headshot:67:current.png/w_213,q_auto:best/v1/people/{p.get('id')}/headshot/67/current",
        })
    return results


def get_full_game_analysis(game_pk: int) -> dict:
    """Master function — full breakdown of a game."""
    game_data = _get(f"{MLB_API_V1_1}/game/{game_pk}/feed/live")
    if not game_data:
        return {"error": "Game not found"}

    game_info = game_data.get("gameData", {})
    game_status = game_info.get("status", {})
    teams_info = game_info.get("teams", {})
    venue_info = game_info.get("venue", {})
    weather_info = game_info.get("weather", {})
    datetime_info = game_info.get("datetime", {})
    probable_pitchers = game_info.get("probablePitchers", {})

    away_team = teams_info.get("away", {})
    home_team = teams_info.get("home", {})
    venue_id = venue_info.get("id")
    venue_name = venue_info.get("name", "")
    game_date = datetime_info.get("officialDate", date.today().strftime("%Y-%m-%d"))
    game_time = datetime_info.get("dateTime", "")

    away_pitcher_info = probable_pitchers.get("away", {})
    home_pitcher_info = probable_pitchers.get("home", {})

    away_pitcher_id = away_pitcher_info.get("id")
    home_pitcher_id = home_pitcher_info.get("id")

    season = datetime.now().year

    away_pitcher_stats = get_pitcher_season_stats(away_pitcher_id, season) if away_pitcher_id else {}
    home_pitcher_stats = get_pitcher_season_stats(home_pitcher_id, season) if home_pitcher_id else {}

    away_pitcher_arsenal = get_pitch_arsenal(away_pitcher_id, season) if away_pitcher_id else []
    home_pitcher_arsenal = get_pitch_arsenal(home_pitcher_id, season) if home_pitcher_id else []

    away_pitcher_splits = get_pitcher_splits(away_pitcher_id, season) if away_pitcher_id else {}
    home_pitcher_splits = get_pitcher_splits(home_pitcher_id, season) if home_pitcher_id else {}

    away_pitcher_recent = get_pitcher_recent_starts(away_pitcher_id, season, 5) if away_pitcher_id else []
    home_pitcher_recent = get_pitcher_recent_starts(home_pitcher_id, season, 5) if home_pitcher_id else []

    boxscore = _get(f"{MLB_API}/game/{game_pk}/boxscore") or {}
    box_teams = boxscore.get("teams", {})
    away_lineup = _extract_lineup(box_teams.get("away", {}))
    home_lineup = _extract_lineup(box_teams.get("home", {}))

    away_team_id = away_team.get("id")
    home_team_id = home_team.get("id")
    lineup_status = "confirmed"
    if not away_lineup and away_team_id:
        away_lineup = get_projected_lineup(away_team_id, season, game_date)
        lineup_status = "projected"
    if not home_lineup and home_team_id:
        home_lineup = get_projected_lineup(home_team_id, season, game_date)
        lineup_status = "projected"

    weather = get_weather_for_venue(venue_id, game_date, game_time)
    if weather_info:
        weather["mlb_reported"] = {
            "condition": weather_info.get("condition", ""),
            "temp": weather_info.get("temp", ""),
            "wind": weather_info.get("wind", ""),
        }

    park_factors = get_ballpark_factors(venue_name)

    away_vs_home_pitcher = []
    home_vs_away_pitcher = []

    if home_pitcher_id:
        for batter in away_lineup[:9]:
            if batter.get("player_id"):
                h2h = get_batter_vs_pitcher(batter["player_id"], home_pitcher_id)
                away_vs_home_pitcher.append({
                    "batter": batter,
                    "h2h": h2h,
                    "matchup_grade": _grade_matchup(h2h.get("career_summary", {}), batter),
                })
                time.sleep(0.2)

    if away_pitcher_id:
        for batter in home_lineup[:9]:
            if batter.get("player_id"):
                h2h = get_batter_vs_pitcher(batter["player_id"], away_pitcher_id)
                home_vs_away_pitcher.append({
                    "batter": batter,
                    "h2h": h2h,
                    "matchup_grade": _grade_matchup(h2h.get("career_summary", {}), batter),
                })
                time.sleep(0.2)

    matchup_edge = _overall_matchup_edge(
        away_pitcher_stats, home_pitcher_stats,
        away_lineup, home_lineup,
        park_factors, weather
    )

    return {
        "game_pk": game_pk,
        "game_date": game_date,
        "game_time": game_time,
        "status": game_status.get("detailedState", ""),
        "venue": {"id": venue_id, "name": venue_name},
        "away_team": {
            "id": away_team.get("id"),
            "name": away_team.get("name", ""),
            "abbr": away_team.get("abbreviation", ""),
            "record": _team_record(away_team),
        },
        "home_team": {
            "id": home_team.get("id"),
            "name": home_team.get("name", ""),
            "abbr": home_team.get("abbreviation", ""),
            "record": _team_record(home_team),
        },
        "pitchers": {
            "away": {
                "info": {"id": away_pitcher_id, "name": away_pitcher_info.get("fullName", "TBD")},
                "stats": away_pitcher_stats,
                "arsenal": away_pitcher_arsenal,
                "splits": away_pitcher_splits,
                "recent_starts": away_pitcher_recent,
            },
            "home": {
                "info": {"id": home_pitcher_id, "name": home_pitcher_info.get("fullName", "TBD")},
                "stats": home_pitcher_stats,
                "arsenal": home_pitcher_arsenal,
                "splits": home_pitcher_splits,
                "recent_starts": home_pitcher_recent,
            },
        },
        "lineups": {
            "away": away_lineup,
            "home": home_lineup,
            "status": lineup_status,
        },
        "matchups": {
            "away_batters_vs_home_pitcher": away_vs_home_pitcher,
            "home_batters_vs_away_pitcher": home_vs_away_pitcher,
        },
        "weather": weather,
        "park_factors": park_factors,
        "analysis": matchup_edge,
        "season": season,
    }


def _extract_lineup(team_data: dict) -> list:
    batting_order = team_data.get("battingOrder", [])
    players = team_data.get("players", {})
    lineup = []
    for i, pid in enumerate(batting_order):
        key = f"ID{pid}"
        p = players.get(key, {})
        person = p.get("person", {})
        pos = p.get("position", {})
        s = p.get("seasonStats", {}).get("batting", {})
        lineup.append({
            "order": i + 1,
            "player_id": pid,
            "name": person.get("fullName", ""),
            "position": pos.get("abbreviation", ""),
            "bats": p.get("batSide", {}).get("code", ""),
            "avg": s.get("avg", ".000"),
            "obp": s.get("obp", ".000"),
            "slg": s.get("slg", ".000"),
            "ops": s.get("ops", ".000"),
            "hr": s.get("homeRuns", 0),
            "rbi": s.get("rbi", 0),
        })
    return lineup


def _team_record(team_data: dict) -> str:
    record = team_data.get("record", {})
    return f"{record.get('wins', 0)}-{record.get('losses', 0)}"


def _grade_matchup(career_stats: dict, batter: dict) -> dict:
    """
    Grade batter vs this specific pitcher from H2H history.
    When H2H PA < 5, falls back to season OPS+ context.

    OPS thresholds are intentionally higher for the H2H grade because
    career OPS vs a specific pitcher (even a dominant one) regresses heavily
    toward the batter's true talent — small sample noise is brutal.
    We Bayesian-shrink: blend H2H OPS with season OPS based on PA.
    """
    season_ops  = float(batter.get("ops",  ".700") or ".700")
    season_avg  = float(batter.get("avg",  ".240") or ".240")
    h2h_pa = (career_stats or {}).get("pa", 0)

    if not career_stats or h2h_pa < 5:
        # No meaningful H2H — grade on season OPS
        if season_ops >= 0.920:
            return {"grade": "A",  "label": "Elite Season OPS",  "color": "emerald"}
        elif season_ops >= 0.830:
            return {"grade": "B+", "label": "Strong Hitter",      "color": "green"}
        elif season_ops >= 0.750:
            return {"grade": "B",  "label": "Above Avg",          "color": "green"}
        elif season_ops >= 0.680:
            return {"grade": "C",  "label": "Average",            "color": "yellow"}
        elif season_ops >= 0.580:
            return {"grade": "D",  "label": "Below Avg",          "color": "orange"}
        else:
            return {"grade": "F",  "label": "Struggling",         "color": "red"}

    try:
        h2h_ops = float(career_stats.get("ops", ".700") or ".700")
        h2h_avg = float(career_stats.get("avg", ".240") or ".240")

        # Bayesian shrinkage: blend H2H with season based on sample
        # Full trust at 40+ PA; ~50% shrink at 10 PA
        blend = min(h2h_pa / 40.0, 1.0)
        adj_ops = blend * h2h_ops + (1 - blend) * season_ops
        adj_avg = blend * h2h_avg + (1 - blend) * season_avg

        if adj_ops >= 1.050 or adj_avg >= 0.400:
            return {"grade": "A+", "label": "Crushes This Pitcher", "color": "emerald"}
        elif adj_ops >= 0.880 or adj_avg >= 0.310:
            return {"grade": "A",  "label": "Strong vs Pitcher",    "color": "emerald"}
        elif adj_ops >= 0.780 or adj_avg >= 0.270:
            return {"grade": "B",  "label": "Favorable History",    "color": "green"}
        elif adj_ops >= 0.680 or adj_avg >= 0.230:
            return {"grade": "C",  "label": "Even Matchup",         "color": "yellow"}
        elif adj_ops >= 0.550 or adj_avg >= 0.180:
            return {"grade": "D",  "label": "Pitcher Has Edge",     "color": "orange"}
        else:
            return {"grade": "F",  "label": "Pitcher Dominates",    "color": "red"}
    except Exception:
        return {"grade": "?", "label": "Limited Data", "color": "zinc"}


def _overall_matchup_edge(away_stats, home_stats, away_lineup, home_lineup, park_factors, weather) -> dict:
    notes = []
    score = 0.0

    def era_score(stats):
        try:
            era = float(stats.get("stats", {}).get("era", "4.50") or "4.50")
            if era < 3.00:
                return 2.0
            elif era < 3.50:
                return 1.5
            elif era < 4.00:
                return 1.0
            elif era < 4.50:
                return 0.5
            elif era < 5.00:
                return -0.5
            else:
                return -1.0
        except:
            return 0.0

    away_ace_score = era_score(away_stats)
    home_ace_score = era_score(home_stats)

    if away_ace_score > home_ace_score:
        score += (away_ace_score - home_ace_score) * 0.5
        notes.append(f"Away pitcher ERA edge ({away_stats.get('stats', {}).get('era', '?')} vs {home_stats.get('stats', {}).get('era', '?')})")
    elif home_ace_score > away_ace_score:
        score -= (home_ace_score - away_ace_score) * 0.5
        notes.append(f"Home pitcher ERA edge ({home_stats.get('stats', {}).get('era', '?')} vs {away_stats.get('stats', {}).get('era', '?')})")

    park_hr = park_factors.get("hr", 1.0)
    if park_hr >= 1.15:
        notes.append(f"HR-friendly park (PF: {park_hr:.2f})")
    elif park_hr <= 0.88:
        notes.append(f"HR-suppressing park (PF: {park_hr:.2f})")

    weather_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0
    if abs(weather_score) >= 1.0:
        notes.append(weather.get("impact", {}).get("note", ""))

    total_runs_estimate = 9.0 * (park_hr * 0.3 + 0.7) + weather_score * 0.5
    total_runs_estimate = round(max(5.0, min(14.0, total_runs_estimate)), 1)

    if score >= 1.5:
        game_edge = "Away Team Pitching Advantage"
    elif score >= 0.5:
        game_edge = "Slight Away Edge"
    elif score <= -1.5:
        game_edge = "Home Team Pitching Advantage"
    elif score <= -0.5:
        game_edge = "Slight Home Edge"
    else:
        game_edge = "Even Matchup"

    return {
        "edge": game_edge,
        "score": round(score, 2),
        "notes": notes,
        "estimated_total": total_runs_estimate,
        "over_under_lean": "Over" if weather_score >= 1.0 and park_hr >= 1.05 else "Under" if weather_score <= -1.0 and park_hr <= 0.95 else "Neutral",
    }


# ── Statcast / Baseball Savant Data Layer ─────────────────────────────────────

SAVANT_BATTING_URL  = "https://baseballsavant.mlb.com/leaderboard/statcast?type=batter&year={year}&position=&team=&min=10&csv=true"
SAVANT_PITCHING_URL = "https://baseballsavant.mlb.com/leaderboard/statcast?type=pitcher&year={year}&position=&team=&min=1&csv=true"
SAVANT_XSTATS_URL   = "https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=batter&year={year}&position=&team=&min=10&csv=true"
SAVANT_BAT_TRACK_URL = "https://baseballsavant.mlb.com/leaderboard/bat-tracking?type=batter&year={year}&min=10&csv=true"

_savant_batting:   dict = {}
_savant_pitching:  dict = {}
_savant_xstats:    dict = {}
_savant_bat_track: dict = {}


def _fetch_savant_csv(url: str) -> list:
    import csv, io
    headers = {"User-Agent": "Mozilla/5.0 PropStats/1.0"}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        text = r.text.lstrip('﻿')
        reader = csv.DictReader(io.StringIO(text))
        return [row for row in reader]
    except Exception:
        return []


def _safe_float(val, default=0.0):
    try:
        return float(val) if val not in (None, '', 'null') else default
    except (ValueError, TypeError):
        return default


def load_savant_batting(season: int = None) -> dict:
    global _savant_batting
    if not season:
        season = datetime.now().year
    if season in _savant_batting:
        return _savant_batting[season]
    rows = _fetch_savant_csv(SAVANT_BATTING_URL.format(year=season))
    result = {}
    for row in rows:
        pid = row.get("player_id", "").strip()
        if pid:
            result[pid] = {
                "barrel_pct":   _safe_float(row.get("brl_percent")),
                "barrel_pa":    _safe_float(row.get("brl_pa")),
                "hard_hit_pct": _safe_float(row.get("ev95percent")),
                "exit_velo":    _safe_float(row.get("avg_hit_speed")),
                "ev50":         _safe_float(row.get("ev50")),
                "sweet_spot":   _safe_float(row.get("anglesweetspotpercent")),
                "max_ev":       _safe_float(row.get("max_hit_speed")),
                "avg_distance": _safe_float(row.get("avg_distance")),
                "avg_hr_dist":  _safe_float(row.get("avg_hr_distance")),
            }
    if result:
        _savant_batting[season] = result
    return result


def load_savant_pitching(season: int = None) -> dict:
    global _savant_pitching
    if not season:
        season = datetime.now().year
    if season in _savant_pitching:
        return _savant_pitching[season]
    rows = _fetch_savant_csv(SAVANT_PITCHING_URL.format(year=season))
    result = {}
    for row in rows:
        pid = row.get("player_id", "").strip()
        if pid:
            result[pid] = {
                "barrel_pct_against":   _safe_float(row.get("brl_percent")),
                "hard_hit_pct_against": _safe_float(row.get("ev95percent")),
                "exit_velo_against":    _safe_float(row.get("avg_hit_speed")),
                "ev50_against":         _safe_float(row.get("ev50")),
                "sweet_spot_against":   _safe_float(row.get("anglesweetspotpercent")),
            }
    if result:
        _savant_pitching[season] = result
    return result


def load_savant_xstats(season: int = None) -> dict:
    global _savant_xstats
    if not season:
        season = datetime.now().year
    if season in _savant_xstats:
        return _savant_xstats[season]
    rows = _fetch_savant_csv(SAVANT_XSTATS_URL.format(year=season))
    result = {}
    for row in rows:
        pid = row.get("player_id", "").strip()
        if pid:
            result[pid] = {
                "xba":    _safe_float(row.get("est_ba")),
                "xslg":   _safe_float(row.get("est_slg")),
                "xwoba":  _safe_float(row.get("est_woba")),
                "ba":     _safe_float(row.get("ba")),
                "slg":    _safe_float(row.get("slg")),
                "woba":   _safe_float(row.get("woba")),
            }
    if result:
        _savant_xstats[season] = result
    return result


def load_bat_tracking(season: int = None) -> dict:
    global _savant_bat_track
    if not season:
        season = datetime.now().year
    if season in _savant_bat_track:
        return _savant_bat_track[season]
    rows = _fetch_savant_csv(SAVANT_BAT_TRACK_URL.format(year=season))
    result = {}
    for row in rows:
        pid = str(row.get("id", "")).strip()
        if pid:
            result[pid] = {
                "avg_bat_speed":     _safe_float(row.get("avg_bat_speed")),
                "hard_swing_rate":   _safe_float(row.get("hard_swing_rate")),
                "blast_per_swing":   _safe_float(row.get("blast_per_swing")),
                "blast_per_contact": _safe_float(row.get("blast_per_bat_contact")),
                "squared_up_swing":  _safe_float(row.get("squared_up_per_swing")),
                "swing_length":      _safe_float(row.get("swing_length")),
                "swings":            _safe_float(row.get("swings_competitive")),
            }
    if result:
        _savant_bat_track[season] = result
    return result


def get_batter_savant(player_id: int, season: int = None) -> dict:
    """Combined Statcast + xStats + bat tracking for a single batter."""
    if not season:
        season = datetime.now().year
    pid = str(player_id)
    batting  = load_savant_batting(season).get(pid, {})
    xstats   = load_savant_xstats(season).get(pid, {})
    bat_track = load_bat_tracking(season).get(pid, {})
    return {**batting, **xstats, **bat_track}


def get_pitcher_savant(player_id: int, season: int = None) -> dict:
    """Statcast metrics from pitcher perspective (what batters do against them)."""
    if not season:
        season = datetime.now().year
    return load_savant_pitching(season).get(str(player_id), {})


def get_today_savant_leaderboards(season: int = None) -> dict:
    """Pre-load all Savant leaderboards for today's analysis (call once at startup)."""
    if not season:
        season = datetime.now().year
    return {
        "batting":     load_savant_batting(season),
        "pitching":    load_savant_pitching(season),
        "xstats":      load_savant_xstats(season),
        "bat_tracking": load_bat_tracking(season),
    }
