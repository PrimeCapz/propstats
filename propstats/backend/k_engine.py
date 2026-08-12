"""
k_engine.py — Pitcher strikeout prop board.

Pitcher K Score (0-100):
  When putaway data available:
    Whiff/Swing (42%) + K% (24%) + Putaway% (22%) + Command/inv-BB% (12%)
    + P/PA bonus (+1/+2.5/+4 at ≥3.88/≥3.95/≥4.00)
  Fallback (no putaway):
    Whiff/Swing (55%) + K% (30%) + Command (15%)
  Tiers: K ELITE ≥72 | K Threat 55-72 | Manageable <55

Putaway% = 2-strike-count K rate (how often pitcher closes out the AB).
P/PA = pitches per plate appearance (deep counts → more swing opportunities).

Projected K Line:
  proj_k = blended_k_rate × proj_bf
  blended_k_rate = pitcher_K% × 0.65 + opp_lineup_K% × 0.35
  proj_bf = 25 (MLB average SP batters faced)
  edge_vs_line = proj_k − posted_line
  Poisson P(over/under) at nearest 0.5-unit line

Batter K Vulnerability (0-100):
  batter K% (40%) + arsenal-weighted whiff% vs pitcher (40%) + SwStr% (20%)
  Tags: HIGH K RISK | WHIFF MACHINE | STRIKEOUT PRONE | K PROP TARGET

Runs independently — no shared state with hr_engine.
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
    get_team_roster_ids,
    get_pitcher_throws,
    load_savant_pitcher_k,
    load_savant_batter_k,
    load_savant_pitcher_arsenal,
    load_savant_batter_pitch_splits,
)

LEAGUE_K_PCT  = 22.0   # MLB avg K% (%)
LEAGUE_BF_SP  = 25.0   # avg starter batters faced per game
LEAGUE_SWSTR  = 11.0   # avg SwStr%

# ── Recent pitcher form (last 3 starts) ──────────────────────────────────────

def _pitcher_recent_form(pitcher_id: int, lookback: int = 3) -> dict:
    """
    Fetch pitcher's last `lookback` starts from MLB API game log.
    Returns adjusted proj_bf multiplier and form label.
    ERA > 5: shorten outing expectation. Recent IP/GS < 4.5: early-exit risk.
    """
    try:
        url = (f"{MLB_API}/people/{pitcher_id}/stats"
               f"?stats=gameLog&group=pitching&season=2026&sportId=1")
        data = _get(url)
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        # Filter to starts only (IP > 1.0 typically, or GS marker)
        starts = [s for s in splits
                  if _safe(s.get("stat", {}).get("inningsPitched")) >= 1.0][-lookback:]
        if not starts:
            return {"bf_mult": 1.0, "form_label": "", "recent_era": None, "recent_ip_pg": None,
                    "start_logs": [], "last_start_date": "", "last_start_opp": "", "n_starts": 0}

        total_er = sum(_safe(s["stat"].get("earnedRuns")) for s in starts)
        total_ip = sum(_safe(s["stat"].get("inningsPitched")) for s in starts)
        n = len(starts)
        recent_era = (total_er / total_ip * 9) if total_ip > 0 else 0.0
        recent_ip_pg = total_ip / n if n > 0 else 5.0

        # BF multiplier: fewer expected BF when ERA high or outings short.
        # High-SwStr% pitchers (whiff generators) exit less often from ERA alone —
        # their runs come from hard contact/HRs, not from losing bat-missing ability.
        # We fetch SwStr% separately in build_k_board and pass it back; here we
        # use a sentinel value of None (not yet known at form-fetch time).
        # The caller may override bf_mult post-hoc via _apply_swstr_guard().
        bf_mult = 1.0
        if recent_era >= 7.0:
            bf_mult = 0.75  # likely pulled by 4th inning
        elif recent_era >= 5.0:
            bf_mult = 0.85  # early exit risk
        elif recent_era <= 2.50 and recent_ip_pg >= 6.0:
            bf_mult = 1.05  # going deep, more BF

        # Short recent outings regardless of ERA
        if recent_ip_pg < 4.5 and bf_mult > 0.80:
            bf_mult = min(bf_mult, 0.82)

        # Form label for display
        if recent_era >= 7.0:
            form_label = f"⚠ SHAKY({recent_era:.2f}ERA/{recent_ip_pg:.1f}IP)"
        elif recent_era >= 5.0:
            form_label = f"↓ SOFT({recent_era:.2f}ERA/{recent_ip_pg:.1f}IP)"
        elif recent_era <= 2.50:
            form_label = f"↑ HOT({recent_era:.2f}ERA/{recent_ip_pg:.1f}IP)"
        else:
            form_label = f"→ STABLE({recent_era:.2f}ERA/{recent_ip_pg:.1f}IP)"

        # Individual start logs (most-recent first)
        start_logs = []
        for s in reversed(starts):
            stat     = s.get("stat", {})
            opp_info = s.get("opponent") or s.get("team") or {}
            pitches  = int(_safe(stat.get("numberOfPitches", 0)))
            bf       = int(_safe(stat.get("battersFaced", 0)))
            start_logs.append({
                "date":    s.get("date", ""),
                "opp":     opp_info.get("abbreviation", ""),
                "ip":      stat.get("inningsPitched", "0.0"),
                "bb":      int(_safe(stat.get("baseOnBalls", 0))),
                "k":       int(_safe(stat.get("strikeOuts", 0))),
                "er":      int(_safe(stat.get("earnedRuns", 0))),
                "pitches": pitches,
                "bf":      bf,
            })

        last_start = starts[-1] if starts else {}
        last_opp   = (last_start.get("opponent") or last_start.get("team") or {})

        return {
            "bf_mult":        round(bf_mult, 3),
            "form_label":     form_label,
            "recent_era":     round(recent_era, 2),
            "recent_ip_pg":   round(recent_ip_pg, 1),
            "n_starts":       n,
            "start_logs":     start_logs,
            "last_start_date": last_start.get("date", ""),
            "last_start_opp":  last_opp.get("abbreviation", ""),
        }
    except Exception:
        return {"bf_mult": 1.0, "form_label": "", "recent_era": None, "recent_ip_pg": None,
                "start_logs": [], "last_start_date": "", "last_start_opp": "", "n_starts": 0}

def _apply_swstr_guard(bf_mult: float, recent_era: float | None,
                       recent_ip_pg: float | None, swstr_pct: float) -> float:
    """
    High-SwStr% pitchers (whiff generators) tend to keep getting Ks even when
    ERA is elevated from hard contact / home runs — their early-exit risk is
    lower than ERA alone implies.  Apply a softer BF penalty when SwStr% ≥ 11.5.
    """
    if swstr_pct < 11.5 or recent_era is None:
        return bf_mult
    # Only relax if the penalty was purely ERA-driven (not short-outing driven)
    if recent_ip_pg is not None and recent_ip_pg < 4.5:
        return bf_mult  # short outings stand regardless of whiff rate
    if recent_era >= 7.0 and bf_mult <= 0.76:
        # Whiff arm: soften the extreme pull (0.75→0.88)
        bf_mult = max(bf_mult, 0.88)
    elif recent_era >= 5.0 and bf_mult <= 0.86:
        # Whiff arm: soften moderate pull (0.85→0.94)
        bf_mult = max(bf_mult, 0.94)
    return round(bf_mult, 3)


# ── Scoring helpers ──────────────────────────────────────────────────────────

def _scale(val, lo, mid, hi):
    """Linear scale: val at lo→0, mid→50, hi→100, clamped."""
    if val is None:
        return 0.0
    if val <= lo:
        return 0.0
    if val >= hi:
        return 100.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    return 50.0 + 50.0 * (val - mid) / (hi - mid)


def _safe(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "-") else default
    except Exception:
        return default


def _poisson_over(lam: float, line: float) -> float:
    """P(X > line) = 1 - Poisson CDF(floor(line), λ). Returns 0-100."""
    k = int(math.floor(line))
    cdf = sum(math.exp(-lam) * (lam ** i) / math.factorial(i) for i in range(k + 1))
    return round((1 - cdf) * 100, 1)


def _poisson_under(lam: float, line: float) -> float:
    """P(X < line) = P(X <= floor(line-0.5)) for half-point lines."""
    k = int(math.floor(line - 0.5))
    cdf = sum(math.exp(-lam) * (lam ** i) / math.factorial(i) for i in range(k + 1))
    return round(cdf * 100, 1)


# ── Pitcher K scoring ────────────────────────────────────────────────────────

def _pitcher_putaway_pct(pitcher_id: int, pitcher_arsenal: dict) -> float:
    """Usage-weighted putaway% (2-strike K rate) across pitcher's arsenal."""
    pid = str(pitcher_id)
    arsenal = pitcher_arsenal.get(pid, [])
    total_usage = sum(_safe(p.get("usage_pct")) for p in arsenal)
    if not arsenal or total_usage == 0:
        return 0.0
    weighted = sum(
        _safe(p.get("usage_pct")) * _safe(p.get("put_away_pct"))
        for p in arsenal
    )
    return round(weighted / total_usage, 1)


