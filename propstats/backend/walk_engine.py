"""
walk_engine.py — Pitcher walk prop board.

Walk Score (0-100):
  Pitcher BB% (40%) + Recent walk trend (20%) + Opp lineup BB draw (25%) + Chase inverse (15%)
  Tiers: WALK MACHINE >68 | WALK THREAT 52-68 | NEUTRAL <52

Projected Walks:
  proj_bb = blended_bb_rate × proj_bf
  blended_bb_rate = pitcher_bb_pct × 0.65 + opp_lineup_bb_pct × 0.35
  proj_bf = 25 (MLB average SP batters faced)
  Poisson P(over/under) at nearest 0.5-unit line

Runs independently — no shared state with k_engine or hr_engine.
"""

import json
import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    _get, MLB_API,
    get_today_games,
    get_team_roster_ids,
    load_savant_pitcher_k,
    load_savant_pitcher_velo,
    load_savant_batter_k,
)

LEAGUE_BB_PCT  = 8.5    # MLB avg pitcher BB%
LEAGUE_BF_SP   = 25.0   # avg SP batters faced per game
LEAGUE_OPP_BB  = 8.5    # MLB avg batter BB draw rate
LEAGUE_CHASE   = 29.0   # MLB avg pitcher chase rate (batters chasing out-of-zone)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "-") else default
    except Exception:
        return default


def _scale(val, lo, mid, hi):
    """Linear interpolation: lo→0, mid→50, hi→100, clamped 0-100."""
    if val is None:
        return 0.0
    if val <= lo:
        return 0.0
    if val >= hi:
        return 100.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    return 50.0 + 50.0 * (val - mid) / (hi - mid)


def _poisson_over(lam: float, line: float) -> float:
    """P(X > line) for Poisson(λ). Returns 0-100."""
    k = int(math.floor(line))
    cdf = sum(math.exp(-lam) * (lam ** i) / math.factorial(i) for i in range(k + 1))
    return round((1 - cdf) * 100, 1)


def _to_odds(p: float) -> str:
    if p <= 0 or p >= 100:
        return "EVEN"
    pf = p / 100.0
    if pf >= 0.5:
        return f"-{round((pf / (1 - pf)) * 100)}"
    return f"+{round(((1 - pf) / pf) * 100)}"


def _fmt(val, fmt=".1f", suffix="", none_str="  -"):
    if val is None or val == 0.0:
        return none_str
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return none_str


# ── Recent walk form ─────────────────────────────────────────────────────────

