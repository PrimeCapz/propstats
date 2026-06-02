"""
Odds + Props Engine
- ESPN competition odds (DraftKings lines — free, no key)
- MLB Stats API batter/pitcher recent game logs
- Algorithmic prop analyzer: K props, hit props, HR props, totals
"""

import requests
import time
from datetime import datetime, date
from typing import Optional

MLB_API = "https://statsapi.mlb.com/api/v1"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_ODDS = "https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/events/{eid}/competitions/{eid}/odds"
HEADERS = {"User-Agent": "PropStats/1.0"}


# ── ESPN game_pk → ESPN event ID mapping ─────────────────────────────────────

def get_espn_game_map(game_date: str = None) -> dict:
    """Returns {(away_abbr, home_abbr): espn_id} for all games on a date."""
    if not game_date:
        game_date = date.today().strftime("%Y%m%d")
    else:
        game_date = game_date.replace("-", "")

    try:
        r = requests.get(ESPN_SCOREBOARD, params={"dates": game_date}, headers=HEADERS, timeout=10)
        r.raise_for_status()
        events = r.json().get("events", [])
    except Exception:
        return {}

    mapping = {}
    for e in events:
        eid = e.get("id", "")
        comp = e.get("competitions", [{}])[0]
        teams = {c.get("homeAway"): c.get("team", {}).get("abbreviation", "").upper()
                 for c in comp.get("competitors", [])}
        away = teams.get("away", "")
        home = teams.get("home", "")
        if away and home:
            mapping[(away, home)] = eid
    return mapping


