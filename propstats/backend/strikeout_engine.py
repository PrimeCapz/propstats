"""
strikeout_engine.py — Standalone pitcher K probability model.

Poisson distribution: λ = adj_K_rate × expected_BF
- Season K% × lineup adjustment factor × expected batters faced
- Blended with L5 K average (50/50) for recency weight
- Arsenal K score: weighted put_away_pct across pitch mix
- Right tail mass: P(K ≥ mean + 3) for upside profiling
- VIG-adjusted edge vs -110 market (52.4% implied break-even)

Runs independently from odds_engine / build_prop_sheet.
"""

import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    _get, MLB_API,
    get_pitcher_season_stats,
    get_pitcher_recent_starts,
    get_pitch_arsenal,
    get_today_games,
    load_savant_pitcher_k,
)

LEAGUE_K_PCT   = 0.228   # MLB avg K rate per PA (2025-26)
MARKET_VIG_BEP = 0.524   # -110 break-even probability
CA             = "/root/.ccr/ca-bundle.crt"
PROXY          = os.environ.get("HTTPS_PROXY", "")
PROXIES        = {"https": PROXY, "http": PROXY} if PROXY else None


# ── Poisson math ────────────────────────────────────────────────────────────

def _pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


def _cdf(k: int, lam: float) -> float:
    """P(X ≤ k)"""
    return sum(_pmf(i, lam) for i in range(max(0, k) + 1))


def _p_at_least(n: int, lam: float) -> float:
    """P(X ≥ n)"""
    return max(0.0, 1.0 - _cdf(n - 1, lam))


def _right_tail(mean_k: float, lam: float, margin: int = 3) -> float:
    """P(K ≥ floor(mean_k) + margin) — big outperformance probability."""
    return _p_at_least(int(mean_k) + margin, lam)


# ── IP / BF helpers ─────────────────────────────────────────────────────────

def _ip_to_dec(ip_str) -> float:
    """'6.2' → 6.667 decimal innings."""
    try:
        parts = str(ip_str).split(".")
        return int(parts[0]) + (int(parts[1]) if len(parts) > 1 else 0) / 3.0
    except Exception:
        return 0.0


def _k_pct_to_float(raw) -> float:
    """Parse MLB API strikeoutPercentage — handles '0.285', '28.5', or '-'."""
    try:
        v = float(str(raw).replace("%", "").strip())
        return v / 100.0 if v > 1.0 else v
    except Exception:
        return 0.0


# ── Team K rate (lineup adjustment) ─────────────────────────────────────────

def _team_k_pct(team_id: int, season: int) -> float:
    """Opponent team's season K rate (K/PA). Falls back to league average."""
    data = _get(f"{MLB_API}/teams/{team_id}/stats", {
        "stats": "season", "group": "hitting", "season": season, "sportId": 1,
    })
    if not data:
        return LEAGUE_K_PCT
    for entry in data.get("stats", []):
        for split in entry.get("splits", []):
            s = split.get("stat", {})
            k  = s.get("strikeOuts", 0) or 0
            pa = s.get("plateAppearances", 0) or 0
            if pa > 0:
                return k / pa
    return LEAGUE_K_PCT


# ── Pitcher K profile ────────────────────────────────────────────────────────