def _pitcher_k_score(pitcher_id: int, pitcher_k_data: dict, pitcher_arsenal: dict) -> dict:
    """
    0-100 K Score for a pitcher.
    swstr_pct = whiff% per swing (Savant whiff_percent, avg ~24%, elite ~32%).
    putaway_pct = usage-weighted 2-strike K rate from arsenal (avg ~19%, elite ~26%).
    p_per_pa = pitches per plate appearance (avg ~3.85).
    """
    pid = str(pitcher_id)
    d   = pitcher_k_data.get(pid, {})

    swstr    = _safe(d.get("swstr_pct"))   # whiff/swing, 18-34% range
    k_pct    = _safe(d.get("k_pct"))       # season K%
    bb_pct   = _safe(d.get("bb_pct"))      # walk %
    p_per_pa = _safe(d.get("p_per_pa"))    # pitches per PA from Savant custom LB
    putaway  = _pitcher_putaway_pct(pitcher_id, pitcher_arsenal)  # 2-strike K rate

    s_swstr   = _scale(swstr,   16.0, 24.0, 34.0)        # avg 24%, elite 34%
    s_k       = _scale(k_pct,   13.0, 22.0, 35.0)         # avg 22%, elite 35%
    s_command = _scale(14.0 - bb_pct, 3.0, 7.0, 11.0)    # low BB% = good command
    s_putaway = _scale(putaway, 12.0, 19.0, 27.0)         # avg 19%, elite 27%

    data_sparse = (swstr == 0 and k_pct == 0)
    if data_sparse:
        score = 0.0
    elif putaway > 0:
        # Full formula: putaway replaces some K% weight (K% and putaway are correlated
        # but putaway specifically captures 2-strike conversion, the direct K driver)
        score = (s_swstr * 0.42 + s_k * 0.24 + s_putaway * 0.22 + s_command * 0.12)
    else:
        # Fallback when arsenal putaway data unavailable
        score = (s_swstr * 0.55 + s_k * 0.30 + s_command * 0.15)

    # P/PA bonus: more pitches per AB = deeper counts = more swing chances
    # Bounded to avoid inflating past 100
    if p_per_pa >= 4.00:
        ppa_bonus = 4.0
    elif p_per_pa >= 3.95:
        ppa_bonus = 2.5
    elif p_per_pa >= 3.88:
        ppa_bonus = 1.0
    else:
        ppa_bonus = 0.0
    if not data_sparse:
        score = min(100.0, score + ppa_bonus)

    # DATA SPARSE + stuff-elite floor: ERA from 1 start is noise; if underlying
    # whiff/K metrics are elite (Snell pattern), floor the score at 55 so the
    # pitcher isn't faded purely because of a small sample ERA blowup.
    stuff_elite_override = False
    if data_sparse and (swstr >= 28.0 or k_pct >= 30.0):
        score = max(score, 55.0)
        data_sparse = False
        stuff_elite_override = True

    # Tier
    if stuff_elite_override:
        tier = "K Threat"      # upgraded from DATA SPARSE — trust the stuff, not the ERA
    elif data_sparse:
        tier = "DATA SPARSE"   # no Savant data — monitor manually; could be K threat
    elif score >= 72:
        tier = "K ELITE"
    elif score >= 55:
        tier = "K Threat"
    else:
        tier = "Manageable"

    # Top whiff pitches (by pitcher whiff% per pitch type)
    arsenal = pitcher_arsenal.get(pid, [])
    top_whiff = sorted(
        [p for p in arsenal if (p.get("whiff_pct") or 0) >= 15],
        key=lambda x: -(x.get("whiff_pct") or 0)
    )[:3]

    return {
        "score":              round(score, 1),
        "tier":               tier,
        "stuff_elite":        stuff_elite_override,
        "swstr_pct":          swstr,
        "k_pct":              k_pct,
        "bb_pct":             bb_pct,
        "putaway_pct":        putaway,
        "p_per_pa":           p_per_pa,
        "ppa_bonus":          ppa_bonus,
        "top_whiff_pitches": top_whiff,
        "components": {
            "s_swstr":   round(s_swstr, 1),
            "s_k":       round(s_k, 1),
            "s_putaway": round(s_putaway, 1),
            "s_cmd":     round(s_command, 1),
        },
    }


