"""
nrfi_engine.py — NRFI / YRFI prop board.

Scores each game 0-100 for first-inning run likelihood (higher = YRFI).

Signal stack (weights):
  Away pitcher 1st-inn ERA    25%  — 1st-inn runs allowed across last 5 starts
  Home pitcher 1st-inn ERA    25%  — same
  Away team 1st-inn offense   20%  — avg 1st-inn runs scored (last 21 days)
  Home team 1st-inn offense   20%  — same
  Walk flag (both pitchers)   10%  — high BB% pitchers walk guys early

Verdicts:
  Score ≥ 62  → YRFI  STRONG
  Score 52-62 → YRFI  LEAN
  Score 43-52 → NEUTRAL (no play)
  Score 38-43 → NRFI  LEAN
  Score ≤ 38  → NRFI  STRONG

Walk-board auto-flag:
  If either pitcher's BB% ≥ 11.0, the walk component pushes toward YRFI
  regardless of ERA-based signals.
"""

import math
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    _get, MLB_API, get_today_games, load_savant_pitcher_k,
    get_team_lineup, get_pitcher_rest,
)

LEAGUE_BB_PCT  = 8.5    # MLB avg pitcher BB%
LEAGUE_1ST_ERA = 4.50   # ~0.5 ER/start in 1st inning × 9
LEAGUE_1ST_RPG = 0.35   # teams average ~0.35 R in 1st inning per game
LEAGUE_OBP     = 0.320  # MLB avg leadoff OBP

_linescore_cache: dict = {}   # game_pk → (away_r_1st, home_r_1st)
_team_inn1_cache: dict = {}   # team_id → result dict


def _safe(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "-") else default
    except Exception:
        return default


def _scale(val, lo, mid, hi):
    """Linear scale: lo→0, mid→50, hi→100, clamped."""
    if val is None:
        return 50.0
    if val <= lo:
        return 0.0
    if val >= hi:
        return 100.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    return 50.0 + 50.0 * (val - mid) / (hi - mid)


# ── Leadoff batter OBP ───────────────────────────────────────────────────────

def _leadoff_obp(game_pk: int, team_side: str) -> float:
    """OBP of the leadoff batter from confirmed lineup. Falls back to league avg."""
    try:
        lineup = get_team_lineup(game_pk, team_side)
        if not lineup:
            return LEAGUE_OBP
        lead = next((p for p in lineup if p.get("order") == 1), lineup[0] if lineup else None)
        if not lead:
            return LEAGUE_OBP
        obp_str = lead.get("season_obp") or lead.get("obp") or ""
        obp = float(obp_str) if obp_str not in ("", ".000", "0") else 0.0
        return obp if 0.200 <= obp <= 0.500 else LEAGUE_OBP
    except Exception:
        return LEAGUE_OBP


# ── Pitcher rest adjustment ───────────────────────────────────────────────────

def _pitcher_rest_label(pitcher_id: int, game_date: str, season: int) -> str:
    """Return a short label when rest is unusual (short or extra)."""
    try:
        rest = get_pitcher_rest(pitcher_id, game_date, season)
        if rest.get("short_rest"):
            return f"SHORT REST ({rest['days_rest']}d)"
        if rest.get("extra_rest"):
            return f"EXTRA REST ({rest['days_rest']}d)"
        if rest.get("high_pitch_count"):
            return f"HIGH PC ({rest['last_pitch_count']}p)"
        return ""
    except Exception:
        return ""


# ── Linescore helpers ─────────────────────────────────────────────────────────

def _linescore_inn1(game_pk: int) -> tuple:
    """Return (away_runs_1st, home_runs_1st). Results cached by game_pk."""
    if game_pk in _linescore_cache:
        return _linescore_cache[game_pk]
    try:
        data    = _get(f"{MLB_API}/game/{game_pk}/linescore") or {}
        innings = data.get("innings", [])
        if innings:
            inn1   = innings[0]
            result = (
                int(inn1.get("away", {}).get("runs", 0) or 0),
                int(inn1.get("home", {}).get("runs", 0) or 0),
            )
        else:
            result = (0, 0)
    except Exception:
        result = (0, 0)
    _linescore_cache[game_pk] = result
    return result


# ── Pitcher first-inning stats ────────────────────────────────────────────────

