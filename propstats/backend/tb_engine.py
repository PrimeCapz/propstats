"""
tb_engine.py — Batter Total Bases O/U board.

TB Score (0-100, high = extra-base likely):
  xSLG (30%) + ISO (25%) + Barrel% (25%) + Pull% / hard-hit blend (20%)

Projected TB:
  lambda = (batter_xslg × exp_ab × park_hr_factor × pitcher_vuln) / tb_per_hit_ratio
  Poisson P(≥1), P(≥2), P(≥3), P(≥4) for TB lines 0.5 / 1.5 / 2.5 / 3.5

Pitcher matchup:
  Pitcher HR/9 + FB% allowed → determines if extra bases are elevated/suppressed
  L5 pitcher HR rate used when available

Batter tiers:
  XB MACHINE ≥72 | XB LIKELY 56-72 | NEUTRAL <56
"""

import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from baseball_engine import (
    shrink_rate,
    pa_split,
    PEN_SLG_MULT,
    LEAGUE_AB_RATE,
    _get, MLB_API,
    get_today_games,
    get_team_roster_ids,
    get_pitcher_throws,
    get_park_hr_factor,
    load_savant_xstats,
    load_savant_batter_hr,
    load_savant_batting,
    load_savant_pitcher_k,
    load_savant_pitcher_hr,
    PARK_FACTORS,
)

LEAGUE_XSLG   = 0.400   # MLB avg xSLG
LEAGUE_BA     = 0.244   # MLB avg BA (2026 season, 153,666 AB)
LEAGUE_ISO    = 0.152   # MLB avg ISO
LEAGUE_BRL    = 7.0     # MLB avg barrel%
LEAGUE_TB9    = 14.5    # MLB avg TB/9 allowed by SP
LEAGUE_AB_SP  = 22.0    # avg AB vs SP per game
LEAGUE_BF_SP  = 25.0    # avg SP batters faced


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


# ---------------------------------------------------------------------------
# Pitcher TB profile
# ---------------------------------------------------------------------------
_pitcher_tb_cache: dict = {}


def _pitcher_tb_profile(pitcher_id: int, season: int) -> dict:
    """
    Return pitcher TB-allowed tendency from last 5 starts.
    tb_pg: total bases allowed per game
    tb_vuln: multiplier 0.85 – 1.20
    """
    cache_key = (pitcher_id, season)
    if cache_key in _pitcher_tb_cache:
        return _pitcher_tb_cache[cache_key]

    result = {"tb_pg": 0.0, "tb_vuln": 1.0, "label": ""}
    try:
        url = (
            f"{MLB_API}/people/{pitcher_id}/stats"
            f"?stats=gameLog&group=pitching&season={season}&gameType=R"
        )
        data = _get(url)
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [s for s in splits if _safe(s.get("stat", {}).get("inningsPitched", 0)) >= 1.0][-5:]
        if not starts:
            _pitcher_tb_cache[cache_key] = result
            return result

        total_tb = 0.0
        for s in starts:
            st = s.get("stat", {})
            h  = _safe(st.get("hits"))
            bb = _safe(st.get("baseOnBalls"))
            hr = _safe(st.get("homeRuns"))
            # Estimate XB from available data: doubles + triples ~ hits*0.22 typical
            est_singles = h - hr - (h * 0.22)
            tb = est_singles + (h * 0.22 * 2.5) + (hr * 4)
            total_tb += max(tb, 0)

        n = len(starts)
        tb_pg = round(total_tb / n, 2) if n else 0.0
        result["tb_pg"] = tb_pg

        if tb_pg >= 18.0:
            result["tb_vuln"] = 1.20
            result["label"] = "L5 TB VULN"
        elif tb_pg >= 14.0:
            result["tb_vuln"] = 1.10
            result["label"] = "L5 TB ELEV"
        elif tb_pg <= 8.0 and n >= 3:
            result["tb_vuln"] = 0.82
            result["label"] = "L5 TB LOCK"
        elif tb_pg <= 11.0 and n >= 3:
            result["tb_vuln"] = 0.90
            result["label"] = "L5 TB LOW"

    except Exception:
        pass

    _pitcher_tb_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Batter TB score