def _proj_k_line(pitcher_k_data: dict, pitcher_id: int, opp_k_pct: float,
                 proj_bf: float = LEAGUE_BF_SP, bf_mult: float = 1.0,
                 k_score: float = 0.0, swstr_pct: float = 0.0) -> dict:
    """
    Project K count and nearest prop line with Poisson over/under %.
    bf_mult adjusts expected batters faced based on pitcher recent form.
    k_score and swstr_pct used to apply confidence floor guards.
    """
    pid = str(pitcher_id)
    d = pitcher_k_data.get(pid, {})
    p_k_pct = _safe(d.get("k_pct")) or LEAGUE_K_PCT

    # Blend: 65% pitcher, 35% opponent lineup
    opp = opp_k_pct if opp_k_pct > 0 else LEAGUE_K_PCT
    blended_k_pct = (p_k_pct * 0.65 + opp * 0.35) / 100.0

    effective_bf = proj_bf * bf_mult
    lam = blended_k_pct * effective_bf  # expected K count (λ for Poisson)
    lam = max(0.5, lam)

    # Nearest standard prop line (0.5 below projection)
    line = math.floor(lam * 2) / 2  # round down to nearest 0.5
    if line < 3.5:
        line = 3.5

    over_pct  = _poisson_over(lam, line)
    under_pct = 100.0 - over_pct

    # American odds from probability
    def _to_odds(p):
        if p <= 0 or p >= 100:
            return "EVEN"
        pf = p / 100.0
        if pf >= 0.5:
            return f"-{round((pf / (1 - pf)) * 100)}"
        return f"+{round(((1 - pf) / pf) * 100)}"

    # Label recommendation
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

    # Guard 1: K ELITE arms (score ≥ 65) can't be LEAN/STRONG UNDER.
    # These pitchers genuinely miss bats — any "under" signal is noise from
    # a reduced BF estimate, not from lost bat-missing ability.
    if k_score >= 65 and "UNDER" in confidence:
        confidence = "PUSH ZONE"

    # Guard 2: High-SwStr% arms (≥ league avg 11%) blocked from LEAN UNDER.
    # If a pitcher whiffs batters at or above league average, the under call
    # requires more than just a BF-reduction from high ERA.
    if swstr_pct >= LEAGUE_SWSTR and confidence == "LEAN UNDER":
        confidence = "PUSH ZONE"

    return {
        "proj_k":      round(lam, 1),
        "line":        line,
        "edge_vs_line": round(lam - line, 2),   # positive = model projects over
        "over_pct":    over_pct,
        "under_pct":   under_pct,
        "over_odds":   _to_odds(over_pct),
        "under_odds":  _to_odds(under_pct),
        "confidence":  confidence,
        "blended_k_pct": round(blended_k_pct * 100, 1),
        "pitcher_k_pct": round(p_k_pct, 1),
        "opp_k_pct":   round(opp, 1),
        "effective_bf": round(effective_bf, 1),
    }