def _pitcher_first_inn_stats(pitcher_id: int, season: int, n_starts: int = 5) -> dict:
    """
    Compute pitcher's 1st-inning ERA from their last n_starts.

    Method:
      - Fetch game log → find starts (IP ≥ 1.0) → take last n_starts
      - For each start, pull linescore → read 1st-inning runs for the
        opposing side (away_runs if pitcher was home, home_runs if away)
      - ERA = (total_1st_inn_ER / starts) × 9   (each start = 1 IP in 1st)

    Returns dict with era_1st, gave_up_run_rate, bb_per_start, gs, label.
    """
    default = {
        "era_1st": LEAGUE_1ST_ERA, "gave_up_run_rate": 0.35,
        "bb_per_start": None, "gs": 0, "runs_1st": [], "label": "",
    }
    try:
        url  = (f"{MLB_API}/people/{pitcher_id}/stats"
                f"?stats=gameLog&group=pitching&season={season}&gameType=R")
        data = _get(url) or {}
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [
            s for s in splits
            if _safe(s.get("stat", {}).get("inningsPitched")) >= 1.0
        ][-n_starts:]
        if not starts:
            return default

        runs_1st = []
        bb_list  = []
        for s in starts:
            gm      = s.get("game", {})
            pk      = gm.get("gamePk")
            is_home = s.get("isHome", False)
            stat    = s.get("stat", {})
            bb_list.append(int(_safe(stat.get("baseOnBalls", 0))))
            if not pk:
                continue
            away_r, home_r = _linescore_inn1(int(pk))
            # Pitcher on HOME team → faces away batters (top 1st) → away_r is against them
            # Pitcher on AWAY team → faces home batters (bottom 1st) → home_r is against them
            opp_r = away_r if is_home else home_r
            runs_1st.append(opp_r)
            time.sleep(0.07)

        gs = len(runs_1st)
        if gs == 0:
            return default

        total    = sum(runs_1st)
        era_1st  = (total / gs) * 9        # 1 IP per start → ER × 9 / 1
        run_rate = sum(1 for r in runs_1st if r > 0) / gs
        bb_avg   = sum(bb_list) / len(bb_list) if bb_list else None

        if era_1st >= 7.0:
            label = f"SLOW STARTER ({era_1st:.1f} 1st-ERA)"
        elif era_1st >= 4.5:
            label = f"shaky 1st ({era_1st:.1f} 1st-ERA)"
        elif era_1st <= 2.0:
            label = f"locks 1st ({era_1st:.1f} 1st-ERA)"
        else:
            label = ""

        return {
            "era_1st":          round(era_1st, 2),
            "gave_up_run_rate": round(run_rate, 2),
            "bb_per_start":     round(bb_avg, 2) if bb_avg is not None else None,
            "gs":               gs,
            "runs_1st":         runs_1st,
            "label":            label,
        }
    except Exception:
        return default


# ── Team first-inning offense rate ────────────────────────────────────────────

def _team_first_inn_rate(team_id: int, game_date: str,
                         lookback_days: int = 21) -> dict:
    """
    Average 1st-inning runs scored per game for team_id over last lookback_days.
    Cached by team_id (safe when all games share the same game_date).
    """
    if team_id in _team_inn1_cache:
        return _team_inn1_cache[team_id]

    default = {
        "r_per_game_1st": LEAGUE_1ST_RPG, "score_rate": 0.35,
        "gs": 0, "label": "",
    }
    try:
        end_dt   = datetime.strptime(game_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)
        start    = start_dt.strftime("%Y-%m-%d")
        end      = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")

        url  = (f"{MLB_API}/schedule?sportId=1&teamId={team_id}"
                f"&startDate={start}&endDate={end}"
                f"&hydrate=linescore&gameType=R")
        data = _get(url) or {}

        first_inn_runs = []
        for date_entry in data.get("dates", []):
            for gm in date_entry.get("games", []):
                if gm.get("status", {}).get("abstractGameState") != "Final":
                    continue
                teams   = gm.get("teams", {})
                home_id = teams.get("home", {}).get("team", {}).get("id")
                away_id = teams.get("away", {}).get("team", {}).get("id")
                is_home = (home_id == team_id)
                is_away = (away_id == team_id)
                if not (is_home or is_away):
                    continue

                innings = gm.get("linescore", {}).get("innings", [])
                if innings:
                    inn1 = innings[0]
                    side = "home" if is_home else "away"
                    runs = int(inn1.get(side, {}).get("runs", 0) or 0)
                else:
                    pk = gm.get("gamePk")
                    if not pk:
                        continue
                    away_r, home_r = _linescore_inn1(int(pk))
                    runs = home_r if is_home else away_r
                first_inn_runs.append(runs)

        if not first_inn_runs:
            _team_inn1_cache[team_id] = default
            return default

        n          = len(first_inn_runs)
        rpg        = sum(first_inn_runs) / n
        score_rate = sum(1 for r in first_inn_runs if r > 0) / n

        if rpg >= 0.60:
            label = f"HOT 1ST INN ({rpg:.2f}R/G · scores {score_rate:.0%})"
        elif rpg >= 0.40:
            label = f"AVG 1ST INN ({rpg:.2f}R/G)"
        else:
            label = f"COLD 1ST INN ({rpg:.2f}R/G)"

        result = {
            "r_per_game_1st": round(rpg, 3),
            "score_rate":     round(score_rate, 2),
            "gs":             n,
            "label":          label,
        }
        _team_inn1_cache[team_id] = result
        return result
    except Exception:
        _team_inn1_cache[team_id] = default
        return default