# ---------------------------------------------------------------------------

def _batter_tb_score(
    batter_id: int,
    xstats: dict,
    batter_hr_data: dict,
    savant_batting: dict,
) -> dict:
    """
    Score a batter 0-100 for total-base potential.
    xSLG (30%) + ISO (25%) + Barrel% (25%) + pull/hard-hit blend (20%)
    """
    xs = xstats.get(str(batter_id), {})
    hr = batter_hr_data.get(str(batter_id), {})
    sb = savant_batting.get(str(batter_id), {})

    xs_pa     = int(xs.get("pa") or 0)
    # Regress by sample size so 40-PA call-ups stop topping the board.
    xslg      = shrink_rate(_safe(xs.get("xslg") or xs.get("est_slg")), xs_pa, LEAGUE_XSLG)
    iso       = _safe(hr.get("iso"))
    brl_pct   = _safe(hr.get("brl_percent") or sb.get("barrel_batted_rate"))
    pull_pct  = _safe(hr.get("pull_percent") or sb.get("pull_percent"))
    hard_pct  = _safe(hr.get("hard_hit_percent") or sb.get("hard_hit_percent"))

    # Blend pull% and hard-hit% for power direction signal
    power_blend = pull_pct * 0.55 + hard_pct * 0.45 if (pull_pct > 0 or hard_pct > 0) else 0.0

    s_xslg  = _scale(xslg,       0.280, LEAGUE_XSLG, 0.560)
    s_iso   = _scale(iso,        0.080, LEAGUE_ISO,  0.280)
    s_brl   = _scale(brl_pct,   2.0,   LEAGUE_BRL,  16.0)
    s_power = _scale(power_blend, 22.0, 38.0,        58.0)

    if xslg > 0 and iso > 0 and brl_pct > 0:
        score = s_xslg * 0.30 + s_iso * 0.25 + s_brl * 0.25 + s_power * 0.20
    elif xslg > 0 and iso > 0:
        score = s_xslg * 0.38 + s_iso * 0.32 + s_brl * 0.15 + s_power * 0.15
    elif xslg > 0:
        score = s_xslg * 0.50 + s_iso * 0.25 + s_power * 0.25
    else:
        score = 50.0  # no data — league neutral

    if score >= 72:
        tier = "XB MACHINE"
    elif score >= 56:
        tier = "XB LIKELY"
    else:
        tier = "NEUTRAL"

    return {
        "score": round(score, 1),
        "tier":  tier,
        "xstat_pa": xs_pa,
        "thin_sample": xs_pa < 120,
        "xslg":  round(xslg, 3),
        "iso":   round(iso, 3),
        "brl_pct": round(brl_pct, 1),
        "pull_pct": round(pull_pct, 1),
        "hard_pct": round(hard_pct, 1),
    }


# ---------------------------------------------------------------------------
# TB projection
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Total-bases distribution
# ---------------------------------------------------------------------------
# Total bases are NOT Poisson. Measured over 720 confirmed starters (three
# Sep-2026 slates, mean 1.50 TB), the real distribution is zero-inflated with a
# fat spike at 4:
#     TB      0      1      2      3      4      5      6+
#   actual 36.9%  27.2%  13.6%   5.0%   9.4%   4.0%   3.8%
#   Poisson 22.3% 33.5%  25.1%  12.5%   4.7%   1.4%   0.4%
# Poisson understates P(0 TB) by 15 points and misses the home-run spike
# entirely, so P(2+) came out badly wrong in both directions depending on lambda.
# Modelling each AB as a categorical outcome and convolving is exact and cheap.

# League hit mix, 2026 season totals (153,666 AB / 37,501 H, 1.642 bases per hit)
LEAGUE_HIT_MIX = {1: 0.6544, 2: 0.1890, 3: 0.0165, 4: 0.1401}