# ── Batter K vulnerability ───────────────────────────────────────────────────

def _arsenal_whiff_vs_batter(pitcher_id: int, batter_id: int,
                              pitcher_arsenal: dict, batter_pitch_splits: dict) -> float:
    """
    Usage-weighted batter whiff% against this pitcher's specific arsenal.
    Returns a % (e.g. 25.4 means batter whiffs 25.4% of swings vs this pitch mix).
    """
    pid = str(pitcher_id)
    bid = str(batter_id)
    arsenal = pitcher_arsenal.get(pid, [])
    b_splits = batter_pitch_splits.get(bid, {})

    total_usage = sum(_safe(p.get("usage_pct")) for p in arsenal)
    if total_usage == 0 or not arsenal:
        return 0.0

    weighted = 0.0
    covered  = 0.0
    for pitch in arsenal:
        pt    = pitch.get("pitch_type", "")
        usage = _safe(pitch.get("usage_pct"))
        if usage <= 0:
            continue
        bstat = b_splits.get(pt, {})
        batter_whiff = _safe(bstat.get("whiff_pct"))
        if batter_whiff == 0.0:
            # Fall back to pitcher's own whiff% on that pitch
            batter_whiff = _safe(pitch.get("whiff_pct"))
        weighted += usage * batter_whiff
        covered  += usage

    if covered == 0:
        return 0.0
    return round(weighted / covered, 1)


def _batter_k_vuln(batter_id: int, pitcher_id: int,
                   batter_pitch_splits: dict, pitcher_arsenal: dict,
                   batter_k_data: dict) -> dict:
    """
    0-100 K vulnerability score for one batter vs pitcher matchup.
    swstr_pct here = batter's whiff% per swing (avg ~24%, high = vulnerable).
    """
    pid = str(batter_id)
    bk  = batter_k_data.get(pid, {})

    k_pct     = _safe(bk.get("k_pct"))
    swstr_pct = _safe(bk.get("swstr_pct"))  # batter whiff/swing rate
    arsenal_whiff = _arsenal_whiff_vs_batter(pitcher_id, batter_id,
                                              pitcher_arsenal, batter_pitch_splits)

    s_k_pct  = _scale(k_pct,        10.0, 22.0, 38.0)  # 22% = avg K%, 38% = very vulnerable
    s_whiff  = _scale(arsenal_whiff, 16.0, 24.0, 36.0)  # whiff/swing: 24% avg, 36% = vulnerable
    s_swstr  = _scale(swstr_pct,     16.0, 24.0, 36.0)  # batter whiff/swing: same scale

    if k_pct == 0 and arsenal_whiff == 0:
        score = 0.0
    else:
        score = s_k_pct * 0.40 + s_whiff * 0.40 + s_swstr * 0.20

    # Tags
    tags = []
    if score >= 70:
        tags.append("HIGH K RISK")
    if arsenal_whiff >= 30.0:
        tags.append("WHIFF MACHINE")
    if k_pct >= 28.0:
        tags.append("STRIKEOUT PRONE")
    if score >= 65 and arsenal_whiff >= 25.0:
        tags.append("K PROP TARGET")

    # Expected Ks per game (rough: K% × 4 PA expected)
    exp_k = round(k_pct / 100.0 * 3.8, 2) if k_pct else None

    return {
        "k_vuln_score":   round(score, 1),
        "k_pct":          k_pct,
        "swstr_pct":      swstr_pct,
        "arsenal_whiff":  arsenal_whiff,
        "exp_k_per_game": exp_k,
        "tags":           tags,
    }


# ── Per-batter fast entry ────────────────────────────────────────────────────

def _quick_batter_k_entry(batter_id: int, batter_name: str, bats: str,
                           pitcher_id: int, pitcher_name: str,
                           pitcher_arsenal: dict, batter_pitch_splits: dict,
                           batter_k_data: dict) -> dict:
    vuln = _batter_k_vuln(batter_id, pitcher_id, batter_pitch_splits,
                           pitcher_arsenal, batter_k_data)
    pid  = str(batter_id)
    ev   = batter_k_data.get(pid, {})

    return {
        "batter_id":      batter_id,
        "batter_name":    batter_name,
        "bats":           bats,
        "k_vuln_score":   vuln["k_vuln_score"],
        "k_pct":          vuln["k_pct"],
        "swstr_pct":      vuln["swstr_pct"],
        "arsenal_whiff":  vuln["arsenal_whiff"],
        "exp_k_per_game": vuln["exp_k_per_game"],
        "tags":           vuln["tags"],
        "pitcher_name":   pitcher_name,
    }


