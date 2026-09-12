"""
f5_engine.py — First 5 Innings (F5) prop model.

Models F5 Total (runs scored in first 5 innings) and F5 pitcher lines.

SP Run-Allowed Model (0-100, high = more runs allowed):
  SP ERA (30%) + Recent RA/5-inning (35%) + Opp offense quality (20%) + Park (15%)

Team Offense F5 Score:
  Team R/G (35%) + OBP (30%) + SP quality (25%) + Leadoff OBP (10%)

F5 Total:
  λ = expected_ra5_away + expected_ra5_home
  Poisson P(over) for 3.5 / 4.5 / 5.5 / 6.5 total lines

No bullpen variance — F5 is purely a starter market.
"""

import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    _get, MLB_API,
    get_today_games,
    get_pitcher_rest,
    PARK_FACTORS,
)

LEAGUE_ERA     = 4.15   # MLB avg ERA 2026
LEAGUE_RA5     = 2.30   # League avg RA in first 5 innings (ERA × 5/9)
LEAGUE_RG      = 4.60   # MLB avg runs/game
LEAGUE_OBP     = 0.320  # MLB avg OBP
LEAGUE_IP_SP   = 5.4    # Avg innings per SP start
LEAGUE_K_PCT   = 22.5   # MLB avg K%