# ── Game NRFI score ───────────────────────────────────────────────────────────

def _game_nrfi_score(
    sp_away: dict, sp_home: dict,
    off_away: dict, off_home: dict,
    bb_pct_away: float, bb_pct_home: float,
    leadoff_obp_away: float = LEAGUE_OBP,
    leadoff_obp_home: float = LEAGUE_OBP,
) -> dict:
    """
    Score 0-100 for first-inning run likelihood (higher = YRFI).

    Component breakdown:
      era_away    (22%): away starter's 1st-inn ERA → away team scores in top-1st
      era_home    (22%): home starter's 1st-inn ERA → home team scores in bot-1st
      off_away    (17%): away offense in 1st (top-1st, bats against home SP)
      off_home    (17%): home offense in 1st (bot-1st, bats against away SP)
      leadoff_away (8%): away team leadoff batter OBP (top-1st)
      leadoff_home (8%): home team leadoff batter OBP (bot-1st)
      walk         (6%): avg walk signal for both starters
    """
    # Pitcher 1st-inn ERA: 0 ERA → 0pts, 4.50 → 50pts, 9.0+ → 100pts
    s_era_away = _scale(sp_away.get("era_1st", LEAGUE_1ST_ERA), 0.0, 4.50, 9.0)
    s_era_home = _scale(sp_home.get("era_1st", LEAGUE_1ST_ERA), 0.0, 4.50, 9.0)

    # Team 1st-inn offense: 0 R/G → 0pts, 0.35 → 50pts, 0.70+ → 100pts
    s_off_away = _scale(off_away.get("r_per_game_1st", LEAGUE_1ST_RPG), 0.0, 0.35, 0.70)
    s_off_home = _scale(off_home.get("r_per_game_1st", LEAGUE_1ST_RPG), 0.0, 0.35, 0.70)

    # Leadoff OBP: .260 → 0pts, .320 → 50pts, .400+ → 100pts
    # Higher OBP leadoff = more likely to reach base and set up 1st-inn run
    s_lead_away = _scale(leadoff_obp_away, 0.260, 0.320, 0.400)
    s_lead_home = _scale(leadoff_obp_home, 0.260, 0.320, 0.400)

    # Walk component: 0% → 0pts, 8.5% (avg) → 50pts, 14%+ → 100pts
    s_walk_away = _scale(bb_pct_away, 0.0, LEAGUE_BB_PCT, 14.0)
    s_walk_home = _scale(bb_pct_home, 0.0, LEAGUE_BB_PCT, 14.0)
    s_walk      = (s_walk_away + s_walk_home) / 2.0

    score = (
        s_era_away  * 0.20 +
        s_era_home  * 0.20 +
        s_off_away  * 0.18 +
        s_off_home  * 0.18 +
        s_lead_away * 0.10 +
        s_lead_home * 0.10 +
        s_walk      * 0.04
    )
    score = round(score, 1)

    if score >= 62:
        verdict, confidence = "YRFI", "STRONG"
    elif score >= 52:
        verdict, confidence = "YRFI", "LEAN"
    elif score <= 38:
        verdict, confidence = "NRFI", "STRONG"
    elif score <= 47:
        verdict, confidence = "NRFI", "LEAN"
    else:
        verdict, confidence = "NEUTRAL", "—"

    # Walk-board auto-flag: if either starter is walk-heavy, note it
    walk_flag = (bb_pct_away >= 11.0 or bb_pct_home >= 11.0)

    # Downgrade NRFI LEAN to NEUTRAL when walk flag is set
    if verdict == "NRFI" and confidence == "LEAN" and walk_flag:
        verdict, confidence = "NEUTRAL", "—"

    return {
        "score":      score,
        "verdict":    verdict,
        "confidence": confidence,
        "walk_flag":  walk_flag,
        "leadoff_obp_away": round(leadoff_obp_away, 3),
        "leadoff_obp_home": round(leadoff_obp_home, 3),
        "components": {
            "era_away":     round(s_era_away, 1),
            "era_home":     round(s_era_home, 1),
            "off_away":     round(s_off_away, 1),
            "off_home":     round(s_off_home, 1),
            "leadoff_away": round(s_lead_away, 1),
            "leadoff_home": round(s_lead_home, 1),
            "walk":         round(s_walk, 1),
        },
    }