def _hit_mix(ba: float, slg: float) -> dict:
    """Split a batter's hits into 1B/2B/3B/HR shares matching their SLG/BA.

    Starts from the league mix and moves weight between singles and home runs
    until the mean bases per hit equals slg/ba, holding doubles and triples at
    league rates (they vary far less between hitters than power does).
    """
    if ba <= 0:
        return dict(LEAGUE_HIT_MIX)
    target = max(1.05, min(2.60, slg / ba))
    s2, s3 = LEAGUE_HIT_MIX[2], LEAGUE_HIT_MIX[3]
    # remaining share splits between 1B (1 base) and HR (4 bases):
    #   s1 + s4 = R  and  s1 + 4*s4 = target - 2*s2 - 3*s3
    R = 1.0 - s2 - s3
    need = target - 2 * s2 - 3 * s3
    s4 = (need - R) / 3.0
    s4 = max(0.0, min(R, s4))
    return {1: R - s4, 2: s2, 3: s3, 4: s4}


def _tb_distribution(ba: float, slg: float, exp_ab: float, max_tb: int = 12) -> list:
    """Exact P(total bases = k) for a batter over exp_ab at-bats.

    Each AB is categorical over {0,1,2,3,4} bases; the per-AB distribution is
    convolved exp_ab times. Fractional AB are handled by mixing the two
    neighbouring integer AB counts.
    """
    ba = max(0.0, min(0.6, ba))
    mix = _hit_mix(ba, slg)
    per_ab = [0.0] * 5
    per_ab[0] = 1.0 - ba
    for bases, share in mix.items():
        per_ab[bases] += ba * share

    def convolve(n: int) -> list:
        dist = [1.0] + [0.0] * max_tb
        for _ in range(n):
            nxt = [0.0] * (max_tb + 1)
            for k, pk in enumerate(dist):
                if pk <= 0:
                    continue
                for b, pb in enumerate(per_ab):
                    if pb <= 0:
                        continue
                    nxt[min(k + b, max_tb)] += pk * pb
            dist = nxt
        return dist

    lo = max(1, int(exp_ab))
    frac = exp_ab - lo
    d_lo = convolve(lo)
    if frac <= 0.001:
        return d_lo
    d_hi = convolve(lo + 1)
    return [d_lo[i] * (1 - frac) + d_hi[i] * frac for i in range(max_tb + 1)]


def _tb_at_least(dist: list, k: int) -> float:
    return sum(dist[k:]) if k < len(dist) else 0.0


def _proj_tb(
    batter_score: float,
    batter_bats: str,
    venue_name: str,
    pitcher_hr_data: dict,
    pitcher_id: int,
    season: int,
    xslg: float,
    iso: float,
    tb_profile: dict,
    order=None,
) -> dict:
    """
    Project TB λ and Poisson probabilities for 0.5 / 1.5 / 2.5 / 3.5 lines.

    λ = blended_slg × exp_ab × park_hr × pitcher_vuln
    TB is derived from SLG (TB per AB by definition).
    """
    # Full-game opportunity: the TB prop settles on the whole game, so AB against
    # the bullpen count as well as the ~3 PA against the starter.
    score_factor = 0.85 + (batter_score / 100.0) * 0.30   # 0.85–1.15 quality tilt
    pa_sp, pa_pen = pa_split(order)
    ab_sp  = pa_sp * score_factor * 0.915                  # 0.915 = (1 - league BB%)
    ab_pen = pa_pen * LEAGUE_AB_RATE
    exp_ab = round(ab_sp + ab_pen, 2)

    # Blended SLG
    ph = pitcher_hr_data.get(str(pitcher_id), {})
    p_slga = _safe(ph.get("slg_against") or ph.get("xslg_against"))
    blended_slg = xslg * 0.60 + (p_slga if p_slga > 0 else LEAGUE_XSLG) * 0.40 \
        if xslg > 0 else LEAGUE_XSLG

    # Park factor
    park_hr = get_park_hr_factor(venue_name, batter_bats)

    # Pitcher TB vulnerability
    tb_vuln = tb_profile.get("tb_vuln", 1.0)

    # Pitcher-specific SLG blend and vulnerability apply to the AB against the
    # starter only; bullpen AB use the batter's own xSLG at the league pen mult.
    base_slg = xslg if xslg > 0 else LEAGUE_XSLG
    lam = (blended_slg * ab_sp * tb_vuln + base_slg * ab_pen * PEN_SLG_MULT) * park_hr

    # Convert the projected SLG back to a per-AB hit rate, then take the exact
    # compound distribution rather than a Poisson on lambda.
    eff_slg = lam / exp_ab if exp_ab > 0 else LEAGUE_XSLG
    eff_ba  = eff_slg / max(1.05, LEAGUE_XSLG / max(0.001, LEAGUE_BA))
    tb_dist = _tb_distribution(eff_ba, eff_slg, exp_ab)

    p1 = round(_tb_at_least(tb_dist, 1) * 100, 1)  # P(TB ≥ 1)  → O0.5
    p2 = round(_tb_at_least(tb_dist, 2) * 100, 1)  # P(TB ≥ 2)  → O1.5
    p3 = round(_tb_at_least(tb_dist, 3) * 100, 1)  # P(TB ≥ 3)  → O2.5
    p4 = round(_tb_at_least(tb_dist, 4) * 100, 1)  # P(TB ≥ 4)  → O3.5

    if p3 >= 55:
        conf = "STRONG O2.5"
    elif p3 >= 44:
        conf = "LEAN O2.5"
    elif p2 >= 62:
        conf = "STRONG O1.5"
    elif p2 >= 52:
        conf = "LEAN O1.5"
    elif p2 < 38:
        conf = "LEAN U1.5"
    else:
        conf = "NEUTRAL"

    return {
        "lam":  round(lam, 3),
        "p1":   p1,
        "p2":   p2,
        "p3":   p3,
        "p4":   p4,
        "conf": conf,
        "exp_ab": exp_ab,
        "ab_vs_sp": round(ab_sp, 2),
        "ab_vs_pen": round(ab_pen, 2),
    }