def _pitcher_k_profile(pitcher_id: int, as_of_date: str, season: int, savant_k: dict) -> dict:
    stats  = get_pitcher_season_stats(pitcher_id, season=season, as_of_date=as_of_date)
    recent = get_pitcher_recent_starts(pitcher_id, season=season, limit=5, as_of_date=as_of_date)
    ars    = get_pitch_arsenal(pitcher_id, season=season)

    s = stats.get("stats", {})

    # Season K rate — prefer Statcast k_pct (more accurate), fall back to MLB API
    sv = savant_k.get(str(pitcher_id), {})
    sv_k_pct = sv.get("k_pct", 0)
    if sv_k_pct and sv_k_pct > 1:
        sv_k_pct = sv_k_pct / 100.0   # Savant returns as e.g. 28.5

    k_pct = sv_k_pct if sv_k_pct > 0 else _k_pct_to_float(s.get("k_pct", 0))
    if k_pct <= 0:
        k9_raw = s.get("k9", 0)
        try:
            k9 = float(str(k9_raw))
            k_pct = k9 / (9 * 4.05)
        except Exception:
            k_pct = LEAGUE_K_PCT

    # Savant K-stuff metrics
    swstr_pct = sv.get("swstr_pct", 0)
    if swstr_pct and swstr_pct > 1:
        swstr_pct = swstr_pct / 100.0
    csw_pct = sv.get("csw_pct", 0)
    if csw_pct and csw_pct > 1:
        csw_pct = csw_pct / 100.0

    # Season IP for BF estimate
    season_ip  = _ip_to_dec(s.get("innings_pitched", "0.0"))
    season_gs  = s.get("games_started", 0) or 1
    season_k   = s.get("strikeouts", 0) or 0
    season_bb  = s.get("walks", 0) or 0
    season_h   = s.get("hits", 0) or 0

    # Estimate season BF: outs + K (already in outs) + BB + H
    season_outs = season_ip * 3
    season_bf   = season_outs + season_bb + season_h   # reasonable proxy

    # IP per start — use L5 average; fall back to season average
    if recent:
        l5_ips  = [_ip_to_dec(r["ip"]) for r in recent]
        l5_ks   = [r["k"] for r in recent]
        avg_ip  = sum(l5_ips) / len(l5_ips)
        l5_k_avg = sum(l5_ks) / len(l5_ks)
        l5_k_range = (min(l5_ks), max(l5_ks))
    else:
        avg_ip    = season_ip / season_gs if season_gs > 0 else 5.5
        l5_ks     = []
        l5_k_avg  = 0.0
        l5_k_range = (0, 0)

    expected_bf = avg_ip * 4.05   # BF per IP constant

    # Arsenal: usage% from MLB API; use Savant SwStr%/CSW% as overall K-stuff
    # (pitch-type level whiff/putaway not available from MLB API endpoint)
    top_velo_pitch = max(ars, key=lambda p: p.get("avg_velocity") or 0) if ars else None

    return {
        "k_pct":          k_pct,
        "swstr_pct":      swstr_pct,
        "csw_pct":        csw_pct,
        "avg_ip":         avg_ip,
        "expected_bf":    expected_bf,
        "l5_k_avg":       l5_k_avg,
        "l5_k_range":     l5_k_range,
        "l5_ks":          l5_ks,
        "arsenal":        ars,
        "top_velo_pitch": top_velo_pitch,
        "throws":         stats.get("throws", "?"),
        "season_k":       season_k,
        "season_bf":      season_bf,
        "season_gs":      season_gs,
    }


# ── Single-pitcher analysis ──────────────────────────────────────────────────

