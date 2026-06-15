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

def get_batter_last_n(batter_id: int, season: int = None, n: int = 5, as_of_date: str = None) -> list:
    """Last n games for a batter — AB, H, HR, RBI, BB, K, result."""
    if not season:
        season = datetime.now().year

    params = {"stats": "gameLog", "group": "hitting", "season": season, "sportId": 1}
    if as_of_date:
        params["endDate"] = as_of_date

    data = None
    try:
        r = requests.get(f"{MLB_API}/people/{batter_id}/stats",
                         params=params, headers=HEADERS, timeout=10)
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
                "r": stat.get("runs", 0),
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
                            opposing_lineup: list, line: float = None,
                            pitcher_csw: float = None,
                            pitcher_arsenal: list = None,
                            umpire_k_rate: float = None,
                            pitcher_swstr: float = None) -> dict:
    """Evaluate a pitcher's strikeout prop.

    Primary: avg Ks per recent start (more predictive than K/9 game-to-game).
    Gate 1: < 3 qualifying starts → NEUTRAL (insufficient sample).
    Gate 2: ERA > 5.0 → blocks K OVER (pitcher gets knocked out early).
    Variance filter: K range >= 6 across recent starts → NEUTRAL (too inconsistent).
    Tier 2: K/9 supporting signal, CSW%, opposing lineup whiff rate.
    """
    s = pitcher_stats.get("stats", {})
    k9 = float(s.get("k9", 0) or 0)

    try:
        era = float(s.get("era", "4.50") or "4.50")
    except Exception:
        era = 4.50

    start_games = [g for g in recent_starts if g.get("gs", 0) > 0 or float(str(g.get("ip","0")).split(".")[0]) >= 3][:5]
    recent_k_list = [g.get("k", 0) for g in start_games]
    avg_ip = _avg_ip(start_games)

    # Weighted K average — last 2 starts count 1.5x (recency bias)
    if len(start_games) >= 2:
        weights = [1.5 if i < 2 else 1.0 for i in range(len(start_games))]
        total_w = sum(weights)
        avg_k_per_start = sum(g.get("k", 0) * w for g, w in zip(start_games, weights)) / total_w
    elif start_games:
        avg_k_per_start = sum(g.get("k", 0) for g in start_games) / len(start_games)
    else:
        avg_k_per_start = 0

    # ── Gate: insufficient starts ─────────────────────────────────────────────
    if len(start_games) < 3:
        suggested = round((k9 / 9) * avg_ip - 0.5, 1) if k9 > 0 else 4.5
        return {
            "prop_type": "Strikeouts",
            "pitcher": pitcher_stats.get("name", ""),
            "suggested_line": max(2.5, min(suggested, 12.5)),
            "line": line or max(2.5, min(suggested, 12.5)),
            "lean": "NEUTRAL",
            "confidence": "Slight",
            "score": 0,
            "k9": k9,
            "csw": pitcher_csw,
            "avg_k_per_start": round(avg_k_per_start, 1),
            "recent_k_games": recent_k_list,
            "notes": ["Fewer than 3 qualifying starts — skipping K prop"],
        }

    score = 0
    notes = []
    force_neutral = False

    # ── Variance filter: stdev-based (range was too sensitive to single outliers) ──
    if len(recent_k_list) >= 3:
        import statistics as _stats
        k_stdev = _stats.stdev(recent_k_list)
        k_range = max(recent_k_list) - min(recent_k_list)
        # Exclude low-pitch-count outliers (bullpen game / early hook) before judging variance
        clean_k_list = [g.get("k", 0) for g in start_games if (g.get("pitches", 100) or 100) >= 80]
        clean_stdev = _stats.stdev(clean_k_list) if len(clean_k_list) >= 3 else k_stdev
        if clean_stdev >= 3.5:
            force_neutral = True
            notes.append(f"High K variance (stdev {clean_stdev:.1f}, games: {recent_k_list}) — calling NEUTRAL")
        elif k_stdev >= 3.5 and clean_stdev < 3.5:
            notes.append(f"K variance normalizes when low-pitch outliers removed (clean stdev {clean_stdev:.1f})")

    # ── Early exit gate: replaces ERA gate (ERA ≠ K rate; avg IP predicts exit risk) ──
    # ERA penalized high-ERA pitchers like Singer/Lorenzen who still strikeout batters.
    # avg_ip directly measures whether the pitcher will last long enough to accumulate Ks.
    if avg_ip < 4.0:
        force_neutral = True
        notes.append(f"Avg IP {avg_ip:.1f} — too short for K prop reliability, calling NEUTRAL")
    elif avg_ip < 5.0:
        score -= 1
        notes.append(f"Short avg IP ({avg_ip:.1f}) — early exit risk, K ceiling reduced")

    # ── Computed FIP: note only, not scored (FIP uses Ks in formula — circular for K props) ──
    # Still useful as a context note when FIP and ERA diverge significantly.
    try:
        ip_str = str(s.get("innings_pitched", "0.0") or "0.0")
        ip_parts = ip_str.split(".")
        ip_float = int(ip_parts[0]) + (int(ip_parts[1]) / 3 if len(ip_parts) > 1 else 0)
        hr_s = int(s.get("home_runs", 0) or 0)
        bb_s = int(s.get("walks", 0) or 0)
        k_s  = int(s.get("strikeouts", 0) or 0)
        fip_computed = round((13 * hr_s + 3 * bb_s - 2 * k_s) / ip_float + 3.10, 2) if ip_float >= 10 else None
        if fip_computed and era > 0:
            era_fip_gap = round(era - fip_computed, 2)
            if era_fip_gap >= 1.20 and fip_computed <= 4.50:
                notes.append(f"ERA ({era:.2f}) >> FIP ({fip_computed}) — ERA inflated by defense/luck, K ability intact")
            elif era_fip_gap <= -1.00 and era <= 3.50:
                notes.append(f"FIP ({fip_computed}) >> ERA ({era:.2f}) — ERA flatters, true K/BB profile weaker")
    except Exception:
        fip_computed = None

    # ── PRIMARY: Avg K per recent start ──────────────────────────────────────
    if avg_k_per_start >= 9:
        score += 3; notes.append(f"Dominant: avg {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start >= 7.5:
        score += 2; notes.append(f"Strong: avg {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start >= 6.0:
        score += 1; notes.append(f"Avg {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start <= 4.5:
        score -= 2; notes.append(f"Low: only {avg_k_per_start:.1f} K/start recently")
    elif avg_k_per_start <= 5.5:
        score -= 1; notes.append(f"Below-avg {avg_k_per_start:.1f} K/start recently")

    # ── SECONDARY: K/9 supporting signal ─────────────────────────────────────
    if k9 >= 11:
        score += 2; notes.append(f"Elite K/9 ({k9:.1f})")
    elif k9 >= 9.5:
        score += 1; notes.append(f"High K/9 ({k9:.1f})")
    elif k9 <= 6.5:
        score -= 1; notes.append(f"Low K/9 ({k9:.1f}) — contact pitcher")

    # ── Pitch velocity gap signal: large FB-to-offspeed diff → more Ks ──────────
    if pitcher_arsenal:
        ff_velo = next((p.get("avg_velocity", 0) for p in pitcher_arsenal if p.get("pitch_type") in ("FF", "SI")), 0)
        os_velos = [p.get("avg_velocity", 0) for p in pitcher_arsenal
                    if p.get("pitch_type") in ("CH", "CU", "SL", "ST", "FS") and p.get("avg_velocity", 0) > 0]
        if ff_velo > 0 and os_velos:
            velo_gap = ff_velo - min(os_velos)
            if velo_gap >= 10:
                score += 1; notes.append(f"Large FB-offspeed gap ({velo_gap:.1f} mph) — elite tunneling, K upside")
            elif velo_gap >= 7:
                notes.append(f"Good FB-offspeed gap ({velo_gap:.1f} mph)")

    # ── Tier 2: CSW% signal ───────────────────────────────────────────────────
    if pitcher_csw is not None and pitcher_csw > 0:
        if pitcher_csw >= 32:
            score += 2; notes.append(f"Elite CSW% ({pitcher_csw:.1f}%) — K machine")
        elif pitcher_csw >= 29:
            score += 1; notes.append(f"High CSW% ({pitcher_csw:.1f}%)")
        elif pitcher_csw <= 24:
            score -= 1; notes.append(f"Low CSW% ({pitcher_csw:.1f}%) — weak swing-and-miss")

    # ── Tier 2: SwStr% (swinging strike rate) — fastest-stabilizing K signal ─
    if pitcher_swstr is not None and pitcher_swstr > 0:
        if pitcher_swstr >= 30:
            score += 2; notes.append(f"Elite SwStr% ({pitcher_swstr:.1f}%) — generates whiffs at elite rate")
        elif pitcher_swstr >= 26:
            score += 1; notes.append(f"High SwStr% ({pitcher_swstr:.1f}%)")
        elif pitcher_swstr <= 18:
            score -= 1; notes.append(f"Low SwStr% ({pitcher_swstr:.1f}%) — limited swing-and-miss")

    # ── Tier 2: Umpire K-rate signal (underrated market edge) ────────────────
    # Books adjust umpire into game totals / ML but are slower on individual pitcher K props.
    # MLB average ≈ 15.0 K/game at HP. ≥17.5 = pitcher-friendly zone; ≤13.0 = tight zone.
    if umpire_k_rate is not None:
        if umpire_k_rate >= 17.5:
            score += 1
            notes.append(f"Pitcher-friendly HP umpire ({umpire_k_rate:.1f} K/game avg) — books slow to adjust K props")
        elif umpire_k_rate <= 13.0:
            score -= 1
            notes.append(f"Hitter-friendly HP umpire ({umpire_k_rate:.1f} K/game avg) — tight zone, limits K ceiling")

    # ── Tier 2: Opposing lineup K% (strikeout rate per PA) ───────────────────
    # Replaces broken whiff_rate check — lineups now carry so/pa from seasonStats
    if opposing_lineup:
        lineup_k_rates = []
        for b in opposing_lineup:
            b_so = b.get("so", 0)
            b_pa = b.get("pa", 0)
            if b_pa >= 50:
                lineup_k_rates.append(b_so / b_pa * 100)
        if lineup_k_rates:
            avg_lineup_k_pct = sum(lineup_k_rates) / len(lineup_k_rates)
            if avg_lineup_k_pct >= 26:
                score += 2; notes.append(f"K-prone lineup ({avg_lineup_k_pct:.1f}% K rate) — K OVER boost")
            elif avg_lineup_k_pct >= 22:
                score += 1; notes.append(f"Above-avg K lineup ({avg_lineup_k_pct:.1f}% K rate)")
            elif avg_lineup_k_pct <= 16:
                score -= 2; notes.append(f"Contact lineup ({avg_lineup_k_pct:.1f}% K rate) — K OVER risk")
            elif avg_lineup_k_pct <= 19:
                score -= 1; notes.append(f"Below-avg K lineup ({avg_lineup_k_pct:.1f}% K rate)")

    suggested_line = round(avg_k_per_start - 0.5, 1) if avg_k_per_start > 0 else round((k9 / 9) * avg_ip - 0.5, 1)
    suggested_line = max(2.5, min(suggested_line, 12.5))

    if force_neutral:
        label = "NEUTRAL"
    else:
        label = "OVER" if score >= 4 else "UNDER" if score <= -3 else "NEUTRAL"
    confidence = "Strong" if abs(score) >= 4 else "Lean" if abs(score) >= 2 else "Slight"

    # K/9 gate: pitchers with K/9 ≥ 6.0 have real K ability — suppress UNDER
    # even when recent starts look shaky (injury return, low pitch counts, etc.)
    if label == "UNDER" and k9 >= 6.0:
        label = "NEUTRAL"
        notes.append(f"K/9 {k9:.1f} — K UNDER suppressed (pitcher has legitimate K rate)")

    return {
        "prop_type": "Strikeouts",
        "pitcher": pitcher_stats.get("name", ""),
        "suggested_line": suggested_line,
        "line": line or suggested_line,
        "lean": label,
        "confidence": confidence,
        "score": score,
        "k9": k9,
        "era": era,
        "csw": pitcher_csw,
        "avg_k_per_start": round(avg_k_per_start, 1),
        "recent_k_games": recent_k_list,
        "notes": notes,
    }


def analyze_batter_hit_prop(batter_stats: dict, recent_games: list,
                             pitcher_stats: dict, h2h: dict,
                             line: float = 0.5,
                             pitcher_hand: str = None,
                             is_home: bool = False,
                             park_factors: dict = None,
                             batter_savant: dict = None) -> dict:
    """Evaluate a batter's hits prop (Over/Under 0.5 hits default).

    Tier 1 signals: platoon edge, LD%, xBA vs BA, BABIP regression,
                    hot-streak dampener, H2H min-10-PA gate.
    Tier 2 signals: home/away OPS split.
    """
    import math

    s = batter_stats.get("stats", {})
    pa = int(s.get("pa", 0) or 0)

    def _f(v, default=0.0):
        try:
            return float(str(v).lstrip(".") and v or default)
        except Exception:
            return default

    season_avg = _f(s.get("avg", ".000"))
    season_ops = _f(s.get("ops", ".000"))
    season_babip = _f(s.get("babip", ".000"))

    # ── Null-data gate ────────────────────────────────────────────────────────
    # If we have no meaningful batting data, don't issue a misleading lean.
    l5_avg_raw = _last5_avg(recent_games)
    l5_avg = l5_avg_raw if l5_avg_raw is not None else season_avg
    if season_avg == 0.0 and (l5_avg_raw is None or l5_avg_raw == 0.0) and pa < 30:
        return {
            "prop_type": "Hits",
            "batter": batter_stats.get("name", ""),
            "line": line,
            "lean": "NEUTRAL",
            "confidence": "Slight",
            "score": 0,
            "season_avg": ".000",
            "l5_avg": ".000",
            "recent_hits": [],
            "recent_tb": [],
            "h2h_avg": "No data",
            "h2h_pa": 0,
            "streak": "",
            "notes": ["Insufficient data — fewer than 30 PA"],
            "insufficient_data": True,
        }

    streak = _last5_streak(recent_games)
    recent_hits = [g.get("h", 0) for g in recent_games]
    recent_tb = [g.get("total_bases", 0) for g in recent_games]

    # Pitcher avg against
    p_stats = pitcher_stats.get("stats", {}) if pitcher_stats else {}
    p_avg_against = _f(p_stats.get("avg", ".250") or ".250", 0.250)

    # H2H — require ≥ 10 PA for signal (was 5, bumped for sample reliability)
    career = h2h.get("career_summary", {}) if h2h else {}
    h2h_pa = career.get("pa", 0)
    h2h_avg = _f(career.get("avg", ".000") or ".000") if h2h_pa >= 10 else None

    score = 0
    notes = []

    # ── L5 form ───────────────────────────────────────────────────────────────
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

    # ── Pitcher quality (avg against) ────────────────────────────────────────
    if p_avg_against <= 0.200:
        score -= 2; notes.append(f"Pitcher dominates — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against <= 0.230:
        score -= 1; notes.append(f"Pitcher tough — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against >= 0.290:
        score += 2; notes.append(f"Pitcher very hittable — .{int(p_avg_against*1000):03d} avg against")
    elif p_avg_against >= 0.270:
        score += 1; notes.append(f"Pitcher hittable — .{int(p_avg_against*1000):03d} avg against")

    # ── Dominant pitcher ERA gate ─────────────────────────────────────────────
    # Applied after avg-against so both signals can stack or offset each other.
    p_era_raw = p_stats.get("era", "4.50")
    try:
        p_era = float(p_era_raw or "4.50")
    except Exception:
        p_era = 4.50
    if p_era <= 1.80:
        score -= 3; notes.append(f"Elite ace on mound (ERA {p_era:.2f}) — hit OVER suppressed")
    elif p_era <= 2.50:
        score -= 2; notes.append(f"Dominant starter (ERA {p_era:.2f}) — hit OVER penalized")

    # ── H2H (min 10 PA) — Bayesian shrinkage scales signal by PA confidence ────
    # At 10 PA: 33% weight | 20 PA: 67% | 30+ PA: full signal
    if h2h_avg is not None:
        h2h_conf = min(h2h_pa / 30.0, 1.0)
        raw_h2h_pts = 0
        h2h_label = ""
        if h2h_avg >= 0.350:
            raw_h2h_pts = 3; h2h_label = f"Owns this pitcher (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)"
        elif h2h_avg >= 0.320:
            raw_h2h_pts = 2; h2h_label = f"Strong H2H (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)"
        elif h2h_avg >= 0.270:
            raw_h2h_pts = 1; h2h_label = f"Good H2H history (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)"
        elif h2h_avg <= 0.150:
            raw_h2h_pts = -2; h2h_label = f"Dominated historically (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)"
        elif h2h_avg <= 0.200:
            raw_h2h_pts = -1; h2h_label = f"Tough H2H (.{int(h2h_avg*1000):03d} in {h2h_pa} PA)"
        if raw_h2h_pts != 0:
            adj_pts = round(raw_h2h_pts * h2h_conf)
            if adj_pts != 0:
                score += adj_pts
                conf_note = "" if h2h_conf >= 0.99 else f" [{int(h2h_conf*100)}% conf, {h2h_pa} PA]"
                notes.append(h2h_label + conf_note)
            else:
                notes.append(f"Weak H2H signal ({h2h_label[:30]}... — low PA sample, ignored)")

    # ── Hit streak ────────────────────────────────────────────────────────────
    if streak and "streak" in streak:
        try:
            streak_n = int(streak.split("-")[0])
            if streak_n >= 5:
                score += 1; notes.append(streak)
        except Exception:
            pass

    # ── TIER 1: Platoon edge ──────────────────────────────────────────────────
    batter_hand = batter_stats.get("bats", "R")
    p_hand = (pitcher_hand or "R").upper()
    platoon = get_handedness_edge(batter_hand, p_hand)
    if platoon >= 1.10:
        score += 1; notes.append(f"Platoon advantage ({batter_hand} vs {p_hand}HP) +{(platoon-1)*100:.0f}%")
    elif platoon >= 1.05:
        notes.append(f"Slight platoon edge ({batter_hand} vs {p_hand}HP)")
    elif platoon <= 0.93:
        score -= 1; notes.append(f"Same-hand matchup disadvantage ({batter_hand} vs {p_hand}HP)")

    # ── TIER 1: Pitcher splits vs batter handedness ───────────────────────────
    p_splits = pitcher_stats.get("splits", {}) if pitcher_stats else {}
    split_key = "vs. Left" if batter_hand == "L" else "vs. Right"
    split_d = p_splits.get(split_key, {})
    if split_d:
        try:
            split_ip  = float(split_d.get("ip", "0.0") or "0.0")
            split_ops = float(split_d.get("ops", ".000") or ".000")
            if split_ip >= 20 and split_ops > 0:
                hand_lbl = "LHB" if batter_hand == "L" else "RHB"
                if split_ops >= 0.810:
                    score += 2; notes.append(f"Pitcher bleeds vs {hand_lbl} (.{int(split_ops*1000)} OPS allowed)")
                elif split_ops >= 0.750:
                    score += 1; notes.append(f"Pitcher hittable vs {hand_lbl} (.{int(split_ops*1000)} OPS allowed)")
                elif split_ops <= 0.580:
                    score -= 1; notes.append(f"Pitcher dominates {hand_lbl} (.{int(split_ops*1000)} OPS allowed)")
        except Exception:
            pass

    # ── TIER 1: Line Drive % ──────────────────────────────────────────────────
    ld_pct = _f(s.get("ld_pct", 0))
    bip = int(s.get("balls_in_play", 0) or 0)
    if bip >= 50 and ld_pct > 0:
        if ld_pct >= 26:
            score += 2; notes.append(f"Elite LD% ({ld_pct:.1f}%) — sustained contact quality")
        elif ld_pct >= 22:
            score += 1; notes.append(f"High LD% ({ld_pct:.1f}%) — reliable contact")
        elif ld_pct <= 13:
            score -= 1; notes.append(f"Low LD% ({ld_pct:.1f}%) — weak batted-ball profile")

    # ── TIER 1: xBA vs actual BA (luck regression) ────────────────────────────
    xba_raw = s.get("xba", "")
    if xba_raw and pa >= 50:
        try:
            xba = float(str(xba_raw).lstrip(".") and xba_raw or 0)
            ba_delta = xba - season_avg
            if ba_delta >= 0.040:
                score += 1; notes.append(f"xBA ({xba:.3f}) >> BA ({season_avg:.3f}) — unlucky, OVER regression")
            elif ba_delta <= -0.040:
                score -= 1; notes.append(f"BA ({season_avg:.3f}) >> xBA ({xba:.3f}) — lucky, UNDER regression")
        except Exception:
            pass

    # ── TIER 1: BABIP regression signal ──────────────────────────────────────
    # L5 BABIP: (H - HR) / (AB - K - HR) per game
    l5_bip = sum(max((g.get("ab", 0) - g.get("k", 0) - g.get("hr", 0)), 0) for g in recent_games)
    l5_babip_h = sum(max(g.get("h", 0) - g.get("hr", 0), 0) for g in recent_games)
    l5_babip = round(l5_babip_h / l5_bip, 3) if l5_bip >= 6 else None

    if l5_babip is not None:
        if l5_babip > 0.450:
            score -= 3; notes.append(f"L5 BABIP {l5_babip:.3f} — extreme luck, sharp regression likely")
        elif l5_babip > 0.420:
            score -= 2; notes.append(f"L5 BABIP {l5_babip:.3f} — luck-driven hot streak, regression likely")
        elif l5_babip < 0.200 and season_babip > 0.280 and season_avg >= 0.230:
            score += 1; notes.append(f"L5 BABIP {l5_babip:.3f} — cold streak unlucky, bounce-back due")

    # ── TIER 1: Hot-streak dampener (scaled by magnitude) ────────────────────
    delta = l5_avg - season_avg if season_avg > 0 else 0
    if delta > 0.150 and h2h_pa < 15 and score > 0 and len(recent_games) >= 4:
        score -= 2
        notes.append(f"Strong hot-streak dampener — L5 +{delta:.3f} above season avg")
    elif delta > 0.100 and h2h_pa < 10 and score > 0 and len(recent_games) >= 4:
        score -= 1
        notes.append(f"Hot-streak dampener — L5 +{delta:.3f} above season, no H2H anchor")

    # ── TIER 1: K-risk dampener — high-whiff batter vs high-K pitcher ────────
    # Strikeout-heavy batters facing elite K pitchers get fewer balls in play
    batter_whiff = _f(s.get("whiff_rate", 0))
    p_k9_raw = _f((pitcher_stats.get("stats", {}) if pitcher_stats else {}).get("k9", 0))
    if batter_whiff >= 28 and p_k9_raw >= 9.0:
        score -= 1; notes.append(f"K-risk matchup — batter whiff {batter_whiff:.0f}% vs pitcher K/9 {p_k9_raw:.1f}")
    elif batter_whiff >= 32:
        score -= 1; notes.append(f"High batter whiff rate ({batter_whiff:.0f}%) — contact risk")

    # ── TIER 1: wRC+ — park-and-league-adjusted offensive production ──────────
    # More predictive than BA/OPS for true offensive ability; 100 = league avg.
    wrc_plus = _f(s.get("wrc_plus", 0) or 0)
    if wrc_plus >= 140 and pa >= 50:
        score += 1; notes.append(f"Elite wRC+ ({int(wrc_plus)}) — elite offensive producer, contact sustains")
    elif wrc_plus > 0 and wrc_plus <= 75 and pa >= 50:
        score -= 1; notes.append(f"Weak wRC+ ({int(wrc_plus)}) — below-avg hitter, hit prop penalized")

    # ── TIER 1: Groundball% — GB hitters sustain higher BABIP ────────────────
    gb_pct = _f(s.get("gb_pct", 0))
    fb_pct = _f(s.get("fb_pct", 0))
    if bip >= 50 and gb_pct > 0:
        if gb_pct >= 50:
            score += 1; notes.append(f"High GB% ({gb_pct:.0f}%) — sustains elevated BABIP")
        elif fb_pct >= 45:
            score -= 1; notes.append(f"Fly-ball hitter ({fb_pct:.0f}% FB) — lower BABIP profile")

    # ── TIER 1: Exit velocity — hard contact sustains BABIP hits ─────────────
    avg_ev = _f(s.get("exit_velocity", 0))
    if avg_ev >= 92:
        score += 1; notes.append(f"Hard contact ({avg_ev:.1f} mph avg EV) — BABIP sustains")
    elif avg_ev > 0 and avg_ev <= 85:
        score -= 1; notes.append(f"Soft contact ({avg_ev:.1f} mph avg EV) — BABIP risk")

    # ── TIER 2: Home/Away OPS split ───────────────────────────────────────────
    home_ops = _f(s.get("home_ops", 0))
    away_ops = _f(s.get("away_ops", 0))
    home_pa = int(s.get("home_pa", 0) or 0)
    away_pa = int(s.get("away_pa", 0) or 0)
    if home_pa >= 25 and away_pa >= 25:
        ops_delta = (home_ops - away_ops) if is_home else (away_ops - home_ops)
        venue_label = "Home" if is_home else "Road"
        if ops_delta >= 0.120:
            score += 1; notes.append(f"{venue_label} OPS boost (+{ops_delta:.3f} vs opposite)")
        elif ops_delta <= -0.120:
            score -= 1; notes.append(f"{venue_label} OPS drag (-{abs(ops_delta):.3f} vs opposite)")

    # ── Park factor (hit) ─────────────────────────────────────────────────────
    pf = park_factors or {}
    park_hit = pf.get("hit", 1.0)
    park_run = pf.get("run", 1.0)
    if park_hit >= 1.20 or park_run >= 1.40:
        score += 3; notes.append(f"Extreme hitter's park (Hit PF {park_hit:.2f} / Run PF {park_run:.2f}) — UNDERs suppressed")
    elif park_hit >= 1.10 or park_run >= 1.20:
        score += 2; notes.append(f"Strong hitter's park (Hit PF {park_hit:.2f} / Run PF {park_run:.2f})")
    elif park_hit >= 1.05 or park_run >= 1.10:
        score += 1; notes.append(f"Hitter-friendly park (Hit PF {park_hit:.2f})")
    elif park_hit <= 0.85 or park_run <= 0.85:
        score -= 1; notes.append(f"Pitcher-friendly park (Hit PF {park_hit:.2f} / Run PF {park_run:.2f})")
    elif park_hit <= 0.78 or park_run <= 0.78:
        score -= 2; notes.append(f"Strong pitcher's park (Hit PF {park_hit:.2f} / Run PF {park_run:.2f})")

    # ── TIER 1: Statcast batter quality (Savant CSV) ──────────────────────────
    # Positive contribution capped at +3 so batter profile alone can't cross
    # the OVER threshold — pitcher/park signals must stack for a call.
    if batter_savant:
        sv_barrel     = _f(batter_savant.get("barrel_pct", 0))
        sv_hard_hit   = _f(batter_savant.get("hard_hit_pct", 0))
        sv_sweet_spot = _f(batter_savant.get("sweet_spot", 0))
        sv_bat_speed  = _f(batter_savant.get("avg_bat_speed", 0))

        _sv_pos = 0; _sv_neg = 0; _sv_notes = []

        if sv_barrel >= 12:
            _sv_pos += 2; _sv_notes.append(f"Elite barrel% ({sv_barrel:.1f}%) — power contact boosts hit floor")
        elif sv_barrel >= 8:
            _sv_pos += 1; _sv_notes.append(f"Good barrel% ({sv_barrel:.1f}%) — solid contact quality")
        elif sv_barrel > 0 and sv_barrel <= 3:
            _sv_neg -= 1; _sv_notes.append(f"Weak barrel% ({sv_barrel:.1f}%) — poor contact quality")

        if sv_hard_hit >= 50:
            _sv_pos += 1; _sv_notes.append(f"Hard-hit% {sv_hard_hit:.1f}% — quality contact above avg")
        elif sv_hard_hit > 0 and sv_hard_hit <= 30:
            _sv_neg -= 1; _sv_notes.append(f"Low hard-hit% ({sv_hard_hit:.1f}%) — soft contact risk")

        if sv_sweet_spot >= 38:
            _sv_pos += 1; _sv_notes.append(f"Sweet spot% {sv_sweet_spot:.1f}% — optimal launch angle for hits")

        if sv_bat_speed >= 75:
            _sv_pos += 1; _sv_notes.append(f"Elite bat speed ({sv_bat_speed:.1f} mph) — hard contact potential")

        score += min(_sv_pos, 3) + _sv_neg
        notes.extend(_sv_notes)

    # UNDER threshold raised to -4: even cold hitters get 1+ hit ~40% of the time.
    # Hit UNDERs at -3 threshold ran 38% — tightening to require stronger conviction.
    lean = "OVER" if score >= 5 else "UNDER" if score <= -4 else "NEUTRAL"
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
        "h2h_avg": f".{int(h2h_avg*1000):03d}" if h2h_avg is not None else "No data",
        "h2h_pa": h2h_pa,
        "streak": streak,
        "ld_pct": ld_pct,
        "l5_babip": l5_babip,
        "platoon": round(platoon, 3),
        "notes": notes,
    }


def analyze_batter_hr_prop(batter_stats: dict, recent_games: list,
                            pitcher_stats: dict, h2h: dict,
                            park_factors: dict, weather: dict,
                            line: float = 0.5,
                            batter_savant: dict = None) -> dict:
    """Evaluate a batter's HR prop."""
    def _sv(v, d=0.0):
        try: return float(v or d)
        except: return d

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

    # Pitcher splits HR rate vs batter handedness
    batter_hand = batter_stats.get("bats", "R")
    p_splits = pitcher_stats.get("splits", {}) if pitcher_stats else {}
    split_key = "vs. Left" if batter_hand == "L" else "vs. Right"
    split_d = p_splits.get(split_key, {})
    if split_d:
        try:
            split_ip = float(split_d.get("ip", "0.0") or "0.0")
            split_hr = split_d.get("hr", 0)
            if split_ip >= 20 and split_hr > 0:
                hr_per_100 = (split_hr / (split_ip * 4.3)) * 100
                hand_lbl = "LHB" if batter_hand == "L" else "RHB"
                if hr_per_100 >= 4.0:
                    score += 2; notes.append(f"Pitcher allows {hr_per_100:.1f} HR/100 to {hand_lbl}")
                elif hr_per_100 >= 2.8:
                    score += 1; notes.append(f"Pitcher HR-prone vs {hand_lbl} ({hr_per_100:.1f} HR/100)")
        except Exception:
            pass

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

    # ── Statcast batter quality (Savant CSV) — barrel% is the strongest HR predictor
    # Positive contribution capped at +2: batter power profile alone cannot
    # cross the OVER-5 threshold — pitcher HR-proneness and park must confirm.
    if batter_savant:
        sv_barrel    = _sv(batter_savant.get("barrel_pct"))
        sv_hard_hit  = _sv(batter_savant.get("hard_hit_pct"))
        sv_xslg      = _sv(batter_savant.get("xslg"))
        sv_slg       = _sv(s.get("slg", 0) or 0)
        sv_bat_speed  = _sv(batter_savant.get("avg_bat_speed"))
        sv_blast     = _sv(batter_savant.get("blast_per_swing"))

        _sv_pos = 0; _sv_neg = 0; _sv_notes = []

        if sv_barrel >= 15:
            _sv_pos += 2; _sv_notes.append(f"Elite barrel% ({sv_barrel:.1f}%) — strongest HR predictor")
        elif sv_barrel >= 10:
            _sv_pos += 1; _sv_notes.append(f"Strong barrel% ({sv_barrel:.1f}%) — HR power quality")
        elif sv_barrel > 0 and sv_barrel <= 3:
            _sv_neg -= 2; _sv_notes.append(f"Weak barrel% ({sv_barrel:.1f}%) — not a HR threat")

        if sv_hard_hit >= 50:
            _sv_pos += 1; _sv_notes.append(f"Hard-hit% {sv_hard_hit:.1f}% — power contact quality")

        if sv_xslg > 0 and sv_slg > 0 and (sv_xslg - sv_slg) >= 0.060:
            _sv_pos += 1; _sv_notes.append(f"xSLG ({sv_xslg:.3f}) >> SLG ({sv_slg:.3f}) — HR regression due")

        if sv_bat_speed >= 75:
            _sv_pos += 1; _sv_notes.append(f"Elite bat speed ({sv_bat_speed:.1f} mph) — power potential")

        if sv_blast >= 12:
            _sv_pos += 1; _sv_notes.append(f"Blast/swing {sv_blast:.1f}% — max-effort power swings")

        score += min(_sv_pos, 2) + _sv_neg
        notes.extend(_sv_notes)

    # HR OVER raised to 6: Savant batter-quality cap (+2) means pitcher/park signals
    # must stack. At threshold 5 with Savant, mediocre plays scored 3+2=5 (OVER).
    # Threshold 6 requires genuinely multi-signal conviction before flagging.
    lean = "OVER" if score >= 6 else "UNDER" if score <= -2 else "NEUTRAL"
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


def analyze_hrrbi_prop(batter_stats: dict, recent_games: list,
                       pitcher_stats: dict, h2h: dict,
                       park_factors: dict, weather: dict,
                       line: float = 1.5) -> dict:
    """
    H + R + RBI combined prop — typical lines 1.5 / 2.5.
    Signals: multi-hit rate, RBI pace, run-scoring rate, order position.
    """
    s    = batter_stats.get("stats", {})
    pa   = s.get("pa", 0) or 1
    gp   = max(pa / 3.9, 1)   # estimate games played from PA

    hits_pg = s.get("hits", 0) / gp
    r_pg    = s.get("runs", 0) / gp
    rbi_pg  = s.get("rbi", 0) / gp
    season_hrrbi_pg = hits_pg + r_pg + rbi_pg

    # L5 H+R+RBI
    l5_hrrbi = [g.get("h",0) + g.get("r",0) + g.get("rbi",0) for g in recent_games[:5]]
    l5_avg   = sum(l5_hrrbi) / len(l5_hrrbi) if l5_hrrbi else 0
    l5_over  = sum(1 for x in l5_hrrbi if x >= line)  # games clearing the line

    # Pitcher walk rate inflates BB (indirect run scorer)
    p_stats  = pitcher_stats.get("stats", {}) if pitcher_stats else {}
    p_era    = float(p_stats.get("era", "4.50") or "4.50")
    p_bb9    = float(p_stats.get("bb9", "3.0")  or "3.0")
    p_hr9    = float(p_stats.get("hr9", "1.0")  or "1.0")
    p_baa    = float(p_stats.get("avg", ".250") or ".250")

    park_run = park_factors.get("run", 1.0)
    park_hr  = park_factors.get("hr",  1.0)

    # H2H RBI/R history
    career   = (h2h or {}).get("career_summary", {})
    h2h_pa   = career.get("pa", 0)
    h2h_rbi  = career.get("rbi", 0)
    h2h_conf = min(h2h_pa / 30.0, 1.0)

    score  = 0
    notes  = []

    # 1. Season pace
    if season_hrrbi_pg >= line + 1.0:
        score += 2; notes.append(f"Season pace {season_hrrbi_pg:.2f} H+R+RBI/game — comfortably clears line")
    elif season_hrrbi_pg >= line + 0.25:
        score += 1; notes.append(f"Season pace {season_hrrbi_pg:.2f} H+R+RBI/game — above line")
    elif season_hrrbi_pg < line - 0.5:
        score -= 2; notes.append(f"Season pace {season_hrrbi_pg:.2f} H+R+RBI/game — below line")
    elif season_hrrbi_pg < line - 0.1:
        score -= 1; notes.append(f"Season pace {season_hrrbi_pg:.2f} H+R+RBI/game — borderline")

    # 2. Recent form
    if l5_avg >= line + 1.5:
        score += 2; notes.append(f"Scorching L5: avg {l5_avg:.1f} H+R+RBI/game  {l5_hrrbi}")
    elif l5_avg >= line + 0.5:
        score += 1; notes.append(f"Hot L5: avg {l5_avg:.1f} H+R+RBI/game  {l5_hrrbi}")
    elif l5_avg < line - 1.0:
        score -= 2; notes.append(f"Ice cold L5: avg {l5_avg:.1f} H+R+RBI/game  {l5_hrrbi}")
    elif l5_avg < line - 0.4:
        score -= 1; notes.append(f"Cool L5: avg {l5_avg:.1f} H+R+RBI/game  {l5_hrrbi}")

    # 3. Line-clearing consistency
    if l5_over >= 4:
        score += 1; notes.append(f"Cleared {line} H+R+RBI in {l5_over}/5 recent games")
    elif l5_over <= 1 and len(l5_hrrbi) >= 4:
        score -= 1; notes.append(f"Only cleared {line} H+R+RBI in {l5_over}/5 recent games")

    # 4. Hittable pitcher
    if p_era >= 5.00:
        score += 1; notes.append(f"High-ERA pitcher ({p_era:.2f}) — run-scoring environment elevated")
    elif p_era <= 2.80:
        score -= 1; notes.append(f"Dominant starter (ERA {p_era:.2f}) — caps H+R+RBI ceiling")

    if p_baa >= 0.275:
        score += 1; notes.append(f"Pitcher allows high avg (.{int(p_baa*1000):03d} BAA) — baserunner traffic")

    if p_bb9 >= 4.0:
        score += 1; notes.append(f"Wild pitcher (BB/9={p_bb9:.1f}) — extra baserunners create R/RBI opportunities")

    # 5. HR-prone pitcher / park boosts R+RBI
    if p_hr9 >= 1.20 or park_hr >= 1.15:
        score += 1; notes.append(f"HR-friendly matchup — HR carries 1H+1R+RBI in one swing")

    # 6. Park run factor
    if park_run >= 1.15:
        score += 1; notes.append(f"Hitter's park (Run PF {park_run:.2f}) — inflates scoring environment")
    elif park_run <= 0.88:
        score -= 1; notes.append(f"Pitcher's park (Run PF {park_run:.2f}) — suppresses run production")

    # 7. H2H RBI history
    if h2h_pa >= 10 and h2h_conf >= 0.33:
        h2h_rbi_pg = h2h_rbi / max(h2h_pa / 3.5, 1)
        if h2h_rbi_pg >= 0.5:
            score += 1; notes.append(f"H2H RBI rate ({h2h_rbi} RBI / {h2h_pa} PA) vs this pitcher")

    lean = "OVER" if score >= 3 else "UNDER" if score <= -3 else "NEUTRAL"
    conf = "Strong" if abs(score) >= 5 else "Lean" if abs(score) >= 3 else "Slight"

    return {
        "prop_type":        "H+R+RBI",
        "batter":           batter_stats.get("name", ""),
        "line":             line,
        "lean":             lean,
        "confidence":       conf,
        "score":            score,
        "season_hrrbi_pg":  round(season_hrrbi_pg, 2),
        "l5_hrrbi":         l5_hrrbi,
        "l5_avg_hrrbi":     round(l5_avg, 2),
        "l5_over":          l5_over,
        "hits_pg":          round(hits_pg, 2),
        "r_pg":             round(r_pg, 2),
        "rbi_pg":           round(rbi_pg, 2),
        "notes":            notes,
    }


def analyze_fantasy_score_prop(batter_stats: dict, recent_games: list,
                                pitcher_stats: dict, h2h: dict,
                                park_factors: dict, weather: dict,
                                line: float = 6.5) -> dict:
    """
    PrizePicks Baseball Fantasy Score.
    Scoring: 1B=3 | 2B=5 | 3B=8 | HR=10 | R=2 | RBI=2 | BB=2 | SB=5 | K=-1
    Typical lines: 5.5 / 6.5 / 7.5 / 8.5
    """
    s   = batter_stats.get("stats", {})
    pa  = s.get("pa", 0) or 1
    gp  = max(pa / 3.9, 1)

    # Season rate: estimate hit-type distribution from SLG/AVG (= total bases per hit).
    # PrizePicks pts per hit type: 1B=3, 2B=5, 3B=8, HR=10.
    # Linear interp: pts/hit ≈ 3 + 2*(tb_h - 1), capped at 10.
    avg_val = max(float(s.get("avg", ".250") or ".250"), 0.100)
    slg = max(float(s.get("slg", ".400") or ".400"), 0.100)
    tb_h = min(slg / avg_val, 4.0)
    hit_pts_mult = min(3.0 + 2.0 * (tb_h - 1.0), 10.0)

    h_pg   = (s.get("hits", 0) or 0) / gp
    r_pg   = (s.get("runs", 0) or 0) / gp
    rbi_pg = (s.get("rbi",  0) or 0) / gp
    bb_pg  = (s.get("bb",   0) or 0) / gp
    sb_pg  = (s.get("sb",   0) or 0) / gp
    k_pg   = (s.get("so",   0) or s.get("k", 0) or 0) / gp

    season_fs_pg = h_pg * hit_pts_mult + r_pg * 2 + rbi_pg * 2 + bb_pg * 2 + sb_pg * 5 - k_pg * 1

    obp = float(s.get("obp", ".300") or ".300")

    # L5 PrizePicks fantasy scores using actual hit-type breakdown from game logs
    l5_fs = []
    for g in recent_games[:5]:
        _h  = g.get("h",  0) or 0
        _d  = g.get("doubles", 0) or 0
        _hr = g.get("hr", 0) or 0
        _tb = g.get("total_bases", 0) or 0
        _t  = max((_tb - _h - _d - 3 * _hr) // 2, 0)
        _s1 = max(_h - _d - _hr - _t, 0)
        fs  = (_s1 * 3 + _d * 5 + _t * 8 + _hr * 10
               + (g.get("r",   0) or 0) * 2
               + (g.get("rbi", 0) or 0) * 2
               + (g.get("bb",  0) or 0) * 2
               + (g.get("sb",  0) or 0) * 5
               - (g.get("k",   0) or 0) * 1)
        l5_fs.append(max(fs, 0))
    l5_avg = sum(l5_fs) / len(l5_fs) if l5_fs else 0
    l5_over = sum(1 for x in l5_fs if x >= line)

    # Pitcher signals
    p_stats = pitcher_stats.get("stats", {}) if pitcher_stats else {}
    p_era   = float(p_stats.get("era", "4.50") or "4.50")
    p_bb9   = float(p_stats.get("bb9", "3.0")  or "3.0")
    p_hr9   = float(p_stats.get("hr9", "1.0")  or "1.0")
    p_baa   = float(p_stats.get("avg", ".250") or ".250")

    park_run = park_factors.get("run", 1.0)
    park_hr  = park_factors.get("hr",  1.0)
    wx_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0

    score  = 0
    notes  = []

    # Auto-select display line based on PP-scale season production.
    # suggested_line is returned as metadata; all scoring uses the passed-in `line`.
    if season_fs_pg >= 8.5:
        suggested_line = 8.5
    elif season_fs_pg >= 7.0:
        suggested_line = 7.5
    elif season_fs_pg >= 5.5:
        suggested_line = 6.5
    else:
        suggested_line = 5.5

    # Use the passed-in line (or caller can pass suggested_line explicitly)
    eval_line = line

    # 1. Season rate vs actual line — primary anchor (most predictive signal)
    gap = season_fs_pg - eval_line
    if gap >= 1.0:
        score += 3; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — comfortably above {eval_line} line")
    elif gap >= 0.5:
        score += 2; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — above {eval_line} line")
    elif gap >= 0.1:
        score += 1; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — at the {eval_line} line")
    elif gap <= -1.5:
        score -= 3; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — well below {eval_line} line")
    elif gap <= -0.8:
        score -= 2; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — below {eval_line} line")
    elif gap <= -0.2:
        score -= 1; notes.append(f"Season PP rate {season_fs_pg:.2f} pts/g — under {eval_line} line")

    # 2. Recent form — secondary modifier (max ±2; season + matchup carry the call)
    if l5_avg >= eval_line + 2.0:
        score += 2; notes.append(f"Hot L5 — avg {l5_avg:.1f} PP pts  {l5_fs}")
    elif l5_avg >= eval_line + 0.5:
        score += 1; notes.append(f"Solid L5 — avg {l5_avg:.1f} PP pts  {l5_fs}")
    elif l5_avg < eval_line - 2.0:
        score -= 2; notes.append(f"Cold L5 — avg {l5_avg:.1f} PP pts  {l5_fs}")
    elif l5_avg < eval_line - 1.0:
        score -= 1; notes.append(f"Soft L5 — avg {l5_avg:.1f} PP pts  {l5_fs}")
    else:
        notes.append(f"L5 near line — avg {l5_avg:.1f} PP pts  {l5_fs}")

    # 3. Line-clearing consistency — informational, smaller penalty for 0-of-5
    if l5_over >= 4:
        score += 1; notes.append(f"Cleared {eval_line} PP pts in {l5_over}/5 recent games")
    elif l5_over == 0 and len(l5_fs) >= 4:
        score -= 1; notes.append(f"0/{len(l5_fs)} recent games clearing {eval_line} PP pts")

    # 3b. Hot-streak regression dampener: if L5 far outpaces season rate AND season
    # rate is below the line, the hot stretch is variance/schedule-driven, not ability.
    # Green L5 alone is a trap — need season production to confirm the OVER.
    _l5_delta = l5_avg - season_fs_pg
    if _l5_delta >= 5.0 and season_fs_pg < eval_line:
        score -= 2; notes.append(
            f"Hot-streak regression risk — L5 avg {l5_avg:.1f} far above season {season_fs_pg:.1f} pts/g; "
            f"season rate below line, bet relies on streak continuing"
        )
    elif _l5_delta >= 3.0 and season_fs_pg < eval_line - 0.5:
        score -= 1; notes.append(
            f"Streak caution — L5 avg {l5_avg:.1f} outpacing season {season_fs_pg:.1f} pts/g; "
            f"season rate below line anchor"
        )

    # 4. SB threat — +5 PP pts per stolen base
    if sb_pg >= 0.25:
        score += 1; notes.append(f"Active SB threat ({s.get('sb',0)} SB, {sb_pg:.2f}/g) — +5 PP pts per steal")
    elif sb_pg >= 0.12:
        notes.append(f"Occasional SB ({s.get('sb',0)} SB, {sb_pg:.2f}/g) — +5 pts when active")

    # 5. OBP / walk rate — drives BB points
    if obp >= 0.380:
        score += 1; notes.append(f"Elite OBP ({obp:.3f}) — walks inflate fantasy score")
    elif obp <= 0.280:
        score -= 1; notes.append(f"Poor OBP ({obp:.3f}) — low BB floor")

    # 6. Power (HR = H+R+RBI in one AB = +3 effective fantasy pts)
    hr_pg = s.get("hr", 0) / gp
    if hr_pg >= 0.065:
        score += 1; notes.append(f"Power bat ({s.get('hr',0)} HR) — HR worth 3 effective pts")

    # 7. Pitcher walk rate
    if p_bb9 >= 4.5:
        score += 1; notes.append(f"Wild pitcher (BB/9={p_bb9:.1f}) — free bases boost R+BB scoring")
    elif p_bb9 <= 1.8:
        score -= 1; notes.append(f"Pitcher walks nobody (BB/9={p_bb9:.1f}) — limits BB category")

    # 8. Pitcher ERA / run environment — meaningful matchup weight
    if p_era >= 6.0:
        score += 2; notes.append(f"Very hittable pitcher (ERA {p_era:.2f}) — prime FS spot")
    elif p_era >= 5.0:
        score += 1; notes.append(f"Hittable pitcher (ERA {p_era:.2f}) — elevated run environment")
    elif p_era <= 2.50:
        score -= 2; notes.append(f"Elite starter (ERA {p_era:.2f}) — suppresses all FS categories")
    elif p_era <= 3.50:
        score -= 1; notes.append(f"Strong starter (ERA {p_era:.2f}) — limits FS ceiling")

    # 9. Park + weather
    if park_run >= 1.15:
        score += 1; notes.append(f"Hitter's park (Run PF {park_run:.2f})")
    elif park_run <= 0.88:
        score -= 1; notes.append(f"Pitcher's park (Run PF {park_run:.2f})")

    if wx_score >= 2.0:
        score += 1; notes.append("Hot weather — inflates HR/runs/fantasy scoring")

    lean = "OVER" if score >= 4 else "UNDER" if score <= -4 else "NEUTRAL"
    conf = "Strong" if abs(score) >= 6 else "Lean" if abs(score) >= 4 else "Slight"

    return {
        "prop_type":        "Fantasy Score",
        "batter":           batter_stats.get("name", ""),
        "line":             eval_line,
        "lean":             lean,
        "confidence":       conf,
        "score":            score,
        "season_fs_pg":     round(season_fs_pg, 2),
        "l5_fs":            l5_fs,
        "l5_avg_fs":        round(l5_avg, 2),
        "l5_over":          l5_over,
        "suggested_line":   suggested_line,
        "breakdown": {
            "h_pg":         round(h_pg, 2),
            "hit_pts_mult": round(hit_pts_mult, 2),
            "r_pg":         round(r_pg, 2),
            "rbi_pg":       round(rbi_pg, 2),
            "bb_pg":        round(bb_pg, 2),
            "sb_pg":        round(sb_pg, 2),
            "k_pg":         round(k_pg, 2),
        },
        "obp":  s.get("obp", ".000"),
        "slg":  s.get("slg", ".000"),
        "ops":  s.get("ops", ".000"),
        "sb_season": s.get("sb", 0),
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


def analyze_nrfi_prop(away_pitcher_stats: dict, home_pitcher_stats: dict,
                      park_factors: dict, weather: dict,
                      umpire_k_rate: float = None) -> dict:
    """Tier 3: No Run First Inning (NRFI) prop model.

    Uses Poisson distribution to estimate P(0 runs) in the first inning for each
    half-inning, then multiplies them for joint NRFI probability.

    First-inning ERA adjustment: starters allow ~15% fewer runs in the first
    inning (batters unprepared, pitcher fresh) — calibrated from MLB 2022-25 data.
    """
    import math

    def _era(p):
        try:
            return float((p or {}).get("stats", {}).get("era", "4.50") or "4.50")
        except Exception:
            return 4.50

    def _fi_no_run_prob(season_era: float, park_run: float) -> float:
        # First-inning ERA ≈ season ERA × 1.05 — top of lineup bats first, scoring
        # premium vs average innings (~12% higher run rate in inning 1 empirically).
        # ERA capped at 7.0: pitchers with 8-11 ERA get knocked around in innings 3-5,
        # but often open cleanly in the 1st before the lineup adjusts. Extreme ERAs
        # (10+ like today's Gusto / Lorenzen) were over-driving YRFI confidence.
        effective_era = min(season_era, 7.0)
        fi_era = effective_era * 1.05
        # Park adjustment — softer for single inning
        fi_era_adj = fi_era * (1.0 + (park_run - 1.0) * 0.40)
        # Expected runs in 1 IP via Poisson: lambda = ERA / 9
        lam = max(fi_era_adj / 9.0, 0.10)
        return math.exp(-lam)   # P(X=0) for Poisson(lambda)

    park_run = park_factors.get("run", 1.0)
    weather_score = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0
    weather_adj = 1.0 + weather_score * 0.015   # tiny weather nudge per run factor

    away_era = _era(away_pitcher_stats)
    home_era = _era(home_pitcher_stats)

    # Umpire adjustment: pitcher-friendly HP ump → fewer runs (more Ks = fewer BIP = fewer runs).
    # Calibrated effect: ±1 K/game ≈ ±0.5% NRFI probability shift.
    ump_nrfi_mult = 1.0
    ump_note = None
    if umpire_k_rate is not None:
        delta = umpire_k_rate - 15.0  # deviation from MLB avg (~15 K/game)
        ump_nrfi_mult = 1.0 + delta * 0.003  # ±3% at extremes (±5 K/game from avg)
        ump_nrfi_mult = max(0.92, min(1.08, ump_nrfi_mult))
        if umpire_k_rate >= 17.5:
            ump_note = f"Pitcher-friendly HP ump ({umpire_k_rate:.1f} K/game) — NRFI boosted"
        elif umpire_k_rate <= 13.0:
            ump_note = f"Hitter-friendly HP ump ({umpire_k_rate:.1f} K/game) — NRFI dampened"

    # Away bats vs home pitcher (top of 1st)
    p_no_away_score = _fi_no_run_prob(home_era, park_run) * (1.0 / weather_adj) * ump_nrfi_mult
    # Home bats vs away pitcher (bottom of 1st)
    p_no_home_score = _fi_no_run_prob(away_era, park_run) * (1.0 / weather_adj) * ump_nrfi_mult

    p_nrfi = round(p_no_away_score * p_no_home_score, 3)
    p_yrfi = round(1.0 - p_nrfi, 3)

    # YRFI tightened from ≤40% to ≤35%: June 10 showed TEX@KC (37%) and other
    # marginal calls misfiring. Extreme-ERA pitchers also capped at 7.0 to prevent
    # over-confident YRFI on single-bad-pitcher games (Gusto 10.80, Lorenzen 8.01 both missed).
    lean = "NRFI" if p_nrfi >= 0.65 else "YRFI" if p_nrfi <= 0.35 else "NEUTRAL"
    confidence = "Strong" if abs(p_nrfi - 0.50) >= 0.14 else "Lean" if abs(p_nrfi - 0.50) >= 0.08 else "Slight"

    notes = [
        f"P(NRFI) = {p_nrfi:.1%} | P(YRFI) = {p_yrfi:.1%}",
        f"Away SP ERA {away_era:.2f} → est. FI ERA {away_era*1.05:.2f}",
        f"Home SP ERA {home_era:.2f} → est. FI ERA {home_era*1.05:.2f}",
    ]
    if ump_note:
        notes.append(ump_note)
    if weather_score >= 1.0:
        notes.append(weather.get("impact", {}).get("note", "Weather boosts scoring"))

    return {
        "prop_type": "NRFI",
        "lean": lean,
        "confidence": confidence,
        "score": round((p_nrfi - 0.53) * 20, 2),  # normalized scoring for sorting
        "p_nrfi": p_nrfi,
        "p_yrfi": p_yrfi,
        "away_era": away_era,
        "home_era": home_era,
        "notes": notes,
    }


def build_prop_sheet(game_analysis: dict, as_of_date: str = None) -> dict:
    """Master prop sheet builder — takes full game_analysis output, returns ranked props."""
    from baseball_engine import get_batter_vs_pitcher, get_batter_season_stats, get_pitcher_savant, get_game_umpire, get_batter_savant
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

    # Pitcher handedness — try top-level, then nested info
    away_p_hand = (away_p.get("throws") or away_p.get("info", {}).get("throws") or "R").upper()
    home_p_hand = (home_p.get("throws") or home_p.get("info", {}).get("throws") or "R").upper()

    park = game_analysis.get("park_factors", {})
    weather = game_analysis.get("weather", {})
    season = game_analysis.get("season", datetime.now().year)

    # ── Fetch Savant pitcher K-metrics (SwStr%, K%) and HP umpire ────────────
    game_pk = game_analysis.get("game_pk")
    away_savant = get_pitcher_savant(away_p_id, season) if away_p_id else {}
    home_savant = get_pitcher_savant(home_p_id, season) if home_p_id else {}
    away_swstr = away_savant.get("swstr_pct") or None
    home_swstr = home_savant.get("swstr_pct") or None
    away_csw = away_savant.get("csw_pct") or None
    home_csw = home_savant.get("csw_pct") or None

    umpire = {}
    if game_pk:
        try:
            umpire = get_game_umpire(game_pk)
        except Exception:
            umpire = {}
    umpire_k_rate = umpire.get("k_rate")  # None if unknown umpire

    props = []

    # ── Game Total ──
    total_prop = analyze_total(away_p_stats, home_p_stats, park, weather,
                               game_analysis.get("game_odds", {}))
    props.append(total_prop)

    # ── NRFI (Tier 3) ──
    if away_p_stats and home_p_stats:
        nrfi = analyze_nrfi_prop(away_p_stats, home_p_stats, park, weather,
                                 umpire_k_rate=umpire_k_rate)
        if umpire.get("name") and umpire["name"] != "Unknown":
            nrfi["umpire"] = umpire.get("name")
            nrfi["umpire_k_rate"] = umpire_k_rate
        props.append(nrfi)

    # ── Pitcher K props ──
    # away pitcher faces home lineup; home pitcher faces away lineup
    away_p_arsenal = away_p.get("arsenal", [])
    home_p_arsenal = home_p.get("arsenal", [])

    if away_p_stats:
        kp = analyze_pitcher_k_prop(away_p_stats, away_p_recent,
                                    game_analysis.get("lineups", {}).get("home", []),
                                    pitcher_arsenal=away_p_arsenal,
                                    pitcher_csw=away_csw,
                                    pitcher_swstr=away_swstr,
                                    umpire_k_rate=umpire_k_rate)
        kp["side"] = "away"
        kp["pitcher_team"] = game_analysis.get("away_team", {}).get("abbr", "")
        kp["faces_lineup"] = game_analysis.get("home_team", {}).get("abbr", "")
        kp["swstr_pct"] = away_swstr
        kp["umpire"] = umpire.get("name") if umpire.get("name") != "Unknown" else None
        props.append(kp)

    if home_p_stats:
        kp = analyze_pitcher_k_prop(home_p_stats, home_p_recent,
                                    game_analysis.get("lineups", {}).get("away", []),
                                    pitcher_arsenal=home_p_arsenal,
                                    pitcher_csw=home_csw,
                                    pitcher_swstr=home_swstr,
                                    umpire_k_rate=umpire_k_rate)
        kp["side"] = "home"
        kp["pitcher_team"] = game_analysis.get("home_team", {}).get("abbr", "")
        kp["faces_lineup"] = game_analysis.get("away_team", {}).get("abbr", "")
        kp["swstr_pct"] = home_swstr
        kp["umpire"] = umpire.get("name") if umpire.get("name") != "Unknown" else None
        props.append(kp)

    # ── Batter props (hits + HR) ──
    matchups = game_analysis.get("matchups", {})

    def process_batters(batter_list, pitcher_stats, pitcher_id, side_label,
                        opp_pitcher_hand, batter_is_home):
        # side_label = team side of the BATTER ("home"/"away"), NOT which pitcher they face.
        # Home batters face the away pitcher; away batters face the home pitcher.
        opp_name = pitcher_stats.get("name", "") if pitcher_stats else ""
        hr_per_pitcher = {}   # cap HR props at 3 per opposing pitcher
        for item in batter_list[:9]:
            batter = item.get("batter", {})
            bid = batter.get("player_id")
            if not bid:
                continue
            h2h = item.get("h2h", {})

            batter_full = get_batter_season_stats(bid, season, as_of_date)
            if not batter_full:
                _time.sleep(0.1)
                continue

            recent = get_batter_last_n(bid, season, 5, as_of_date)
            b_savant = get_batter_savant(bid, season)
            _time.sleep(0.15)

            # Hits prop — pass pitcher hand, home/away context, and park factors
            hit_p = analyze_batter_hit_prop(
                batter_full, recent, pitcher_stats, h2h, 0.5,
                pitcher_hand=opp_pitcher_hand,
                is_home=batter_is_home,
                park_factors=park,
                batter_savant=b_savant,
            )
            hit_p["order"] = batter.get("order", 0)
            hit_p["batter_side"] = side_label          # which team the batter plays for
            hit_p["side"] = side_label                  # kept for backwards compat
            hit_p["opposing_pitcher"] = opp_name        # the pitcher this batter actually faces
            hit_p["opposing_pitcher_id"] = pitcher_id
            hit_p["recent_games"] = recent
            # Include all actionable props: any OVER/UNDER call, or high-signal neutrals
            if not hit_p.get("insufficient_data") and (
                hit_p.get("lean") in ("OVER", "UNDER") or abs(hit_p["score"]) >= 2
            ):
                props.append(hit_p)

            # HR prop — cap at 3 per opposing pitcher to avoid over-stacking
            hr_p = analyze_batter_hr_prop(batter_full, recent, pitcher_stats, h2h, park, weather, 0.5, batter_savant=b_savant)
            hr_p["order"] = batter.get("order", 0)
            hr_p["batter_side"] = side_label
            hr_p["side"] = side_label
            hr_p["opposing_pitcher"] = opp_name
            hr_p["opposing_pitcher_id"] = pitcher_id
            p_hr_count = hr_per_pitcher.get(pitcher_id, 0)
            if abs(hr_p["score"]) >= 4 and p_hr_count < 3:
                props.append(hr_p)
                hr_per_pitcher[pitcher_id] = p_hr_count + 1

            # H+R+RBI prop (1.5 line)
            hrrbi_p = analyze_hrrbi_prop(batter_full, recent, pitcher_stats, h2h, park, weather, 1.5)
            hrrbi_p["order"] = batter.get("order", 0)
            hrrbi_p["batter_side"] = side_label
            hrrbi_p["side"] = side_label
            hrrbi_p["opposing_pitcher"] = opp_name
            hrrbi_p["opposing_pitcher_id"] = pitcher_id
            if hrrbi_p.get("lean") in ("OVER", "UNDER") or abs(hrrbi_p["score"]) >= 2:
                props.append(hrrbi_p)

            # Fantasy Score prop — PP-calibrated line from season rate + matchup bump
            _s = batter_full.get("stats", {})
            _gp = max((_s.get("pa", 0) or 1) / 3.9, 1)
            _avg_v = max(float(_s.get("avg", ".250") or ".250"), 0.100)
            _slg_v = max(float(_s.get("slg", ".400") or ".400"), 0.100)
            _hit_m = min(3.0 + 2.0 * (min(_slg_v / _avg_v, 4.0) - 1.0), 10.0)
            _h_pg  = (_s.get("hits", 0) or 0) / _gp
            _r_pg  = (_s.get("runs", 0) or 0) / _gp
            _rbi_g = (_s.get("rbi",  0) or 0) / _gp
            _bb_g  = (_s.get("bb",   0) or 0) / _gp
            _sb_g  = (_s.get("sb",   0) or 0) / _gp
            _k_g   = (_s.get("so", 0) or _s.get("k", 0) or 0) / _gp
            _fs_rate = _h_pg * _hit_m + _r_pg * 2 + _rbi_g * 2 + _bb_g * 2 + _sb_g * 5 - _k_g
            # Base line from PP season rate
            if _fs_rate >= 8.5:   _fs_line = 8.5
            elif _fs_rate >= 7.0: _fs_line = 7.5
            elif _fs_rate >= 5.5: _fs_line = 6.5
            else:                  _fs_line = 5.5
            # Bump line up for hittable pitcher or hitter's park (books do the same)
            _p_s = pitcher_stats.get("stats", {}) if pitcher_stats else {}
            _p_era = float(_p_s.get("era", "4.50") or "4.50")
            _p_bb9 = float(_p_s.get("bb9", "3.0")  or "3.0")
            _park_run = park.get("run", 1.0)
            _bump = 0.0
            if _p_era >= 6.0:     _bump += 1.0
            elif _p_era >= 5.0:   _bump += 0.5
            if _p_bb9 >= 4.5:     _bump += 0.5
            if _park_run >= 1.20: _bump += 0.5
            _fs_line = round(min(_fs_line + _bump, 9.5) * 2) / 2
            fs_p = analyze_fantasy_score_prop(batter_full, recent, pitcher_stats, h2h, park, weather, _fs_line)
            fs_p["order"] = batter.get("order", 0)
            fs_p["batter_side"] = side_label
            fs_p["side"] = side_label
            fs_p["opposing_pitcher"] = opp_name
            fs_p["opposing_pitcher_id"] = pitcher_id
            if fs_p.get("lean") in ("OVER", "UNDER") or abs(fs_p["score"]) >= 2:
                props.append(fs_p)

    if home_p_stats and home_p_id:
        process_batters(
            matchups.get("away_batters_vs_home_pitcher", []),
            home_p_stats, home_p_id, "away",
            opp_pitcher_hand=home_p_hand, batter_is_home=False,
        )
    if away_p_stats and away_p_id:
        process_batters(
            matchups.get("home_batters_vs_away_pitcher", []),
            away_p_stats, away_p_id, "home",
            opp_pitcher_hand=away_p_hand, batter_is_home=True,
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
    """
    0.0–1.0 composite power score from Statcast.

    Weight rationale (from predictive studies):
      - EV50: most stable season-to-season predictor of HR output (35%)
      - Barrel%: direct batted-ball quality, highly HR-correlated (30%)
      - Hard-hit%: broader contact quality (20%)
      - xSLG: expected slugging from EV/LA distribution (15%)
    Blast% removed — too correlated with barrel% to add independent signal.
    """
    score = 0.0
    weight = 0.0

    barrel = savant.get("barrel_pct", 0) or 0
    hard   = savant.get("hard_hit_pct", 0) or 0
    ev50   = savant.get("ev50", 0) or 0
    xslg   = savant.get("xslg", 0) or 0

    # EV50 (league median ~88 mph; elite ~95+) — weight 35%
    if ev50 > 0:
        # Normalize: 80 mph = 0.0, 100 mph = 1.0
        score  += min(max(ev50 - 80, 0) / 20.0, 1.0) * 0.35
        weight += 0.35

    # Barrel% (league avg ~8%; elite ~18%+) — weight 30%
    if barrel > 0:
        score  += min(barrel / 18.0, 1.0) * 0.30
        weight += 0.30

    # Hard-hit% (league avg ~37%; elite ~55%+) — weight 20%
    if hard > 0:
        score  += min(hard / 60.0, 1.0) * 0.20
        weight += 0.20

    # xSLG (league avg ~.430; elite ~.650+) — weight 15%
    if xslg > 0:
        score  += min(xslg / 0.750, 1.0) * 0.15
        weight += 0.15

    return round(score / weight, 3) if weight > 0 else 0.0


def calc_pitcher_vulnerability(savant: dict, pitcher_stats: dict) -> float:
    """0.0–1.0 pitcher HR/hard-contact vulnerability."""
    score  = 0.0
    weight = 0.0

    barrel_ag = savant.get("barrel_pct_against", 0) or 0
    hard_ag   = savant.get("hard_hit_pct_against", 0) or 0
    ev_ag     = savant.get("exit_velo_against", 0) or 0
    def _fv(v, default):
        try: return float(v) if v and str(v) not in ("-", "-.--", "") else default
        except Exception: return default
    hr9 = _fv(pitcher_stats.get("stats", {}).get("hr9"), 1.0) if pitcher_stats else 1.0
    era = _fv(pitcher_stats.get("stats", {}).get("era"), 4.50) if pitcher_stats else 4.50

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



# ── HR Model constants (2024-25 Statcast population) ─────────────────────────
_LEAGUE_BARREL_PCT    = 8.0    # league avg barrel% of batted balls
_LEAGUE_HR_PER_BARREL = 0.40   # ~40% of barrels become HRs
_LEAGUE_BIP_PER_PA    = 0.72   # balls-in-play per PA (excl. K, BB, HBP)
_LEAGUE_HR_RATE       = 0.033  # HR per PA (~33/1000 PA league wide)
_LEAGUE_GAME_PROB     = 0.062  # P(HR in one game) for avg batter vs avg pitcher
_LEAGUE_HR9           = 1.20   # league avg HR allowed per 9 IP
_AVG_PA_PER_GAME      = 3.3    # average plate appearances per game

def calc_hr_probability(batter_stats: dict, batter_savant: dict,
                        pitcher_stats: dict, pitcher_savant: dict,
                        park: dict, weather: dict,
                        handedness_edge: float = 1.0) -> float:
    """
    Component-based HR probability model v2.

    Batter component: blends raw HR/PA (useful when sample is large) with a
    Statcast barrel-rate expected HR rate (stable predictor for small samples).
    Hard-hit% and EV50 apply soft adjustments.

    Pitcher component: blends raw HR/9 with barrel%-against-derived xHR/9,
    weighted by estimated batters faced (more IP = trust raw HR/9 more).

    Bayesian regression: final probability regresses toward league-average
    game probability (6.2%) based on batter's PA. Eliminates the old
    step-function 30/80 PA threshold.

    Calibration targets:
      - League avg batter vs league avg pitcher, neutral park: ~6-7%
      - Elite power bat (Schwarber tier) in hitter's park: ~18-22%
      - Slap hitter vs elite pitcher in pitcher's park: ~2-3%
    """
    s   = batter_stats.get("stats", {})
    pa  = max(s.get("pa", 0) or 1, 1)
    hr  = s.get("hr", 0) or 0
    raw_hr_rate = hr / pa

    # ── Batter: Statcast-calibrated expected HR rate ──────────────────────────
    barrel_pct   = batter_savant.get("barrel_pct",   _LEAGUE_BARREL_PCT) or _LEAGUE_BARREL_PCT
    hard_hit_pct = batter_savant.get("hard_hit_pct", 37.0) or 37.0
    ev50         = batter_savant.get("ev50", 88.0) or 88.0
    xslg         = batter_savant.get("xslg", 0.430) or 0.430

    # Barrel→xHR: barrel_pct is % of batted balls; convert to per-PA
    barrel_per_pa    = (barrel_pct / 100) * _LEAGUE_BIP_PER_PA
    xhr_from_barrel  = barrel_per_pa * _LEAGUE_HR_PER_BARREL  # ~0.023 at league avg

    # Hard-hit% soft adjustment (centered on league avg 37%)
    hard_adj = (hard_hit_pct / 37.0) ** 0.20  # low exponent — secondary signal

    # EV50 adjustment: each 4 mph above 88 ≈ +5% xHR rate
    ev_adj = 1.0 + max(-0.15, min(0.20, (ev50 - 88.0) / 4.0 * 0.05))

    # Blend raw HR/PA with barrel xHR based on sample size
    # At 350 PA: 55% raw, 45% barrel xHR. At 100 PA: 29% raw, 71% barrel xHR.
    raw_weight = min(pa / 350, 0.55)
    batter_xhr = (raw_weight * raw_hr_rate + (1 - raw_weight) * xhr_from_barrel)
    batter_xhr *= hard_adj * ev_adj

    # ── Pitcher: blended HR/9 using barrel% against for sample correction ─────
    p_stats = (pitcher_stats or {}).get("stats", {})
    p_hr9   = float(p_stats.get("hr9", "1.20") or "1.20")

    # Estimate batters faced from innings pitched for sample regression
    try:
        ip_raw = str(p_stats.get("inningsPitched", p_stats.get("ip", "0")) or "0")
        parts  = ip_raw.split(".")
        ip_dec = int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 3.0
    except Exception:
        ip_dec = 0.0
    est_bf = max(ip_dec * 4.3, 0)

    p_barrel_against = pitcher_savant.get("barrel_pct_against", _LEAGUE_BARREL_PCT) or _LEAGUE_BARREL_PCT
    # Barrel%-against → expected HR/9 (normalized: 8% barrel = league-avg 1.20 HR/9)
    p_xhr9_barrel = (p_barrel_against / _LEAGUE_BARREL_PCT) * _LEAGUE_HR9

    # Blend raw HR/9 with barrel-expected (trust raw more as sample grows)
    p_bf_weight = min(est_bf / 250, 0.60)
    p_xhr9      = p_bf_weight * p_hr9 + (1 - p_bf_weight) * p_xhr9_barrel
    pitcher_adj = max(0.40, min(2.00, p_xhr9 / _LEAGUE_HR9))

    # ── Context adjustments ───────────────────────────────────────────────────
    park_adj    = park.get("hr", 1.0)
    w_score     = weather.get("impact", {}).get("score", 0) if weather.get("available") else 0
    weather_adj = 1.0 + w_score * 0.025   # per unit of weather score; soft

    # ── Per-PA rate → per-game probability ───────────────────────────────────
    daily_rate = batter_xhr * pitcher_adj * park_adj * weather_adj * handedness_edge

    # Binomial: P(≥1 HR in 3.3 PA)
    prob_raw = 1.0 - (1.0 - daily_rate) ** _AVG_PA_PER_GAME

    # Bayesian regression toward league game probability
    # At 250 PA: full confidence. At 50 PA: 20% weight on own rate.
    confidence = min(pa / 250, 1.0)
    prob = confidence * prob_raw + (1 - confidence) * _LEAGUE_GAME_PROB

    return round(min(max(prob, 0.015), 0.25), 4)


def get_handedness_edge(batter_hand: str, pitcher_hand: str) -> float:
    """
    Platoon multiplier for HR probability.

    Empirical platoon splits on HRs (Statcast 2019-24 population):
      LHB vs RHP: +11% HR rate vs same-handed matchup
      RHB vs LHP: +9% HR rate vs same-handed matchup
      Same hand:  -7% (pitchers attack same-handed hitters more effectively)
      Switch hitter: +5% (always gets platoon side, but often less extreme power)
    """
    b = (batter_hand or "R").upper()
    p = (pitcher_hand or "R").upper()
    if b == "B":
        return 1.05       # switch hitter: modest platoon boost
    if b == "L" and p == "R":
        return 1.11       # LHB vs RHP: strongest platoon split in baseball
    if b == "R" and p == "L":
        return 1.09       # RHB vs LHP: strong platoon advantage
    return 0.93           # same-hand: pitchers have approach advantage


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


def build_pitcher_vulnerability_preview(game_analyses: list) -> dict:
    """
    Tiered pitcher vulnerability report across today's games.

    TIER_1  (bleeding):  ERA ≥ 5.0 or hittable from both sides
    TIER_2  (vulnerable): one-sided weak spot or moderate ERA
    VOLUME_ACE:           elite K-rate but some HR/contact vulnerability
    LEAVE_ALONE:          shutdown — avoid targeting
    """
    from baseball_engine import get_pitcher_savant

    tier1     = []
    tier2     = []
    vol_aces  = []
    leave     = []
    seen      = set()

    def _sp(val, default=0.0):
        try:
            return float(str(val).replace("-", "0") or default)
        except Exception:
            return default

    for analysis in game_analyses:
        if "error" in analysis:
            continue
        pitchers  = analysis.get("pitchers", {})
        matchups  = analysis.get("matchups", {})
        season    = analysis.get("season", datetime.now().year)
        away_team = analysis.get("away_team", {})
        home_team = analysis.get("home_team", {})
        game_info = analysis.get("game", {})
        game_time = game_info.get("game_time_local", game_info.get("datetime", ""))

        for side, opp_batters_key, this_team, opp_team in [
            ("home", "away_batters_vs_home_pitcher", home_team, away_team),
            ("away", "home_batters_vs_away_pitcher", away_team, home_team),
        ]:
            p_info   = pitchers.get(side, {})
            # p_info["stats"] is the pitcher profile object; actual season stats
            # are nested one level deeper at p_info["stats"]["stats"]
            p_profile = p_info.get("stats", {})
            p_stats   = p_profile.get("stats", {})
            p_splits  = p_info.get("splits", {})
            p_recent  = p_info.get("recent_starts", [])
            p_id      = p_info.get("info", {}).get("id")
            p_name    = p_profile.get("name", "Unknown")
            p_throws  = (p_profile.get("throws") or
                         p_info.get("info", {}).get("throws") or "R").upper()

            if not p_id or p_id in seen:
                continue
            seen.add(p_id)

            era   = _sp(p_stats.get("era",  "4.50"), 4.50)
            hr9   = _sp(p_stats.get("hr9",  "1.0"),  1.0)
            k9    = _sp(p_stats.get("k9",   "8.0"),  8.0)
            whip  = _sp(p_stats.get("whip", "1.30"), 1.30)
            ip_s  = _sp(p_stats.get("innings_pitched", "0.0"), 0.0)
            gs    = p_stats.get("games_started", 0) or 0
            avg_ip = round(ip_s / max(gs, 1), 2)

            p_savant  = get_pitcher_savant(p_id, season)
            barrel_ag = p_savant.get("barrel_pct_against", 0) or 0
            hard_ag   = p_savant.get("hard_hit_pct_against", 0) or 0
            vuln      = calc_pitcher_vulnerability(p_savant, {"stats": p_stats})

            # L3 ERA from recent starts
            l3 = p_recent[:3]
            l3_era = None
            if l3:
                l3_er = sum(s.get("earned_runs", 0) for s in l3)
                l3_ip = sum(_sp(s.get("innings_pitched", "0.0"), 0.0) for s in l3)
                l3_era = round((l3_er * 9) / l3_ip, 2) if l3_ip > 0 else None

            # LHB / RHB splits
            def _split(sp):
                if not sp:
                    return None
                ip_ = _sp(sp.get("ip", "0.0"), 0.0)
                if ip_ < 5:
                    return None
                hr_ = sp.get("hr", 0)
                pa_approx = ip_ * 4.3
                return {
                    "era":       round(_sp(sp.get("era", "0.00"), 0.0), 2),
                    "ops":       round(_sp(sp.get("ops", ".000"), 0.0), 3),
                    "avg":       sp.get("avg", "---"),
                    "hr_per_100": round((hr_ / max(pa_approx, 1)) * 100, 1),
                    "ip":        ip_,
                }

            vs_lhb = _split(p_splits.get("vs. Left"))
            vs_rhb = _split(p_splits.get("vs. Right"))

            lhb_ops = vs_lhb["ops"] if vs_lhb else era / 9.0
            rhb_ops = vs_rhb["ops"] if vs_rhb else era / 9.0
            lhb_era_ = vs_lhb["era"] if vs_lhb else era
            rhb_era_ = vs_rhb["era"] if vs_rhb else era

            if lhb_ops >= 0.790 and rhb_ops >= 0.790:
                weak_side = "BOTH"
            elif vs_lhb and vs_rhb and (lhb_ops > rhb_ops + 0.055 or lhb_era_ > rhb_era_ + 0.80):
                weak_side = "LHB"
            elif vs_lhb and vs_rhb and (rhb_ops > lhb_ops + 0.055 or rhb_era_ > lhb_era_ + 0.80):
                weak_side = "RHB"
            elif not vs_lhb and not vs_rhb:
                weak_side = "NEITHER"
            else:
                weak_side = "NEITHER"

            # Attack bats — opposing lineup matching pitcher's weak side
            attack_bats = []
            for item in matchups.get(opp_batters_key, [])[:9]:
                b = item.get("batter", {})
                b_hand  = b.get("bats", "R")
                matches = (
                    weak_side == "BOTH" or
                    (weak_side == "LHB" and b_hand in ("L", "S")) or
                    (weak_side == "RHB" and b_hand in ("R", "S"))
                )
                if matches:
                    attack_bats.append({
                        "name":  b.get("name", "?"),
                        "order": b.get("order", 0),
                        "hand":  b_hand,
                    })

            rec = {
                "pitcher":       p_name,
                "pitcher_id":    p_id,
                "throws":        p_throws,
                "team":          this_team.get("name", "?"),
                "opp_team":      opp_team.get("name", "?"),
                "game_time":     game_time,
                "era":           era,
                "hr9":           hr9,
                "k9":            round(k9, 1),
                "whip":          whip,
                "avg_ip":        avg_ip,
                "vuln_score":    vuln,
                "barrel_pct_ag": round(barrel_ag, 1),
                "hard_hit_ag":   round(hard_ag, 1),
                "l3_era":        l3_era,
                "vs_lhb":        vs_lhb,
                "vs_rhb":        vs_rhb,
                "weak_side":     weak_side,
                "attack_bats":   attack_bats,
            }

            if era >= 5.0 or (era >= 4.2 and vuln >= 0.62) or weak_side == "BOTH":
                rec["tier"] = "TIER_1"
                tier1.append(rec)
            elif era >= 4.0 or (era >= 3.7 and vuln >= 0.48) or (weak_side in ("LHB","RHB") and era >= 3.5):
                rec["tier"] = "TIER_2"
                tier2.append(rec)
            elif k9 >= 9.0 and era <= 3.8 and (hr9 >= 1.05 or barrel_ag >= 9.0):
                rec["tier"] = "VOLUME_ACE"
                vol_aces.append(rec)
            elif era <= 3.5 and vuln < 0.42:
                rec["tier"] = "LEAVE_ALONE"
                leave.append(rec)
            else:
                rec["tier"] = "NEUTRAL"

    for lst in (tier1, tier2):
        lst.sort(key=lambda x: x["era"], reverse=True)

    return {
        "tier1_bleeding":   tier1,
        "tier2_vulnerable": tier2,
        "volume_aces":      vol_aces,
        "leave_alone":      leave,
        "counts": {
            "tier1":        len(tier1),
            "tier2":        len(tier2),
            "volume_aces":  len(vol_aces),
            "leave_alone":  len(leave),
        },
    }