# ---------------------------------------------------------------------------
# Build board
# ---------------------------------------------------------------------------

def build_tb_board(game_date: str = None) -> list:
    if not game_date:
        game_date = datetime.now().strftime("%Y-%m-%d")

    season = int(game_date[:4])
    games  = get_today_games(game_date)
    if not games:
        return []

    # Load Savant caches
    xstats          = load_savant_xstats(season)
    batter_hr_data  = load_savant_batter_hr(season)
    savant_batting  = load_savant_batting(season)
    pitcher_k_data  = load_savant_pitcher_k(season)
    pitcher_hr_data = load_savant_pitcher_hr(season)

    rows = []
    for game in games:
        game_pk      = game.get("game_pk")
        venue_name   = game.get("venue_name", "")
        away_team_id = game["away"]["team_id"]
        home_team_id = game["home"]["team_id"]
        sp_away_id   = game["away"]["probable_pitcher"]["id"]
        sp_home_id   = game["home"]["probable_pitcher"]["id"]
        sp_away_name = game["away"]["probable_pitcher"]["name"]
        sp_home_name = game["home"]["probable_pitcher"]["name"]

        for team_id, opp_sp_id, opp_sp_name in [
            (away_team_id, sp_home_id, sp_home_name),
            (home_team_id, sp_away_id, sp_away_name),
        ]:
            if not team_id or not opp_sp_id:
                continue

            # Get pitcher data
            p_throws = get_pitcher_throws(opp_sp_id)
            tb_profile = _pitcher_tb_profile(opp_sp_id, season)

            # Get roster batters
            try:
                roster = get_team_roster_ids(team_id, season)
            except Exception:
                continue

            for b in roster:
                batter_id   = b.get("id")
                batter_name = b.get("name", "")
                batter_bats = b.get("bats", "R")
                if not batter_id:
                    continue

                score_data = _batter_tb_score(batter_id, xstats, batter_hr_data, savant_batting)
                proj = _proj_tb(
                    batter_score=score_data["score"],
                    batter_bats=batter_bats or "R",
                    venue_name=venue_name,
                    pitcher_hr_data=pitcher_hr_data,
                    pitcher_id=opp_sp_id,
                    season=season,
                    xslg=score_data["xslg"],
                    iso=score_data["iso"],
                    tb_profile=tb_profile,
                )

                rows.append({
                    "game_pk":       game_pk,
                    "game_date":     game_date,
                    "venue":         venue_name,
                    "batter_id":     batter_id,
                    "batter_name":   batter_name,
                    "batter_bats":   batter_bats or "R",
                    "opp_sp_id":     opp_sp_id,
                    "opp_sp_name":   opp_sp_name,
                    "p_throws":      p_throws,
                    "tb_score":      score_data["score"],
                    "tier":          score_data["tier"],
                    "xslg":          score_data["xslg"],
                    "xstat_pa":      score_data.get("xstat_pa", 0),
                    "thin_sample":   score_data.get("thin_sample", False),
                    "iso":           score_data["iso"],
                    "brl_pct":       score_data["brl_pct"],
                    "pull_pct":      score_data["pull_pct"],
                    "hard_pct":      score_data["hard_pct"],
                    "lam":           proj["lam"],
                    "p1":            proj["p1"],
                    "p2":            proj["p2"],
                    "p3":            proj["p3"],
                    "p4":            proj["p4"],
                    "conf":          proj["conf"],
                    "exp_ab":        proj["exp_ab"],
                    "tb_pg":         tb_profile.get("tb_pg", 0.0),
                    "tb_label":      tb_profile.get("label", ""),
                })

    rows.sort(key=lambda r: r["p3"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Format board
# ---------------------------------------------------------------------------

def format_tb_board(rows: list, top_n: int = 60) -> str:
    if not rows:
        return "No TB board data available.\n"

    date_str = rows[0].get("game_date", "Today") if rows else "Today"
    lines    = [f"TOTAL BASES PROP BOARD — {date_str}", "=" * 68, ""]

    # Group by game/pitcher
    from collections import defaultdict
    by_sp: dict = defaultdict(list)
    for r in rows:
        key = (r["game_pk"], r["opp_sp_id"])
        by_sp[key].append(r)

    # Sort pitcher groups by average p3
    def _avg_p3(group):
        return sum(r["p3"] for r in group) / len(group) if group else 0.0

    sorted_groups = sorted(by_sp.values(), key=_avg_p3, reverse=True)

    printed = 0
    for group in sorted_groups:
        if printed >= top_n:
            break
        sp_name  = group[0]["opp_sp_name"]
        p_throws = group[0]["p_throws"]
        venue    = group[0]["venue"]
        tb_lbl   = group[0]["tb_label"]

        header = f"vs {sp_name} ({p_throws}) @ {venue}"
        if tb_lbl:
            header += f"  [{tb_lbl}]"
        lines.append(header)
        lines.append("-" * len(header))

        group_sorted = sorted(group, key=lambda r: r["p3"], reverse=True)
        for r in group_sorted[:12]:
            tier     = r["tier"]
            name     = r["batter_name"]
            bats     = r["batter_bats"]
            xslg_str = f"xSLG:{r['xslg']:.3f}" if r["xslg"] > 0 else ""
            iso_str  = f"ISO:{r['iso']:.3f}" if r["iso"] > 0 else ""
            brl_str  = f"BRL:{r['brl_pct']:.1f}%" if r["brl_pct"] > 0 else ""
            conf     = r["conf"]
            p2       = r["p2"]
            p3       = r["p3"]
            p4       = r["p4"]

            stats_parts = [s for s in [xslg_str, iso_str, brl_str] if s]
            stats_str   = "  ".join(stats_parts)

            tier_tag = f"[{tier}]" if tier != "NEUTRAL" else ""
            lines.append(
                f"  {name:<22} {bats}  {tier_tag:<14}"
                f"  O0.5:{r['p1']:4.1f}%  O1.5:{p2:4.1f}%  O2.5:{p3:4.1f}%  O3.5:{p4:4.1f}%"
                f"  [{conf}]"
            )
            if stats_str:
                lines.append(f"    {stats_str}")
            printed += 1

        lines.append("")

    # XB MACHINE callout section
    machines = [r for r in rows if r["tier"] == "XB MACHINE"]
    if machines:
        lines.append("=" * 68)
        lines.append("XB MACHINE TARGETS")
        lines.append("-" * 40)
        for r in sorted(machines, key=lambda x: x["p3"], reverse=True)[:15]:
            lines.append(
                f"  {r['batter_name']:<22} vs {r['opp_sp_name']:<20}"
                f"  O2.5:{r['p3']:4.1f}%  [{r['conf']}]"
            )
        lines.append("")

    return "\n".join(lines)