def _pitcher_recent_walk_form(pitcher_id: int, season_bb_pct: float,
                               lookback: int = 5, season: int = 2026) -> dict:
    """
    Last `lookback` starts from MLB API game log.
    Returns recent_bb_pg, trend (RISING/STABLE/FALLING), bf_mult, start_logs.
    """
    default = {
        "recent_bb_pg": None, "recent_bb_pct": None, "recent_ip_pg": None,
        "recent_era": None, "trend": "STABLE", "bf_mult": 1.0,
        "n_starts": 0, "start_logs": [],
    }
    try:
        url = (f"{MLB_API}/people/{pitcher_id}/stats"
               f"?stats=gameLog&group=pitching&season={season}&sportId=1")
        data = _get(url)
        if not data:
            return default
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [s for s in splits
                  if _safe(s.get("stat", {}).get("inningsPitched")) >= 1.0][-lookback:]
        if not starts:
            return default

        n = len(starts)
        total_bb = sum(_safe(s["stat"].get("baseOnBalls")) for s in starts)
        total_ip = sum(_safe(s["stat"].get("inningsPitched")) for s in starts)
        total_bf = sum(_safe(s["stat"].get("battersFaced")) for s in starts)
        total_er = sum(_safe(s["stat"].get("earnedRuns")) for s in starts)

        recent_bb_pg  = total_bb / n
        recent_bb_pct = (total_bb / total_bf * 100) if total_bf > 0 else season_bb_pct
        recent_ip_pg  = total_ip / n if n > 0 else 5.0
        recent_era    = (total_er / total_ip * 9) if total_ip > 0 else 4.50

        # Trend: compare most recent half vs earlier half
        trend = "STABLE"
        if n >= 4:
            mid = n // 2
            rbb = sum(_safe(s["stat"].get("baseOnBalls")) for s in starts[-mid:]) / mid
            ebb = sum(_safe(s["stat"].get("baseOnBalls")) for s in starts[:n - mid]) / (n - mid)
            if rbb > ebb + 0.8:
                trend = "RISING"
            elif rbb < ebb - 0.8:
                trend = "FALLING"

        # BF multiplier (early-exit risk)
        bf_mult = 1.0
        if recent_era >= 7.0:
            bf_mult = 0.80
        elif recent_era >= 5.0:
            bf_mult = 0.88
        elif recent_era <= 2.50 and recent_ip_pg >= 6.0:
            bf_mult = 1.05
        if recent_ip_pg < 4.5 and bf_mult > 0.80:
            bf_mult = min(bf_mult, 0.82)

        start_logs = []
        for s in reversed(starts):
            stat = s.get("stat", {})
            opp_info = s.get("opponent") or s.get("team") or {}
            start_logs.append({
                "date": s.get("date", ""),
                "opp":  opp_info.get("abbreviation", ""),
                "ip":   stat.get("inningsPitched", "0.0"),
                "bb":   int(_safe(stat.get("baseOnBalls"))),
                "k":    int(_safe(stat.get("strikeOuts"))),
                "er":   int(_safe(stat.get("earnedRuns"))),
            })

        return {
            "recent_bb_pg":  round(recent_bb_pg, 2),
            "recent_bb_pct": round(recent_bb_pct, 1),
            "recent_ip_pg":  round(recent_ip_pg, 1),
            "recent_era":    round(recent_era, 2),
            "trend":         trend,
            "bf_mult":       round(bf_mult, 3),
            "n_starts":      n,
            "start_logs":    start_logs,
        }
    except Exception:
        return default


# ── Walk score ───────────────────────────────────────────────────────────────

def _pitcher_walk_score(pitcher_id: int, pitcher_k_data: dict, pitcher_velo_data: dict,
                        recent_form: dict, opp_bb_pct: float) -> dict:
    """
    0-100 Walk Score. High score = pitcher likely to issue many walks.
    Components: BB%(40) + Recent trend(20) + Opp patience(25) + Chase inverse(15)
    """
    pid = str(pitcher_id)
    kd  = pitcher_k_data.get(pid, {})
    vd  = pitcher_velo_data.get(pid, {})

    bb_pct  = _safe(kd.get("bb_pct")) or _safe(vd.get("bb_pct")) or LEAGUE_BB_PCT
    chase   = _safe(vd.get("chase_pct")) or LEAGUE_CHASE

    recent_bb_pct = _safe(recent_form.get("recent_bb_pct")) or bb_pct
    trend = recent_form.get("trend", "STABLE")

    # (1) Season BB% — scale 3%→0, 8.5%→50, 15%→100
    s_bb = _scale(bb_pct, 3.0, 8.5, 15.0)

    # (2) Recent walk rate — scale 3%→0, 8.5%→50, 16%→100; RISING +8, FALLING -8
    s_recent = _scale(recent_bb_pct, 3.0, 8.5, 16.0)
    if trend == "RISING":
        s_recent = min(100.0, s_recent + 8.0)
    elif trend == "FALLING":
        s_recent = max(0.0, s_recent - 8.0)

    # (3) Opponent lineup BB draw — scale 6%→0, 8.5%→50, 14%→100
    opp = opp_bb_pct if opp_bb_pct > 0 else LEAGUE_OPP_BB
    s_opp = _scale(opp, 6.0, 8.5, 14.0)

    # (4) Inverse pitcher chase rate — low chase = batters stay patient = more walks
    # Scale: 35% chase→0, 29% chase→50 (avg), 20% chase→100
    s_chase_inv = _scale(35.0 - chase, 0.0, 6.0, 15.0)

    data_sparse = (bb_pct == LEAGUE_BB_PCT and kd.get("bb_pct") is None and vd.get("bb_pct") is None)
    if data_sparse:
        score = 0.0
    else:
        score = s_bb * 0.40 + s_recent * 0.20 + s_opp * 0.25 + s_chase_inv * 0.15

    # Tier
    if data_sparse:
        tier = "DATA SPARSE"
    elif score >= 68:
        tier = "WALK MACHINE"
    elif score >= 52:
        tier = "WALK THREAT"
    else:
        tier = "NEUTRAL"

    # Tags
    tags = []
    if bb_pct >= 12.0:
        tags.append("HIGH BB%")
    elif bb_pct >= 9.0:
        tags.append("WALK HAPPY")
    if trend == "RISING":
        tags.append("WORSENING CTRL")
    elif trend == "FALLING":
        tags.append("IMPROVING CTRL")
    if opp >= 9.5:
        tags.append("PATIENT LINEUP")
    if chase <= 25.0:
        tags.append("LOW CHASE ARM")  # pitcher rarely gets chases → batters work counts

    return {
        "score":      round(score, 1),
        "tier":       tier,
        "bb_pct":     round(bb_pct, 1),
        "chase_pct":  round(chase, 1),
        "opp_bb_pct": round(opp, 1),
        "tags":       tags,
        "components": {
            "s_bb":        round(s_bb, 1),
            "s_recent":    round(s_recent, 1),
            "s_opp":       round(s_opp, 1),
            "s_chase_inv": round(s_chase_inv, 1),
        },
    }