# ── Main build ───────────────────────────────────────────────────────────────

def build_k_board(game_date: str) -> list:
    """
    Build full K Prop Board for all games on game_date.
    Sorted by pitcher K Score descending.
    """
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    # Load all Savant data (cached after first call)
    pitcher_k_data      = load_savant_pitcher_k(season)
    batter_k_data       = load_savant_batter_k(season)
    pitcher_arsenal     = load_savant_pitcher_arsenal(season)
    batter_pitch_splits = load_savant_batter_pitch_splits(season)

    results = []

    for g in games:
        venue = g.get("venue_name", "Unknown")

        for side in ("away", "home"):
            opp_side     = "home" if side == "away" else "away"
            pitcher_info = g[side]["probable_pitcher"]
            opp_team_id  = g[opp_side]["team_id"]
            opp_abbr     = g[opp_side]["team_abbr"]
            pitcher_id   = pitcher_info.get("id")
            pitcher_name = pitcher_info.get("name", "TBD")

            if not pitcher_id:
                continue

            pitcher_throws = get_pitcher_throws(pitcher_id)
            time.sleep(0.10)

            k_score_data = _pitcher_k_score(pitcher_id, pitcher_k_data, pitcher_arsenal)
            swstr_pct    = k_score_data.get("swstr_pct", 0.0)

            # Recent pitcher form — adjusts expected BF for early-exit risk.
            # Apply SwStr% guard: whiff generators shouldn't be penalized as
            # heavily for ERA-driven outing-length estimates.
            recent_form = _pitcher_recent_form(pitcher_id)
            guarded_bf_mult = _apply_swstr_guard(
                recent_form.get("bf_mult", 1.0),
                recent_form.get("recent_era"),
                recent_form.get("recent_ip_pg"),
                swstr_pct,
            )
            recent_form["bf_mult"] = guarded_bf_mult
            time.sleep(0.10)

            # Opposing roster
            roster = get_team_roster_ids(opp_team_id, season)
            time.sleep(0.15)

            # Compute opp lineup K% from batter_k_data (avg of batters with data)
            opp_k_pcts = []
            for b in roster:
                pid = str(b.get("id", ""))
                bk = _safe(batter_k_data.get(pid, {}).get("k_pct"))
                if bk > 0:
                    opp_k_pcts.append(bk)
            opp_k_pct = round(sum(opp_k_pcts) / len(opp_k_pcts), 1) if opp_k_pcts else LEAGUE_K_PCT

            proj = _proj_k_line(
                pitcher_k_data, pitcher_id, opp_k_pct,
                bf_mult=recent_form.get("bf_mult", 1.0),
                k_score=k_score_data.get("score", 0.0),
                swstr_pct=swstr_pct,
            )

            # Compute P/PA from game-log pitch counts (Savant CSV field is empty).
            # MLB game log provides numberOfPitches + battersFaced per start.
            start_logs_raw = recent_form.get("start_logs", [])
            ppa_starts = [(l["pitches"], l["bf"])
                          for l in start_logs_raw if l.get("pitches", 0) > 0 and l.get("bf", 0) > 0]
            if ppa_starts:
                avg_p_per_pa = round(
                    sum(p / b for p, b in ppa_starts) / len(ppa_starts), 2
                )
                recent_form["p_per_pa"] = avg_p_per_pa
                # Always store p_per_pa in k_score for display; only apply bonus
                # when Savant CSV didn't already supply it (p_per_pa was 0).
                k_score_data["p_per_pa"] = avg_p_per_pa
                if k_score_data.get("ppa_bonus", 0) == 0:
                    if avg_p_per_pa >= 4.00:
                        ppa_bonus_calc = 4.0
                    elif avg_p_per_pa >= 3.95:
                        ppa_bonus_calc = 2.5
                    elif avg_p_per_pa >= 3.88:
                        ppa_bonus_calc = 1.0
                    else:
                        ppa_bonus_calc = 0.0
                    if ppa_bonus_calc > 0:
                        k_score_data["ppa_bonus"] = ppa_bonus_calc
                        k_score_data["score"]     = min(100.0, k_score_data["score"] + ppa_bonus_calc)
                        s = k_score_data["score"]
                        k_score_data["tier"] = (
                            "K ELITE"    if s >= 72 else
                            "K Threat"   if s >= 55 else
                            "Manageable"
                        )

            # Recent K surge: flag when avg K/start over last 2 starts is ≥1.20× projection
            start_logs = recent_form.get("start_logs", [])
            surge_logs = start_logs[:2]  # most recent 2 starts carry the signal
            if len(surge_logs) >= 2:
                avg_k_recent = sum(l.get("k", 0) for l in surge_logs) / len(surge_logs)
                proj_k_val   = proj.get("proj_k", 0)
                if proj_k_val > 0 and avg_k_recent >= proj_k_val * 1.20:
                    recent_form["k_surge"]     = True
                    recent_form["k_surge_avg"] = round(avg_k_recent, 1)
                    # Boost k_score: surge = pitcher is outperforming model, ranking should reflect it
                    surge_boost = 4.0
                    k_score_data["score"] = min(100.0, k_score_data["score"] + surge_boost)
                    k_score_data["surge_boost"] = surge_boost
                    s = k_score_data["score"]
                    k_score_data["tier"] = (
                        "K ELITE"    if s >= 72 else
                        "K Threat"   if s >= 55 else
                        "Manageable"
                    )
                else:
                    recent_form["k_surge"] = False
                    k_score_data["surge_boost"] = 0.0
            elif len(start_logs) >= 1:
                avg_k_recent = start_logs[0].get("k", 0)
                proj_k_val   = proj.get("proj_k", 0)
                if proj_k_val > 0 and avg_k_recent >= proj_k_val * 1.35:
                    recent_form["k_surge"]     = True
                    recent_form["k_surge_avg"] = round(float(avg_k_recent), 1)
                    surge_boost = 2.0
                    k_score_data["score"] = min(100.0, k_score_data["score"] + surge_boost)
                    k_score_data["surge_boost"] = surge_boost
                    s = k_score_data["score"]
                    k_score_data["tier"] = (
                        "K ELITE"    if s >= 72 else
                        "K Threat"   if s >= 55 else
                        "Manageable"
                    )
                else:
                    recent_form["k_surge"] = False
                    k_score_data["surge_boost"] = 0.0
            else:
                recent_form["k_surge"] = False
                k_score_data["surge_boost"] = 0.0

            # Early Hook Risk: high ERA + short outings cap K accumulation
            # regardless of stuff quality. Reduce proj_k by 20% and flag.
            # Triggered when recent ERA > 5.0 AND avg IP/G < 5.5.
            rf_era = recent_form.get("recent_era") or 0.0
            rf_ip  = recent_form.get("recent_ip_pg") or 5.5
            if rf_era > 5.0 and rf_ip < 5.5 and recent_form.get("n_starts", 0) >= 1:
                capped_proj_k = round(proj.get("proj_k", 0) * 0.80, 1)
                proj = dict(proj)
                proj["proj_k"]      = capped_proj_k
                proj["early_hook"]  = True
                if proj.get("line", 0) > 0:
                    proj["edge_vs_line"] = round(capped_proj_k - proj["line"], 2)
                recent_form["early_hook_risk"] = True
            else:
                recent_form["early_hook_risk"] = False

            # Arsenal display (top 3 by usage)
            arsenal_raw = pitcher_arsenal.get(str(pitcher_id), [])
            arsenal_display = sorted(arsenal_raw,
                                     key=lambda x: x.get("usage_pct") or 0,
                                     reverse=True)[:3]

            # Score every roster batter
            batter_entries = []
            for b in roster:
                bid = b.get("id")
                if not bid:
                    continue
                entry = _quick_batter_k_entry(
                    bid, b["name"], b.get("bats", "R"),
                    pitcher_id, pitcher_name,
                    pitcher_arsenal, batter_pitch_splits, batter_k_data,
                )
                batter_entries.append((entry["k_vuln_score"], entry))

            batter_entries.sort(key=lambda x: -x[0])
            top_k_batters = [e for _, e in batter_entries[:8]]

            results.append({
                "game":           f"{g['away']['team_abbr']}@{g['home']['team_abbr']}",
                "game_pk":        g["game_pk"],
                "venue":          venue,
                "pitcher_id":     pitcher_id,
                "pitcher_name":   pitcher_name,
                "pitcher_team":   g[side]["team_abbr"],
                "pitcher_throws": pitcher_throws,
                "opp_team":       opp_abbr,
                "k_score":        k_score_data,
                "proj":           proj,
                "opp_k_pct":      opp_k_pct,
                "recent_form":    recent_form,
                "arsenal":        arsenal_display,
                "top_k_batters":  top_k_batters,
            })

    results.sort(key=lambda x: -(x["k_score"]["score"]))
    return results