def _safe(v, default=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _scale(val, lo, mid, hi):
    """Linear scale: lo→0, mid→50, hi→100 (clamped)."""
    if val <= lo:
        return 0.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    if val <= hi:
        return 50.0 + 50.0 * (val - mid) / (hi - mid)
    return 100.0


def _poisson_at_least(lam, k):
    """P(X >= k) for Poisson(lam)."""
    if lam <= 0:
        return 0.0
    prob_less = 0.0
    for i in range(k):
        prob_less += math.exp(-lam) * (lam ** i) / math.factorial(i)
    return max(0.0, 1.0 - prob_less)


def _poisson_exact(lam, k):
    """P(X == k) for Poisson(lam)."""
    if lam <= 0:
        return 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


# ---------------------------------------------------------------------------
# SP Recent F5 form
# ---------------------------------------------------------------------------
_sp_f5_cache: dict = {}


def _sp_f5_form(pitcher_id: int, season: int) -> dict:
    """
    Fetch pitcher's last 5 starts, compute:
      - avg_ip: average innings pitched
      - avg_ra: average runs allowed (earned)
      - stamina_ok: True if avg_ip >= 4.5
      - f5_ra: estimated runs allowed in exactly 5 innings
      - k_pct: recent K%
      - label: "F5 ACE" / "F5 SOLID" / "F5 SHAKY" / "F5 INJURY RISK" / ""
    """
    cache_key = (pitcher_id, season)
    if cache_key in _sp_f5_cache:
        return _sp_f5_cache[cache_key]

    result = {
        "avg_ip": LEAGUE_IP_SP,
        "avg_ra": LEAGUE_RA5,
        "f5_ra": LEAGUE_RA5,
        "stamina_ok": True,
        "k_pct": LEAGUE_K_PCT,
        "era": LEAGUE_ERA,
        "label": "",
        "n_starts": 0,
    }

    try:
        url = (
            f"{MLB_API}/people/{pitcher_id}/stats"
            f"?stats=gameLog&group=pitching&season={season}&gameType=R"
        )
        data = _get(url)
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [
            s for s in splits
            if _safe(s.get("stat", {}).get("inningsPitched", 0)) >= 1.0
        ][-5:]

        if not starts:
            _sp_f5_cache[cache_key] = result
            return result

        n = len(starts)
        total_ip, total_er, total_r, total_k, total_bf = 0.0, 0.0, 0.0, 0.0, 0.0

        for s in starts:
            st  = s.get("stat", {})
            ip  = _safe(st.get("inningsPitched"))
            er  = _safe(st.get("earnedRuns"))
            r   = _safe(st.get("runs") or st.get("earnedRuns"))
            k   = _safe(st.get("strikeOuts"))
            bf  = _safe(st.get("battersFaced")) or (ip * 3.5)
            total_ip += ip
            total_er += er
            total_r  += r
            total_k  += k
            total_bf += bf

        avg_ip = total_ip / n
        avg_ra = total_r / n        # runs allowed per start
        era_l5 = (total_er / total_ip * 9) if total_ip > 0 else LEAGUE_ERA
        k_pct  = (total_k / total_bf * 100) if total_bf > 0 else LEAGUE_K_PCT

        # Extrapolate RA to exactly 5 innings
        # If avg_ip >= 5.0, use per-inning rate × 5
        # If avg_ip < 5.0, pitcher likely exits before 5 — prorate but flag
        ra_per_inning = avg_ra / avg_ip if avg_ip > 0 else LEAGUE_RA5 / 5.0
        f5_ra = ra_per_inning * 5.0

        # Stamina flag
        stamina_ok = avg_ip >= 4.5

        # Label
        if era_l5 <= 2.80 and stamina_ok:
            label = "F5 ACE"
        elif era_l5 <= 3.80 and stamina_ok:
            label = "F5 SOLID"
        elif era_l5 >= 5.50:
            label = "F5 SHAKY"
        elif not stamina_ok:
            label = "F5 SHORT"
        else:
            label = ""

        result.update({
            "avg_ip":     round(avg_ip, 2),
            "avg_ra":     round(avg_ra, 2),
            "f5_ra":      round(f5_ra, 2),
            "stamina_ok": stamina_ok,
            "k_pct":      round(k_pct, 1),
            "era":        round(era_l5, 2),
            "label":      label,
            "n_starts":   n,
        })

    except Exception:
        pass

    _sp_f5_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Team F5 offense
# ---------------------------------------------------------------------------

def _team_f5_offense(team_id: int, season: int) -> dict:
    """
    Fetch team season stats for offensive F5 estimation.
    Returns {r_pg, obp, r_f5_est, label}
    """
    try:
        url = (
            f"{MLB_API}/teams/{team_id}/stats"
            f"?stats=season&group=hitting&season={season}&gameType=R"
        )
        data = _get(url)
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        if not splits:
            return {"r_pg": LEAGUE_RG, "obp": LEAGUE_OBP, "r_f5_est": LEAGUE_RG * 5 / 9, "label": ""}

        st  = splits[0].get("stat", {})
        g   = _safe(st.get("gamesPlayed")) or 1
        r   = _safe(st.get("runs"))
        obp = _safe(st.get("obp"))

        r_pg    = r / g if g > 0 else LEAGUE_RG
        r_f5_est = r_pg * (5.0 / 9.0)  # rough pro-ration: ~5/9 of runs in first 5
        # Top offenses can score more early — slight upbias for high-obp teams
        if obp > 0.340:
            r_f5_est *= 1.05
        elif obp < 0.300:
            r_f5_est *= 0.95

        if r_pg >= 5.20:
            label = "HOT OFFENSE"
        elif r_pg >= 4.80:
            label = ""
        elif r_pg <= 3.60:
            label = "COLD OFFENSE"
        else:
            label = ""

        return {
            "r_pg":     round(r_pg, 2),
            "obp":      round(obp, 3),
            "r_f5_est": round(r_f5_est, 2),
            "label":    label,
        }
    except Exception:
        return {"r_pg": LEAGUE_RG, "obp": LEAGUE_OBP, "r_f5_est": round(LEAGUE_RG * 5 / 9, 2), "label": ""}


# ---------------------------------------------------------------------------
# F5 game score
# ---------------------------------------------------------------------------

def _f5_game_score(
    sp_form: dict,
    opp_offense: dict,
    park_run_factor: float = 1.0,
    rest_adj: float = 1.0,
) -> dict:
    """
    Compute expected runs allowed by this SP in first 5 innings vs given offense.

    Base RA5 = sp_form["f5_ra"] adjusted for opponent quality and park.
    Opp offense quality: scale r_pg vs LEAGUE_RG → ±15% modifier.
    """
    base_ra5  = sp_form.get("f5_ra", LEAGUE_RA5)
    opp_r_pg  = opp_offense.get("r_pg", LEAGUE_RG)
    opp_obp   = opp_offense.get("obp", LEAGUE_OBP)

    # Offense adjustment: league avg offense → 1.0; ±20% range
    off_ratio = opp_r_pg / LEAGUE_RG
    obp_ratio = opp_obp / LEAGUE_OBP
    opp_adj   = (off_ratio * 0.65 + obp_ratio * 0.35)
    opp_adj   = max(0.75, min(1.30, opp_adj))

    # Stamina: if SP is a short-outing type, bump RA5 slightly (reliever enters earlier)
    stamina_adj = 1.08 if not sp_form.get("stamina_ok", True) else 1.0

    # Rest adjustment (1.0 normal, <1.0 for short rest pitcher)
    expected_ra5 = base_ra5 * opp_adj * park_run_factor * stamina_adj * rest_adj
    expected_ra5 = max(0.20, round(expected_ra5, 3))

    return {
        "expected_ra5": expected_ra5,
        "opp_adj":      round(opp_adj, 3),
        "stamina_adj":  stamina_adj,
    }


# ---------------------------------------------------------------------------
# Build F5 board
# ---------------------------------------------------------------------------

def build_f5_board(game_date: str = None) -> list:
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")

    season = int(game_date[:4])
    games  = get_today_games(game_date)
    if not games:
        return []

    rows = []

    for game in games:
        game_pk      = game.get("game_pk")
        venue_name   = game.get("venue_name", "")
        away_team_id = game["away"]["team_id"]
        home_team_id = game["home"]["team_id"]
        away_abbr    = game["away"]["team_abbr"]
        home_abbr    = game["home"]["team_abbr"]
        sp_away_id   = game["away"]["probable_pitcher"]["id"]
        sp_home_id   = game["home"]["probable_pitcher"]["id"]
        sp_away_name = game["away"]["probable_pitcher"]["name"]
        sp_home_name = game["home"]["probable_pitcher"]["name"]

        if not sp_away_id or not sp_home_id:
            continue

        # Park run factor
        park_data  = PARK_FACTORS.get(venue_name, {})
        park_run   = park_data.get("run", 1.0)

        # SP form
        form_away  = _sp_f5_form(sp_away_id, season)
        form_home  = _sp_f5_form(sp_home_id, season)

        # Rest adjustments
        rest_away = get_pitcher_rest(sp_away_id, game_date, season)
        rest_home = get_pitcher_rest(sp_home_id, game_date, season)

        def rest_mult(ri):
            if ri.get("short_rest"):
                return 1.12   # more runs allowed on short rest
            if ri.get("high_pitch_count"):
                return 1.06
            if ri.get("extra_rest"):
                return 0.97
            return 1.0

        ra_adj_away = rest_mult(rest_away)
        ra_adj_home = rest_mult(rest_home)

        # Team offenses
        off_away = _team_f5_offense(away_team_id, season) if away_team_id else {}
        off_home = _team_f5_offense(home_team_id, season) if home_team_id else {}

        # Expected RA5 per pitcher
        away_ra5_score = _f5_game_score(form_away, off_home, park_run, ra_adj_away)
        home_ra5_score = _f5_game_score(form_home, off_away, park_run, ra_adj_home)

        away_ra5 = away_ra5_score["expected_ra5"]  # runs away SP allows
        home_ra5 = home_ra5_score["expected_ra5"]  # runs home SP allows

        # F5 total λ = away_ra5 (scored by home) + home_ra5 (scored by away)
        lam_total = away_ra5 + home_ra5

        # Poisson probabilities for F5 total lines
        p_o3  = round(_poisson_at_least(lam_total, 4) * 100, 1)   # O3.5 — at least 4 runs
        p_o4  = round(_poisson_at_least(lam_total, 5) * 100, 1)   # O4.5
        p_o5  = round(_poisson_at_least(lam_total, 6) * 100, 1)   # O5.5
        p_o6  = round(_poisson_at_least(lam_total, 7) * 100, 1)   # O6.5

        # F5 total confidence label
        if p_o4 >= 65:
            total_conf = "STRONG O4.5"
        elif p_o4 >= 55:
            total_conf = "LEAN O4.5"
        elif p_o5 >= 52:
            total_conf = "LEAN O5.5"
        elif p_o3 <= 35:
            total_conf = "LEAN U3.5"
        elif p_o4 <= 30:
            total_conf = "LEAN U4.5"
        else:
            total_conf = "NEUTRAL"

        # F5 pitcher comparison — who is favored?
        # Lower ERA5 / higher K% → F5 advantage
        sp_edge = "EVEN"
        edge_margin = abs(form_away["era"] - form_home["era"])
        if edge_margin >= 1.0:
            sp_edge = f"{sp_away_name.split()[-1]} F5 EDGE" if form_away["era"] < form_home["era"] \
                else f"{sp_home_name.split()[-1]} F5 EDGE"

        # Rest labels for output
        rest_lbl_away = (
            "SHORT REST" if rest_away.get("short_rest") else
            "HIGH PC"    if rest_away.get("high_pitch_count") else
            "EXTRA REST" if rest_away.get("extra_rest") else ""
        )
        rest_lbl_home = (
            "SHORT REST" if rest_home.get("short_rest") else
            "HIGH PC"    if rest_home.get("high_pitch_count") else
            "EXTRA REST" if rest_home.get("extra_rest") else ""
        )

        rows.append({
            "game_pk":      game_pk,
            "game_date":    game_date,
            "venue":        venue_name,
            "away_abbr":    away_abbr,
            "home_abbr":    home_abbr,
            "away_team_id": away_team_id,
            "home_team_id": home_team_id,

            "sp_away_id":   sp_away_id,
            "sp_home_id":   sp_home_id,
            "sp_away_name": sp_away_name,
            "sp_home_name": sp_home_name,

            # Away SP stats
            "away_era_l5":  form_away["era"],
            "away_avg_ip":  form_away["avg_ip"],
            "away_k_pct":   form_away["k_pct"],
            "away_f5_ra":   away_ra5,
            "away_label":   form_away["label"],
            "away_rest":    rest_lbl_away,

            # Home SP stats
            "home_era_l5":  form_home["era"],
            "home_avg_ip":  form_home["avg_ip"],
            "home_k_pct":   form_home["k_pct"],
            "home_f5_ra":   home_ra5,
            "home_label":   form_home["label"],
            "home_rest":    rest_lbl_home,

            # Team offenses
            "away_r_pg":    off_away.get("r_pg", LEAGUE_RG),
            "home_r_pg":    off_home.get("r_pg", LEAGUE_RG),
            "off_away_lbl": off_away.get("label", ""),
            "off_home_lbl": off_home.get("label", ""),

            # Park
            "park_run":     park_run,

            # F5 total
            "lam_total":    round(lam_total, 3),
            "p_o3":         p_o3,
            "p_o4":         p_o4,
            "p_o5":         p_o5,
            "p_o6":         p_o6,
            "total_conf":   total_conf,
            "sp_edge":      sp_edge,
        })

    rows.sort(key=lambda r: r["lam_total"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Format F5 board
# ---------------------------------------------------------------------------

def format_f5_board(rows: list) -> str:
    if not rows:
        return "No F5 board data available.\n"

    date_str = rows[0].get("game_date", "Today") if rows else "Today"
    lines = [f"FIRST 5 INNINGS (F5) BOARD — {date_str}", "=" * 72, ""]

    for r in rows:
        venue      = r["venue"]
        away_abbr  = r["away_abbr"]
        home_abbr  = r["home_abbr"]
        sp_away    = r["sp_away_name"]
        sp_home    = r["sp_home_name"]
        park_run   = r["park_run"]

        park_tag   = ""
        if park_run >= 1.15:
            park_tag = f" [HITTER'S PARK ×{park_run:.2f}]"
        elif park_run <= 0.92:
            park_tag = f" [PITCHER'S PARK ×{park_run:.2f}]"

        lines.append(f"{away_abbr} @ {home_abbr}  |  {venue}{park_tag}")
        lines.append("-" * 60)

        # Away SP
        away_lbl  = r["away_label"]
        away_rest = r["away_rest"]
        away_tags = "  ".join(t for t in [away_lbl, away_rest] if t)
        lines.append(
            f"  {sp_away:<24}  ERA(L5):{r['away_era_l5']:.2f}"
            f"  IP/GS:{r['away_avg_ip']:.1f}"
            f"  K%:{r['away_k_pct']:.1f}"
            f"  F5-RA:{r['away_f5_ra']:.2f}"
            + (f"  [{away_tags}]" if away_tags else "")
        )

        # Home SP
        home_lbl  = r["home_label"]
        home_rest = r["home_rest"]
        home_tags = "  ".join(t for t in [home_lbl, home_rest] if t)
        lines.append(
            f"  {sp_home:<24}  ERA(L5):{r['home_era_l5']:.2f}"
            f"  IP/GS:{r['home_avg_ip']:.1f}"
            f"  K%:{r['home_k_pct']:.1f}"
            f"  F5-RA:{r['home_f5_ra']:.2f}"
            + (f"  [{home_tags}]" if home_tags else "")
        )

        # Team offenses
        off_away_lbl = r.get("off_away_lbl", "")
        off_home_lbl = r.get("off_home_lbl", "")
        off_str = (
            f"  {away_abbr} Off:{r['away_r_pg']:.2f} R/G"
            + (f" [{off_away_lbl}]" if off_away_lbl else "")
            + f"   {home_abbr} Off:{r['home_r_pg']:.2f} R/G"
            + (f" [{off_home_lbl}]" if off_home_lbl else "")
        )
        lines.append(off_str)

        # F5 total
        lam   = r["lam_total"]
        conf  = r["total_conf"]
        edge  = r["sp_edge"]
        lines.append(
            f"  F5 Total λ:{lam:.2f}  "
            f"O3.5:{r['p_o3']:4.1f}%  O4.5:{r['p_o4']:4.1f}%  "
            f"O5.5:{r['p_o5']:4.1f}%  O6.5:{r['p_o6']:4.1f}%"
        )
        lines.append(f"  [{conf}]  |  {edge}")
        lines.append("")

    # Summary: best F5 Over plays
    lines.append("=" * 72)
    lines.append("TOP F5 OVER PLAYS  (by O4.5 probability)")
    lines.append("-" * 50)
    sorted_rows = sorted(rows, key=lambda x: x["p_o4"], reverse=True)
    for r in sorted_rows[:8]:
        lines.append(
            f"  {r['away_abbr']} @ {r['home_abbr']:<5}  {r['sp_away_name'].split()[-1]} vs "
            f"{r['sp_home_name'].split()[-1]}  "
            f"λ:{r['lam_total']:.2f}  O4.5:{r['p_o4']:.1f}%  [{r['total_conf']}]"
        )

    lines.append("")
    lines.append("TOP F5 UNDER PLAYS  (by U4.5 probability)")
    lines.append("-" * 50)
    sorted_under = sorted(rows, key=lambda x: x["p_o4"])
    for r in sorted_under[:8]:
        u_prob = round(100 - r["p_o4"], 1)
        lines.append(
            f"  {r['away_abbr']} @ {r['home_abbr']:<5}  {r['sp_away_name'].split()[-1]} vs "
            f"{r['sp_home_name'].split()[-1]}  "
            f"λ:{r['lam_total']:.2f}  U4.5:{u_prob:.1f}%  [ERA:{r['away_era_l5']:.2f}/{r['home_era_l5']:.2f}]"
        )
    lines.append("")

    return "\n".join(lines)
