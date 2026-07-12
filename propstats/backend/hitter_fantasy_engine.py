"""
Hitter Fantasy Engine — DK/FD/PrizePicks hitter scoring projection
Personal use only.

Fantasy Score (0-100):
  Contact(30%) + Power(25%) + OBP(15%) + PitcherGrade(15%) + ArsenalMatch(15%)

ArsenalMatch: weighted batter xwOBA vs the specific pitcher's pitch mix
  — surfaces hidden gems by pitch-type-specific edge rather than raw talent alone

Form signals (from season xwOBA + BA divergence, zero extra API calls):
  HOT  = xwOBA ≥ 0.380 AND BA ≥ 0.280  (skill converting to results)
  DUE  = xwOBA ≥ 0.360 AND BA < 0.240  (positive regression candidate — hidden gem)
  COLD = xwOBA < 0.280 AND BA < 0.230  (genuinely struggling)
  WARM = otherwise

DK Scoring used for proj_pts:
  1B +3 | 2B +5 | 3B +8 | HR +10 | RBI +3.5 | R +3 | BB +3 | SB +6 | HBP +3
"""

import math
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from baseball_engine import (
    get_today_games,
    get_team_roster_ids,
    load_savant_batting,
    load_savant_xstats,
    load_bat_tracking,
    load_sprint_speed,
    load_savant_batter_k,
    load_savant_pitcher_k,
    load_savant_pitching,
    load_savant_batter_hr,
    load_savant_pitcher_arsenal,
    load_savant_batter_pitch_splits,
    PARK_FACTORS,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe(v, default=0.0):
    try:
        return float(v) if v not in (None, "", "null") else default
    except (ValueError, TypeError):
        return default


def _scale(val, lo, mid, hi):
    """Linear scale: lo→0, mid→50, hi→100 (clamped 0-100)."""
    if val <= lo:
        return 0.0
    if val >= hi:
        return 100.0
    if val <= mid:
        return (val - lo) / (mid - lo) * 50.0
    return 50.0 + (val - mid) / (hi - mid) * 50.0


# ── Pitcher matchup grade ──────────────────────────────────────────────────────
# Returns a 0-100 hitter-friendliness score vs this pitcher
# High = good matchup (soft pitcher), Low = tough matchup (ace)

def _pitcher_matchup_grade(pitcher_id: str,
                           pitcher_k_data: dict,
                           pitching_data: dict) -> dict:
    pk = pitcher_k_data.get(pitcher_id, {})
    pd = pitching_data.get(pitcher_id, {})

    k_pct     = _safe(pk.get("k_pct"))      # pitcher K% — penalty for batter
    bb_pct    = _safe(pk.get("bb_pct"))      # pitcher BB% — bonus for batter OBP
    whiff_sw  = _safe(pk.get("swstr_pct"))   # pitcher whiff/swing
    ev_against = _safe(pd.get("exit_velo_against"))  # lower = pitcher suppresses contact
    hh_against = _safe(pd.get("hard_hit_pct_against"))

    # Invert pitcher dominance → batter opportunity score
    # High K% pitcher = low contact opportunity
    s_contact_opp = _scale(30.0 - k_pct,   -5.0, 8.0, 20.0)   # 22% K = neutral, <15% = soft
    s_walk_opp    = _scale(bb_pct,           2.0, 7.0, 14.0)    # high BB% pitcher = OBP gift
    s_contact_q   = _scale(ev_against,      85.0, 88.5, 92.0)   # higher EV against = softer pitcher
    s_hh_opp      = _scale(hh_against,       5.0, 12.0, 20.0)   # more hard contact allowed = softer

    if ev_against == 0.0:
        s_contact_q = 50.0
        s_hh_opp = 50.0

    grade = s_contact_opp * 0.40 + s_walk_opp * 0.20 + s_contact_q * 0.25 + s_hh_opp * 0.15
    grade = max(0.0, min(100.0, grade))

    tier = (
        "★ Soft Arm" if grade >= 68 else
        "◎ Neutral"  if grade >= 45 else
        "○ Avoid"
    )

    return {
        "grade": round(grade, 1),
        "tier": tier,
        "k_pct": k_pct,
        "bb_pct": bb_pct,
        "whiff_sw": whiff_sw,
    }


# ── Arsenal-weighted contact matchup ──────────────────────────────────────────
# Computes weighted batter xwOBA vs the pitcher's actual pitch mix.
# This is what surfaces hidden gems — a lesser-known batter can have a
# specific pitch-type edge (high xwOBA vs cutter/slider) against a pitcher
# whose arsenal is heavy on exactly those pitches.

def _arsenal_weighted_contact(pitcher_id: str, batter_id: str, batter_hand: str,
                               pitcher_arsenal: dict,
                               batter_pitch_splits: dict) -> dict:
    """Return {score: 0-100, weighted_xwoba: float, top_edges: list[str], pitch_summary: str}

    Uses batter handedness to reweight the pitcher's arsenal — pitchers throw
    different pitch mixes to LHB vs RHB (e.g., Lopez: 61% FB to RHB, 51% to LHB).
    Heuristic adjustments based on known pitcher tendencies by batter hand.
    """
    arsenal = pitcher_arsenal.get(pitcher_id, [])
    b_splits = batter_pitch_splits.get(batter_id, {})

    if not arsenal:
        return {"score": 50.0, "weighted_xwoba": 0.0, "top_edges": [], "pitch_summary": ""}

    # Hand-specific pitch type reweighting heuristics:
    # LHB face more breaking balls from RHP (sweepers/sliders), fewer fastballs
    # RHB face more fastballs from RHP
    # Same-hand matchups: more offspeed, less FB dominance
    is_lhb = batter_hand in ("L", "S")  # S = switch (assume worst case = RHP vs LHB)
    hand_factor = {}
    for pitch in arsenal:
        pt = pitch.get("pitch_type", "").upper()
        base_usage = _safe(pitch.get("usage_pct")) / 100.0
        # RHP vs LHB: more SL/ST/SWP, less FC/SI; vs RHB: more FB, less breaking
        if is_lhb:
            if pt in ("SL", "ST", "CU", "KC"):      # breaking balls↑ vs LHB from RHP
                hand_factor[pt] = base_usage * 1.15
            elif pt in ("FF", "FC", "SI"):           # fastballs↓ vs LHB from RHP
                hand_factor[pt] = base_usage * 0.90
            else:
                hand_factor[pt] = base_usage
        else:
            if pt in ("FF", "SI", "FC"):             # fastballs↑ vs RHB from RHP
                hand_factor[pt] = base_usage * 1.08
            elif pt in ("SL", "ST"):
                hand_factor[pt] = base_usage * 0.92
            else:
                hand_factor[pt] = base_usage

    # Normalize so weights sum to ~1
    total_w = sum(hand_factor.values()) or 1.0
    norm_factor = {pt: w / total_w for pt, w in hand_factor.items()}

    weighted = 0.0
    covered  = 0.0
    edges    = []
    pitch_parts = []

    for pitch in sorted(arsenal, key=lambda x: _safe(x.get("usage_pct")), reverse=True):
        pt    = pitch.get("pitch_type", "").upper()
        usage = norm_factor.get(pt, _safe(pitch.get("usage_pct")) / 100.0)
        if usage < 0.03 or not pt:
            continue

        bstat      = b_splits.get(pt, {})
        b_xwoba    = _safe(bstat.get("xwoba"))
        b_whiff    = _safe(bstat.get("whiff_pct"))
        p_xwoba_ag = _safe(pitch.get("xwoba_against"))

        if b_xwoba > 0 and p_xwoba_ag > 0:
            eff_xwoba = b_xwoba * 0.60 + p_xwoba_ag * 0.40
        elif b_xwoba > 0:
            eff_xwoba = b_xwoba
        elif p_xwoba_ag > 0:
            eff_xwoba = p_xwoba_ag
        else:
            eff_xwoba = 0.320

        weighted += usage * eff_xwoba
        covered  += usage

        # Pitch-type edge: high batter xwOBA + pitcher actually throws it ≥15%
        if b_xwoba >= 0.390 and usage >= 0.12:
            edges.append((b_xwoba, f"{pt}({b_xwoba:.3f})"))

        # For pitch summary line — top 3 by usage
        if len(pitch_parts) < 3:
            pitch_parts.append(f"{pt}{usage*100:.0f}%")

    if covered < 0.01:
        return {"score": 50.0, "weighted_xwoba": 0.0, "top_edges": [], "pitch_summary": ""}

    eff = weighted / covered
    score = _scale(eff, 0.270, 0.340, 0.430)
    score = max(0.0, min(100.0, score))

    edges_sorted = [e[1] for e in sorted(edges, key=lambda x: x[0], reverse=True)][:3]

    return {
        "score":          round(score, 1),
        "weighted_xwoba": round(eff, 3),
        "top_edges":      edges_sorted,
        "pitch_summary":  " | ".join(pitch_parts),
    }


# ── Form signal (season xwOBA + BA divergence — no extra API calls) ───────────
# HOT  = high xwOBA + high BA: talent converting to results
# DUE  = high xwOBA + low BA:  positive regression candidate — hidden gem
# COLD = low xwOBA + low BA:   genuinely struggling
# WARM = everything else

def _form_signal(batter_id: str, xstats: dict) -> str:
    xs   = xstats.get(batter_id, {})
    xwoba = _safe(xs.get("xwoba"))
    ba    = _safe(xs.get("ba"))

    if xwoba < 0.01 or ba < 0.01:
        return "—"

    if xwoba >= 0.380 and ba >= 0.280:
        return "HOT"
    if xwoba >= 0.360 and ba < 0.240:
        return "DUE"    # unlucky / positive regression candidate
    if xwoba < 0.280 and ba < 0.230:
        return "COLD"
    return "WARM"


# ── Batter component scores ────────────────────────────────────────────────────

def _contact_score(batter_id: str, batting: dict, xstats: dict, batter_k: dict) -> float:
    bd = batting.get(batter_id, {})
    xs = xstats.get(batter_id, {})
    bk = batter_k.get(batter_id, {})

    xba       = _safe(xs.get("xba"))         # expected batting average
    ba        = _safe(xs.get("ba"))           # actual BA (as context)
    k_pct     = _safe(bk.get("k_pct"))       # batter K% — reduces contact
    swstr     = _safe(bk.get("swstr_pct"))    # whiff/swing — contact quality penalty
    sweet_spot = _safe(bd.get("sweet_spot"))  # % balls in 8-32° LA — good contact angle
    hh_pct    = _safe(bd.get("hard_hit_pct"))

    # Use blend of xBA and BA when both available
    if ba > 0:
        eff_avg = xba * 0.6 + ba * 0.4
    else:
        eff_avg = xba if xba > 0 else 0.250

    s_avg     = _scale(eff_avg,  0.200, 0.270, 0.350)
    s_contact = _scale(100.0 - k_pct, 62.0, 78.0, 90.0)   # inverse K%
    s_ss      = _scale(sweet_spot, 25.0, 35.0, 50.0)
    s_hh      = _scale(hh_pct, 25.0, 40.0, 60.0)

    score = s_avg * 0.45 + s_contact * 0.30 + s_ss * 0.15 + s_hh * 0.10
    return round(max(0.0, min(100.0, score)), 1)


def _power_score(batter_id: str, batting: dict, xstats: dict,
                 batter_hr: dict, bat_track: dict) -> float:
    bd = batting.get(batter_id, {})
    xs = xstats.get(batter_id, {})
    hr = batter_hr.get(batter_id, {})
    bt = bat_track.get(batter_id, {})

    xslg      = _safe(xs.get("xslg"))
    barrel_pct = _safe(bd.get("barrel_pct"))
    hard_hit  = _safe(bd.get("hard_hit_pct"))
    xiso      = _safe(hr.get("xiso"))
    bat_speed = _safe(bt.get("avg_bat_speed"))
    blast     = _safe(bt.get("blast_per_swing"))

    if xslg == 0.0:
        xslg = _safe(xs.get("slg")) * 0.9 if _safe(xs.get("slg")) > 0 else 0.380

    s_xslg    = _scale(xslg,      0.330, 0.430, 0.580)
    s_barrel  = _scale(barrel_pct, 3.0,  9.0,  18.0)
    s_hh      = _scale(hard_hit,  25.0, 42.0,  60.0)
    s_xiso    = _scale(xiso,       0.10, 0.180, 0.280) if xiso > 0 else 50.0
    s_speed   = _scale(bat_speed, 67.0, 72.5,  78.0)   if bat_speed > 0 else 50.0
    s_blast   = _scale(blast * 100, 2.0, 5.0,  10.0)   if blast > 0 else 50.0

    if xiso == 0.0:
        score = s_xslg * 0.40 + s_barrel * 0.30 + s_hh * 0.30
    else:
        score = (s_xslg * 0.30 + s_barrel * 0.25 + s_hh * 0.20
                 + s_xiso * 0.15 + s_speed * 0.05 + s_blast * 0.05)

    return round(max(0.0, min(100.0, score)), 1)


def _obp_score(batter_id: str, batter_k: dict, xstats: dict) -> float:
    bk = batter_k.get(batter_id, {})
    xs = xstats.get(batter_id, {})

    bb_pct = _safe(bk.get("bb_pct"))
    xwoba  = _safe(xs.get("xwoba"))
    woba   = _safe(xs.get("woba"))

    if woba > 0:
        eff_woba = xwoba * 0.6 + woba * 0.4
    else:
        eff_woba = xwoba if xwoba > 0 else 0.310

    s_woba = _scale(eff_woba, 0.270, 0.340, 0.430)
    s_bb   = _scale(bb_pct,   4.0,   9.0,  16.0)

    score = s_woba * 0.65 + s_bb * 0.35
    return round(max(0.0, min(100.0, score)), 1)


def _speed_score(batter_id: str, sprint_speed: dict) -> float:
    ss = sprint_speed.get(batter_id, {})
    speed = _safe(ss.get("sprint_speed"))
    if speed == 0.0:
        return 50.0
    return round(_scale(speed, 24.0, 27.0, 31.0), 1)


# ── Stat projections (per game) ────────────────────────────────────────────────
# Uses xBA, xSLG, BB%, K% adjusted for pitcher matchup and park factor

def _proj_stats(batter_id: str, bats: str, pitcher_matchup: dict,
                batting: dict, xstats: dict, batter_k: dict,
                batter_hr: dict, sprint_speed: dict,
                park_name: str) -> dict:
    bd = batting.get(batter_id, {})
    xs = xstats.get(batter_id, {})
    bk = batter_k.get(batter_id, {})
    hr = batter_hr.get(batter_id, {})
    ss = sprint_speed.get(batter_id, {})

    pf = PARK_FACTORS.get(park_name, {})
    park_hit = _safe(pf.get("hit"), 1.0)
    park_hr  = _safe(pf.get("hr"),  1.0)

    xba   = _safe(xs.get("xba"))  or 0.255
    xslg  = _safe(xs.get("xslg")) or 0.385
    xwoba = _safe(xs.get("xwoba")) or 0.310
    k_pct = _safe(bk.get("k_pct")) or 22.0
    bb_pct = _safe(bk.get("bb_pct")) or 8.0

    # Pitcher matchup adjustments
    p_k   = pitcher_matchup["k_pct"]   # pitcher K%
    p_bb  = pitcher_matchup["bb_pct"]  # pitcher BB%
    # Contact opportunity: blend batter K risk with pitcher K tendency
    blended_k  = k_pct * 0.55 + p_k * 0.45
    blended_bb = bb_pct * 0.50 + p_bb * 0.50

    # Projected PA ~4.0 per game, AB = PA × (1-BB%-HBP%)
    proj_pa = 4.0
    bb_rate = blended_bb / 100.0
    k_rate  = blended_k  / 100.0
    proj_bb = proj_pa * bb_rate
    proj_ab = proj_pa * (1.0 - bb_rate - 0.008)  # 0.8% HBP estimate
    proj_hits = xba * proj_ab * park_hit * (1.0 - k_rate * 0.15)  # k_rate reduces contact slightly

    # Total bases: use xSLG on contact
    proj_tb = xslg * proj_ab * park_hit * (1.0 - k_rate * 0.10)
    proj_tb = max(proj_hits, proj_tb)  # TB can't be less than hits

    # Extra-base hits
    proj_1b  = max(0.0, proj_hits * (1.0 - (xslg / (xba + 0.001) - 1.0) * 0.3))
    proj_hr_rate = _safe(hr.get("hr_fb_pct")) / 100.0 * _safe(hr.get("fb_pct")) / 100.0
    if proj_hr_rate == 0.0:
        proj_hr_rate = max(0.0, (xslg - xba) / (proj_ab + 0.001) * 0.35)
    proj_hr = proj_hr_rate * proj_ab * park_hr

    # SB projection
    speed = _safe(ss.get("sprint_speed"))
    if speed >= 29.5:
        proj_sb = 0.12
    elif speed >= 28.0:
        proj_sb = 0.07
    elif speed >= 27.0:
        proj_sb = 0.04
    else:
        proj_sb = 0.01

    # RBI/Run estimate: crude but workable
    # RBI ~= 0.25 per hit + 1.2 per HR
    # Runs ~= 0.40 per OBP event (hit+BB)
    proj_rbi = proj_hits * 0.25 + proj_hr * 1.20
    proj_run = (proj_hits + proj_bb) * 0.35

    # DK fantasy points
    xtra_bases = max(0.0, proj_tb - proj_hits)
    dk_pts = (
        proj_hits  * 3.0
        + xtra_bases * 2.0    # extra base bonus (2B/3B over single value)
        + proj_hr   * 7.0     # HR bonus (10 - 3 already counted in hits)
        + proj_rbi  * 3.5
        + proj_run  * 3.0
        + proj_bb   * 3.0
        + proj_sb   * 6.0
    )

    return {
        "proj_hits":  round(proj_hits, 2),
        "proj_tb":    round(proj_tb,   2),
        "proj_hr":    round(proj_hr,   3),
        "proj_bb":    round(proj_bb,   2),
        "proj_sb":    round(proj_sb,   2),
        "proj_rbi":   round(proj_rbi,  2),
        "proj_run":   round(proj_run,  2),
        "proj_dk":    round(dk_pts,    1),
        "xba":        round(xba,  3),
        "xslg":       round(xslg, 3),
        "xwoba":      round(xwoba, 3),
        "k_pct":      round(k_pct, 1),
        "bb_pct":     round(bb_pct, 1),
        "barrel_pct": round(_safe(bd.get("barrel_pct")), 1),
        "hard_hit":   round(_safe(bd.get("hard_hit_pct")), 1),
        "sprint":     round(speed, 1),
    }


# ── Tags ───────────────────────────────────────────────────────────────────────

def _build_tags(proj: dict, contact_score: float, power_score: float,
                obp_score: float, speed_sc: float,
                form: str = "—", arsenal: dict = None) -> list:
    tags = []

    # Form badges first — highest signal for hidden gems
    if form == "HOT":
        tags.append("🔥 HOT")
    elif form == "DUE":
        tags.append("📈 DUE")   # high xwOBA, low BA = positive regression pick
    elif form == "COLD":
        tags.append("❄ COLD")

    # Pitch-type edges vs this specific pitcher — key hidden gem signal
    if arsenal and arsenal.get("top_edges"):
        edge_str = " ".join(arsenal["top_edges"])
        tags.append(f"PITCH EDGE: {edge_str}")

    # Standard performance tags
    if proj["proj_hits"] >= 0.80:
        tags.append("CONTACT MACHINE")
    if proj["proj_tb"] >= 1.20:
        tags.append("POWER + CONTACT")
    if proj["proj_hr"] >= 0.08:
        tags.append("HR THREAT")
    if proj["proj_bb"] >= 0.55:
        tags.append("ON-BASE THREAT")
    if proj["sprint"] >= 29.0:
        tags.append("SPEED THREAT")
    if proj["barrel_pct"] >= 12.0:
        tags.append("BARREL MACHINE")
    if proj["xwoba"] >= 0.380:
        tags.append("ELITE xwOBA")
    return tags


# ── Build ──────────────────────────────────────────────────────────────────────

def build_hitter_fantasy_board(game_date: str) -> list:
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    # Pre-load all data (all batch CSVs — no per-player API calls)
    batting          = load_savant_batting(season)
    xstats           = load_savant_xstats(season)
    bat_track        = load_bat_tracking(season)
    sprint_speed     = load_sprint_speed(season)
    batter_k         = load_savant_batter_k(season)
    pitcher_k        = load_savant_pitcher_k(season)
    pitching         = load_savant_pitching(season)
    batter_hr        = load_savant_batter_hr(season)
    pitcher_arsenal  = load_savant_pitcher_arsenal(season)
    batter_splits    = load_savant_batter_pitch_splits(season)

    results = []

    for game in games:
        venue = game.get("venue_name", "Unknown")

        for side, opp_side in [("home", "away"), ("away", "home")]:
            side_data    = game.get(side, {})
            opp_data     = game.get(opp_side, {})
            team_id  = side_data.get("team_id")
            team_abv = side_data.get("team_abbr", "")
            opp_abv  = opp_data.get("team_abbr", "")
            pitcher_info = opp_data.get("probable_pitcher", {})
            pitcher_id   = str(pitcher_info.get("id", "")) if pitcher_info else ""
            pitcher_name = pitcher_info.get("name", "TBD") if pitcher_info else "TBD"
            pitcher_hand = "R"

            if not team_id:
                continue

            matchup = _pitcher_matchup_grade(pitcher_id, pitcher_k, pitching)
            roster  = get_team_roster_ids(team_id, season)

            for batter in roster:
                bid  = str(batter.get("id", ""))
                name = batter.get("name", "")
                bats = batter.get("bats", "R")
                pos  = batter.get("pos", "")

                proj = _proj_stats(bid, bats, matchup, batting, xstats,
                                   batter_k, batter_hr, sprint_speed, venue)

                cs  = _contact_score(bid, batting, xstats, batter_k)
                ps  = _power_score(bid, batting, xstats, batter_hr, bat_track)
                os_ = _obp_score(bid, batter_k, xstats)
                sp  = _speed_score(bid, sprint_speed)

                # Arsenal-weighted contact: batter xwOBA vs pitcher's specific pitch mix
                # Hand-adjusted: RHP throws different mix to LHB vs RHB
                arsenal = _arsenal_weighted_contact(
                    pitcher_id, bid, bats, pitcher_arsenal, batter_splits
                )

                # Form signal: xwOBA vs BA divergence (no extra API calls)
                form = _form_signal(bid, xstats)

                # FantasyScore — 5 components; arsenal match reduces big-name bias
                # by rewarding specific pitch-type edges over raw season talent
                fantasy_score = (
                    cs             * 0.30
                    + ps           * 0.25
                    + os_          * 0.15
                    + matchup["grade"] * 0.15
                    + arsenal["score"] * 0.15
                )
                fantasy_score = round(max(0.0, min(100.0, fantasy_score)), 1)

                tags = _build_tags(proj, cs, ps, os_, sp, form=form, arsenal=arsenal)

                results.append({
                    "batter_id":     bid,
                    "name":          name,
                    "bats":          bats,
                    "pos":           pos,
                    "team":          team_abv,
                    "opp":           opp_abv,
                    "pitcher_name":  pitcher_name,
                    "pitcher_hand":  pitcher_hand,
                    "pitcher_id":    pitcher_id,
                    "venue":         venue,
                    "game_str":      f"{game.get('away', {}).get('team_abbr', '')}@{game.get('home', {}).get('team_abbr', '')}",
                    "fantasy_score": fantasy_score,
                    "contact_score": cs,
                    "power_score":   ps,
                    "obp_score":     os_,
                    "speed_score":   sp,
                    "matchup":       matchup,
                    "arsenal":       arsenal,
                    "form":          form,
                    "proj":          proj,
                    "tags":          tags,
                })

    results.sort(key=lambda x: x["fantasy_score"], reverse=True)
    return results


# ── Formatters ─────────────────────────────────────────────────────────────────

def format_hitter_fantasy_board(results: list, game_date: str,
                                 top_n: int = 5) -> str:
    """Top hitters per team ranked by FantasyScore, with arsenal match + form."""
    lines = []
    w = 120
    lines.append("=" * w)
    lines.append(f"  HITTER FANTASY BOARD — {game_date}")
    lines.append(f"  FantasyScore: Contact(30%) + Power(25%) + OBP(15%) + PitcherGrade(15%) + ArsenalMatch(15%)")
    lines.append(f"  ArsenalMatch = batter xwOBA vs pitcher's actual pitch mix (hand-adjusted)")
    lines.append(f"  Form: HOT=converting | DUE=positive regression gem | COLD=struggling")
    lines.append(f"  Proj DK Pts: 1B×3 | 2B×5 | HR×10 | RBI×3.5 | R×3 | BB×3 | SB×6")
    lines.append("=" * w)
    lines.append("")

    games_seen = {}
    for r in results:
        g = r["game_str"]
        if g not in games_seen:
            games_seen[g] = {}
        t = r["team"]
        if t not in games_seen[g]:
            games_seen[g][t] = []
        games_seen[g][t].append(r)

    for game_str, team_dict in games_seen.items():
        parts = game_str.split("@") if "@" in game_str else [game_str, ""]
        away_abv, home_abv = parts[0], parts[1]

        away_batters = sorted(team_dict.get(away_abv, []),
                              key=lambda x: x["fantasy_score"], reverse=True)
        home_batters = sorted(team_dict.get(home_abv, []),
                              key=lambda x: x["fantasy_score"], reverse=True)

        away_pitcher = away_batters[0]["pitcher_name"] if away_batters else "TBD"
        home_pitcher = home_batters[0]["pitcher_name"] if home_batters else "TBD"
        away_mq = away_batters[0]["matchup"] if away_batters else {"grade": 0.0, "tier": ""}
        home_mq = home_batters[0]["matchup"] if home_batters else {"grade": 0.0, "tier": ""}

        lines.append(f"  ┌─ {game_str}")
        lines.append(f"  │  {away_abv} faces {home_pitcher}  │  PitcherGrade: {away_mq['grade']:.0f} {away_mq['tier']}")
        lines.append(f"  │  {home_abv} faces {away_pitcher}  │  PitcherGrade: {home_mq['grade']:.0f} {home_mq['tier']}")
        lines.append(f"  │")
        hdr = (f"  │  {'BATTER':<22} {'H':1} {'FORM':4} {'FS':5} {'CS':5} {'PS':5} "
               f"{'OBP':5} {'ARM':5} {'DK':5}  {'AxWOB':5}  {'xBA':5}  {'xSLG':5}  "
               f"{'HITS':4}  {'TB':4}  {'HR%':5}  {'BB':4}  TAGS / PITCH EDGES")
        lines.append(hdr)
        lines.append(f"  │  {'─'*113}")

        for side_batters, label in [(away_batters, away_abv), (home_batters, home_abv)]:
            if not side_batters:
                continue
            lines.append(f"  │  ── {label} ──")
            for b in side_batters[:top_n]:
                p = b["proj"]
                ar = b.get("arsenal", {})
                form_str = b.get("form", "—")
                tag_str = " | ".join(b["tags"]) if b["tags"] else ""
                pitch_summ = ar.get("pitch_summary", "")
                lines.append(
                    f"  │  {b['name']:<22} {b['bats']:1} {form_str:<4} "
                    f"{b['fantasy_score']:5.1f} {b['contact_score']:5.1f} "
                    f"{b['power_score']:5.1f} {b['obp_score']:5.1f} "
                    f"{ar.get('score', 50.0):5.1f} {p['proj_dk']:5.1f}  "
                    f"{ar.get('weighted_xwoba', 0.0):.3f}  {p['xba']:.3f}  {p['xslg']:.3f}  "
                    f"{p['proj_hits']:.2f}  {p['proj_tb']:.2f}  "
                    f"{p['proj_hr']*100:4.1f}%  {p['proj_bb']:.2f}  "
                    f"{tag_str}"
                )
                if pitch_summ:
                    lines.append(f"  │  {'':22}   {'':4}       {'':5} {'':5} {'':5} "
                                 f"{'':5} {'':5} {'':5}  pitch mix: {pitch_summ}")
        lines.append(f"  └{'─'*113}")
        lines.append("")

    lines.append("=" * w)
    return "\n".join(lines)


def format_hitter_fantasy_spotlight(results: list, game_date: str,
                                     min_score: float = 70.0,
                                     top_n: int = 40) -> str:
    """Ranked overall best fantasy plays across the full slate — with form + pitch edges."""
    lines = []
    w = 130
    lines.append("=" * w)
    lines.append(f"  HITTER FANTASY SPOTLIGHT — {game_date}  (FantasyScore ≥ {min_score:.0f})")
    lines.append(f"  Ranked by FantasyScore  |  ARM = ArsenalMatch (batter xwOBA vs pitcher's mix, hand-adjusted)")
    lines.append(f"  DUE = positive regression gem (high xwOBA, low BA — unlucky, about to break out)")
    lines.append("=" * w)
    lines.append(
        f"  {'BATTER':<22} {'H':1} {'FRM':4} {'FS':5} {'ARM':5} {'DK':5}  "
        f"{'AxWOB':5}  {'xBA':5}  {'xSLG':5}  {'HITS':4}  {'TB':4}  {'HR%':5}  "
        f"{'GAME':<14} {'PITCHER':<24} {'GRADE'}"
    )
    lines.append("  " + "─" * (w - 2))

    shown = 0
    for r in results:
        if r["fantasy_score"] < min_score:
            continue
        if shown >= top_n:
            break
        p  = r["proj"]
        m  = r["matchup"]
        ar = r.get("arsenal", {})
        form_str = r.get("form", "—")
        tag_str  = " | ".join(r["tags"]) if r["tags"] else ""
        lines.append(
            f"  {r['name']:<22} {r['bats']:1} {form_str:<4} "
            f"{r['fantasy_score']:5.1f} {ar.get('score', 50.0):5.1f} {p['proj_dk']:5.1f}  "
            f"{ar.get('weighted_xwoba', 0.0):.3f}  {p['xba']:.3f}  {p['xslg']:.3f}  "
            f"{p['proj_hits']:.2f}  {p['proj_tb']:.2f}  "
            f"{p['proj_hr']*100:4.1f}%  "
            f"{r['game_str']:<14} {r['pitcher_name']:<24} {m['grade']:.0f} {m['tier']}"
        )
        if tag_str:
            lines.append(f"  {'':22}   {'':4}       {'':5}        {tag_str}")
        shown += 1

    lines.append("=" * w)
    return "\n".join(lines)


def format_hitter_prop_targets(results: list, game_date: str) -> str:
    """Prop-specific targets: Hits O0.5, TB O1.5, and best HR plays."""
    lines = []
    w = 106
    lines.append("=" * w)
    lines.append(f"  HITTER PROP TARGETS — {game_date}")
    lines.append("=" * w)

    # Hits Over 0.5 — sorted by proj_hits
    hits_sorted = sorted(results, key=lambda x: x["proj"]["proj_hits"], reverse=True)
    lines.append("\n  ── HITS OVER 0.5  (proj hits ≥ 0.65) ──")
    lines.append(f"  {'BATTER':<22} {'H':1} {'FRM':4} {'HITS':5}  {'AxWOB':5}  {'xBA':5}  {'xwOBA':5}  {'K%':5}  {'GAME':<14} {'PITCHER':<24} {'GRADE'}")
    lines.append("  " + "─" * 100)
    for r in hits_sorted:
        p  = r["proj"]
        ar = r.get("arsenal", {})
        if p["proj_hits"] < 0.65:
            break
        m = r["matchup"]
        form_str = r.get("form", "—")
        lines.append(
            f"  {r['name']:<22} {r['bats']:1} {form_str:<4} {p['proj_hits']:5.2f}  "
            f"{ar.get('weighted_xwoba', 0.0):.3f}  {p['xba']:.3f}  {p['xwoba']:.3f}  "
            f"{p['k_pct']:4.1f}%  {r['game_str']:<14} {r['pitcher_name']:<24} {m['grade']:.0f} {m['tier']}"
        )

    # Total Bases Over 1.5
    tb_sorted = sorted(results, key=lambda x: x["proj"]["proj_tb"], reverse=True)
    lines.append("\n  ── TOTAL BASES OVER 1.5  (proj TB ≥ 1.05) ──")
    lines.append(f"  {'BATTER':<22} {'H':1} {'FRM':4} {'TB':5}  {'ARM':5}  {'xSLG':5}  {'BRL%':5}  {'HH%':5}  {'GAME':<14} {'PITCHER':<24} {'GRADE'}")
    lines.append("  " + "─" * 100)
    for r in tb_sorted:
        p  = r["proj"]
        ar = r.get("arsenal", {})
        if p["proj_tb"] < 1.05:
            break
        m = r["matchup"]
        form_str = r.get("form", "—")
        lines.append(
            f"  {r['name']:<22} {r['bats']:1} {form_str:<4} {p['proj_tb']:5.2f}  "
            f"{ar.get('score', 50.0):5.1f}  {p['xslg']:.3f}  "
            f"{p['barrel_pct']:4.1f}%  {p['hard_hit']:4.1f}%  {r['game_str']:<14} "
            f"{r['pitcher_name']:<24} {m['grade']:.0f} {m['tier']}"
        )

    # HR plays
    hr_sorted = sorted(results, key=lambda x: x["proj"]["proj_hr"], reverse=True)
    lines.append("\n  ── HR OVER 0.5  (proj HR rate ≥ 5.0%) ──")
    lines.append(f"  {'BATTER':<22} {'H':1} {'FRM':4} {'HR%':6}  {'ARM':5}  {'xSLG':5}  {'BRL%':5}  {'GAME':<14} {'PITCHER':<24} {'GRADE'}")
    lines.append("  " + "─" * 100)
    for r in hr_sorted:
        p  = r["proj"]
        ar = r.get("arsenal", {})
        if p["proj_hr"] < 0.05:
            break
        m = r["matchup"]
        form_str = r.get("form", "—")
        lines.append(
            f"  {r['name']:<22} {r['bats']:1} {form_str:<4} {p['proj_hr']*100:5.1f}%  "
            f"{ar.get('score', 50.0):5.1f}  {p['xslg']:.3f}  "
            f"{p['barrel_pct']:4.1f}%  {r['game_str']:<14} "
            f"{r['pitcher_name']:<24} {m['grade']:.0f} {m['tier']}"
        )

    lines.append("\n" + "=" * w)
    return "\n".join(lines)