# ── Formatting ───────────────────────────────────────────────────────────────

def _fmt(val, fmt=".1f", suffix="", none_str="  -"):
    if val is None or val == 0.0:
        return none_str
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return none_str


def format_k_board(results: list, game_date: str) -> str:
    lines = []
    W = 108

    lines.append("=" * W)
    lines.append(f"  K PROP BOARD — {game_date}")
    lines.append("  K Score: Whiff/Sw(42) + K%(24) + Putaway%(22) + Command(12) + P/PA bonus  |  Batter Vuln: K% + ArsnlWhiff + SwStr%")
    lines.append("=" * W)

    # Summary table header
    lines.append("")
    lines.append(
        f"  {'PITCHER':<22} {'OPP':<5} {'K_SCR':>6} {'TIER':<14} {'K%':>6} "
        f"{'Whiff/Sw':>9} {'PUTAWAY':>8} {'P/PA':>5} {'BB%':>5} {'PROJ':>5} {'LINE':>5} {'EDGE':>6} {'OPP_K%':>7}"
    )
    lines.append("  " + "-" * 106)

    for r in results:
        ks   = r["k_score"]
        proj = r["proj"]
        tier_sym = ("★" if ks["tier"] == "K ELITE"
                    else "◎" if ks["tier"] == "K Threat"
                    else "⚠" if ks["tier"] == "DATA SPARSE"
                    else "○")
        tier_str = f"{tier_sym} {ks['tier']}"

        k_pct    = _fmt(ks["k_pct"],      ".1f", "%", "   -")
        swstr    = _fmt(ks["swstr_pct"],  ".1f", "%", "   -")
        putaway  = _fmt(ks.get("putaway_pct"), ".1f", "%", "     -")
        ppa      = _fmt(ks.get("p_per_pa"),    ".2f", "",  "   -")
        bb       = _fmt(ks["bb_pct"],     ".1f", "%", "   -")
        proj_k   = _fmt(proj["proj_k"],   ".1f", "",  "  -")
        line_str = f"{proj['line']:.1f}"
        edge     = proj.get("edge_vs_line", 0)
        edge_str = f"+{edge:.2f}" if edge >= 0 else f"{edge:.2f}"
        opp_k    = _fmt(r["opp_k_pct"],  ".1f", "%", "   -")

        surge_flag = " ⚡K-SURGE" if r.get("recent_form", {}).get("k_surge") else ""
        sparse_note = "  ← no Savant data, monitor manually" if ks["tier"] == "DATA SPARSE" else ""
        lines.append(
            f"  {r['pitcher_name']:<22} {r['opp_team']:<5} {ks['score']:>6.1f} {tier_str:<14} "
            f"{k_pct:>6} {swstr:>9} {putaway:>8} {ppa:>5} {bb:>5} {proj_k:>5} {line_str:>5} {edge_str:>6} {opp_k:>7}"
            f"{surge_flag}{sparse_note}"
        )

    lines.append("")
    lines.append("=" * W)
    lines.append("  BATTER MATCHUP REPORT  (K Vulnerability · Arsenal Whiff% · SwStr%)")
    lines.append("=" * W)

    for r in results:
        ks   = r["k_score"]
        proj = r["proj"]

        tier_sym = ("★" if ks["tier"] == "K ELITE"
                    else "◎" if ks["tier"] == "K Threat"
                    else "⚠" if ks["tier"] == "DATA SPARSE"
                    else "○")

        # Arsenal string
        ars = r.get("arsenal", [])
        ars_str = "  ".join(
            f"{p['pitch_name']} {p['usage_pct']:.0f}% [W{p['whiff_pct']:.0f}%]"
            for p in ars if p.get("pitch_name") and p.get("usage_pct")
        )

        # K score pitcher line header
        hand_note = (f"[LHP — vs LHB ×0.91 | vs RHB ×1.09]"
                     if r["pitcher_throws"] == "L"
                     else f"[RHP — vs LHB ×1.09 | vs RHB ×0.91]")

        # Confidence badge
        conf = proj["confidence"]
        conf_badge = (f"  ★★ {conf}" if "STRONG" in conf
                      else f"  ◎ {conf}" if "LEAN" in conf
                      else f"  — {conf}")

        lines.append("")
        lines.append(
            f"  ┌─ {r['pitcher_name']} ({r['pitcher_team']})  vs {r['opp_team']}  │  {r['game']}"
        )
        putaway_str = _fmt(ks.get("putaway_pct"), ".1f", "%", "-")
        ppa_str     = _fmt(ks.get("p_per_pa"),    ".2f", "", "-")
        ppa_bonus   = ks.get("ppa_bonus", 0.0)
        ppa_bonus_str = f" (+{ppa_bonus:.1f})" if ppa_bonus > 0 else ""
        edge        = proj.get("edge_vs_line", 0)
        edge_str    = f"+{edge:.2f}" if edge >= 0 else f"{edge:.2f}"

        lines.append(
            f"  │  K Score: {ks['score']} {tier_sym} {ks['tier']}  │  "
            f"K%: {_fmt(ks['k_pct'],'.1f','%')}  Whiff/Sw: {_fmt(ks['swstr_pct'],'.1f','%')}  "
            f"Putaway: {putaway_str}  P/PA: {ppa_str}{ppa_bonus_str}  BB%: {_fmt(ks['bb_pct'],'.1f','%')}"
        )
        rf = r.get("recent_form", {})
        rf_label = rf.get("form_label", "")
        surge_note = f"  ⚡ K-SURGE avg {rf.get('k_surge_avg')}K/start" if rf.get("k_surge") else ""
        lines.append(
            f"  │  Proj K: {proj['proj_k']}  Line: {proj['line']:.1f}  Edge: {edge_str}  "
            f"Over: {proj['over_pct']}% ({proj['over_odds']})  "
            f"Under: {proj['under_pct']}% ({proj['under_odds']})"
            f"{conf_badge}{surge_note}"
        )
        lines.append(
            f"  │  Opp {r['opp_team']} lineup K%: {_fmt(r['opp_k_pct'],'.1f','%')}  "
            f"Blended K%: {_fmt(proj['blended_k_pct'],'.1f','%')}  "
            f"EffBF: {proj.get('effective_bf', LEAGUE_BF_SP):.1f}  "
            f"{hand_note}  {rf_label}"
        )
        if ars_str:
            lines.append(f"  │  Arsenal: {ars_str}")
        # Recent start log (most-recent first, up to 5)
        logs = r["recent_form"].get("start_logs", [])[:5]
        if logs:
            log_str = "  ".join(
                f"{l['date'][-5:]} vs {l['opp']} {l['ip']}IP {l['bb']}BB {l['k']}K"
                for l in logs
            )
            lines.append(f"  │  Last {len(logs)}G({rf_label}): {log_str}")
        lines.append("  │")

        # Column headers
        lines.append(
            f"  │  {'BATTER':<22} {'H':>2}  {'K_VUL':>6}  {'K%':>6}  {'ARSNL_W':>8}  {'SwStr%':>7}  {'PROJ_K':>6}  TAGS"
        )
        lines.append(f"  │  {'-' * 88}")

        for b in r["top_k_batters"]:
            k_vuln  = _fmt(b["k_vuln_score"], ".1f", "", "   -")
            k_pct_b = _fmt(b["k_pct"],        ".1f", "%", "   -")
            aw      = _fmt(b["arsenal_whiff"], ".1f", "%", "   -")
            sw      = _fmt(b["swstr_pct"],     ".1f", "%", "   -")
            ek      = _fmt(b["exp_k_per_game"],".2f", "",  "  -")
            tag_str = " | ".join(b.get("tags", [])) or ""
            if tag_str:
                tag_str = "◄ " + tag_str
            lines.append(
                f"  │  {b['batter_name']:<22} {b['bats']:>2}  {k_vuln:>6}  {k_pct_b:>6}  "
                f"{aw:>8}  {sw:>7}  {ek:>6}  {tag_str}"
            )

        lines.append(f"  └{'─' * 86}")

    lines.append("")
    lines.append("=" * W)
    return "\n".join(lines)