# ── Walk projection ──────────────────────────────────────────────────────────

def _proj_walk_line(pitcher_id: int, pitcher_k_data: dict, pitcher_velo_data: dict,
                    opp_bb_pct: float, proj_bf: float = LEAGUE_BF_SP,
                    bf_mult: float = 1.0) -> dict:
    """Project walk count via Poisson and compute prop line odds."""
    pid = str(pitcher_id)
    kd  = pitcher_k_data.get(pid, {})
    vd  = pitcher_velo_data.get(pid, {})
    p_bb_pct = _safe(kd.get("bb_pct")) or _safe(vd.get("bb_pct")) or LEAGUE_BB_PCT

    opp = opp_bb_pct if opp_bb_pct > 0 else LEAGUE_OPP_BB
    blended = (p_bb_pct * 0.65 + opp * 0.35) / 100.0

    lam = max(0.3, blended * proj_bf * bf_mult)

    line = math.floor(lam * 2) / 2
    if line < 0.5:
        line = 0.5

    over_pct  = _poisson_over(lam, line)
    under_pct = round(100.0 - over_pct, 1)

    if over_pct >= 62:
        confidence = "STRONG OVER"
    elif over_pct >= 54:
        confidence = "LEAN OVER"
    elif under_pct >= 62:
        confidence = "STRONG UNDER"
    elif under_pct >= 54:
        confidence = "LEAN UNDER"
    else:
        confidence = "PUSH ZONE"

    return {
        "proj_bb":      round(lam, 2),
        "line":         line,
        "over_pct":     over_pct,
        "under_pct":    under_pct,
        "confidence":   confidence,
        "odds_over":    _to_odds(over_pct),
        "odds_under":   _to_odds(under_pct),
        "o1_5":         _poisson_over(lam, 1.5),
        "o2_5":         _poisson_over(lam, 2.5),
        "o3_5":         _poisson_over(lam, 3.5),
        "o4_5":         _poisson_over(lam, 4.5),
        "p_bb_pct":     round(p_bb_pct, 1),
        "opp_bb_pct":   round(opp, 1),
        "blended_bb":   round(blended * 100, 2),
    }


# ── Main board ───────────────────────────────────────────────────────────────