def analyze_pitcher(
    pitcher_id:    int,
    pitcher_name:  str,
    opp_team_id:   int,
    opp_abbr:      str,
    as_of_date:    str,
    season:        int,
    savant_k:      dict = None,
) -> dict:
    if savant_k is None:
        savant_k = {}
    profile = _pitcher_k_profile(pitcher_id, as_of_date, season, savant_k)

    # Lineup K-rate adjustment
    opp_k_pct   = _team_k_pct(opp_team_id, season)
    adj_factor   = opp_k_pct / LEAGUE_K_PCT
    adj_k_rate   = profile["k_pct"] * adj_factor

    # λ: season-adjusted expected K count
    lam_season = adj_k_rate * profile["expected_bf"]

    # Blend season λ with L5 average (50/50) for recency
    if profile["l5_k_avg"] > 0:
        lam = (lam_season + profile["l5_k_avg"]) * 0.5
    else:
        lam = lam_season

    # Probability curve P(K≥n) for n = 1..12
    curve = {n: round(_p_at_least(n, lam), 4) for n in range(1, 13)}

    # Line probability table — common K prop lines
    LINES = [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]
    line_table = {}
    for line in LINES:
        n        = int(line + 0.5)          # line 6.5 → P(K≥7)
        p_over   = _p_at_least(n, lam)
        p_under  = 1.0 - p_over
        ov_edge  = round((p_over  - MARKET_VIG_BEP) * 100, 1)
        un_edge  = round((p_under - MARKET_VIG_BEP) * 100, 1)
        line_table[line] = {
            "p_over":     round(p_over,  4),
            "p_under":    round(p_under, 4),
            "over_edge":  ov_edge,
            "under_edge": un_edge,
        }

    # Right tail mass
    rt_pct = round(_right_tail(lam, lam) * 100, 1)

    # Best lean — find the line closest to the mean K where edge still exists.
    # Scan from the top down: highest line with OVER edge > 5%, OR
    # lowest line with UNDER edge > 5%.  Prefer the line nearest to mean_k.
    lean = "NEUTRAL"
    lean_line = None
    lean_edge = 0.0

    best_over_line  = None
    best_over_edge  = 0.0
    best_under_line = None
    best_under_edge = 0.0

    for line in LINES:
        lp = line_table[line]
        if lp["over_edge"] > 5.0:
            best_over_line = line
            best_over_edge = lp["over_edge"]
        if lp["under_edge"] > 5.0 and best_under_line is None:
            best_under_line = line
            best_under_edge = lp["under_edge"]

    # Choose the lean that is closest to lam (most actionable)
    if best_over_line is not None and best_under_line is not None:
        if abs(lam - best_over_line) <= abs(lam - best_under_line):
            lean, lean_line, lean_edge = "OVER", best_over_line, best_over_edge
        else:
            lean, lean_line, lean_edge = "UNDER", best_under_line, best_under_edge
    elif best_over_line is not None:
        lean, lean_line, lean_edge = "OVER", best_over_line, best_over_edge
    elif best_under_line is not None:
        lean, lean_line, lean_edge = "UNDER", best_under_line, best_under_edge

    return {
        "pitcher_name":  pitcher_name,
        "pitcher_id":    pitcher_id,
        "opp_abbr":      opp_abbr,
        "throws":        profile["throws"],
        "season_k_pct":  round(profile["k_pct"] * 100, 1),
        "opp_k_pct":     round(opp_k_pct * 100, 1),
        "adj_factor":    round(adj_factor, 3),
        "avg_ip":        round(profile["avg_ip"], 1),
        "expected_bf":   round(profile["expected_bf"], 1),
        "lambda":        round(lam, 2),
        "mean_k":        round(lam, 1),
        "lam_season":    round(lam_season, 2),
        "l5_k_avg":      round(profile["l5_k_avg"], 1),
        "l5_ks":         profile["l5_ks"],
        "l5_k_range":    profile["l5_k_range"],
        "swstr_pct":     round(profile["swstr_pct"] * 100, 1),
        "csw_pct":       round(profile["csw_pct"]   * 100, 1),
        "top_velo_pitch": profile["top_velo_pitch"],
        "arsenal":       profile["arsenal"],
        "curve":         curve,
        "line_table":    line_table,
        "right_tail_pct": rt_pct,
        "lean":          lean,
        "lean_line":     lean_line,
        "lean_edge":     lean_edge,
    }


# ── Slate builder ────────────────────────────────────────────────────────────

def build_k_report(game_date: str) -> list:
    """Run K analysis for every probable starter on a given date."""
    season   = int(game_date[:4])
    games    = get_today_games(game_date)
    savant_k = load_savant_pitcher_k(season)   # load once, share across all pitchers
    results  = []

    for game in games:
        away         = game.get("away", {})
        home         = game.get("home", {})
        away_pitcher = away.get("probable_pitcher", {})
        home_pitcher = home.get("probable_pitcher", {})
        game_pk      = game.get("game_pk")
        away_abbr    = away.get("team_abbr", "?")
        home_abbr    = home.get("team_abbr", "?")
        venue        = game.get("venue_name", "")
        game_time    = game.get("game_time", "")

        matchups = [
            (away_pitcher, away_abbr, home, home_abbr),
            (home_pitcher, home_abbr, away,  away_abbr),
        ]

        for pitcher_info, team_abbr, opp_team, opp_abbr in matchups:
            pid   = pitcher_info.get("id")
            pname = pitcher_info.get("name", "TBD")
            opp_id = opp_team.get("team_id")

            if not pid or not opp_id or pname == "TBD":
                continue

            try:
                r = analyze_pitcher(pid, pname, opp_id, opp_abbr, game_date, season, savant_k)
                r.update({
                    "game_pk":   game_pk,
                    "team":      team_abbr,
                    "away":      away_abbr,
                    "home":      home_abbr,
                    "venue":     venue,
                    "game_time": game_time,
                    "matchup":   f"{away_abbr}@{home_abbr}",
                })
                results.append(r)
            except Exception as e:
                results.append({
                    "pitcher_name": pname,
                    "team":    team_abbr,
                    "matchup": f"{away_abbr}@{home_abbr}",
                    "game_pk": game_pk,
                    "error":   str(e),
                    "mean_k":  0,
                })
            time.sleep(0.3)

    results.sort(key=lambda x: x.get("mean_k", 0), reverse=True)
    return results