def format_k_batter_spotlight(results: list, game_date: str,
                               min_k_vuln: float = 60.0) -> str:
    """
    Cross-game batter K vulnerability ranking — all batters above min_k_vuln,
    sorted by k_vuln_score. Shows the most K-prone batters regardless of game.
    """
    all_batters = []
    for r in results:
        for b in r["top_k_batters"]:
            if b.get("k_vuln_score", 0) >= min_k_vuln:
                all_batters.append({
                    **b,
                    "game":         r["game"],
                    "pitcher_name": r["pitcher_name"],
                    "pitcher_throws": r.get("pitcher_throws", "R"),
                    "pitcher_k_score": r["k_score"]["score"],
                    "pitcher_tier":  r["k_score"]["tier"],
                    "proj_k":        r["proj"]["proj_k"],
                    "proj_line":     r["proj"]["line"],
                    "proj_conf":     r["proj"]["confidence"],
                })
    all_batters.sort(key=lambda x: -(x.get("k_vuln_score") or 0))

    lines = []
    W = 110
    lines.append("=" * W)
    lines.append(f"  K VULNERABILITY SPOTLIGHT — {game_date}  (K Vuln ≥ {min_k_vuln})")
    lines.append("  Ranked by K Vulnerability Score = K%(40) + ArsnlWhiff%(40) + SwStr%(20)")
    lines.append("=" * W)
    lines.append("")

    hdr = (f"  {'BATTER':<22} {'H':>2}  {'K_VUL':>6}  {'K%':>6}  {'ARSNL_W':>8}  "
           f"{'SwStr%':>7}  {'PROJ_K':>6}  {'GAME':<12}  {'PITCHER':<22}  {'P_KSCORE':>8}  TAGS")
    lines.append(hdr)
    lines.append("  " + "-" * (W - 2))

    for b in all_batters:
        k_vuln  = _fmt(b["k_vuln_score"], ".1f", "", "   -")
        k_pct_b = _fmt(b["k_pct"],        ".1f", "%", "   -")
        aw      = _fmt(b["arsenal_whiff"], ".1f", "%", "   -")
        sw      = _fmt(b["swstr_pct"],     ".1f", "%", "   -")
        ek      = _fmt(b["exp_k_per_game"],".2f", "",  "  -")
        tag_str = " | ".join(b.get("tags", [])) or ""
        if tag_str:
            tag_str = "◄ " + tag_str
        tier_sym = ("★" if b["pitcher_tier"] == "K ELITE"
                    else "◎" if b["pitcher_tier"] == "K Threat"
                    else "○")
        p_kscore_str = f"{tier_sym}{b['pitcher_k_score']:.1f}"

        lines.append(
            f"  {b['batter_name']:<22} {b['bats']:>2}  {k_vuln:>6}  {k_pct_b:>6}  "
            f"{aw:>8}  {sw:>7}  {ek:>6}  {b['game']:<12}  "
            f"{b['pitcher_name']:<22}  {p_kscore_str:>8}  {tag_str}"
        )

    lines.append("")
    lines.append("=" * W)
    return "\n".join(lines)