# ── Main board builder ────────────────────────────────────────────────────────

def build_nrfi_board(game_date: str) -> list:
    """
    Build NRFI/YRFI board for all games on game_date.
    Returns list sorted by signal strength: strongest YRFI/NRFI first,
    neutral games last.
    """
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    savant_k = load_savant_pitcher_k(season)  # for BB%

    results = []
    for g in games:
        away_pitcher = g["away"]["probable_pitcher"]
        home_pitcher = g["home"]["probable_pitcher"]
        away_pid     = away_pitcher.get("id")
        home_pid     = home_pitcher.get("id")

        sp_away = (
            _pitcher_first_inn_stats(away_pid, season) if away_pid
            else {"era_1st": LEAGUE_1ST_ERA, "gave_up_run_rate": 0.35,
                  "bb_per_start": None, "gs": 0, "runs_1st": [], "label": ""}
        )
        sp_home = (
            _pitcher_first_inn_stats(home_pid, season) if home_pid
            else {"era_1st": LEAGUE_1ST_ERA, "gave_up_run_rate": 0.35,
                  "bb_per_start": None, "gs": 0, "runs_1st": [], "label": ""}
        )

        off_away = _team_first_inn_rate(g["away"]["team_id"], game_date)
        off_home = _team_first_inn_rate(g["home"]["team_id"], game_date)

        bb_away = _safe(savant_k.get(str(away_pid), {}).get("bb_pct")) if away_pid else LEAGUE_BB_PCT
        bb_home = _safe(savant_k.get(str(home_pid), {}).get("bb_pct")) if home_pid else LEAGUE_BB_PCT

        # Leadoff batter OBP — graceful fallback to league avg when lineup not posted
        game_pk = g["game_pk"]
        lo_obp_away = _leadoff_obp(game_pk, "away")
        lo_obp_home = _leadoff_obp(game_pk, "home")

        # Pitcher rest labels (flagged in output but don't affect score directly)
        rest_label_away = _pitcher_rest_label(away_pid, game_date, season) if away_pid else ""
        rest_label_home = _pitcher_rest_label(home_pid, game_date, season) if home_pid else ""

        nrfi = _game_nrfi_score(
            sp_away, sp_home, off_away, off_home, bb_away, bb_home,
            lo_obp_away, lo_obp_home,
        )

        results.append({
            "game":            f"{g['away']['team_abbr']}@{g['home']['team_abbr']}",
            "game_pk":         game_pk,
            "venue":           g.get("venue_name", ""),
            "game_time":       g.get("game_time", ""),
            "away_team":       g["away"]["team_abbr"],
            "home_team":       g["home"]["team_abbr"],
            "away_pitcher":    away_pitcher.get("name", "TBD"),
            "home_pitcher":    home_pitcher.get("name", "TBD"),
            "away_pitcher_id": away_pid,
            "home_pitcher_id": home_pid,
            "sp_away":         sp_away,
            "sp_home":         sp_home,
            "off_away":        off_away,
            "off_home":        off_home,
            "bb_pct_away":     round(bb_away, 1),
            "bb_pct_home":     round(bb_home, 1),
            "leadoff_obp_away": lo_obp_away,
            "leadoff_obp_home": lo_obp_home,
            "rest_label_away": rest_label_away,
            "rest_label_home": rest_label_home,
            "nrfi":            nrfi,
        })

    # Strongest signal (furthest from 50) first
    results.sort(key=lambda r: -abs(r["nrfi"]["score"] - 50.0))
    return results