def get_game_odds_by_espn_id(espn_id: str) -> dict:
    """Pull DraftKings odds for one game from ESPN."""
    try:
        r = requests.get(ESPN_ODDS.format(eid=espn_id), headers=HEADERS, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception:
        return {}

    # Prefer DraftKings (priority 1), fall back to first available
    items.sort(key=lambda x: x.get("provider", {}).get("priority", 99))
    if not items:
        return {}

    best = items[0]
    away_odds = best.get("awayTeamOdds", {})
    home_odds = best.get("homeTeamOdds", {})

    # Determine favourite label from details string e.g. "BAL -137"
    details = best.get("details", "")

    return {
        "provider": best.get("provider", {}).get("name", ""),
        "moneyline": {
            "away": away_odds.get("moneyLine"),
            "home": home_odds.get("moneyLine"),
            "favorite": "home" if home_odds.get("favorite") else "away",
            "details": details,
        },
        "run_line": {
            "spread": best.get("spread", -1.5),
            "away_rl": f"+1.5 ({_rl_odds(away_odds, True)})" if not away_odds.get("favorite") else f"-1.5 ({_rl_odds(away_odds, False)})",
            "home_rl": f"-1.5 ({_rl_odds(home_odds, False)})" if home_odds.get("favorite") else f"+1.5 ({_rl_odds(home_odds, True)})",
        },
        "total": {
            "line": best.get("overUnder"),
            "over_odds": int(best.get("overOdds", -110)),
            "under_odds": int(best.get("underOdds", -110)),
        },
    }


def _rl_odds(team_odds: dict, is_plus: bool) -> str:
    try:
        open_data = team_odds.get("open", {})
        spread_data = open_data.get("spread", {})
        american = spread_data.get("american", "")
        return str(american) if american else "-110"
    except Exception:
        return "-110"


def get_all_game_odds(game_date: str = None) -> dict:
    """Returns {(away_abbr, home_abbr): odds_dict} for all today's games."""
    mapping = get_espn_game_map(game_date)
    result = {}
    for key, eid in mapping.items():
        odds = get_game_odds_by_espn_id(eid)
        if odds:
            result[key] = odds
        time.sleep(0.15)
    return result


# ── Batter recent game log ────────────────────────────────────────────────────

def get_batter_last_n(batter_id: int, season: int = None, n: int = 5) -> list:
    """Last n games for a batter — AB, H, HR, RBI, BB, K, result."""
    if not season:
        season = datetime.now().year

    data = None
    try:
        r = requests.get(f"{MLB_API}/people/{batter_id}/stats",
                         params={"stats": "gameLog", "group": "hitting",
                                 "season": season, "sportId": 1},
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    games = []
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            stat = split.get("stat", {})
            opponent = split.get("opponent", {})
            is_home = split.get("isHome", False)
            games.append({
                "date": split.get("date", ""),
                "opponent": opponent.get("abbreviation", ""),
                "home_away": "vs" if is_home else "@",
                "ab": stat.get("atBats", 0),
                "h": stat.get("hits", 0),
                "hr": stat.get("homeRuns", 0),
                "rbi": stat.get("rbi", 0),
                "bb": stat.get("baseOnBalls", 0),
                "k": stat.get("strikeOuts", 0),
                "avg": stat.get("avg", ".000"),
                "sb": stat.get("stolenBases", 0),
                "doubles": stat.get("doubles", 0),
                "total_bases": _calc_tb(stat),
            })

    return sorted(games, key=lambda x: x["date"], reverse=True)[:n]


def _calc_tb(stat: dict) -> int:
    h = stat.get("hits", 0) or 0
    d = stat.get("doubles", 0) or 0
    t = stat.get("triples", 0) or 0
    hr = stat.get("homeRuns", 0) or 0
    return h + d + 2 * t + 3 * hr


def get_pitcher_last_n(pitcher_id: int, season: int = None, n: int = 5) -> list:
    """Alias wrapper — returns recent starts with K count."""
    if not season:
        season = datetime.now().year
    try:
        r = requests.get(f"{MLB_API}/people/{pitcher_id}/stats",
                         params={"stats": "gameLog", "group": "pitching",
                                 "season": season, "sportId": 1},
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    games = []
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            stat = split.get("stat", {})
            opponent = split.get("opponent", {})
            gs = stat.get("gamesStarted", 0)
            ip = stat.get("inningsPitched", "0.0")
            k = stat.get("strikeOuts", 0)
            bb = stat.get("baseOnBalls", 0)
            er = stat.get("earnedRuns", 0)
            h = stat.get("hits", 0)
            hr = stat.get("homeRuns", 0)
            pitches = stat.get("numberOfPitches", 0)
            games.append({
                "date": split.get("date", ""),
                "opponent": opponent.get("abbreviation", ""),
                "gs": gs,
                "ip": ip,
                "h": h, "er": er, "bb": bb, "k": k, "hr": hr,
                "pitches": pitches,
            })

    return sorted(games, key=lambda x: x["date"], reverse=True)[:n]


# ── Prop Analyzer ─────────────────────────────────────────────────────────────

def _fmt_ml(ml):
    if ml is None:
        return "N/A"
    if ml > 0:
        return f"+{ml}"
    return str(ml)


def _last5_avg(games: list) -> Optional[float]:
    ab = sum(g.get("ab", 0) for g in games)
    h = sum(g.get("h", 0) for g in games)
    return round(h / ab, 3) if ab > 0 else None


def _last5_streak(games: list) -> str:
    """Count consecutive games with a hit."""
    streak = 0
    for g in games:
        if g.get("h", 0) > 0:
            streak += 1
        else:
            break
    return f"{streak}-game hit streak" if streak > 0 else "No active hit streak"


def analyze_pitcher_k_prop(pitcher_stats: dict, recent_starts: list,
                            opposing_lineup: list, line: float = None) -> dict:
    """Evaluate a pitcher's strikeout prop."""
    s = pitcher_stats.get("stats", {})
    k9 = float(s.get("k9", 0) or 0)
    season_gs = s.get("games_started", 0) or 0

    # Average Ks per start from recent log
    start_games = [g for g in recent_starts if g.get("gs", 0) > 0 or float(str(g.get("ip","0")).split(".")[0]) >= 3][:5]
    avg_k_per_start = (sum(g.get("k", 0) for g in start_games) / len(start_games)) if start_games else 0
    recent_k_list = [g.get("k", 0) for g in start_games]

    # Estimate projected IP
    avg_ip = _avg_ip(start_games)

    # Score
    score = 0
    notes = []

    if k9 >= 11:
        score += 3; notes.append(f"Elite K/9 ({k9:.1f})")
    elif k9 >= 9.5:
        score += 2; notes.append(f"High K/9 ({k9:.1f})")
    elif k9 >= 8.0:
        score += 1; notes.append(f"Solid K/9 ({k9:.1f})")
    elif k9 <= 6.5:
        score -= 2; notes.append(f"Low K/9 ({k9:.1f}) — contact pitcher")

    if avg_k_per_start >= 9:
        score += 2; notes.append(f"Avg {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start >= 7:
        score += 1; notes.append(f"Avg {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start > 0 and avg_k_per_start <= 5:
        score -= 1; notes.append(f"Only {avg_k_per_start:.1f} K/start recently")

    # Suggested line if none given
    suggested_line = round(avg_k_per_start - 0.5, 1) if avg_k_per_start > 0 else round((k9 / 9) * avg_ip - 0.5, 1)
    suggested_line = max(2.5, min(suggested_line, 12.5))

    label = "OVER" if score >= 2 else "UNDER" if score <= -1 else "NEUTRAL"
    confidence = "Strong" if abs(score) >= 3 else "Lean" if abs(score) >= 2 else "Slight"

    return {
        "prop_type": "Strikeouts",
        "pitcher": pitcher_stats.get("name", ""),
        "suggested_line": suggested_line,
        "line": line or suggested_line,
        "lean": label,
        "confidence": confidence,
        "score": score,
        "k9": k9,
        "avg_k_per_start": round(avg_k_per_start, 1),
        "recent_k_games": recent_k_list,
        "notes": notes,
    }


def analyze_batter_hit_prop(batter_stats: dict, recent_games: list,
                             pitcher_stats: dict, h2h: dict,
                             line: float = 0.5) -> dict:
    """Evaluate a batter's hits prop (Over/Under 0.5 hits default)."""
    s = batter_stats.get("stats", {})
    season_avg = float(s.get("avg", ".250") or ".250")
    season_ops = float(s.get("ops", ".700") or ".700")

    # Last 5 avg
    l5_avg = _last5_avg(recent_games) or season_avg
    streak = _last5_streak(recent_games)
    recent_hits = [g.get("h", 0) for g in recent_games]
    recent_tb = [g.get("total_bases", 0) for g in recent_games]

    # Pitcher avg against
    p_avg_against = float(pitcher_stats.get("stats", {}).get("avg", ".250") or ".250")

    # H2H
    career = h2h.get("career_summary", {})
    h2h_avg = float(career.get("avg", ".000") or ".000") if career.get("pa", 0) >= 5 else None
    h2h_pa = career.get("pa", 0)

    score = 0
    notes = []

    if l5_avg >= 0.360:
        score += 3; notes.append(f"ON FIRE last 5 (.{int(l5_avg*1000):03d} AVG)")
    elif l5_avg >= 0.300:
        score += 2; notes.append(f"Hot last 5 (.{int(l5_avg*1000):03d} AVG)")
    elif l5_avg >= 0.250:
        score += 1; notes.append(f"Solid last 5 (.{int(l5_avg*1000):03d} AVG)")
    elif l5_avg <= 0.100:
        score -= 2; notes.append(f"Ice cold last 5 (.{int(l5_avg*1000):03d} AVG)")
    elif l5_avg <= 0.180:
        score -= 1; notes.append(f"Struggling last 5 (.{int(l5_avg*1000):03d} AVG)")

    if p_avg_against <= 0.200:
        score -= 2; notes.append(f"Pitcher dominates — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against <= 0.230:
        score -= 1; notes.append(f"Pitcher tough — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against >= 0.270:
        score += 1; notes.append(f"Pitcher hittable — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against >= 0.290:
        score += 2; notes.append(f"Pitcher very hittable — .{int(p_avg_against*1000):03d} avg against")

    if h2h_avg is not None:
        if h2h_avg >= 0.320:
            score += 2; notes.append(f"Owns this pitcher (.{int(h2h_avg*1000):03d} AVG in {h2h_pa} PA)")
        elif h2h_avg >= 0.270:
            score += 1; notes.append(f"Good H2H history (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)")
        elif h2h_avg <= 0.150:
            score -= 2; notes.append(f"Dominated historically (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)")
        elif h2h_avg <= 0.200:
            score -= 1; notes.append(f"Tough H2H (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)")

    if streak and "streak" in streak:
        try:
            streak_n = int(streak.split("-")[0])
            if streak_n >= 5:
                score += 1; notes.append(streak)
        except Exception:
            pass

    lean = "OVER" if score >= 2 else "UNDER" if score <= -1 else "NEUTRAL"
    confidence = "Strong" if abs(score) >= 4 else "Lean" if abs(score) >= 2 else "Slight"

    return {
        "prop_type": "Hits",
        "batter": batter_stats.get("name", ""),
        "line": line,
        "lean": lean,
        "confidence": confidence,
        "score": score,
        "season_avg": f".{int(season_avg*1000):03d}",
        "l5_avg": f".{int(l5_avg*1000):03d}",
        "recent_hits": recent_hits,
        "recent_tb": recent_tb,
        "h2h_avg": f".{int(h2h_avg*1000):03d}" if h2h_avg else "No data",
        "h2h_pa": h2h_pa,
        "streak": streak,
        "notes": notes,
    }


def analyze_batter_hr_prop(batter_stats: dict, recent_games: list,
                            pitcher_stats: dict, h2h: dict,
                            park_factors: dict, weather: dict,
                            line: float = 0.5) -> dict:
    """Evaluate a batter's HR prop."""
    s = batter_stats.get("stats", {})
    pa = s.get("pa", 0) or 1
    hr = s.get("hr", 0) or 0
    hr_rate = hr / pa if pa > 0 else 0

    p_hr9 = float(pitcher_stats.get("stats", {}).get("hr9", "1.0") or "1.0")
    park_hr = park_factors.get("hr", 1.0)
    weather_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0

    career = h2h.get("career_summary", {})
    h2h_hr = career.get("hr", 0)
    h2h_pa = career.get("pa", 0)

    score = 0
    notes = []

    if hr_rate >= 0.065:
        score += 2; notes.append(f"Power bat ({hr} HR in {pa} PA)")
    elif hr_rate >= 0.045:
        score += 1; notes.append(f"Decent power ({hr} HR / {pa} PA)")
    elif hr_rate <= 0.015:
        score -= 2; notes.append(f"Low HR rate ({hr} HR / {pa} PA)")

    if p_hr9 >= 1.30:
        score += 2; notes.append(f"Pitcher gives up HRs ({p_hr9} HR/9)")
    elif p_hr9 >= 1.00:
        score += 1; notes.append(f"Pitcher slightly HR-prone ({p_hr9} HR/9)")
    elif p_hr9 <= 0.60:
        score -= 1; notes.append(f"Pitcher suppresses HRs ({p_hr9} HR/9)")

    if park_hr >= 1.15:
        score += 2; notes.append(f"Hitter's park (HR PF: {park_hr:.2f})")
    elif park_hr >= 1.08:
        score += 1; notes.append(f"Slight HR park (PF: {park_hr:.2f})")
    elif park_hr <= 0.88:
        score -= 1; notes.append(f"Pitcher's park (HR PF: {park_hr:.2f})")

    if weather_score >= 2.0:
        score += 2; notes.append(weather.get("impact", {}).get("note", "Weather HR boost"))
    elif weather_score >= 1.0:
        score += 1; notes.append("Weather slightly HR-friendly")
    elif weather_score <= -1.0:
        score -= 1; notes.append("Weather suppresses HRs")

    if h2h_pa >= 5 and h2h_hr >= 2:
        score += 1; notes.append(f"{h2h_hr} HR in {h2h_pa} career PA vs pitcher")

    # Check recent HRs
    recent_hr_total = sum(g.get("hr", 0) for g in recent_games)
    if recent_hr_total >= 3:
        score += 1; notes.append(f"{recent_hr_total} HR in last {len(recent_games)} games")

    lean = "OVER" if score >= 3 else "UNDER" if score <= -2 else "NEUTRAL"
    confidence = "Strong" if abs(score) >= 4 else "Lean" if abs(score) >= 2 else "Slight"

    return {
        "prop_type": "Home Run",
        "batter": batter_stats.get("name", ""),
        "line": line,
        "lean": lean,
        "confidence": confidence,
        "score": score,
        "hr_this_season": hr,
        "hr_rate": round(hr_rate, 4),
        "park_hr_pf": park_hr,
        "weather_score": weather_score,
        "h2h_hr": h2h_hr,
        "h2h_pa": h2h_pa,
        "recent_hr": [g.get("hr", 0) for g in recent_games],
        "notes": notes,
    }


def analyze_total(away_pitcher: dict, home_pitcher: dict,
                  park_factors: dict, weather: dict,
                  game_odds: dict) -> dict:
    """Evaluate the game total Over/Under."""
    def era_val(p):
        try:
            return float(p.get("stats", {}).get("era", "4.50") or "4.50")
        except Exception:
            return 4.50

    def whip_val(p):
        try:
            return float(p.get("stats", {}).get("whip", "1.30") or "1.30")
        except Exception:
            return 1.30

    away_era = era_val(away_pitcher)
    home_era = era_val(home_pitcher)
    avg_era = (away_era + home_era) / 2
    away_whip = whip_val(away_pitcher)
    home_whip = whip_val(home_pitcher)
    avg_whip = (away_whip + home_whip) / 2

    park_run = park_factors.get("run", 1.0)
    weather_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0
    posted_total = game_odds.get("total", {}).get("line") if game_odds else None

    score = 0
    notes = []

    if avg_era >= 5.50:
        score += 3; notes.append(f"Both SPs are struggling (avg ERA {avg_era:.2f})")
    elif avg_era >= 4.75:
        score += 2; notes.append(f"Leaky pitching avg ERA {avg_era:.2f}")
    elif avg_era >= 4.25:
        score += 1; notes.append(f"Below-avg pitching avg ERA {avg_era:.2f}")
    elif avg_era <= 2.75:
        score -= 3; notes.append(f"Elite pitching avg ERA {avg_era:.2f}")
    elif avg_era <= 3.25:
        score -= 2; notes.append(f"Strong pitching avg ERA {avg_era:.2f}")
    elif avg_era <= 3.75:
        score -= 1; notes.append(f"Good pitching avg ERA {avg_era:.2f}")

    if avg_whip >= 1.50:
        score += 1; notes.append(f"High avg WHIP ({avg_whip:.2f}) — lots of baserunners")
    elif avg_whip <= 1.05:
        score -= 1; notes.append(f"Low avg WHIP ({avg_whip:.2f}) — few baserunners")

    if park_run >= 1.15:
        score += 2; notes.append(f"Run-boosting park (PF: {park_run:.2f})")
    elif park_run >= 1.05:
        score += 1; notes.append(f"Hitter-friendly park (PF: {park_run:.2f})")
    elif park_run <= 0.88:
        score -= 2; notes.append(f"Run-suppressing park (PF: {park_run:.2f})")
    elif park_run <= 0.95:
        score -= 1; notes.append(f"Pitcher-friendly park (PF: {park_run:.2f})")

    if weather_score >= 2.0:
        score += 2; notes.append(weather.get("impact", {}).get("note", "Big weather offense boost"))
    elif weather_score >= 1.0:
        score += 1; notes.append(weather.get("impact", {}).get("note", "Slight weather boost"))
    elif weather_score <= -1.0:
        score -= 1; notes.append(weather.get("impact", {}).get("note", "Weather suppresses offense"))

    lean = "OVER" if score >= 2 else "UNDER" if score <= -1 else "NEUTRAL"
    confidence = "Strong" if abs(score) >= 4 else "Lean" if abs(score) >= 2 else "Slight"

    return {
        "prop_type": "Game Total",
        "lean": lean,
        "confidence": confidence,
        "score": score,
        "posted_line": posted_total,
        "avg_era": round(avg_era, 2),
        "park_run_pf": park_run,
        "weather_score": weather_score,
        "notes": notes,
    }


def _avg_ip(games: list) -> float:
    total = 0.0
    for g in games:
        ip = g.get("ip", "0.0")
        try:
            parts = str(ip).split(".")
            total += int(parts[0]) + int(parts[1] if len(parts) > 1 else 0) / 3
        except Exception:
            pass
    return total / len(games) if games else 5.0


def build_prop_sheet(game_analysis: dict) -> dict:
    """Master prop sheet builder — takes full game_analysis output, returns ranked props."""
    from baseball_engine import get_batter_vs_pitcher, get_batter_season_stats
    import time as _time

    pitchers = game_analysis.get("pitchers", {})
    away_p = pitchers.get("away", {})
    home_p = pitchers.get("home", {})
    away_p_stats = away_p.get("stats", {})
    home_p_stats = home_p.get("stats", {})
    away_p_recent = away_p.get("recent_starts", [])
    home_p_recent = home_p.get("recent_starts", [])
    away_p_id = away_p.get("info", {}).get("id")
    home_p_id = home_p.get("info", {}).get("id")

    park = game_analysis.get("park_factors", {})
    weather = game_analysis.get("weather", {})
    season = game_analysis.get("season", datetime.now().year)

    props = []

    # ── Game Total ──
    total_prop = analyze_total(away_p_stats, home_p_stats, park, weather,
                               game_analysis.get("game_odds", {}))
    props.append(total_prop)

    # ── Pitcher K props ──
    if away_p_stats:
        kp = analyze_pitcher_k_prop(away_p_stats, away_p_recent,
                                    game_analysis.get("lineups", {}).get("home", []))
        kp["side"] = "away"
        props.append(kp)

    if home_p_stats:
        kp = analyze_pitcher_k_prop(home_p_stats, home_p_recent,
                                    game_analysis.get("lineups", {}).get("away", []))
        kp["side"] = "home"
        props.append(kp)

    # ── Batter props (hits + HR) ──
    matchups = game_analysis.get("matchups", {})

    def process_batters(batter_list, pitcher_stats, pitcher_id, side_label):
        for item in batter_list[:9]:
            batter = item.get("batter", {})
            bid = batter.get("player_id")
            if not bid:
                continue
            h2h = item.get("h2h", {})

            batter_full = get_batter_season_stats(bid, season)
            if not batter_full:
                _time.sleep(0.1)
                continue

            recent = get_batter_last_n(bid, season, 5)
            _time.sleep(0.15)

            # Hits prop
            hit_p = analyze_batter_hit_prop(batter_full, recent, pitcher_stats, h2h, 0.5)
            hit_p["order"] = batter.get("order", 0)
            hit_p["side"] = side_label
            hit_p["recent_games"] = recent
            if abs(hit_p["score"]) >= 2:
                props.append(hit_p)

            # HR prop
            hr_p = analyze_batter_hr_prop(batter_full, recent, pitcher_stats, h2h, park, weather, 0.5)
            hr_p["order"] = batter.get("order", 0)
            hr_p["side"] = side_label
            if abs(hr_p["score"]) >= 2:
                props.append(hr_p)

    if home_p_stats and home_p_id:
        process_batters(
            matchups.get("away_batters_vs_home_pitcher", []),
            home_p_stats, home_p_id, "away"
        )
    if away_p_stats and away_p_id:
        process_batters(
            matchups.get("home_batters_vs_away_pitcher", []),
            away_p_stats, away_p_id, "home"
        )

    # Sort: Strong > Lean, then by abs(score)
    def sort_key(p):
        conf_rank = {"Strong": 0, "Lean": 1, "Slight": 2}.get(p.get("confidence", "Slight"), 2)
        return (conf_rank, -abs(p.get("score", 0)))

    props.sort(key=sort_key)
    return {
        "game_pk": game_analysis.get("game_pk"),
        "away": game_analysis.get("away_team", {}).get("abbr", ""),
        "home": game_analysis.get("home_team", {}).get("abbr", ""),
        "props": props,
        "top_plays": [p for p in props if p.get("confidence") in ("Strong", "Lean") and p.get("lean") != "NEUTRAL"][:8],
    }


# ── Advanced Statcast Scoring Models ──────────────────────────────────────────

def calc_batter_power(savant: dict) -> float:
    """0.0–1.0 composite batter power score from Statcast metrics."""
    score = 0.0
    weight = 0.0

    barrel = savant.get("barrel_pct", 0) or 0
    hard   = savant.get("hard_hit_pct", 0) or 0
    ev50   = savant.get("ev50", 0) or 0
    xslg   = savant.get("xslg", 0) or 0
    blast  = (savant.get("blast_per_swing", 0) or 0) * 100
    sweet  = savant.get("sweet_spot", 0) or 0

    # Barrel% (league avg ~8%) — weight 30%
    if barrel > 0:
        score  += min(barrel / 20.0, 1.0) * 0.30
        weight += 0.30

    # Hard hit% (league avg ~37%) — weight 25%
    if hard > 0:
        score  += min(hard / 65.0, 1.0) * 0.25
        weight += 0.25

    # EV50 (50th pct exit velo, avg ~88 mph) — weight 20%
    if ev50 > 0:
        score  += min(max(ev50 - 80, 0) / 20.0, 1.0) * 0.20
        weight += 0.20

    # xSLG (league avg ~.430) — weight 15%
    if xslg > 0:
        score  += min(xslg / 0.80, 1.0) * 0.15
        weight += 0.15

    # Blast% per swing (league avg ~12%) — weight 10%
    if blast > 0:
        score  += min(blast / 25.0, 1.0) * 0.10
        weight += 0.10

    return round(score / weight, 3) if weight > 0 else 0.0


def calc_pitcher_vulnerability(savant: dict, pitcher_stats: dict) -> float:
    """0.0–1.0 pitcher HR/hard-contact vulnerability."""
    score  = 0.0
    weight = 0.0

    barrel_ag = savant.get("barrel_pct_against", 0) or 0
    hard_ag   = savant.get("hard_hit_pct_against", 0) or 0
    ev_ag     = savant.get("exit_velo_against", 0) or 0
    hr9       = float(pitcher_stats.get("stats", {}).get("hr9", "1.0") or "1.0") if pitcher_stats else 1.0
    era       = float(pitcher_stats.get("stats", {}).get("era", "4.50") or "4.50") if pitcher_stats else 4.50

    # Barrel% against (weight 35%)
    if barrel_ag > 0:
        score  += min(barrel_ag / 18.0, 1.0) * 0.35
        weight += 0.35

    # Hard hit% against (weight 25%)
    if hard_ag > 0:
        score  += min(hard_ag / 55.0, 1.0) * 0.25
        weight += 0.25

    # Exit velo against (weight 20%)
    if ev_ag > 0:
        score  += min(max(ev_ag - 84, 0) / 10.0, 1.0) * 0.20
        weight += 0.20

    # HR/9 (league avg ~1.2, weight 20%)
    score  += min(hr9 / 2.5, 1.0) * 0.20
    weight += 0.20

    return round(score / weight, 3) if weight > 0 else round(min(hr9 / 2.5, 1.0), 3)


def calc_context_score(park: dict, weather: dict, grade: str) -> float:
    """0.0–1.0 combined park + weather + matchup-grade context."""
    score = 0.50  # neutral base

    park_hr = park.get("hr", 1.0)
    w_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0

    score += (park_hr - 1.0) * 0.5
    score += w_score * 0.04

    grade_adj = {"A+": 0.08, "A": 0.05, "B": 0.02, "C": 0.0, "D": -0.03, "F": -0.06}
    score += grade_adj.get(grade, 0.0)

    return round(min(max(score, 0.0), 1.0), 3)


def calc_hr_probability(batter_stats: dict, batter_savant: dict,
                        pitcher_stats: dict, pitcher_savant: dict,
                        park: dict, weather: dict,
                        handedness_edge: float = 1.0) -> float:
    """
    Estimate single-game HR probability (0.0–1.0).

    Calibration target: elite power bat in optimal matchup ~20-22%, league
    avg batter vs league avg pitcher ~5-7%.  Previous model inflated to 49%+
    due to uncapped barrel_adj compounding.

    handedness_edge: caller passes a multiplier (e.g. 1.08 for platoon
    advantage, 0.93 for disadvantage) from the batter/pitcher splits.
    """
    s     = batter_stats.get("stats", {})
    pa    = max(s.get("pa", 0) or 1, 1)
    hr    = s.get("hr", 0) or 0
    base_rate = hr / pa

    park_adj    = park.get("hr", 1.0)
    weather_adj = 1.0 + (weather.get("impact", {}).get("score", 0) if weather.get("available") else 0) * 0.03
    p_hr9       = float((pitcher_stats or {}).get("stats", {}).get("hr9", "1.2") or "1.2")
    league_hr9  = 1.20
    # Soft-cap pitcher adjustment so outliers (2.0 HR/9) don't dominate
    pitcher_adj = min(p_hr9 / league_hr9, 1.8)

    barrel_batter  = batter_savant.get("barrel_pct", 8.0) or 8.0
    barrel_pitcher = pitcher_savant.get("barrel_pct_against", 8.0) or 8.0
    # Separate batter/pitcher barrel signals — combine additively, not multiplicatively
    barrel_batter_adj  = barrel_batter / 8.0       # 1.0 = league avg
    barrel_pitcher_adj = barrel_pitcher / 8.0      # 1.0 = league avg
    barrel_adj = (barrel_batter_adj ** 0.35) * (barrel_pitcher_adj ** 0.25)
    barrel_adj = min(barrel_adj, 2.0)              # was 3.0 — tighter cap

    daily_hr_rate = base_rate * park_adj * weather_adj * pitcher_adj * barrel_adj * handedness_edge

    # 3.3 PA per game (more realistic average including pitcher's spot & short games)
    avg_pa = 3.3
    prob = 1.0 - (1.0 - daily_hr_rate) ** avg_pa

    # Calibration floor/ceiling: realistic range is 1%–25%
    return round(min(max(prob, 0.01), 0.25), 4)


def get_handedness_edge(batter_hand: str, pitcher_hand: str) -> float:
    """
    Return a platoon multiplier for HR probability.
    Platoon splits on HR: LHB vs RHP and RHB vs LHP produce ~8-12% more HRs.
    Same-hand matchups are slightly suppressive.
    """
    b = (batter_hand or "R").upper()
    p = (pitcher_hand or "R").upper()
    if b == "B":          # switch hitter — always gets favorable side
        return 1.06
    if b != p:            # platoon advantage
        return 1.09
    return 0.94           # same-hand — slight suppression


def get_value_hr_picks(game_analyses: list, min_prob: float = 0.12, max_prob: float = 0.21) -> list:
    """
    Surface 'sleeper' HR bats in the 12-21% probability band — the Bleday tier.
    These are mid-power batters (barrel 8-14%) facing HR-prone pitchers that
    the model under-surfaces because they don't dominate any single metric.
    Ordered by (prob - implied_prob) to find the best value.
    """
    from baseball_engine import get_batter_savant, get_pitcher_savant, get_batter_season_stats
    results = []
    seen = set()

    for analysis in game_analyses:
        if "error" in analysis:
            continue
        pitchers = analysis.get("pitchers", {})
        park     = analysis.get("park_factors", {})
        weather  = analysis.get("weather", {})
        matchups = analysis.get("matchups", {})
        season   = analysis.get("season", datetime.now().year)
        away_t   = analysis.get("away_team", {})
        home_t   = analysis.get("home_team", {})

        for batter_list, pitcher_side, batter_team in [
            (matchups.get("away_batters_vs_home_pitcher", []), "home", away_t.get("name", "")),
            (matchups.get("home_batters_vs_away_pitcher", []), "away", home_t.get("name", "")),
        ]:
            pitcher_info  = pitchers.get(pitcher_side, {})
            pitcher_stats = pitcher_info.get("stats", {})
            pitcher_id    = pitcher_info.get("info", {}).get("id")
            pitcher_name  = pitcher_stats.get("name", "Unknown")
            p_hr9 = float((pitcher_stats.get("stats", {}) or {}).get("hr9", "1.2") or "1.2")
            if not pitcher_id:
                continue

            p_savant = get_pitcher_savant(pitcher_id, season)
            p_hand   = pitcher_info.get("info", {}).get("pitchHand", {}).get("code", "R")

            for entry in batter_list[:9]:
                batter     = entry.get("batter", {})
                batter_id  = batter.get("player_id")
                batter_name = batter.get("name", "Unknown")
                b_hand = batter.get("batSide", {}).get("code", "R") if isinstance(batter.get("batSide"), dict) else "R"

                if not batter_id or (batter_id, pitcher_id) in seen:
                    continue
                seen.add((batter_id, pitcher_id))

                b_savant = get_batter_savant(batter_id, season)
                b_stats  = get_batter_season_stats(batter_id, season)
                b_barrel = b_savant.get("barrel_pct", 0) or 0

                # Value tier: not dominant but real power
                if b_barrel < 7.0:
                    continue

                hand_edge = get_handedness_edge(b_hand, p_hand)
                hr_prob = calc_hr_probability(b_stats, b_savant, pitcher_stats, p_savant, park, weather, hand_edge)

                if not (min_prob <= hr_prob <= max_prob):
                    continue

                # Implied prob from +300 default (most mid-tier HR props are +250 to +400)
                fair_odds = prob_to_american(hr_prob)

                results.append({
                    "batter":        batter_name,
                    "batter_team":   batter_team,
                    "batter_hand":   b_hand,
                    "pitcher":       pitcher_name,
                    "pitcher_hand":  p_hand,
                    "platoon_edge":  "YES" if (b_hand != p_hand or b_hand == "B") else "no",
                    "hr_prob_pct":   round(hr_prob * 100, 1),
                    "fair_odds":     fair_odds,
                    "barrel_pct":    round(b_barrel, 1),
                    "pitcher_hr9":   round(p_hr9, 2),
                    "park_hr_pf":    park.get("hr", 1.0),
                    "order":         batter.get("order", 0),
                    "park_name":     analysis.get("venue", {}).get("name", ""),
                })

    results.sort(key=lambda x: x["hr_prob_pct"], reverse=True)
    return results[:15]


def calc_ev(hr_prob: float, hr_odds: int) -> float:
    """Expected value in $ for a $100 bet on HR."""
    if not hr_odds or hr_odds == 0:
        return 0.0
    if hr_odds > 0:
        payout = hr_odds
    else:
        payout = 10000 / abs(hr_odds)
    ev = (hr_prob * payout) - ((1 - hr_prob) * 100)
    return round(ev, 2)


def prob_to_american(prob: float) -> str:
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return "N/A"
    if prob >= 0.5:
        odds = round(-prob / (1 - prob) * 100)
        return str(odds)
    else:
        odds = round((1 - prob) / prob * 100)
        return f"+{odds}"


def power_match_rating(batter_power: float, pitcher_vuln: float) -> int:
    """Returns 1, 2, or 3 fire emojis based on power × vulnerability."""
    combined = batter_power * pitcher_vuln
    if combined >= 0.35:
        return 3
    if combined >= 0.18:
        return 2
    return 1


def get_meatball_matchups(game_analyses: list) -> list:
    """
    Top meatball matchups: high-barrel batter vs high-barrel-allowed pitcher.
    Proxy for 'heart zone xSLG vs zone-5 pitchers'.
    """
    from baseball_engine import get_batter_savant, get_pitcher_savant
    results = []
    seen = set()

    for analysis in game_analyses:
        if "error" in analysis:
            continue
        pitchers = analysis.get("pitchers", {})
        park     = analysis.get("park_factors", {})
        weather  = analysis.get("weather", {})
        away_t   = analysis.get("away_team", {})
        home_t   = analysis.get("home_team", {})
        matchups = analysis.get("matchups", {})
        season   = analysis.get("season", datetime.now().year)

        for batter_list, pitcher_side, batter_team in [
            (matchups.get("away_batters_vs_home_pitcher", []), "home", away_t.get("name", "")),
            (matchups.get("home_batters_vs_away_pitcher", []), "away", home_t.get("name", "")),
        ]:
            pitcher_info  = pitchers.get(pitcher_side, {})
            pitcher_stats = pitcher_info.get("stats", {})
            pitcher_id    = pitcher_info.get("info", {}).get("id")
            pitcher_name  = pitcher_stats.get("name", "Unknown")

            if not pitcher_id:
                continue
            p_savant = get_pitcher_savant(pitcher_id, season)
            p_vuln   = calc_pitcher_vulnerability(p_savant, pitcher_stats)
            p_barrel = p_savant.get("barrel_pct_against", 0)
            p_ev     = p_savant.get("exit_velo_against", 0)

            for entry in batter_list[:9]:
                batter     = entry.get("batter", {})
                batter_id  = batter.get("player_id")
                batter_name = batter.get("name", "Unknown")
                if not batter_id or (batter_id, pitcher_id) in seen:
                    continue
                seen.add((batter_id, pitcher_id))

                b_savant   = get_batter_savant(batter_id, season)
                b_power    = calc_batter_power(b_savant)
                b_xslg     = b_savant.get("xslg", 0)
                b_barrel   = b_savant.get("barrel_pct", 0)
                b_bat_speed = b_savant.get("avg_bat_speed", 0)

                combined = b_power * p_vuln
                if combined < 0.10 or b_xslg < 0.350:
                    continue

                matchup_score = round(b_xslg * p_vuln * (park.get("hr", 1.0)), 4)

                results.append({
                    "batter":       batter_name,
                    "batter_team":  batter_team,
                    "pitcher":      pitcher_name,
                    "batter_xslg":  round(b_xslg, 3),
                    "batter_barrel": round(b_barrel, 1),
                    "batter_bat_speed": round(b_bat_speed, 1),
                    "pitcher_barrel_against": round(p_barrel, 1),
                    "pitcher_ev_against": round(p_ev, 1),
                    "batter_power": b_power,
                    "pitcher_vuln": p_vuln,
                    "park_hr_pf":   park.get("hr", 1.0),
                    "matchup_score": matchup_score,
                    "fire_rating":  power_match_rating(b_power, p_vuln),
                })

    results.sort(key=lambda x: x["matchup_score"], reverse=True)
    return results[:20]


def get_blast_alerts(game_analyses: list) -> list:
    """
    Batters with high blast/barrel rates facing HR-prone pitchers.
    Includes EV calculation if HR odds available.
    """
    from baseball_engine import get_batter_savant, get_pitcher_savant, get_batter_season_stats
    results = []
    seen = set()

    for analysis in game_analyses:
        if "error" in analysis:
            continue
        pitchers  = analysis.get("pitchers", {})
        park      = analysis.get("park_factors", {})
        weather   = analysis.get("weather", {})
        matchups  = analysis.get("matchups", {})
        season    = analysis.get("season", datetime.now().year)
        away_t    = analysis.get("away_team", {})
        home_t    = analysis.get("home_team", {})

        for batter_list, pitcher_side, batter_team in [
            (matchups.get("away_batters_vs_home_pitcher", []), "home", away_t.get("name", "")),
            (matchups.get("home_batters_vs_away_pitcher", []), "away", home_t.get("name", "")),
        ]:
            pitcher_info  = pitchers.get(pitcher_side, {})
            pitcher_stats = pitcher_info.get("stats", {})
            pitcher_id    = pitcher_info.get("info", {}).get("id")
            pitcher_name  = pitcher_stats.get("name", "Unknown")
            if not pitcher_id:
                continue

            p_savant = get_pitcher_savant(pitcher_id, season)
            p_hr9    = float((pitcher_stats.get("stats", {}) or {}).get("hr9", "1.2") or "1.2")
            p_barrel = p_savant.get("barrel_pct_against", 0)
            p_vuln   = calc_pitcher_vulnerability(p_savant, pitcher_stats)

            for entry in batter_list[:9]:
                batter     = entry.get("batter", {})
                batter_id  = batter.get("player_id")
                batter_name = batter.get("name", "Unknown")
                order       = batter.get("order", 0)
                if not batter_id or (batter_id, pitcher_id) in seen:
                    continue
                seen.add((batter_id, pitcher_id))

                b_savant = get_batter_savant(batter_id, season)
                b_stats  = get_batter_season_stats(batter_id, season)
                b_barrel = b_savant.get("barrel_pct", 0)
                b_blast  = (b_savant.get("blast_per_swing", 0) or 0) * 100
                b_power  = calc_batter_power(b_savant)
                b_ev50   = b_savant.get("ev50", 0)

                # Surface blast threats — OR logic so mid-barrel/high-blast bats aren't filtered
                if b_barrel < 7.0 and b_blast < 10.0:
                    continue

                b_hand   = batter.get("batSide", {}).get("code", "R") if isinstance(batter.get("batSide"), dict) else "R"
                p_hand   = pitcher_info.get("info", {}).get("pitchHand", {}).get("code", "R")
                hand_edge = get_handedness_edge(b_hand, p_hand)
                hr_prob  = calc_hr_probability(b_stats, b_savant, pitcher_stats, p_savant, park, weather, hand_edge)
                fair_odds = prob_to_american(hr_prob)
                context   = calc_context_score(park, weather, entry.get("matchup_grade", {}).get("grade", "C"))

                danger_combo = b_barrel >= 12.0 and p_hr9 >= 1.20

                results.append({
                    "batter":        batter_name,
                    "batter_team":   batter_team,
                    "order":         order,
                    "pitcher":       pitcher_name,
                    "blast_pct":     round(b_blast, 1),
                    "barrel_pct":    round(b_barrel, 1),
                    "pitcher_hr9":   round(p_hr9, 2),
                    "pitcher_barrel_against": round(p_barrel, 1),
                    "batter_power":  b_power,
                    "pitcher_vuln":  p_vuln,
                    "context_score": context,
                    "hr_probability": round(hr_prob * 100, 1),
                    "fair_odds":      fair_odds,
                    "ev50":           round(b_ev50, 1),
                    "fire_rating":    power_match_rating(b_power, p_vuln),
                    "danger_combo":   danger_combo,
                    "park_hr_pf":     park.get("hr", 1.0),
                    "park_name":      analysis.get("venue", {}).get("name", ""),
                    "platoon_edge":   "YES" if (b_hand != p_hand or b_hand == "B") else "no",
                    "batter_hand":    b_hand,
                    "pitcher_hand":   p_hand,
                })

    # Primary: calibrated HR probability; secondary: danger_combo flag
    results.sort(key=lambda x: (x["hr_probability"], x["danger_combo"]), reverse=True)
    return results[:20]


def get_bat_speed_surges(game_analyses: list) -> list:
    """
    Batters showing high bat speed. Returns ranked by avg_bat_speed.
    """
    from baseball_engine import get_batter_savant
    results = []
    seen = set()

    for analysis in game_analyses:
        if "error" in analysis:
            continue
        matchups = analysis.get("matchups", {})
        pitchers = analysis.get("pitchers", {})
        season   = analysis.get("season", datetime.now().year)
        away_t   = analysis.get("away_team", {})
        home_t   = analysis.get("home_team", {})

        for batter_list, pitcher_side, batter_team in [
            (matchups.get("away_batters_vs_home_pitcher", []), "home", away_t.get("name", "")),
            (matchups.get("home_batters_vs_away_pitcher", []), "away", home_t.get("name", "")),
        ]:
            pitcher_info = pitchers.get(pitcher_side, {})
            pitcher_name = pitcher_info.get("stats", {}).get("name", "Unknown")

            for entry in batter_list[:9]:
                batter     = entry.get("batter", {})
                batter_id  = batter.get("player_id")
                batter_name = batter.get("name", "Unknown")
                if not batter_id or batter_id in seen:
                    continue
                seen.add(batter_id)

                b_savant   = get_batter_savant(batter_id, season)
                bat_speed  = b_savant.get("avg_bat_speed", 0)
                hard_swing = b_savant.get("hard_swing_rate", 0) * 100
                blast      = b_savant.get("blast_per_swing", 0) * 100
                swings     = b_savant.get("swings", 0)

                if bat_speed < 68 or swings < 20:
                    continue

                results.append({
                    "batter":        batter_name,
                    "batter_team":   batter_team,
                    "pitcher":       pitcher_name,
                    "avg_bat_speed": round(bat_speed, 1),
                    "hard_swing_rate": round(hard_swing, 1),
                    "blast_pct":     round(blast, 1),
                    "swings":        int(swings),
                })

    results.sort(key=lambda x: x["avg_bat_speed"], reverse=True)
    return results[:15]


def build_hr_matchup_table(game_analysis: dict) -> list:
    """
    Build the full HR matchup grid for one game (like the screenshot table).
    Returns list of rows with all scoring metrics.
    """
    from baseball_engine import get_batter_savant, get_pitcher_savant, get_batter_season_stats
    import time as _t

    pitchers  = game_analysis.get("pitchers", {})
    park      = game_analysis.get("park_factors", {})
    weather   = game_analysis.get("weather", {})
    matchups  = game_analysis.get("matchups", {})
    season    = game_analysis.get("season", datetime.now().year)
    rows = []

    for batter_list, pitcher_side in [
        (matchups.get("away_batters_vs_home_pitcher", []), "home"),
        (matchups.get("home_batters_vs_away_pitcher", []), "away"),
    ]:
        pitcher_info  = pitchers.get(pitcher_side, {})
        pitcher_stats = pitcher_info.get("stats", {})
        pitcher_id    = pitcher_info.get("info", {}).get("id")
        pitcher_name  = pitcher_stats.get("name", "Unknown")
        if not pitcher_id:
            continue

        p_savant = get_pitcher_savant(pitcher_id, season)
        p_vuln   = calc_pitcher_vulnerability(p_savant, pitcher_stats)

        for entry in batter_list[:9]:
            batter     = entry.get("batter", {})
            batter_id  = batter.get("player_id")
            if not batter_id:
                continue
            grade = entry.get("matchup_grade", {}).get("grade", "C")
            batter_name = batter.get("name", "Unknown")

            b_savant  = get_batter_savant(batter_id, season)
            b_stats   = get_batter_season_stats(batter_id, season)
            _t.sleep(0.05)

            b_power  = calc_batter_power(b_savant)
            hr_prob  = calc_hr_probability(b_stats, b_savant, pitcher_stats, p_savant, park, weather)
            context  = calc_context_score(park, weather, grade)
            fire     = power_match_rating(b_power, p_vuln)
            fair_ml  = prob_to_american(hr_prob)

            s = b_stats.get("stats", {})
            pa  = max(s.get("pa", 0) or 1, 1)
            hr  = s.get("hr", 0) or 0
            avg = s.get("avg", ".000")
            ops = s.get("ops", ".000")

            # Recent form
            l5_hits = [g.get("h", 0) for g in get_batter_last_n(batter_id, season, 5)]
            recent_hr = sum(g.get("hr", 0) for g in get_batter_last_n(batter_id, season, 5))
            avg_l5_h = sum(l5_hits) / len(l5_hits) if l5_hits else 0
            form = "Hot" if avg_l5_h >= 1.2 else "Cold" if avg_l5_h <= 0.4 else "Neutral"

            rows.append({
                "batter":         batter_name,
                "order":          batter.get("order", 0),
                "grade":          grade,
                "pitcher":        pitcher_name,
                "form":           form,
                "hr_prob_pct":    round(hr_prob * 100, 1),
                "fair_odds":      fair_ml,
                "batter_power":   b_power,
                "pitcher_vuln":   p_vuln,
                "context_score":  context,
                "fire_rating":    fire,
                "season_hr":      hr,
                "season_pa":      pa,
                "season_avg":     avg,
                "season_ops":     ops,
                "xslg":           b_savant.get("xslg", 0),
                "barrel_pct":     b_savant.get("barrel_pct", 0),
                "avg_bat_speed":  b_savant.get("avg_bat_speed", 0),
                "blast_pct":      round((b_savant.get("blast_per_swing", 0) or 0) * 100, 1),
                "hard_hit_pct":   b_savant.get("hard_hit_pct", 0),
                "ev50":           b_savant.get("ev50", 0),
                "recent_hr":      recent_hr,
            })

    rows.sort(key=lambda x: x["hr_prob_pct"], reverse=True)
    return rows
