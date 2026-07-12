"""
k_engine.py — Pitcher strikeout prop board.

Pitcher K Score (0-100):
  SwStr% (40%) + CSW% (35%) + K% (15%) + Command/inverse-BB% (10%)
  Tiers: K ELITE >72 | K Threat 55-72 | Manageable <55

Projected K Line:
  proj_k = blended_k_rate × proj_bf
  blended_k_rate = pitcher_K% × 0.65 + opp_lineup_K% × 0.35
  proj_bf = 25 (MLB average SP batters faced)
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

def _pitcher_k_score(pitcher_id: int, pitcher_k_data: dict, pitcher_arsenal: dict) -> dict:
    """
    0-100 K Score for a pitcher.
    swstr_pct here = whiff% per swing (from Savant custom leaderboard),
    typically 18-34% range (league avg ~24%).
    """
    pid = str(pitcher_id)
    d   = pitcher_k_data.get(pid, {})
    arsenal = pitcher_arsenal.get(pid, [])

    swstr  = _safe(d.get("swstr_pct"))  # whiff% per swing (18-34% range)
    k_pct  = _safe(d.get("k_pct"))      # strikeout %
    bb_pct = _safe(d.get("bb_pct"))     # walk %

    # Scale — swstr is whiff/swing (avg ~24%, elite ~32%)
    s_swstr   = _scale(swstr,  16.0, 24.0, 34.0)       # 24% = avg, 34% = elite
    s_k       = _scale(k_pct,  13.0, 22.0, 35.0)        # 22% = avg, 35% = elite
    s_command = _scale(14.0 - bb_pct, 3.0, 7.0, 11.0)   # low BB% = good command

    if swstr == 0 and k_pct == 0:
        score = 0.0
    else:
        score = (s_swstr * 0.55 + s_k * 0.30 + s_command * 0.15)

    # Tier
    if score >= 72:
        tier = "K ELITE"
    elif score >= 55:
        tier = "K Threat"
    else:
        tier = "Manageable"

    # Top whiff pitches (by pitcher whiff% per pitch type)
    top_whiff = sorted(
        [p for p in arsenal if (p.get("whiff_pct") or 0) >= 15],
        key=lambda x: -(x.get("whiff_pct") or 0)
    )[:3]

    return {
        "score":    round(score, 1),
        "tier":     tier,
        "swstr_pct": swstr,
        "k_pct":    k_pct,
        "bb_pct":   bb_pct,
        "top_whiff_pitches": top_whiff,
        "components": {
            "s_swstr": round(s_swstr, 1),
            "s_k":     round(s_k, 1),
            "s_cmd":   round(s_command, 1),
        },
    }


def _proj_k_line(pitcher_k_data: dict, pitcher_id: int, opp_k_pct: float,
                 proj_bf: float = LEAGUE_BF_SP) -> dict:
    """
    Project K count and nearest prop line with Poisson over/under %.
    """
    pid = str(pitcher_id)
    d = pitcher_k_data.get(pid, {})
    p_k_pct = _safe(d.get("k_pct")) or LEAGUE_K_PCT

    # Blend: 65% pitcher, 35% opponent lineup
    opp = opp_k_pct if opp_k_pct > 0 else LEAGUE_K_PCT
    blended_k_pct = (p_k_pct * 0.65 + opp * 0.35) / 100.0

    lam = blended_k_pct * proj_bf  # expected K count (λ for Poisson)
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

    return {
        "proj_k":    round(lam, 1),
        "line":      line,
        "over_pct":  over_pct,
        "under_pct": under_pct,
        "over_odds": _to_odds(over_pct),
        "under_odds": _to_odds(under_pct),
        "confidence": confidence,
        "blended_k_pct": round(blended_k_pct * 100, 1),
        "pitcher_k_pct": round(p_k_pct, 1),
        "opp_k_pct": round(opp, 1),
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

            proj = _proj_k_line(pitcher_k_data, pitcher_id, opp_k_pct)

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
    W = 94

    lines.append("=" * W)
    lines.append(f"  K PROP BOARD — {game_date}")
    lines.append("  Pitcher K Score: SwStr%(40) + CSW%(35) + K%(15) + Command(10)  |  Batter Vuln: K% + ArsnlWhiff + SwStr%")
    lines.append("=" * W)

    # Summary table header
    lines.append("")
    lines.append(f"  {'PITCHER':<22} {'OPP':<5} {'K_SCR':>6} {'TIER':<14} {'K%':>6} {'Whiff/Sw':>9} {'BB%':>5} {'PROJ':>5} {'LINE':>5} {'OPP_K%':>7}")
    lines.append("  " + "-" * 90)

    for r in results:
        ks   = r["k_score"]
        proj = r["proj"]
        tier_sym = ("★" if ks["tier"] == "K ELITE"
                    else "◎" if ks["tier"] == "K Threat"
                    else "○")
        tier_str = f"{tier_sym} {ks['tier']}"

        k_pct    = _fmt(ks["k_pct"],    ".1f", "%", "   -")
        swstr    = _fmt(ks["swstr_pct"], ".1f", "%", "   -")
        bb       = _fmt(ks["bb_pct"],    ".1f", "%", "   -")
        proj_k   = _fmt(proj["proj_k"],  ".1f", "",  "  -")
        line_str = f"{proj['line']:.1f}"
        opp_k    = _fmt(r["opp_k_pct"], ".1f", "%", "   -")

        lines.append(
            f"  {r['pitcher_name']:<22} {r['opp_team']:<5} {ks['score']:>6.1f} {tier_str:<14} "
            f"{k_pct:>6} {swstr:>9} {bb:>5} {proj_k:>5} {line_str:>5} {opp_k:>7}"
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
        lines.append(
            f"  │  K Score: {ks['score']} {tier_sym} {ks['tier']}  │  "
            f"K%: {_fmt(ks['k_pct'],'.1f','%')}  Whiff/Swing: {_fmt(ks['swstr_pct'],'.1f','%')}  "
            f"BB%: {_fmt(ks['bb_pct'],'.1f','%')}"
        )
        lines.append(
            f"  │  Proj K: {proj['proj_k']}  Line: {proj['line']:.1f}  "
            f"Over: {proj['over_pct']}% ({proj['over_odds']})  "
            f"Under: {proj['under_pct']}% ({proj['under_odds']})"
            f"{conf_badge}"
        )
        lines.append(
            f"  │  Opp {r['opp_team']} lineup K%: {_fmt(r['opp_k_pct'],'.1f','%')}  "
            f"Blended K%: {_fmt(proj['blended_k_pct'],'.1f','%')}  "
            f"{hand_note}"
        )
        if ars_str:
            lines.append(f"  │  Arsenal: {ars_str}")
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
