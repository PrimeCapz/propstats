"""
batter_k_engine.py — Individual batter strikeout prop board.

Batter K Score (0-100, high = high strikeout risk):
  K% (35%) + Chase/O-Swing% (28%) + SwStr% (22%) + Contact% inverse (15%)

Pitcher component adjusts the K rate upward for elite strikeout pitchers.

Lines: O0.5 (batter strikes out at least once), O1.5 (at least twice)

Tiers:
  K MACHINE ≥72 | K RISK 55-72 | CONTACT ≤38
"""

import math
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    _get, MLB_API,
    get_today_games,
    get_team_roster_ids,
    get_pitcher_throws,
    load_savant_xstats,
    load_savant_batting,
    load_savant_pitcher_k,
    load_savant_pitcher_velo,
    PARK_FACTORS,
)

LEAGUE_K_PCT    = 22.5   # MLB avg K%
LEAGUE_CHASE    = 30.0   # MLB avg O-Swing%
LEAGUE_SWSTR    = 11.0   # MLB avg SwStr%
LEAGUE_CONTACT  = 77.5   # MLB avg Contact%
LEAGUE_AB_SP    = 22.0   # avg AB vs SP per game
LEAGUE_PA_SP    = 25.0   # avg PA vs SP


def _safe(v, default=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def _scale(val, lo, mid, hi):
    """lo→0, mid→50, hi→100 (clamped)."""
    if val <= lo:
        return 0.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    if val <= hi:
        return 50.0 + 50.0 * (val - mid) / (hi - mid)
    return 100.0


def _poisson_at_least(lam, k):
    if lam <= 0:
        return 0.0
    prob_less = sum(
        math.exp(-lam) * (lam ** i) / math.factorial(i)
        for i in range(k)
    )
    return max(0.0, 1.0 - prob_less)


# ---------------------------------------------------------------------------
# Pitcher K profile for batter matchup
# ---------------------------------------------------------------------------
_pitcher_k_profile_cache: dict = {}


def _pitcher_k_profile(pitcher_id: int, season: int, pitcher_k_data: dict, pitcher_velo_data: dict) -> dict:
    """
    Return pitcher-side K metrics: k_pct, swstr_pct, chase_pct
    Used to adjust batter K rate up/down.
    """
    cache_key = (pitcher_id, season)
    if cache_key in _pitcher_k_profile_cache:
        return _pitcher_k_profile_cache[cache_key]

    pk  = pitcher_k_data.get(str(pitcher_id), {})
    pv  = pitcher_velo_data.get(str(pitcher_id), {})

    p_k_pct    = _safe(pk.get("k_percent") or pk.get("k_pct"))
    p_swstr    = _safe(pk.get("whiff_percent") or pk.get("swstr_pct"))
    p_chase    = _safe(pv.get("chase_percent") or pv.get("chase_pct"))
    p_putaway  = _safe(pk.get("putaway_percent") or pk.get("putaway_pct"))

    # Pitcher K multiplier vs league avg: ≥30% K → 1.20, ≤15% K → 0.82
    k_mult = 1.0
    if p_k_pct >= 30:
        k_mult = 1.20
    elif p_k_pct >= 26:
        k_mult = 1.12
    elif p_k_pct >= 22:
        k_mult = 1.05
    elif p_k_pct >= 18:
        k_mult = 0.95
    elif p_k_pct >= 14:
        k_mult = 0.88
    elif p_k_pct > 0:
        k_mult = 0.82

    label = ""
    if p_k_pct >= 28:
        label = "ELITE K%"
    elif p_k_pct >= 23:
        label = "HIGH K%"
    elif p_k_pct <= 16 and p_k_pct > 0:
        label = "LOW K%"
    elif p_k_pct <= 13 and p_k_pct > 0:
        label = "CONTACT PITCHER"

    result = {
        "p_k_pct":   round(p_k_pct, 1),
        "p_swstr":   round(p_swstr, 1),
        "p_chase":   round(p_chase, 1),
        "p_putaway": round(p_putaway, 1),
        "k_mult":    round(k_mult, 3),
        "label":     label,
    }
    _pitcher_k_profile_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Batter K score
# ---------------------------------------------------------------------------

def _batter_k_score(batter_id: int, savant_batting: dict, xstats: dict) -> dict:
    """
    Score a batter 0-100 for K risk.
    K% (35%) + Chase/O-Swing% (28%) + SwStr% (22%) + Contact% inverse (15%)
    """
    sb = savant_batting.get(str(batter_id), {})
    xs = xstats.get(str(batter_id), {})

    k_pct   = _safe(sb.get("k_percent") or sb.get("strikeout_percent"))
    chase   = _safe(sb.get("oz_swing_percent") or sb.get("chase_percent"))
    swstr   = _safe(sb.get("whiff_percent") or sb.get("swinging_strike_percent"))
    contact = _safe(sb.get("z_contact_percent") or sb.get("contact_percent"))

    # s_contact: LOW contact = HIGH K risk → invert
    s_k       = _scale(k_pct,    12.0, LEAGUE_K_PCT,   36.0)
    s_chase   = _scale(chase,    18.0, LEAGUE_CHASE,   42.0)
    s_swstr   = _scale(swstr,     5.0, LEAGUE_SWSTR,   20.0)
    s_contact_inv = 100.0 - _scale(contact, 60.0, LEAGUE_CONTACT, 92.0)

    if k_pct > 0 and chase > 0 and swstr > 0:
        score = s_k * 0.35 + s_chase * 0.28 + s_swstr * 0.22 + s_contact_inv * 0.15
    elif k_pct > 0 and chase > 0:
        score = s_k * 0.44 + s_chase * 0.36 + s_swstr * 0.20
    elif k_pct > 0 and swstr > 0:
        score = s_k * 0.50 + s_swstr * 0.32 + s_contact_inv * 0.18
    elif k_pct > 0:
        score = s_k * 0.65 + s_contact_inv * 0.35
    else:
        score = 50.0  # no data

    if score >= 72:
        tier = "K MACHINE"
    elif score >= 55:
        tier = "K RISK"
    elif score <= 38:
        tier = "CONTACT"
    else:
        tier = "NEUTRAL"

    return {
        "score":   round(score, 1),
        "tier":    tier,
        "k_pct":   round(k_pct, 1),
        "chase":   round(chase, 1),
        "swstr":   round(swstr, 1),
        "contact": round(contact, 1),
    }


# ---------------------------------------------------------------------------
# Batter K projection
# ---------------------------------------------------------------------------

def _proj_batter_k(
    batter_score: float,
    k_pct: float,
    p_profile: dict,
    pa_estimate: float = LEAGUE_PA_SP,
) -> dict:
    """
    Project expected K count λ = batter_k_rate × pitcher_k_mult × PA_estimate.
    Poisson for P(K ≥ 1) → O0.5, P(K ≥ 2) → O1.5.
    """
    # Batter K rate (use individual stat if available, else back-calculate from score)
    if k_pct > 0:
        batter_k_rate = k_pct / 100.0
    else:
        # Map score 0-100 → K rate 0.08 – 0.42
        batter_k_rate = 0.08 + (batter_score / 100.0) * 0.34

    # Pitcher K multiplier
    k_mult = p_profile.get("k_mult", 1.0)

    lam = batter_k_rate * k_mult * pa_estimate

    p1 = round(_poisson_at_least(lam, 1) * 100, 1)   # O0.5
    p2 = round(_poisson_at_least(lam, 2) * 100, 1)   # O1.5

    if p2 >= 55:
        conf = "STRONG O1.5"
    elif p2 >= 44:
        conf = "LEAN O1.5"
    elif p1 <= 52:
        conf = "LEAN U0.5"
    elif p2 <= 28:
        conf = "LEAN U1.5"
    else:
        conf = "NEUTRAL"

    return {
        "lam":  round(lam, 3),
        "p1":   p1,
        "p2":   p2,
        "conf": conf,
    }


# ---------------------------------------------------------------------------
# Build board
# ---------------------------------------------------------------------------

def build_batter_k_board(game_date: str = None) -> list:
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")

    season = int(game_date[:4])
    games  = get_today_games(game_date)
    if not games:
        return []

    savant_batting = load_savant_batting(season)
    xstats         = load_savant_xstats(season)
    pitcher_k_data = load_savant_pitcher_k(season)
    pitcher_velo   = load_savant_pitcher_velo(season)

    rows = []

    for game in games:
        game_pk      = game.get("gamePk")
        venue_name   = game.get("venue_name", "")
        away_team_id = game.get("teams", {}).get("away", {}).get("team", {}).get("id")
        home_team_id = game.get("teams", {}).get("home", {}).get("team", {}).get("id")

        sp_away_id   = game.get("sp_away_id")
        sp_home_id   = game.get("sp_home_id")
        sp_away_name = game.get("sp_away_name", "TBD")
        sp_home_name = game.get("sp_home_name", "TBD")

        for team_id, opp_sp_id, opp_sp_name in [
            (away_team_id, sp_home_id, sp_home_name),
            (home_team_id, sp_away_id, sp_away_name),
        ]:
            if not team_id or not opp_sp_id:
                continue

            p_throws  = get_pitcher_throws(opp_sp_id, season)
            p_profile = _pitcher_k_profile(opp_sp_id, season, pitcher_k_data, pitcher_velo)

            try:
                roster = get_team_roster_ids(team_id, season)
            except Exception:
                continue

            for batter_id, batter_name, batter_bats in roster:
                score_data = _batter_k_score(batter_id, savant_batting, xstats)
                proj       = _proj_batter_k(
                    batter_score=score_data["score"],
                    k_pct=score_data["k_pct"],
                    p_profile=p_profile,
                )

                rows.append({
                    "game_pk":      game_pk,
                    "game_date":    game_date,
                    "venue":        venue_name,
                    "batter_id":    batter_id,
                    "batter_name":  batter_name,
                    "batter_bats":  batter_bats or "R",
                    "opp_sp_id":    opp_sp_id,
                    "opp_sp_name":  opp_sp_name,
                    "p_throws":     p_throws,
                    "k_score":      score_data["score"],
                    "tier":         score_data["tier"],
                    "k_pct":        score_data["k_pct"],
                    "chase":        score_data["chase"],
                    "swstr":        score_data["swstr"],
                    "contact":      score_data["contact"],
                    "p_k_pct":      p_profile["p_k_pct"],
                    "p_label":      p_profile["label"],
                    "lam":          proj["lam"],
                    "p1":           proj["p1"],
                    "p2":           proj["p2"],
                    "conf":         proj["conf"],
                })

    rows.sort(key=lambda r: r["p2"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Format board
# ---------------------------------------------------------------------------

def format_batter_k_board(rows: list, top_n: int = 60) -> str:
    if not rows:
        return "No batter K board data available.\n"

    date_str = rows[0].get("game_date", "Today") if rows else "Today"
    lines = [f"BATTER STRIKEOUT PROP BOARD — {date_str}", "=" * 68, ""]

    from collections import defaultdict
    by_sp: dict = defaultdict(list)
    for r in rows:
        key = (r["game_pk"], r["opp_sp_id"])
        by_sp[key].append(r)

    def _avg_p2(group):
        return sum(r["p2"] for r in group) / len(group) if group else 0.0

    sorted_groups = sorted(by_sp.values(), key=_avg_p2, reverse=True)

    printed = 0
    for group in sorted_groups:
        if printed >= top_n:
            break
        sp_name  = group[0]["opp_sp_name"]
        p_throws = group[0]["p_throws"]
        p_k_pct  = group[0]["p_k_pct"]
        p_label  = group[0]["p_label"]
        venue    = group[0]["venue"]

        p_k_str = f"K%:{p_k_pct:.1f}" if p_k_pct > 0 else ""
        header  = f"vs {sp_name} ({p_throws}) @ {venue}"
        if p_label:
            header += f"  [{p_label}]"
        if p_k_str:
            header += f"  {p_k_str}"
        lines.append(header)
        lines.append("-" * len(header))

        group_sorted = sorted(group, key=lambda r: r["p2"], reverse=True)
        for r in group_sorted[:12]:
            tier     = r["tier"]
            name     = r["batter_name"]
            bats     = r["batter_bats"]
            k_pct_s  = f"K%:{r['k_pct']:.1f}" if r["k_pct"] > 0 else ""
            chase_s  = f"Chase:{r['chase']:.1f}" if r["chase"] > 0 else ""
            swstr_s  = f"SwStr:{r['swstr']:.1f}" if r["swstr"] > 0 else ""
            conf     = r["conf"]
            p1       = r["p1"]
            p2       = r["p2"]

            stats_parts = [s for s in [k_pct_s, chase_s, swstr_s] if s]
            stats_str   = "  ".join(stats_parts)

            tier_tag = f"[{tier}]" if tier not in ("NEUTRAL",) else ""
            lines.append(
                f"  {name:<22} {bats}  {tier_tag:<13}"
                f"  O0.5:{p1:4.1f}%  O1.5:{p2:4.1f}%"
                f"  λ:{r['lam']:.2f}  [{conf}]"
            )
            if stats_str:
                lines.append(f"    {stats_str}")
            printed += 1

        lines.append("")

    # K MACHINE callout section
    machines = [r for r in rows if r["tier"] == "K MACHINE"]
    if machines:
        lines.append("=" * 68)
        lines.append("K MACHINE TARGETS  (highest O1.5 probability)")
        lines.append("-" * 45)
        for r in sorted(machines, key=lambda x: x["p2"], reverse=True)[:15]:
            lines.append(
                f"  {r['batter_name']:<22} vs {r['opp_sp_name']:<20}"
                f"  O1.5:{r['p2']:4.1f}%  [{r['conf']}]"
            )
        lines.append("")

    # CONTACT callout section
    contacts = [r for r in rows if r["tier"] == "CONTACT"]
    if contacts:
        lines.append("=" * 68)
        lines.append("CONTACT HITTERS vs HIGH-K PITCHERS  (U0.5 targets)")
        lines.append("-" * 50)
        for r in sorted(contacts, key=lambda x: x["p1"])[:10]:
            u_prob = round(100 - r["p1"], 1)
            lines.append(
                f"  {r['batter_name']:<22} vs {r['opp_sp_name']:<20}"
                f"  U0.5:{u_prob:4.1f}%  K%:{r['k_pct']:.1f}"
            )
        lines.append("")

    return "\n".join(lines)