# ── Display ───────────────────────────────────────────────────────────────────

def format_nrfi_board(results: list, game_date: str) -> str:
    lines = []
    W = 100
    lines.append("=" * W)
    lines.append(f"  NRFI / YRFI BOARD — {game_date}")
    lines.append("  Score 0-100 (higher = YRFI). Signals: 1st-inn ERA (50%) + Team 1st-inn R/G (40%) + Walk% (10%)")
    lines.append("=" * W)
    lines.append(
        f"  {'GAME':<14} {'VERDICT':<14} {'SCR':>5}  "
        f"{'AWAY SP':<22} {'ERA1':>5}  "
        f"{'HOME SP':<22} {'ERA1':>5}  "
        f"{'ATM OFF':>7} {'HTM OFF':>7}  "
        f"{'BB-A':>5} {'BB-H':>5}"
    )
    lines.append("  " + "-" * (W - 2))

    for r in results:
        nrfi = r["nrfi"]
        v    = nrfi["verdict"]
        conf = nrfi["confidence"]
        scr  = nrfi["score"]
        sym  = ("★" if conf == "STRONG" and v == "YRFI" else
                "◎" if conf == "LEAN"   and v == "YRFI" else
                "●" if conf == "STRONG" and v == "NRFI" else
                "○" if conf == "LEAN"   and v == "NRFI" else "—")
        verdict_str = f"{sym} {conf} {v}"
        wf   = " ⚡BB" if nrfi.get("walk_flag") else ""

        era_a = r["sp_away"].get("era_1st", 0)
        era_h = r["sp_home"].get("era_1st", 0)
        off_a = r["off_away"].get("r_per_game_1st", 0)
        off_h = r["off_home"].get("r_per_game_1st", 0)

        lines.append(
            f"  {r['game']:<14} {verdict_str:<14} {scr:>5.1f}  "
            f"{r['away_pitcher']:<22} {era_a:>5.2f}  "
            f"{r['home_pitcher']:<22} {era_h:>5.2f}  "
            f"{off_a:>7.3f} {off_h:>7.3f}  "
            f"{r['bb_pct_away']:>5.1f} {r['bb_pct_home']:>5.1f}"
            f"{wf}"
        )

    lines.append("")
    lines.append("  Detail:")
    for r in results:
        nrfi = r["nrfi"]
        if nrfi["verdict"] == "NEUTRAL":
            continue
        v    = nrfi["verdict"]
        conf = nrfi["confidence"]
        c    = nrfi["components"]
        lines.append(
            f"  {r['game']:<14} {conf} {v}  score={nrfi['score']:.1f}  "
            f"era_away={c['era_away']:.0f} era_home={c['era_home']:.0f} "
            f"off_away={c['off_away']:.0f} off_home={c['off_home']:.0f} "
            f"walk={c['walk']:.0f}"
        )
        sp_a_lbl = r["sp_away"].get("label", "")
        sp_h_lbl = r["sp_home"].get("label", "")
        off_a_lbl = r["off_away"].get("label", "")
        off_h_lbl = r["off_home"].get("label", "")
        rest_a = r.get("rest_label_away", "")
        rest_h = r.get("rest_label_home", "")
        lo_a = r.get("leadoff_obp_away", 0)
        lo_h = r.get("leadoff_obp_home", 0)
        lo_str = ""
        if lo_a != LEAGUE_OBP or lo_h != LEAGUE_OBP:
            lo_str = f"Leadoff OBP: {r['away_team']} {lo_a:.3f} | {r['home_team']} {lo_h:.3f}"
        detail_parts = [x for x in [sp_a_lbl, sp_h_lbl, off_a_lbl, off_h_lbl, rest_a, rest_h, lo_str] if x]
        if detail_parts:
            lines.append(f"    → {' | '.join(detail_parts)}")

    lines.append("=" * W)
    return "\n".join(lines)
