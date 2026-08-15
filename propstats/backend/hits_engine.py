"""
hits_engine.py — Batter Hits O/U 1.5 prop board.

Hit Score (0-100, high = hit-likely):
  xBA (30%) + LD% (25%) + BABIP vs pitcher (20%) + Contact% proxy (15%) + GB% bonus (10%)
  GB% bonus: ground ball hitters get more infield hits

Projected Hits:
  proj_h = blended_contact_rate × exp_AB × park_hit_factor
  Poisson P(≥1), P(≥2) for O/U 0.5, 1.5, 2.5 lines

Pitcher matchup:
  Pitcher H/9 allowed (recent 5 starts), BABIP allowed, GB% allowed
  High GB% allowed pitcher = more hits allowed (more balls in play)

Batter tiers:
  HIT MACHINE ≥70 | HIT LIKELY 55-70 | NEUTRAL <55
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
    get_batter_handedness_splits,
    load_savant_xstats,
    load_savant_batter_hr,
    load_savant_batting,
    load_savant_pitcher_k,
    load_savant_pitcher_hr,
    PARK_FACTORS,
)

LEAGUE_BA    = 0.248   # MLB avg batting average
LEAGUE_LD    = 21.5    # MLB avg LD%
LEAGUE_BABIP = 0.298   # MLB avg BABIP
LEAGUE_GB    = 44.0    # MLB avg GB%
LEAGUE_H9    = 8.5     # MLB avg hits allowed per 9 innings
LEAGUE_AB_SP = 22.0    # avg AB faced by SP (BF 25 minus BB/K)
LEAGUE_BF_SP = 25.0    # avg SP batters faced


def _safe(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "-") else default
    except Exception:
        return default


def _scale(val, lo, mid, hi):
    if val is None:
        return 0.0
    if val <= lo:
        return 0.0
    if val >= hi:
        return 100.0
    if val <= mid:
        return 50.0 * (val - lo) / (mid - lo)
    return 50.0 + 50.0 * (val - mid) / (hi - mid)


def _poisson_at_least(lam: float, k: int) -> float:
    """P(X >= k) for Poisson(λ). Returns 0-100."""
    cdf = sum(math.exp(-lam) * (lam ** i) / math.factorial(i) for i in range(k))
    return round((1 - cdf) * 100, 1)


def _pitcher_h_profile(pitcher_id: int, season: int) -> dict:
    """H/9 allowed + BABIP-proxy from last 5 starts and season stats."""
    default = {"h9_recent": LEAGUE_H9, "h9_season": LEAGUE_H9,
               "gb_pct_allowed": LEAGUE_GB, "k_pct": 22.0, "label": ""}
    try:
        url = (f"{MLB_API}/people/{pitcher_id}/stats"
               f"?stats=gameLog&group=pitching&season={season}&sportId=1")
        data = _get(url) or {}
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [s for s in splits
                  if _safe(s.get("stat", {}).get("inningsPitched")) >= 1.0][-5:]
        if not starts:
            return default

        total_h  = sum(int(_safe(s["stat"].get("hits", 0))) for s in starts)
        total_ip = sum(_safe(s["stat"].get("inningsPitched")) for s in starts)
        h9_recent = (total_h / total_ip * 9) if total_ip > 0 else LEAGUE_H9

        if h9_recent >= 10.5:
            label = f"HIT PRONE ({h9_recent:.1f} H/9 L5)"
        elif h9_recent <= 6.5:
            label = f"HIT SUPPRESSOR ({h9_recent:.1f} H/9 L5)"
        else:
            label = ""

        return {
            "h9_recent":      round(h9_recent, 2),
            "h9_season":      LEAGUE_H9,  # season H/9 from pitcher stats
            "gb_pct_allowed": LEAGUE_GB,  # from Savant pitcher_hr data
            "k_pct":          22.0,
            "label":          label,
        }
    except Exception:
        return default


def _batter_hit_score(batter_id: int, xstats: dict, batter_hr_data: dict,
                      savant_batting: dict) -> dict:
    """
    0-100 Hit Score for a batter.
    xBA (30%) + LD% (25%) + Hard Hit% proxy (20%) + Contact (15%) + GB% (10%)
    """
    pid = str(batter_id)
    xs  = xstats.get(pid, {})
    d   = batter_hr_data.get(pid, {})
    ev  = savant_batting.get(pid, {})

    xba      = _safe(xs.get("xba"))          # expected batting average
    ba       = _safe(xs.get("ba"))           # actual season BA
    ld_pct   = _safe(d.get("la_avg"))        # proxy for LD% via launch angle
    hh_pct   = _safe(ev.get("hard_hit_pct"))
    gb_pct   = _safe(d.get("fb_pct"))        # we'll use inverse of FB% as GB proxy
    sweet    = _safe(d.get("sweet_spot_pct")) # sweet spot pct is contact quality proxy
    xslg     = _safe(d.get("xslg"))

    # Use xBA if available, fall back to actual BA
    contact_ba = xba if xba > 0 else ba if ba > 0 else LEAGUE_BA

    # LD% proxy: ideal launch angle 10-20° → high LD%. We infer from la_avg.
    # If la_avg 10-18° → elite LD%, 18-22° gap power, <8° GB, >25° FB
    la_avg = _safe(d.get("la_avg"))
    if 10.0 <= la_avg <= 18.0:
        ld_proxy = 28.0 + (18.0 - abs(la_avg - 14.0)) * 1.5  # peaks at 14°
    elif la_avg > 0:
        ld_proxy = max(14.0, 28.0 - abs(la_avg - 14.0) * 2.0)
    else:
        ld_proxy = LEAGUE_LD

    # Contact quality via hard hit% and sweet spot
    contact_score = sweet * 0.5 + hh_pct * 0.5 if (sweet > 0 and hh_pct > 0) else (sweet or hh_pct)

    # GB% proxy: low LA → more ground balls → more infield hits
    gb_bonus = max(0.0, (8.0 - max(0.0, la_avg)) * 1.5) if la_avg > 0 else 0.0

    s_xba      = _scale(contact_ba, 0.200, 0.250, 0.340)
    s_ld       = _scale(ld_proxy,   14.0,  22.0,  32.0)
    s_contact  = _scale(contact_score, 25.0, 38.0, 52.0)
    s_xslg     = _scale(xslg,       0.300, 0.420, 0.600)  # power contact = extra hits

    if contact_ba == 0 and ld_proxy == LEAGUE_LD:
        score = 0.0
        data_sparse = True
    else:
        data_sparse = False
        score = (s_xba * 0.35 + s_ld * 0.28 + s_contact * 0.22
                 + s_xslg * 0.10 + min(15.0, gb_bonus) * 0.05)

    if data_sparse:
        tier = "DATA SPARSE"
    elif score >= 70:
        tier = "HIT MACHINE"
    elif score >= 55:
        tier = "HIT LIKELY"
    else:
        tier = "NEUTRAL"

    tags = []
    if contact_ba >= 0.300:
        tags.append(f"HIGH xBA ({contact_ba:.3f})")
    if ld_proxy >= 26.0:
        tags.append(f"LINE DRIVE ({ld_proxy:.0f}%LD)")
    if gb_bonus >= 5.0:
        tags.append("GB INFIELD HIT")
    if xslg >= 0.500:
        tags.append(f"POWER CONTACT ({xslg:.3f}xSLG)")

    return {
        "hit_score":   round(score, 1),
        "tier":        tier,
        "xba":         round(contact_ba, 3),
        "ld_proxy":    round(ld_proxy, 1),
        "hh_pct":      round(hh_pct, 1),
        "xslg":        round(xslg, 3),
        "tags":        tags,
        "data_sparse": data_sparse,
    }


def _proj_hits(batter_id: int, pitcher_id: int, xstats: dict, batter_hr_data: dict,
               savant_batting: dict, pitcher_k_data: dict, pitcher_h_profile: dict,
               venue_name: str, bats: str = "R", p_throws: str = "R",
               season: int = None) -> dict:
    """Project hit count and compute Poisson P(≥1), P(≥2).
    p_throws: pitcher handedness ('L'/'R') used for batter vs-hand splits.
    """
    pid = str(batter_id)
    ppid = str(pitcher_id)

    xs = xstats.get(pid, {})
    ba = _safe(xs.get("xba")) or _safe(xs.get("ba")) or LEAGUE_BA

    # Pitcher K% reduces expected AB contact
    pk = pitcher_k_data.get(ppid, {})
    pitcher_k_pct = _safe(pk.get("k_pct")) or 22.0
    pitcher_bb_pct = _safe(pk.get("bb_pct")) or 8.5

    # Expected AB = BF × (1 - BB% - K%) × contact_factor
    exp_ab = LEAGUE_BF_SP * (1.0 - (pitcher_k_pct + pitcher_bb_pct) / 100.0)
    exp_ab = max(8.0, exp_ab)

    # Park hit factor
    park_hit = 1.0
    for park, factors in PARK_FACTORS.items():
        if park.lower() in venue_name.lower() or venue_name.lower() in park.lower():
            park_hit = factors.get("hit", 1.0)
            break

    # Pitcher H/9 adjustment
    h9_ratio = pitcher_h_profile.get("h9_recent", LEAGUE_H9) / LEAGUE_H9
    blended_ba = ba * h9_ratio * 0.6 + ba * 0.4  # 60% weight on pitcher H/9 adj

    # Batter vs pitcher handedness: season split BA modifier
    hand_adj = 1.0
    hand_label = ""
    if season and p_throws in ("L", "R"):
        split_key = "vs_l" if p_throws == "L" else "vs_r"
        splits = get_batter_handedness_splits(batter_id, season)
        hand_split = splits.get(split_key, {})
        split_ba = hand_split.get("ba", 0.0)
        split_pa = hand_split.get("pa", 0)
        if split_ba > 0 and split_pa >= 30:
            # Compare split BA to overall xBA; blend 50/50 for stability
            hand_adj = (split_ba / ba) * 0.50 + 1.0 * 0.50 if ba > 0 else 1.0
            hand_adj = max(0.78, min(1.28, hand_adj))  # cap at ±28%
            if hand_adj >= 1.12:
                hand_label = f"HOT vs {p_throws}HP BA:{split_ba:.3f}"
            elif hand_adj <= 0.88:
                hand_label = f"COLD vs {p_throws}HP BA:{split_ba:.3f}"

    lam = blended_ba * exp_ab * park_hit * hand_adj
    lam = max(0.1, lam)

    p1 = _poisson_at_least(lam, 1)   # P(≥1 hit)
    p2 = _poisson_at_least(lam, 2)   # P(≥2 hits)
    p3 = _poisson_at_least(lam, 3)   # P(≥3 hits)

    if p2 >= 62:
        confidence = "STRONG O1.5"
    elif p2 >= 54:
        confidence = "LEAN O1.5"
    elif (100 - p1) >= 62:
        confidence = "STRONG U0.5"
    elif (100 - p1) >= 54:
        confidence = "LEAN U0.5"
    elif p1 >= 72:
        confidence = "LEAN O0.5"
    else:
        confidence = "NEUTRAL"

    return {
        "proj_h":     round(lam, 2),
        "p_1plus":    p1,
        "p_2plus":    p2,
        "p_3plus":    p3,
        "exp_ab":     round(exp_ab, 1),
        "blended_ba": round(blended_ba, 3),
        "park_hit":   round(park_hit, 2),
        "hand_adj":   round(hand_adj, 3),
        "hand_label": hand_label,
        "confidence": confidence,
    }


def build_hits_board(game_date: str) -> list:
    """
    Hits O/U prop board for all batters on game_date.
    Returns list of per-pitcher matchup entries, sorted by pitcher K% ascending
    (low-K pitchers allow more hits).
    """
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    xstats          = load_savant_xstats(season)
    batter_hr_data  = load_savant_batter_hr(season)
    savant_batting  = load_savant_batting(season)
    pitcher_k_data  = load_savant_pitcher_k(season)
    pitcher_hr_data = load_savant_pitcher_hr(season)

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
            time.sleep(0.08)

            h_profile = _pitcher_h_profile(pitcher_id, season)
            time.sleep(0.08)

            roster = get_team_roster_ids(opp_team_id, season)
            time.sleep(0.12)

            # Score every roster batter
            batter_entries = []
            for b in roster:
                bid = b.get("id")
                if not bid:
                    continue
                hs = _batter_hit_score(bid, xstats, batter_hr_data, savant_batting)
                proj = _proj_hits(bid, pitcher_id, xstats, batter_hr_data,
                                  savant_batting, pitcher_k_data, h_profile,
                                  venue, b.get("bats", "R"), pitcher_throws, season)
                batter_entries.append({
                    "batter_id":    bid,
                    "batter_name":  b["name"],
                    "bats":         b.get("bats", "R"),
                    "hit_score":    hs["hit_score"],
                    "tier":         hs["tier"],
                    "xba":          hs["xba"],
                    "ld_proxy":     hs["ld_proxy"],
                    "xslg":         hs["xslg"],
                    "tags":         hs["tags"],
                    "hand_label":   proj.get("hand_label", ""),
                    "proj":         proj,
                })

            batter_entries.sort(key=lambda x: -(x["hit_score"]))

            pid_str = str(pitcher_id)
            pk = pitcher_k_data.get(pid_str, {})
            pitcher_k_pct = _safe(pk.get("k_pct")) or 22.0

            results.append({
                "game":           f"{g['away']['team_abbr']}@{g['home']['team_abbr']}",
                "game_pk":        g["game_pk"],
                "venue":          venue,
                "pitcher_id":     pitcher_id,
                "pitcher_name":   pitcher_name,
                "pitcher_team":   g[side]["team_abbr"],
                "pitcher_throws": pitcher_throws,
                "opp_team":       opp_abbr,
                "pitcher_k_pct":  pitcher_k_pct,
                "h_profile":      h_profile,
                "top_batters":    batter_entries[:8],
                "all_batters":    batter_entries,
            })

    # Sort by pitcher K% ascending — low-K pitchers give up more hits
    results.sort(key=lambda x: x["pitcher_k_pct"])
    return results


def format_hits_board(results: list, game_date: str) -> str:
    W = 108
    lines = []
    lines.append("=" * W)
    lines.append(f"  HITS PROP BOARD — {game_date}")
    lines.append("  Hit Score: xBA(35%) + LD%(28%) + Contact(22%) + xSLG(10%) + GB(5%)")
    lines.append("  Sorted by pitcher K% ASC (low-K pitchers allow more contact)")
    lines.append("=" * W)

    for r in results:
        ph = r["h_profile"]
        plab = ph.get("label", "")
        lines.append("")
        lines.append(
            f"  ┌─ {r['pitcher_name']} ({r['pitcher_team']})  vs {r['opp_team']}  "
            f"│  K%={r['pitcher_k_pct']:.1f}%  H/9(L5)={ph['h9_recent']:.1f}"
            + (f"  [{plab}]" if plab else "")
        )
        lines.append(
            f"  │  {'BATTER':<22} {'H':>2}  {'HIT_SC':>6}  {'xBA':>6}  {'LD%':>5}  "
            f"{'PROJ_H':>6}  {'P≥1':>5}  {'P≥2':>5}  {'CONF':<18}  TAGS"
        )
        lines.append(f"  │  {'-' * 96}")
        for b in r["top_batters"]:
            p = b["proj"]
            hit_sc = f"{b['hit_score']:.1f}"
            xba_s  = f".{int(b['xba']*1000):03d}" if b["xba"] else "  -"
            ld_s   = f"{b['ld_proxy']:.0f}%" if b["ld_proxy"] else "  -"
            ph_s   = f"{p['proj_h']:.2f}" if p["proj_h"] else "  -"
            p1_s   = f"{p['p_1plus']:.0f}%"
            p2_s   = f"{p['p_2plus']:.0f}%"
            conf_s = p.get("confidence", "")
            tag_s  = " | ".join(b.get("tags", []))[:40]
            lines.append(
                f"  │  {b['batter_name']:<22} {b['bats']:>2}  {hit_sc:>6}  "
                f"{xba_s:>6}  {ld_s:>5}  {ph_s:>6}  {p1_s:>5}  {p2_s:>5}  "
                f"{conf_s:<18}  {tag_s}"
            )
        lines.append(f"  └{'─' * 96}")

    # Cross-game HIT MACHINE targets
    lines.append("")
    lines.append("=" * W)
    lines.append("  TOP HIT TARGETS (HIT MACHINE tier, P≥2 hits ≥40%)")
    lines.append("=" * W)
    all_machines = []
    for r in results:
        for b in r["all_batters"]:
            if b["tier"] == "HIT MACHINE" or b["proj"]["p_2plus"] >= 40:
                all_machines.append({**b, "game": r["game"], "pitcher_name": r["pitcher_name"]})
    all_machines.sort(key=lambda x: -x["proj"]["p_2plus"])
    for b in all_machines[:12]:
        p = b["proj"]
        lines.append(
            f"  {b['batter_name']:<22} {b['bats']}  "
            f"HitSc={b['hit_score']:.1f}  xBA={b['xba']:.3f}  "
            f"ProjH={p['proj_h']:.2f}  P≥1={p['p_1plus']:.0f}%  P≥2={p['p_2plus']:.0f}%  "
            f"{p['confidence']}  vs {b['pitcher_name']} [{b['game']}]"
        )
    lines.append("")
    lines.append("=" * W)
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    args = ap.parse_args()
    board = build_hits_board(args.date)
    print(format_hits_board(board, args.date))