def build_walk_board(game_date: str = None, season: int = None) -> list:
    """
    Walk prop board for all starters on game_date.
    Returns list sorted by walk_score descending.
    """
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")
    if not season:
        season = datetime.now().year

    games = get_today_games(game_date)
    if not games:
        return []

    pitcher_k_data    = load_savant_pitcher_k(season)
    pitcher_velo_data = load_savant_pitcher_velo(season)
    batter_k_data     = load_savant_batter_k(season)

    results = []

    for g in games:
        if g.get("status_code") in ("F", "DR"):
            continue

        venue = g.get("venue_name", "Unknown")

        for side, opp_side in [("home", "away"), ("away", "home")]:
            pitcher_info  = g[side]["probable_pitcher"]
            opp_team_id   = g[opp_side]["team_id"]
            opp_abbr      = g[opp_side]["team_abbr"]
            pitcher_id    = pitcher_info.get("id")
            pitcher_name  = pitcher_info.get("name", "TBD")
            pitcher_throws = pitcher_info.get("throws", "R")

            if not pitcher_id:
                continue

            # Opponent lineup patience
            roster = get_team_roster_ids(opp_team_id, season)
            time.sleep(0.12)

            opp_bb_vals = []
            rh_count = 0
            for b in roster:
                pid = str(b.get("id", ""))
                bk  = _safe(batter_k_data.get(pid, {}).get("bb_pct"))
                if bk > 0:
                    opp_bb_vals.append(bk)
                if b.get("bats") in ("R", "S"):
                    rh_count += 1

            opp_bb_pct = round(sum(opp_bb_vals) / len(opp_bb_vals), 1) if opp_bb_vals else LEAGUE_OPP_BB
            rh_pct     = rh_count / len(roster) * 100 if roster else 50.0

            # Platoon nibble factor
            platoon_note = ""
            platoon_mult = 1.0
            if pitcher_throws == "L" and rh_pct >= 60:
                platoon_note = f"LHP vs {rh_pct:.0f}%RHB"
                platoon_mult = 1.05
            elif pitcher_throws == "R" and (100 - rh_pct) >= 60:
                platoon_note = f"RHP vs {100-rh_pct:.0f}%LHB"
                platoon_mult = 1.05

            # Season BB%
            pid_str = str(pitcher_id)
            season_bb = (_safe(pitcher_k_data.get(pid_str, {}).get("bb_pct")) or
                         _safe(pitcher_velo_data.get(pid_str, {}).get("bb_pct")) or
                         LEAGUE_BB_PCT)

            # Recent form
            recent_form = _pitcher_recent_walk_form(pitcher_id, season_bb, season=season)
            time.sleep(0.10)

            # Score
            walk_score_data = _pitcher_walk_score(
                pitcher_id, pitcher_k_data, pitcher_velo_data, recent_form, opp_bb_pct
            )

            # Projection
            proj = _proj_walk_line(
                pitcher_id, pitcher_k_data, pitcher_velo_data, opp_bb_pct,
                bf_mult=recent_form.get("bf_mult", 1.0) * platoon_mult,
            )

            results.append({
                "game":           f"{g['away']['team_abbr']}@{g['home']['team_abbr']}",
                "game_pk":        g["game_pk"],
                "venue":          venue,
                "pitcher_id":     pitcher_id,
                "pitcher_name":   pitcher_name,
                "pitcher_team":   g[side]["team_abbr"],
                "pitcher_throws": pitcher_throws,
                "opp_team":       opp_abbr,
                "walk_score":     walk_score_data,
                "proj":           proj,
                "opp_bb_pct":     opp_bb_pct,
                "rh_pct":         round(rh_pct, 0),
                "platoon_note":   platoon_note,
                "recent_form":    recent_form,
            })

    results.sort(key=lambda x: -(x["walk_score"]["score"]))
    return results


# ── Formatter ────────────────────────────────────────────────────────────────