# ── Text formatter ───────────────────────────────────────────────────────────

def format_k_report(results: list, game_date: str) -> str:
    lines = []
    sep   = "=" * 72

    lines += [
        sep,
        f"  STRIKEOUT MODEL — {game_date}",
        f"  Poisson λ = adj_K_rate × expected_BF  (50% season / 50% L5 blend)",
        f"  Edge = model prob − 52.4% (−110 break-even)",
        sep,
        "",
    ]

    # Summary table
    lines.append(f"  {'PITCHER':<22} {'OPP':>4}  {'MEAN K':>6}  {'L5 AVG':>6}  {'L5 RANGE':>8}  {'LINEUP ADJ':>10}  {'LEAN'}")
    lines.append("  " + "-" * 68)
    for r in results:
        if "error" in r:
            lines.append(f"  {r['pitcher_name']:<22}  ERROR: {r['error'][:35]}")
            continue
        rng     = f"{r['l5_k_range'][0]}–{r['l5_k_range'][1]}"
        adj_str = f"{r['adj_factor']:.2f}×"
        lean_str = f"{r['lean']} {r['lean_line'] or ''}".strip()
        lines.append(
            f"  {r['pitcher_name']:<22} {r['opp_abbr']:>4}  {r['mean_k']:>6.1f}  "
            f"{r['l5_k_avg']:>6.1f}  {rng:>8}  {adj_str:>10}  {lean_str}"
        )

    lines += ["", sep, "  PROBABILITY CURVES", sep]

    for r in results:
        if "error" in r:
            continue

        lt  = r["line_table"]
        ars = r.get("arsenal", [])

        swstr = r.get("swstr_pct", 0)
        csw   = r.get("csw_pct",   0)
        tvp   = r.get("top_velo_pitch")

        lines += [
            "",
            f"  ┌─ {r['pitcher_name']} ({r.get('throws','?')}HP)  vs {r['opp_abbr']}  │  {r['matchup']}",
            f"  │  Mean K: {r['mean_k']}  │  L5 avg: {r['l5_k_avg']}  │  L5 games: {r['l5_ks']}",
            f"  │  Season K%: {r['season_k_pct']}%  │  SwStr%: {swstr}%  │  CSW%: {csw}%",
            f"  │  Opp lineup K%: {r['opp_k_pct']}%  │  Adj: {r['adj_factor']:.2f}×  │  exp BF: {r['expected_bf']}",
            f"  │  Right Tail (K≥mean+3): {r['right_tail_pct']}%",
            f"  │",
            f"  │  {'LINE':<6}  {'P(OVER)':>8}  {'EDGE':>7}  │  {'P(UNDER)':>9}  {'EDGE':>7}",
            f"  │  {'─'*6}  {'─'*8}  {'─'*7}  │  {'─'*9}  {'─'*7}",
        ]

        for line in [3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5]:
            if line not in lt:
                continue
            lp     = lt[line]
            flag_o = "  ★ OVER"  if lp["over_edge"]  > 5 else ""
            flag_u = "  ★ UNDER" if lp["under_edge"] > 5 else ""
            lines.append(
                f"  │  {line:<6.1f}  {lp['p_over']*100:>7.1f}%  {lp['over_edge']:>+6.1f}%  │  "
                f"{lp['p_under']*100:>8.1f}%  {lp['under_edge']:>+6.1f}%"
                f"{flag_o}{flag_u}"
            )

        # Arsenal (usage only — velo available, whiff/putaway from Savant summary above)
        if ars:
            lines.append(f"  │")
            lines.append(f"  │  Arsenal  {'PITCH':<18} {'USE%':>5}  {'VELO':>6}")
            for p in sorted(ars, key=lambda x: x["usage_pct"], reverse=True)[:5]:
                vflag = " ← primary" if tvp and p["pitch_name"] == tvp["pitch_name"] else ""
                lines.append(
                    f"  │    {p['pitch_name']:<18} {p['usage_pct']*100:>4.0f}%  {p.get('avg_velocity') or 0:>5.1f}{vflag}"
                )

        # Lean call
        if r["lean"] != "NEUTRAL":
            lines.append(f"  │")
            lines.append(f"  │  ★ LEAN: {r['lean']} {r['lean_line']}  (edge: +{r['lean_edge']:.1f}%)")

        lines.append(f"  └{'─'*68}")

    lines += ["", sep]
    return "\n".join(lines)