def format_walk_board(results: list, game_date: str) -> str:
    W = 100
    lines = []

    lines.append("=" * W)
    lines.append(f"  WALK PROP BOARD — {game_date}")
    lines.append("  Walk Score: BB%(40) + Recent Trend(20) + Opp Patience(25) + Chase Inv(15)  |  Proj = Poisson(blended BB%×BF)")
    lines.append("=" * W)
    lines.append("")
    lines.append(f"  {'PITCHER':<22} {'OPP':<5} {'WLKSCR':>7} {'TIER':<14} {'BB%':>5} {'Chase':>6} {'OppBB%':>7} {'Proj':>5} {'Line':>5} {'Ov%':>5} {'o2.5':>6}")
    lines.append("  " + "-" * 96)

    for r in results:
        ws   = r["walk_score"]
        proj = r["proj"]

        tier_sym = "🔥" if ws["tier"] == "WALK MACHINE" else ("⚠ " if ws["tier"] == "WALK THREAT" else "  ")
        bb_s     = _fmt(ws["bb_pct"],     ".1f", "%", "  -")
        chase_s  = _fmt(ws["chase_pct"],  ".1f", "%", "  -")
        oppbb_s  = _fmt(r["opp_bb_pct"],  ".1f", "%", "  -")
        proj_s   = _fmt(proj["proj_bb"],  ".2f", "",  "  -")
        ov_s     = _fmt(proj["over_pct"], ".0f", "%", "  -")
        ov25_s   = _fmt(proj["o2_5"],     ".0f", "%", "  -")

        lines.append(
            f"  {tier_sym}{r['pitcher_name']:<20} {r['opp_team']:<5}"
            f" {ws['score']:>6.1f} {ws['tier']:<14}"
            f" {bb_s:>5} {chase_s:>6} {oppbb_s:>7}"
            f" {proj_s:>5} {proj['line']:>5.1f}"
            f" {ov_s:>5} {ov25_s:>6}"
        )

        # Tags line
        tag_parts = []
        if r.get("platoon_note"):
            tag_parts.append(r["platoon_note"])
        tag_parts.extend(ws.get("tags", []))
        if tag_parts:
            lines.append(f"      {' | '.join(tag_parts)}")

        # Recent log: last 5 starts
        logs = r["recent_form"].get("start_logs", [])[:5]
        if logs:
            trend = r["recent_form"].get("trend", "")
            log_str = "  ".join(f"{l['date'][-5:]} {l['bb']}BB/{l['ip']}IP" for l in logs)
            lines.append(f"      Last {len(logs)}G({trend}): {log_str}")

        # Projection line breakdown
        lines.append(
            f"      o1.5({proj['o1_5']:.0f}%)  o2.5({proj['o2_5']:.0f}%)  "
            f"o3.5({proj['o3_5']:.0f}%)  o4.5({proj['o4_5']:.0f}%)  "
            f"[blended BB%={proj['blended_bb']:.1f}%]  {proj['confidence']}"
        )
        lines.append("")

    # Summary
    lines.append("=" * W)
    lines.append("  TOP WALK PROP TARGETS")
    lines.append("=" * W)

    machine = [r for r in results if r["walk_score"]["tier"] == "WALK MACHINE"]
    threat  = [r for r in results if r["walk_score"]["tier"] == "WALK THREAT"]

    if machine:
        lines.append("  🔥 WALK MACHINE:")
        for r in machine[:5]:
            p = r["proj"]
            f = r["recent_form"]
            lines.append(
                f"     {r['pitcher_name']} ({r['pitcher_team']}) vs {r['opp_team']}  "
                f"BB%={r['walk_score']['bb_pct']:.1f}%  "
                f"Proj={p['proj_bb']:.2f}  "
                f"o{p['line']:.1f}({p['over_pct']:.0f}%)  "
                f"o2.5({p['o2_5']:.0f}%)  "
                f"Trend={f.get('trend','?')}  RecentBB/G={f.get('recent_bb_pg') or '-'}"
            )
    if threat:
        lines.append("  ⚠ WALK THREAT:")
        for r in threat[:8]:
            p = r["proj"]
            f = r["recent_form"]
            lines.append(
                f"     {r['pitcher_name']} ({r['pitcher_team']}) vs {r['opp_team']}  "
                f"BB%={r['walk_score']['bb_pct']:.1f}%  "
                f"Proj={p['proj_bb']:.2f}  "
                f"o{p['line']:.1f}({p['over_pct']:.0f}%)  "
                f"o2.5({p['o2_5']:.0f}%)"
            )

    lines.append("")
    lines.append(f"  Total starters scored: {len(results)}")
    return "\n".join(lines)


# ── CLI entry ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--save-json", metavar="PATH")
    args = ap.parse_args()

    print(f"Building walk board for {args.date}...")
    board = build_walk_board(args.date)
    print(format_walk_board(board, args.date))

    if args.save_json:
        with open(args.save_json, "w") as f:
            json.dump(board, f, indent=2)
        print(f"\nSaved JSON → {args.save_json}")
