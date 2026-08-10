"""
hr_engine.py — Standalone HR probability and attack board model.

Full Attack Board (pitcher-centric):
  - Pitcher Vulnerability Score 0-100 (xwOBA + barrel% + FB% + LA allowed)
  - Tier: Attackable (>63) / Neutral Lean (45-63) / Avoid (<45)
  - Top 3 target batters per pitcher with 6-metric cards

Batter HR Profile (per matchup):
  - HR probability % via Poisson(λ = blended_hr_rate × matchup_mult × park_mult)
  - Batter HR Score 0-100: BRL/BIP (35%) + Pull% (25%) + SweetSpot (20%) + xISO (15%) + LA (5%)
  - ZoneFit: arsenal-weighted xwOBA on contact proxy (0.000-0.150)
  - HR Form %: L10 HR rate vs season baseline
  - Tags: BARREL SIGNAL, AIR PULL, BLASTS, HOT FORM, PITCH MIX 70%+, POWER PLAY

Runs independently from odds_engine / build_prop_sheet.
"""

import math
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
try:
    from weather_engine import get_weather_for_all_games, wind_bonus_from_component
    _WEATHER_AVAILABLE = True
except Exception:
    _WEATHER_AVAILABLE = False

from baseball_engine import (
    _get, MLB_API,
    get_today_games,
    get_batter_season_stats,
    get_batter_game_log,
    get_batter_pitch_splits,
    get_team_roster_ids,
    get_pitcher_throws,
    load_savant_batter_hr,
    load_savant_pitcher_hr,
    load_savant_pitcher_hr_vs_hand,
    load_savant_pitcher_arsenal,
    load_savant_batter_pitch_splits,
    load_savant_batting,
    load_bat_tracking,
    load_savant_pitcher_velo,
    load_savant_pitcher_release,
    get_h2h_stats,
    PARK_FACTORS,
    PULL_WALLS,
)

LEAGUE_HR_PA   = 0.034   # MLB avg HR/PA 2025-26
MARKET_VIG_BEP = 0.524

# ── Team recent offensive form ────────────────────────────────────────────────

def _team_recent_runs(team_id: int, game_date: str, days: int = 7) -> dict:
    """
    Returns team's average runs/game and HR/game over the last `days` calendar days.
    Hot teams (>5 R/G) get a matchup_score boost for their batters.
    """
    try:
        from datetime import datetime, timedelta
        end_dt   = datetime.strptime(game_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=days)
        start    = start_dt.strftime("%Y-%m-%d")
        end      = (end_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        url = (f"{MLB_API}/schedule?sportId=1&teamId={team_id}"
               f"&startDate={start}&endDate={end}"
               f"&hydrate=linescore&gameType=R")
        data = _get(url)
        runs_list, hr_list = [], []
        for date in data.get("dates", []):
            for gm in date.get("games", []):
                st = gm.get("status", {}).get("abstractGameState", "")
                if st != "Final":
                    continue
                t = gm.get("teams", {})
                for s in ("away", "home"):
                    td = t.get(s, {})
                    if td.get("team", {}).get("id") == team_id:
                        runs_list.append(td.get("score", 0) or 0)
        if not runs_list:
            return {"rpg": 0.0, "hot": False, "mult": 1.0, "label": ""}
        rpg = sum(runs_list) / len(runs_list)
        if rpg >= 6.5:
            mult, label = 1.10, f"🔥 HOT OFFENSE ({rpg:.1f}R/G)"
        elif rpg >= 5.5:
            mult, label = 1.05, f"↑ ACTIVE ({rpg:.1f}R/G)"
        elif rpg <= 3.0:
            mult, label = 0.95, f"↓ COLD ({rpg:.1f}R/G)"
        else:
            mult, label = 1.00, f"→ AVG ({rpg:.1f}R/G)"
        return {"rpg": round(rpg, 2), "hot": rpg >= 5.5, "mult": round(mult, 3), "label": label}
    except Exception:
        return {"rpg": 0.0, "hot": False, "mult": 1.0, "label": ""}


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


# ── Park Fit ─────────────────────────────────────────────────────────────────

def _park_fit_score(brl_bip: float, pull_pct: float, pulled_air_pct: float,
                    blast: float, bats: str, venue: str) -> tuple:
    """
    Returns (park_fit_score 0-100, pull_wall_dist int, pull_wall_label str).

    Pull wall favorability (40%) + Pulled barrel rate proxy (30%)
      + Blast% bat tracking (20%) + Pulled air% (10%)

    RHB pulls to LF → lf_dist; LHB pulls to RF → rf_dist; Switch → best side.
    Short wall (302 ft) → 100; Neutral (330 ft) → 50; Deep (355 ft) → 0.
    """
    walls = None
    venue_lower = venue.lower()
    for park, w in PULL_WALLS.items():
        if park.lower() in venue_lower or venue_lower in park.lower():
            walls = w
            break
    if walls is None:
        walls = {"lf": 330, "rf": 330}

    if bats == "R":
        dist = walls["lf"]
        pull_wall_label = f"{dist}-ft LF line"
    elif bats == "L":
        dist = walls["rf"]
        pull_wall_label = f"{dist}-ft RF line"
    else:
        dist = min(walls["lf"], walls["rf"])
        side = "LF" if walls["lf"] <= walls["rf"] else "RF"
        pull_wall_label = f"{dist}-ft {side} line"

    # _scale(355 - dist): 355-302=53→100, 355-330=25→50, 355-355=0→0
    wall_score     = _scale(355 - dist, 0, 25, 53)
    pulled_brl     = brl_bip * pull_pct / 100.0 if brl_bip and pull_pct else 0.0
    brl_score      = _scale(pulled_brl,    0.0, 3.5, 9.0)
    blast_score    = _scale(blast,         0.02, 0.04, 0.07) if blast else 0.0
    air_score      = _scale(pulled_air_pct, 0.0, 15.0, 35.0) if pulled_air_pct else 0.0

    score = wall_score * 0.40 + brl_score * 0.30 + blast_score * 0.20 + air_score * 0.10
    return round(score, 1), int(dist), pull_wall_label


# ── Arm slot / release helpers ───────────────────────────────────────────────

def _arm_slot_label(degrees: float) -> str:
    if degrees <= 0:
        return ""
    if degrees < 20:
        return "Submarine"
    if degrees < 35:
        return "Sidearm"
    if degrees < 50:
        return "Low 3/4"
    if degrees < 65:
        return "3/4"
    if degrees < 80:
        return "High 3/4"
    return "Over-Top"


def _arm_slot_deception_mult(degrees: float, bats: str, pitcher_throws: str) -> float:
    """
    Low arm slots are more deceptive against same-handed batters.
    Returns multiplier applied to matchup_score (< 1.0 hurts batter, > 1.0 helps).
    """
    if degrees <= 0:
        return 1.0
    same_hand = (bats == pitcher_throws and bats != "S")
    if degrees < 20:    # Submarine
        return 0.75 if same_hand else 1.05
    if degrees < 35:    # Sidearm
        return 0.82 if same_hand else 1.02
    if degrees < 50:    # Low 3/4
        return 0.92 if same_hand else 1.0
    return 1.0          # 3/4 and above: neutral


def _velo_tier(ff_velo: float) -> str:
    if ff_velo <= 0:
        return ""
    if ff_velo < 91:
        return "Soft"
    if ff_velo < 94:
        return "Average"
    if ff_velo < 97:
        return "Hard"
    return "Elite"


# ── Pitcher vulnerability ────────────────────────────────────────────────────

def _vuln_from_data(d: dict, era_fallback: float = 4.50) -> tuple:
    """Compute (score, tier) from a pitcher HR-vuln data dict."""
    barrel = _safe(d.get("barrel_allowed"))
    xwoba  = _safe(d.get("xwoba_allowed"))
    fb_pct = _safe(d.get("fb_pct_allowed"))
    la_avg = _safe(d.get("la_avg_allowed"))
    xslg   = _safe(d.get("xslg_allowed"))
    gb_pct = _safe(d.get("gb_pct_allowed"))

    s_xwoba  = _scale(xwoba,  0.260, 0.320, 0.420)
    s_barrel = _scale(barrel, 3.0,   7.0,   14.0)
    s_fb     = _scale(fb_pct, 20.0,  33.0,  50.0)
    s_la     = _scale(la_avg, 5.0,   14.0,  24.0)
    s_xslg   = _scale(xslg,   0.320, 0.400, 0.540)

    if barrel == 0 and xwoba == 0:
        score = _scale(era_fallback, 2.50, 4.50, 7.50)
    else:
        score = (s_xwoba * 0.30 + s_barrel * 0.28 + s_xslg * 0.20
                 + s_fb * 0.15 + s_la * 0.07)

    # GB suppressor penalty: heavy GB pitchers don't give up HRs even when
    # their contact quality metrics look attackable (e.g. Mikolas at 45.8% GB)
    if gb_pct > 40.0:
        gb_penalty = min(18.0, (gb_pct - 38.0) * 1.5)
        score = max(0.0, score - gb_penalty)

    if score > 63:
        tier = "Attackable"
    elif score > 45:
        tier = "Neutral Lean"
    else:
        tier = "Avoid"
    return round(score, 1), tier


def _pitcher_vuln_score(pitcher_id: int, pitcher_hr_data: dict,
                         pitcher_hr_lhb: dict = None,
                         pitcher_hr_rhb: dict = None) -> dict:
    """
    0-100 vulnerability score + handedness-split scores.
    Higher = more hittable for power.
    """
    pid = str(pitcher_id)
    d   = pitcher_hr_data.get(pid, {})

    barrel   = _safe(d.get("barrel_allowed"))
    xwoba    = _safe(d.get("xwoba_allowed"))
    fb_pct   = _safe(d.get("fb_pct_allowed"))
    gb_pct   = _safe(d.get("gb_pct_allowed"))
    la_avg   = _safe(d.get("la_avg_allowed"))
    xslg     = _safe(d.get("xslg_allowed"))
    era      = _safe(d.get("era"), default=4.50)

    score, tier = _vuln_from_data(d, era)

    # Handedness splits
    lhb_score, lhb_tier = (None, None)
    rhb_score, rhb_tier = (None, None)
    if pitcher_hr_lhb:
        dl = pitcher_hr_lhb.get(pid, {})
        if dl:
            lhb_score, lhb_tier = _vuln_from_data(dl, era)
    if pitcher_hr_rhb:
        dr = pitcher_hr_rhb.get(pid, {})
        if dr:
            rhb_score, rhb_tier = _vuln_from_data(dr, era)

    s_xwoba  = _scale(xwoba,  0.260, 0.320, 0.420)
    s_barrel = _scale(barrel, 3.0,   7.0,   14.0)
    s_fb     = _scale(fb_pct, 20.0,  33.0,  50.0)
    s_la     = _scale(la_avg, 5.0,   14.0,  24.0)
    s_xslg   = _scale(xslg,   0.320, 0.400, 0.540)

    gb_suppressor = gb_pct >= 43.0

    return {
        "score":          score,
        "tier":           tier,
        "lhb_score":      lhb_score,
        "lhb_tier":       lhb_tier,
        "rhb_score":      rhb_score,
        "rhb_tier":       rhb_tier,
        "barrel_allowed": round(barrel, 1),
        "xwoba_allowed":  round(xwoba, 3) if xwoba else None,
        "xslg_allowed":   round(xslg, 3) if xslg else None,
        "fb_pct_allowed": round(fb_pct, 1),
        "gb_pct_allowed": round(gb_pct, 1),
        "la_avg_allowed": round(la_avg, 1),
        "gb_suppressor":  gb_suppressor,
        "era":            round(era, 2) if era else None,
        "components": {
            "xwoba": round(s_xwoba, 1),
            "barrel": round(s_barrel, 1),
            "xslg": round(s_xslg, 1),
            "fb": round(s_fb, 1),
            "la": round(s_la, 1),
        },
    }


def _pitcher_tags(pitcher_id: int, pitcher_hr_data: dict, arsenal_data: dict) -> list:
    """Generate pitcher-side matchup tags."""
    tags = []
    pid = str(pitcher_id)
    d = pitcher_hr_data.get(pid, {})
    arsenal = arsenal_data.get(pid, [])

    xwoba  = _safe(d.get("xwoba_allowed"))
    barrel = _safe(d.get("barrel_allowed"))
    gb_pct = _safe(d.get("gb_pct_allowed"))
    era    = _safe(d.get("era"), 4.50)

    if xwoba > 0.350 and era > 4.50:
        tags.append("MEATBALL PITCHER")
    if barrel > 10.0:
        tags.append("HIGH BARREL RATE ALLOWED")
    # GB suppressor: heavy GB profile limits HR upside even when otherwise Attackable
    if gb_pct >= 43.0:
        tags.append(f"GB SUPPRESSOR ({gb_pct:.0f}% GB)")

    # Pitch mix concentration
    if arsenal:
        top = max(arsenal, key=lambda x: x.get("usage_pct") or 0)
        if (top.get("usage_pct") or 0) >= 70:
            tags.append(f"PITCH MIX 70%+ ({top.get('pitch_name','?')})")

    return tags


# ── Batter HR profile ────────────────────────────────────────────────────────

def _batter_hr_score(batter_hr: dict, savant_batting: dict, bat_track: dict, batter_id: int) -> float:
    """0-100 composite HR power score."""
    pid = str(batter_id)
    d   = batter_hr.get(pid, {})
    ev  = savant_batting.get(pid, {})
    bt  = bat_track.get(pid, {})

    brl_bip    = _safe(d.get("brl_per_bip"))     # league avg ~6.5
    pull_pct   = _safe(d.get("pull_pct"))         # 40% = neutral
    sweet_spot = _safe(d.get("sweet_spot_pct"))   # 33% = neutral
    xiso       = _safe(d.get("xiso"))             # .130 = neutral
    la_avg     = _safe(d.get("la_avg"))           # 12° = neutral
    hh_pct     = _safe(ev.get("hard_hit_pct"))    # from batting leaderboard
    blast      = _safe(bt.get("blast_per_swing")) # bat tracking quality
    hr_fb_pct  = _safe(d.get("hr_fb_pct"))        # season HR/FB% — in-year conversion rate
    ev50       = _safe(ev.get("ev50"))             # 50th pct EV: power floor signal
    avg_hr_dist= _safe(ev.get("avg_hr_dist"))      # avg HR travel distance: raw power

    s_brl     = _scale(brl_bip,    2.0,  7.0,  16.0)
    s_pull    = _scale(pull_pct,   25.0, 40.0, 55.0)
    s_sweet   = _scale(sweet_spot, 25.0, 34.0, 45.0)
    s_xiso    = _scale(xiso,       0.05, 0.14, 0.260)
    s_la      = _scale(la_avg,     4.0,  14.0, 24.0)
    s_hh      = _scale(hh_pct,     30.0, 43.0, 56.0)
    s_blast   = _scale(blast,      0.02, 0.04, 0.07) if blast else 0.0
    # HR/FB%: 6%=low, 14%=avg, 26%=elite — rewards batters actually converting this season
    s_hrfb    = _scale(hr_fb_pct,  6.0,  14.0, 26.0) if hr_fb_pct > 0 else 0.0
    # ev50: 50th-pct EV separates consistent hard contact from peak-only hitters
    s_ev50    = _scale(ev50,       86.0, 93.0, 101.0) if ev50 > 0 else 0.0
    # avg HR distance: 360ft=below avg, 395ft=avg, 430ft=elite raw power
    s_hr_dist = _scale(avg_hr_dist, 360.0, 395.0, 430.0) if avg_hr_dist > 0 else 0.0

    if hh_pct and blast:
        score = (s_brl * 0.24 + s_pull * 0.15 + s_sweet * 0.12
                 + s_xiso * 0.11 + s_la * 0.05 + s_hh * 0.08 + s_blast * 0.03
                 + s_hrfb * 0.12 + s_ev50 * 0.05 + s_hr_dist * 0.05)
    else:
        score = (s_brl * 0.27 + s_pull * 0.20 + s_sweet * 0.16
                 + s_xiso * 0.13 + s_la * 0.06 + s_hrfb * 0.10
                 + s_ev50 * 0.04 + s_hr_dist * 0.04)

    return round(score, 1)


def _zone_fit(batter_id: int, pitcher_id: int,
              batter_pitch_splits: dict, pitcher_arsenal: dict) -> float:
    """
    Arsenal-weighted excess xwOBA on contact.
    ZoneFit = Σ(pitcher pitch usage% × max(0, batter xwOBA vs pitch - 0.320)) / 100
    Range ~0.000-0.150; matches competitor decimal display.
    """
    pid_p = str(pitcher_id)
    pid_b = str(batter_id)
    arsenal = pitcher_arsenal.get(pid_p, [])
    b_splits = batter_pitch_splits.get(pid_b, {})

    if not arsenal or not b_splits:
        return 0.0

    total_usage = sum(p.get("usage_pct") or 0 for p in arsenal)
    if total_usage == 0:
        return 0.0

    zf = 0.0
    for pitch in arsenal:
        pt    = pitch.get("pitch_type", "")
        usage = (pitch.get("usage_pct") or 0) / 100.0
        bstat = b_splits.get(pt, {})
        xwoba = _safe(bstat.get("xwoba"))
        excess = max(0.0, xwoba - 0.320)
        zf += usage * excess

    return round(zf, 3)


def _hr_pitch_analysis(batter_id: int, pitcher_id: int,
                       batter_pitch_splits: dict, pitcher_arsenal: dict,
                       pitcher_velo_data: dict = None,
                       bat_track_data: dict = None) -> dict:
    """
    Per-pitch-type HR matchup breakdown.

    Returns:
      hr_edges     – list of pitches where batter has power advantage
                     (pitcher uses ≥12%, batter xwOBA ≥0.380 OR HH% ≥45%)
      weak_spots   – list of pitches where pitcher has strikeout edge
                     (pitcher uses ≥12%, batter whiff% ≥28% AND xwOBA <0.290)
      suppressors  – pitcher pitches that kill barrels
                     (pitcher uses ≥12%, xwOBA_against <0.280 AND put_away ≥22%)
      pitch_table  – full per-pitch breakdown for display
      hr_zone_score – 0-100 composite: arsenal-weighted (batter xwOBA×HH bonus)
                      boosted by HH%, penalized by weak-spot exposure
    """
    pid_p   = str(pitcher_id)
    pid_b   = str(batter_id)
    arsenal = pitcher_arsenal.get(pid_p, [])
    b_splits= batter_pitch_splits.get(pid_b, {})

    hr_edges   = []
    weak_spots = []
    suppressors= []
    pitch_table= []

    total_usage = sum(p.get("usage_pct") or 0 for p in arsenal)
    if not arsenal or total_usage == 0:
        return {"hr_edges": [], "weak_spots": [], "suppressors": [],
                "pitch_table": [], "hr_zone_score": 0.0}

    raw_score  = 0.0
    weak_penalty = 0.0

    for pitch in arsenal:
        pt    = pitch.get("pitch_type","")
        usage = _safe(pitch.get("usage_pct"))
        if usage < 1.0:
            continue

        # Batter performance vs this pitch type
        bs        = b_splits.get(pt, {})
        b_xwoba   = _safe(bs.get("xwoba"))
        b_hh      = _safe(bs.get("hard_hit_pct"))
        b_whiff   = _safe(bs.get("whiff_pct"))
        b_rv100   = _safe(bs.get("run_value_per100"))

        # Pitcher effectiveness with this pitch
        p_xwoba_ag= _safe(pitch.get("xwoba_against"))
        p_put_away= _safe(pitch.get("put_away_pct"))
        p_hh_ag   = _safe(pitch.get("hard_hit_pct"))
        p_whiff   = _safe(pitch.get("whiff_pct"))
        p_rv100   = _safe(pitch.get("run_value_per100"))

        # HR zone score component: excess xwOBA × hard-hit bonus
        excess = max(0.0, b_xwoba - 0.320) if b_xwoba else 0.0
        hh_mult = 1.0 + max(0.0, (b_hh - 40.0)) / 100.0 if b_hh else 1.0
        raw_score += (usage / 100.0) * excess * hh_mult

        # Weak spot: pitcher throws it often, batter struggles
        if usage >= 12.0 and b_xwoba and b_whiff:
            if b_whiff >= 28.0 and b_xwoba < 0.290:
                weak_spots.append({
                    "pitch_type": pt,
                    "usage": usage,
                    "b_xwoba": b_xwoba,
                    "b_whiff": b_whiff,
                    "label": f"{pt}({b_whiff:.0f}%WHF·{b_xwoba:.3f})",
                })
                weak_penalty += (usage / 100.0) * (0.290 - b_xwoba)

        # HR edge: batter makes powerful contact on pitcher's pitch
        if usage >= 12.0 and (b_xwoba >= 0.380 or b_hh >= 45.0):
            hr_edges.append({
                "pitch_type": pt,
                "usage": usage,
                "b_xwoba": b_xwoba,
                "b_hh": b_hh,
                "label": f"{pt}({b_xwoba:.3f}xwOBA·{b_hh:.0f}%HH)" if b_hh else f"{pt}({b_xwoba:.3f}xwOBA)",
            })

        # Suppressor: pitcher pitch that kills hard contact
        if usage >= 12.0 and p_xwoba_ag and p_xwoba_ag < 0.280:
            suppressors.append({
                "pitch_type": pt,
                "usage": usage,
                "p_xwoba_ag": p_xwoba_ag,
                "p_put_away": p_put_away,
                "p_whiff": p_whiff,
                "label": f"{pt}({p_xwoba_ag:.3f}xwOBA·{p_put_away:.0f}%PA)" if p_put_away else f"{pt}({p_xwoba_ag:.3f}xwOBA)",
            })

        if b_xwoba or b_hh or b_whiff:
            pitch_table.append({
                "pitch_type": pt,
                "usage": usage,
                "b_xwoba": b_xwoba,
                "b_hh": b_hh,
                "b_whiff": b_whiff,
                "b_rv100": b_rv100,
                "p_xwoba_ag": p_xwoba_ag,
                "p_whiff": p_whiff,
                "p_put_away": p_put_away,
            })

    # Normalize and apply weak-spot penalty
    hr_edges.sort(key=lambda x: -(x.get("b_xwoba") or 0))
    suppressors.sort(key=lambda x: (x.get("p_xwoba_ag") or 1))
    weak_spots.sort(key=lambda x: -(x.get("b_whiff") or 0))
    pitch_table.sort(key=lambda x: -(x.get("usage") or 0))

    # 0-100 scale: raw_score typical range 0.0-0.12
    hr_zone_score = min(100.0, (raw_score - weak_penalty * 0.5) * 800)
    hr_zone_score = max(0.0, round(hr_zone_score, 1))

    # ── Velocity vs bat speed mismatch ────────────────────────────────────────
    velo_signal    = None
    velo_edge      = None
    ff_velo        = 0.0
    bat_speed      = 0.0

    if pitcher_velo_data:
        pv     = pitcher_velo_data.get(str(pitcher_id), {})
        ff_velo= _safe(pv.get("ff_velo")) or _safe(pv.get("fb_velo"))

    if bat_track_data:
        bv     = bat_track_data.get(str(batter_id), {})
        bat_speed = _safe(bv.get("avg_bat_speed"))

    if ff_velo >= 93.0 and bat_speed > 0:
        # Reaction time advantage: bat speed < 70 vs 95+ velo is a mismatch
        # Rule of thumb: every 1 mph of FF velo = ~0.7 mph bat speed equivalent
        adj_velo = ff_velo * 0.72
        if bat_speed >= adj_velo:
            velo_edge = f"BAT SPD EDGE ({bat_speed:.1f}mph bat vs {ff_velo:.1f}mph FF)"
        elif bat_speed < adj_velo - 2.5:
            velo_signal = f"VELO MISMATCH ({ff_velo:.1f}mph FF vs {bat_speed:.1f}mph bat)"

    # ── Count sequencing: 2-strike put-away pitch analysis ───────────────────
    count_seq_signal = None
    eligible_putaway = [p for p in arsenal
                        if _safe(p.get("usage_pct")) >= 12.0
                        and _safe(p.get("put_away_pct")) > 0]
    if eligible_putaway:
        pa_pitch = max(eligible_putaway, key=lambda x: _safe(x.get("put_away_pct")))
        pt_pa    = pa_pitch.get("pitch_type", "")
        pa_pct   = _safe(pa_pitch.get("put_away_pct"))
        if any(w["pitch_type"] == pt_pa for w in weak_spots):
            count_seq_signal = f"2-STK RISK: {pt_pa} ({pa_pct:.0f}%PA put-away)"
        elif any(e["pitch_type"] == pt_pa for e in hr_edges):
            count_seq_signal = f"2-STK EDGE: {pt_pa} ({pa_pct:.0f}%PA put-away)"

    # ── Chase rate signal ─────────────────────────────────────────────────────
    chase_signal = None
    pitcher_chase_pct = 0.0
    if pitcher_velo_data:
        pv = pitcher_velo_data.get(str(pitcher_id), {})
        pitcher_chase_pct = _safe(pv.get("chase_pct"))

    # Batter overall chase% from weighted whiff across splits
    batter_chase_pct = 0.0
    if bat_track_data:
        bv = bat_track_data.get(str(batter_id), {})
        # hard_swing_rate is a proxy for aggressiveness
        batter_chase_pct = _safe(bv.get("hard_swing_rate")) * 100 if _safe(bv.get("hard_swing_rate")) <= 1 else _safe(bv.get("hard_swing_rate"))

    if pitcher_chase_pct >= 30.0:
        chase_signal = f"CHASE THREAT ({pitcher_chase_pct:.0f}% chase rate induced)"

    return {
        "hr_edges":           hr_edges,
        "weak_spots":         weak_spots,
        "suppressors":        suppressors,
        "pitch_table":        pitch_table,
        "hr_zone_score":      hr_zone_score,
        "velo_signal":        velo_signal,
        "velo_edge":          velo_edge,
        "chase_signal":       chase_signal,
        "count_seq_signal":   count_seq_signal,
        "ff_velo":            ff_velo,
        "bat_speed":          bat_speed,
        "pitcher_chase_pct":  pitcher_chase_pct,
    }


def _hr_form(batter_id: int, season_hr: int, season_pa: int,
             game_log: list) -> dict:
    """
    Compare L10 HR rate vs season HR rate.
    Returns form_pct (int 0-100), trend arrow, and near-HR count.
    """
    if season_pa <= 0:
        return {"form_pct": 50, "trend": "→", "l10_hr": 0, "l10_ab": 0,
                "near_hr_L10": 0}

    season_rate = season_hr / season_pa if season_pa else 0.0
    l10 = game_log[-10:] if len(game_log) >= 10 else game_log
    l10_hr = sum(g.get("hr", 0) for g in l10)
    l10_ab = sum(g.get("ab", 0) for g in l10)
    l10_rate = l10_hr / l10_ab if l10_ab > 0 else season_rate

    # near_hr: air outs that weren't HRs in the L10 games (proxy for hard-hit outs)
    near_hr_L10 = sum(g.get("near_hr", max(0, g.get("air_outs", 0) - g.get("hr", 0)))
                      for g in l10)

    if season_rate > 0:
        ratio = l10_rate / season_rate
    else:
        ratio = 1.0

    form_pct = min(99, max(1, int(ratio * 65)))

    if ratio >= 1.30:
        trend = "↑"
    elif ratio <= 0.70:
        trend = "↓"
    else:
        trend = "→"

    return {
        "form_pct":   form_pct,
        "trend":      trend,
        "l10_hr":     l10_hr,
        "l10_ab":     l10_ab,
        "near_hr_L10": near_hr_L10,
        "l10_rate":   round(l10_rate, 4),
        "season_rate": round(season_rate, 4),
    }


def _hr_probability(season_hr: int, season_pa: int, game_log: list,
                    vuln_score: float, park_hr_factor: float,
                    order: int = 4) -> dict:
    """
    P(≥1 HR) in a game using Poisson.
    λ = blended_hr_rate_per_pa × expected_pa × matchup_mult × park_mult
    """
    season_rate = season_hr / season_pa if season_pa > 0 else LEAGUE_HR_PA
    l10 = game_log[-10:] if game_log else []
    l10_hr = sum(g.get("hr", 0) for g in l10)
    l10_ab = sum(g.get("ab", 0) for g in l10)
    l10_rate = l10_hr / l10_ab if l10_ab > 0 else season_rate

    # Blend: 60% season / 40% L10
    base_rate = 0.60 * season_rate + 0.40 * l10_rate

    # Matchup multiplier: vuln 50 = 1.0x, vuln 0 = 0.40x, vuln 100 = 1.70x
    vuln_mult = 0.40 + (vuln_score / 100.0) * 1.30

    # Expected PA by batting order (order 1 ≈ 4.5, order 9 ≈ 3.5)
    exp_pa = max(3.2, 4.6 - (order - 1) * 0.13)

    lam = base_rate * vuln_mult * park_hr_factor * exp_pa
    lam = max(0.001, lam)

    # P(X≥1) with Poisson
    p_zero = math.exp(-lam)
    prob = round((1.0 - p_zero) * 100, 1)

    # Implied odds (American)
    if prob >= 99.0:
        implied_odds = "+100"
    else:
        p = prob / 100.0
        if p >= 0.50:
            implied_odds = f"-{round((p / (1 - p)) * 100)}"
        else:
            implied_odds = f"+{round(((1 - p) / p) * 100)}"

    return {
        "hr_prob":      prob,
        "implied_odds": implied_odds,
        "lam":          round(lam, 3),
        "exp_pa":       round(exp_pa, 1),
        "vuln_mult":    round(vuln_mult, 2),
        "park_mult":    round(park_hr_factor, 2),
        "base_rate_pa": round(base_rate, 4),
    }


def _batter_tags(batter_id: int, batter_hr_data: dict, savant_batting: dict,
                 hr_form_data: dict) -> list:
    """Generate batter-side power tags."""
    tags = []
    pid = str(batter_id)
    d   = batter_hr_data.get(pid, {})
    ev  = savant_batting.get(pid, {})

    brl_bip  = _safe(d.get("brl_per_bip"))
    pull_pct = _safe(d.get("pull_pct"))
    fb_pct   = _safe(d.get("fb_pct"))
    sweet    = _safe(d.get("sweet_spot_pct"))
    la_avg   = _safe(d.get("la_avg"))
    hh_pct   = _safe(ev.get("hard_hit_pct"))
    form     = hr_form_data.get("form_pct", 50)
    trend    = hr_form_data.get("trend", "→")

    if brl_bip >= 10.0:
        tags.append("BARREL SIGNAL")
    if brl_bip >= 7.0 and pull_pct >= 40.0 and fb_pct >= 28.0:
        tags.append("AIR PULL")
    if hh_pct >= 45.0:
        tags.append("BLASTS")
    if sweet >= 38.0:
        tags.append("SWEET SPOT")
    # Launch angle profile flags — key for distinguishing true HR threats
    if la_avg >= 21.0:
        tags.append(f"LOFT HITTER ({la_avg:.0f}°)")
    elif la_avg > 0 and la_avg < 13.0:
        tags.append(f"FLAT SWING ({la_avg:.0f}°)")
    if form >= 80 and trend == "↑":
        tags.append("HOT FORM")
    elif form <= 35 and trend == "↓":
        tags.append("COLD FORM")

    return tags


# ── Per-batter HR analysis ───────────────────────────────────────────────────

def analyze_batter_hr(batter_id: int, batter_name: str, order: int,
                      pitcher_id: int, pitcher_name: str,
                      venue_name: str, game_date: str, season: int,
                      batter_hr_data: dict, pitcher_vuln: dict,
                      savant_batting: dict, bat_track: dict,
                      pitcher_arsenal: dict, batter_pitch_splits: dict) -> dict:
    """Full HR analysis for one batter vs pitcher matchup."""

    # Season stats
    bstats = get_batter_season_stats(batter_id, season, game_date)
    s = bstats.get("stats", {})
    season_hr = s.get("hr", 0) or 0
    season_pa = s.get("pa", 0) or 0
    iso_str   = s.get("iso", "0") or "0"
    bats      = bstats.get("bats", "R")

    # L10 game log
    game_log = get_batter_game_log(batter_id, season, limit=15)

    # Scores
    hr_score   = _batter_hr_score(batter_hr_data, savant_batting, bat_track, batter_id)
    vuln_score = pitcher_vuln.get("score", 50.0)
    zone_fit   = _zone_fit(batter_id, pitcher_id, batter_pitch_splits, pitcher_arsenal)

    # Park factor
    park_info = PARK_FACTORS.get(venue_name, {})
    park_hr   = park_info.get("hr", 1.0)

    # HR probability
    hr_order = order if order else 4
    prob_data = _hr_probability(season_hr, season_pa, game_log, vuln_score, park_hr, hr_order)

    # HR Form
    form_data = _hr_form(batter_id, season_hr, season_pa, game_log)

    # Tags
    tags = _batter_tags(batter_id, batter_hr_data, savant_batting, form_data)

    # Pull Barrel metric
    pid = str(batter_id)
    d = batter_hr_data.get(pid, {})
    brl_bip  = _safe(d.get("brl_per_bip"))
    pull_pct = _safe(d.get("pull_pct"))
    pulled_brl = round(brl_bip * pull_pct / 100, 1) if brl_bip and pull_pct else 0.0

    pid_str = str(batter_id)
    d_hr = batter_hr_data.get(pid_str, {})
    ev_data = savant_batting.get(pid_str, {})

    return {
        "batter_id":    batter_id,
        "batter_name":  batter_name,
        "bats":         bats,
        "order":        order,
        "hr_score":     hr_score,
        "hr_prob":      prob_data["hr_prob"],
        "implied_odds": prob_data["implied_odds"],
        "zone_fit":     zone_fit,
        "hr_form_pct":  form_data["form_pct"],
        "hr_form_trend":form_data["trend"],
        "l10_hr":       form_data["l10_hr"],
        "l10_ab":       form_data["l10_ab"],
        "near_hr_L10":  form_data.get("near_hr_L10", 0),
        "exit_velo":    round(_safe(ev_data.get("exit_velo")), 1) or None,
        "avg_dist":     round(_safe(d_hr.get("avg_distance")), 0) or None,
        "brl_bip":      brl_bip,
        "pull_pct":     pull_pct,
        "fb_pct":       _safe(d.get("fb_pct")),
        "la_avg":       _safe(d.get("la_avg")),
        "sweet_spot":   _safe(d.get("sweet_spot_pct")),
        "xiso":         _safe(d.get("xiso")),
        "xwoba":        _safe(d.get("xwoba")),
        "season_hr":    season_hr,
        "season_pa":    season_pa,
        "iso":          iso_str,
        "pulled_brl":   pulled_brl,
        "park_hr_factor": park_hr,
        "venue":        venue_name,
        "tags":         tags,
        "pitcher_name": pitcher_name,
    }


# ── Attack Board ─────────────────────────────────────────────────────────────

def _platoon_vuln(vuln_score: float, bats: str, pitcher_throws: str) -> float:
    """
    Adjust pitcher vulnerability score by platoon matchup.
    Same-hand matchup (LHB vs LHP, RHB vs RHP): pitcher advantage → lower vuln.
    Opposite-hand matchup (LHB vs RHP, RHB vs LHP): batter platoon edge → higher vuln.
    Switch hitters: neutral (no adjustment).
    """
    if bats == "S":
        return vuln_score
    if bats == pitcher_throws:
        # Same hand — pitcher has platoon edge (about 7-10% HR suppression)
        return max(0.0, vuln_score * 0.91)
    else:
        # Opposite hand — batter has platoon edge (about 7-10% HR boost)
        return min(100.0, vuln_score * 1.09)


def _hand_vuln_score(pitcher_vuln: dict, bats: str, pitcher_throws: str = "R") -> float:
    """Apply platoon adjustment to composite vuln score."""
    base = pitcher_vuln.get("score", 50.0)
    return _platoon_vuln(base, bats, pitcher_throws)


_pitcher_velo_cache: dict = {}     # module-level, populated by build_hr_attack_board
_pitcher_release_cache: dict = {}  # {player_id: {arm_angle, release_ext}}


def _quick_batter_entry(batter_id: int, batter_name: str, bats: str,
                        pitcher_id: int, pitcher_name: str, venue_name: str,
                        pitcher_vuln: dict, pitcher_throws: str,
                        batter_hr_data: dict, savant_batting: dict,
                        bat_track: dict, pitcher_arsenal: dict,
                        batter_pitch_splits: dict) -> dict:
    """
    Savant-only batter profile — no per-batter API calls.
    Uses season xISO as HR rate proxy when no game log available.
    Uses handedness-split pitcher vulnerability score.
    """
    pid  = str(batter_id)
    d    = batter_hr_data.get(pid, {})
    ev   = savant_batting.get(pid, {})
    bt   = bat_track.get(pid, {})

    brl_bip      = _safe(d.get("brl_per_bip"))
    pull_pct     = _safe(d.get("pull_pct"))
    fb_pct       = _safe(d.get("fb_pct"))
    la_avg       = _safe(d.get("la_avg"))
    sweet        = _safe(d.get("sweet_spot_pct"))
    xiso         = _safe(d.get("xiso"))
    iso          = _safe(d.get("iso"))
    xwoba        = _safe(d.get("xwoba"))
    hr_fb_pct    = _safe(d.get("hr_fb_pct"))
    hh_pct       = _safe(ev.get("hard_hit_pct"))
    exit_velo    = _safe(ev.get("exit_velo"))
    avg_dist     = _safe(d.get("avg_distance"))
    pulled_air_pct = _safe(d.get("pulled_air_pct"))
    blast_raw    = _safe(bt.get("blast_per_swing"))

    # xwOBAcon — prefer batter_hr_data (custom leaderboard), fall back to savant_batting
    xwoba_con = _safe(d.get("xwoba_con")) or _safe(ev.get("xwoba_con"))

    # SwStr% — compute from batter pitch splits (weighted whiff% across pitch types)
    b_splits  = batter_pitch_splits.get(pid, {})
    if b_splits:
        _tot_usage = sum(v.get("usage_faced", 0) for v in b_splits.values())
        swstr_pct = (sum(v.get("whiff_pct", 0) * v.get("usage_faced", 0)
                        for v in b_splits.values()) / _tot_usage
                    if _tot_usage > 0 else 0.0)
    else:
        swstr_pct = _safe(ev.get("swstr_pct"))

    # HR/FB% — Savant field (percentage, e.g. 18.0), or xISO-based proxy
    if hr_fb_pct == 0.0 and fb_pct > 0:
        hr_fb_pct = round((xiso * 0.22) / (fb_pct / 100.0) * 100.0, 1)

    hr_score     = _batter_hr_score(batter_hr_data, savant_batting, bat_track, batter_id)
    barrel_score = _scale(brl_bip, 2.0, 7.0, 16.0)
    zone_fit     = _zone_fit(batter_id, pitcher_id, batter_pitch_splits, pitcher_arsenal)

    # Pitch-type matchup analysis: HR edges, weak spots, suppressors, velo/bat mismatch
    pitch_analysis = _hr_pitch_analysis(
        batter_id, pitcher_id, batter_pitch_splits, pitcher_arsenal,
        pitcher_velo_data=_pitcher_velo_cache,
        bat_track_data=bat_track,
    )
    hr_zone_score     = pitch_analysis["hr_zone_score"]
    hr_edges          = pitch_analysis["hr_edges"]
    weak_spots        = pitch_analysis["weak_spots"]
    suppressors       = pitch_analysis["suppressors"]
    pitch_table       = pitch_analysis["pitch_table"]
    velo_signal       = pitch_analysis.get("velo_signal")
    velo_edge         = pitch_analysis.get("velo_edge")
    chase_signal      = pitch_analysis.get("chase_signal")
    count_seq_signal  = pitch_analysis.get("count_seq_signal")
    ff_velo           = pitch_analysis.get("ff_velo", 0.0)
    bat_speed         = pitch_analysis.get("bat_speed", 0.0)
    pitcher_chase_pct = pitch_analysis.get("pitcher_chase_pct", 0.0)

    # matchup_score: batter profile + pitch-type zone fit + raw pitcher vulnerability
    # Pitcher vuln added at 25% so mid-tier batters in prime spots compete with elite bats in avg spots
    vuln_raw = pitcher_vuln.get("score", 50.0)
    if hr_zone_score > 0:
        matchup_score = min(100.0,
            hr_score * 0.35 +
            hr_zone_score * 0.30 +
            zone_fit * 600 * 0.10 +
            vuln_raw * 0.25)
    else:
        matchup_score = min(100.0,
            hr_score * 0.40 +
            zone_fit * 600 * 0.35 +
            vuln_raw * 0.25)

    # Arm slot deception
    arm_data  = _pitcher_release_cache.get(str(pitcher_id), {})
    arm_angle = _safe(arm_data.get("arm_angle"))
    arm_slot  = _arm_slot_label(arm_angle)
    arm_mult  = _arm_slot_deception_mult(arm_angle, bats, pitcher_throws)
    if arm_mult != 1.0:
        matchup_score = min(100.0, max(0.0, matchup_score * arm_mult))

    # Velocity tier
    velo_tier = _velo_tier(ff_velo)

    # Park fit
    park_fit, pull_wall_dist, pull_wall_label = _park_fit_score(
        brl_bip, pull_pct, pulled_air_pct, blast_raw, bats, venue_name
    )

    # Signal Lane + Discovery — now also considers pitch matchup
    has_hr_edge  = len(hr_edges) > 0
    has_weak_spot= len(weak_spots) > 0
    has_suppress = len(suppressors) >= 2  # pitcher has multiple HR-killing weapons

    if hr_score >= 65.0 and park_fit >= 55.0:
        signal_lane = "Elite HR Profile"
        discovery   = "Signal + park fit" + (" + PITCH EDGE" if has_hr_edge else "")
    elif park_fit >= 50.0 and hr_score >= 45.0:
        signal_lane = "No signal"
        discovery   = "Park-Fit Watch"
    else:
        signal_lane = "No signal"
        discovery   = "-"

    # Warning flag if pitcher has suppressor pitches that counter batter's profile
    if has_suppress and not has_hr_edge:
        discovery = (discovery + " ⚠ SUPPRESSED").strip()

    # Use platoon-adjusted vuln score for this batter
    vuln_score = _hand_vuln_score(pitcher_vuln, bats, pitcher_throws)
    est_hr_pa  = xiso * 0.22 if xiso > 0 else LEAGUE_HR_PA
    vuln_mult  = 0.40 + (vuln_score / 100.0) * 1.30
    park_hr    = PARK_FACTORS.get(venue_name, {}).get("hr", 1.0)
    lam = est_hr_pa * vuln_mult * park_hr * 4.0
    lam = max(0.001, lam)
    prob = round((1.0 - math.exp(-lam)) * 100, 1)
    if prob >= 99.0:
        odds = "+100"
    else:
        p = prob / 100.0
        odds = (f"-{round((p/(1-p))*100)}" if p >= 0.50
                else f"+{round(((1-p)/p)*100)}")

    pulled_brl     = round(brl_bip * pull_pct / 100, 1) if brl_bip and pull_pct else 0.0
    pulled_brl_pct = pulled_brl  # proxy; real pulled_brl% would need separate Statcast field
    blast_pct      = round(blast_raw * 100, 1) if 0 < blast_raw <= 1 else round(blast_raw, 1)

    tags = []
    if brl_bip >= 10.0:
        tags.append("BARREL SIGNAL")
    if brl_bip >= 7.0 and pull_pct >= 40.0 and fb_pct >= 28.0:
        tags.append("AIR PULL")
    if hh_pct >= 45.0:
        tags.append("BLASTS")
    if sweet >= 38.0:
        tags.append("SWEET SPOT")
    if hr_fb_pct >= 18.0:
        tags.append("HR/FB ELITE")
    if hr_edges:
        tags.append(f"HR EDGE: {' '.join(e['pitch_type'] for e in hr_edges[:2])}")
    if weak_spots:
        tags.append(f"WEAK: {' '.join(w['pitch_type'] for w in weak_spots[:2])}")
    if suppressors and not hr_edges:
        tags.append(f"SUPPRESSED: {suppressors[0]['pitch_type']}")
    if velo_edge:
        tags.append(velo_edge)
    if velo_signal:
        tags.append(velo_signal)
    if chase_signal:
        tags.append(chase_signal)
    if count_seq_signal:
        tags.append(count_seq_signal)
    if velo_tier:
        tags.append(f"VELO: {velo_tier} ({ff_velo:.1f}mph)")
    if arm_slot and arm_mult != 1.0:
        tags.append(f"ARM: {arm_slot} (×{arm_mult:.2f})")

    return {
        "batter_id":      batter_id,
        "batter_name":    batter_name,
        "bats":           bats,
        "hr_score":       hr_score,
        "barrel_score":   round(barrel_score, 1),
        "matchup_score":  round(matchup_score, 1),
        "hr_prob":        prob,
        "implied_odds":   odds,
        "zone_fit":       zone_fit,
        "hr_zone_score":  hr_zone_score,
        "hr_form_pct":    None,
        "hr_form_trend":  "?",
        "near_hr_L10":    None,
        "exit_velo":      round(exit_velo, 1) if exit_velo else None,
        "avg_dist":       round(avg_dist, 0) if avg_dist else None,
        "brl_bip":        brl_bip,
        "pull_pct":       pull_pct,
        "fb_pct":         fb_pct,
        "la_avg":         la_avg,
        "sweet_spot":     sweet,
        "hh_pct":         hh_pct,
        "xiso":           xiso,
        "iso":            iso,
        "xwoba":          xwoba,
        "xwoba_con":      xwoba_con,
        "swstr_pct":      swstr_pct,
        "hr_fb_pct":      hr_fb_pct,
        "pulled_brl":     pulled_brl,
        "hr_edges":       hr_edges,
        "weak_spots":     weak_spots,
        "suppressors":    suppressors,
        "pitch_table":    pitch_table,
        "velo_signal":    velo_signal,
        "velo_edge":      velo_edge,
        "chase_signal":   chase_signal,
        "ff_velo":        ff_velo,
        "bat_speed":      bat_speed,
        "pitcher_chase_pct": pitcher_chase_pct,
        "pulled_brl_pct": pulled_brl_pct,
        "pulled_air_pct": pulled_air_pct,
        "blast_pct":      blast_pct,
        "park_fit":       park_fit,
        "pull_wall_dist": pull_wall_dist,
        "pull_wall_label": pull_wall_label,
        "signal_lane":    signal_lane,
        "discovery":      discovery,
        "park_hr_factor":    park_hr,
        "vuln_used":         round(vuln_score, 1),
        "venue":             venue_name,
        "tags":              tags,
        "pitcher_name":      pitcher_name,
        "count_seq_signal":  count_seq_signal,
        "arm_slot":          arm_slot,
        "arm_angle":         arm_angle,
        "arm_mult":          arm_mult,
        "velo_tier":         velo_tier,
        "h2h":               {},
        "h2h_signal":        None,
    }


def build_hr_attack_board(game_date: str) -> list:
    """
    Fast build: all data from pre-loaded Savant CSVs, one roster API call per team.
    No per-batter season stats calls — uses xISO-based HR rate proxy.
    Sorted by pitcher vulnerability score descending.
    """
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    global _pitcher_velo_cache, _pitcher_release_cache

    # Load all Savant data once (cached after first call)
    batter_hr_data        = load_savant_batter_hr(season)
    pitcher_hr_data       = load_savant_pitcher_hr(season)
    pitcher_hr_lhb        = load_savant_pitcher_hr_vs_hand(season, "L")
    pitcher_hr_rhb        = load_savant_pitcher_hr_vs_hand(season, "R")
    pitcher_arsenal       = load_savant_pitcher_arsenal(season)
    batter_pitch_splits   = load_savant_batter_pitch_splits(season)
    savant_batting        = load_savant_batting(season)
    bat_track             = load_bat_tracking(season)
    _pitcher_velo_cache   = load_savant_pitcher_velo(season)
    _pitcher_release_cache= load_savant_pitcher_release(season)

    # Fetch game-time wind + temp for all venues (one API call per unique venue)
    venue_weather: dict = {}
    if _WEATHER_AVAILABLE:
        try:
            venue_weather = get_weather_for_all_games(games)
        except Exception:
            venue_weather = {}

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

            vuln   = _pitcher_vuln_score(pitcher_id, pitcher_hr_data,
                                         pitcher_hr_lhb, pitcher_hr_rhb)
            ptags  = _pitcher_tags(pitcher_id, pitcher_hr_data, pitcher_arsenal)
            arsenal_raw     = pitcher_arsenal.get(str(pitcher_id), [])
            arsenal_display = sorted(arsenal_raw, key=lambda x: x.get("usage_pct") or 0,
                                     reverse=True)[:3]

            # Team recent offensive form — boost batters from hot-hitting lineups
            opp_offense = _team_recent_runs(opp_team_id, game_date)
            off_mult = opp_offense.get("mult", 1.0)
            time.sleep(0.10)

            # Roster — one API call per opposing team
            roster = get_team_roster_ids(opp_team_id, season)
            time.sleep(0.15)

            # Score every roster batter using Savant data only
            batter_entries = []
            for b in roster:
                bid = b.get("id")
                if not bid:
                    continue
                entry = _quick_batter_entry(
                    bid, b["name"], b.get("bats", "R"),
                    pitcher_id, pitcher_name, venue,
                    vuln, pitcher_throws,
                    batter_hr_data, savant_batting,
                    bat_track, pitcher_arsenal, batter_pitch_splits,
                )
                # Apply team hot-streak multiplier to matchup_score and hr_prob
                if off_mult != 1.0:
                    entry["matchup_score"] = min(99.9, entry["matchup_score"] * off_mult)
                    entry["hr_prob"]       = min(65.0, entry["hr_prob"] * off_mult)
                    entry["offense_label"] = opp_offense.get("label", "")

                # Apply weather wind bonus/penalty to matchup_score
                w_data = venue_weather.get(venue, {})
                wind_component = w_data.get("wind_component_cf", 0)
                wind_bonus     = w_data.get("wind_bonus", 0)
                wind_tag_str   = w_data.get("tag", "")
                if not w_data.get("dome") and wind_bonus != 0:
                    entry["matchup_score"] = min(99.9, max(0.0, entry["matchup_score"] + wind_bonus))
                if wind_tag_str:
                    entry.setdefault("tags", [])
                    if wind_tag_str not in entry["tags"]:
                        entry["tags"].insert(0, wind_tag_str)
                entry["wind_mph"]          = w_data.get("wind_mph", 0)
                entry["wind_component_cf"] = wind_component
                entry["wind_bonus"]        = wind_bonus
                entry["temp_f"]            = w_data.get("temp_f", 72)

                # Rank by matchup_score — already includes vuln + zone fit + hr profile
                rank_key = entry["matchup_score"]
                batter_entries.append((rank_key, entry))

            batter_entries.sort(key=lambda x: -x[0])
            top_batters = [e for _, e in batter_entries[:8]]

            results.append({
                "game":           f"{g['away']['team_abbr']}@{g['home']['team_abbr']}",
                "game_pk":        g["game_pk"],
                "venue":          venue,
                "pitcher_id":     pitcher_id,
                "pitcher_name":   pitcher_name,
                "pitcher_team":   g[side]["team_abbr"],
                "pitcher_throws": pitcher_throws,
                "opp_team":       opp_abbr,
                "pitcher_side":   side,
                "vuln":           vuln,
                "pitcher_tags":   ptags,
                "arsenal":        arsenal_display,
                "top_batters":    top_batters,
                "opp_offense":    opp_offense,
                "weather":        venue_weather.get(venue, {}),
            })

    results.sort(key=lambda x: -(x["vuln"]["score"]))

    # Tag game stack alerts: attackable pitcher with 3+ batters scoring ≥ 40 matchup_score
    for r in results:
        if r["vuln"]["tier"] == "Attackable":
            stack_count = sum(1 for b in r["top_batters"] if b["matchup_score"] >= 40.0)
            r["stack_alert"] = stack_count >= 3
            r["stack_count"] = stack_count
        else:
            r["stack_alert"] = False
            r["stack_count"] = 0

    return results


def enrich_recent_hr_form(results: list, game_date: str, top_n: int = 120) -> list:
    """
    Post-build: for the top-N batters by matchup_score (across all games), pull a
    short game log (last 10 games) and tag HOT/DUE based on recent HR production.
    Adds 'recent_l5_hr', 'hot_bat' fields and boosts matchup_score by up to 8%.
    Also enriches any batter with matchup_score >= 35 regardless of rank.
    Call after build_hr_attack_board() but before final ranking.
    """
    season = int(game_date[:4])

    # Collect all batters with matchup_score, deduplicate by batter_id
    all_entries = []
    for r in results:
        for b in r["top_batters"]:
            all_entries.append((b["matchup_score"], b["batter_id"], b, r))
    all_entries.sort(key=lambda x: -x[0])

    seen_ids: set = set()
    to_enrich: list = []
    for ms, bid, b, r in all_entries:
        if bid not in seen_ids:
            # Enrich top_n by rank OR any batter with matchup_score >= 35
            if len(to_enrich) < top_n or ms >= 35.0:
                seen_ids.add(bid)
                to_enrich.append((bid, b, r))

    enriched_map: dict = {}  # batter_id -> recent data
    for bid, b, r in to_enrich:
        try:
            log = get_batter_game_log(bid, season, limit=10)
            l5  = log[-5:] if len(log) >= 5 else log
            l5_hr  = sum(g.get("hr", 0) for g in l5)
            l5_ab  = sum(g.get("ab", 0) for g in l5)
            # Season rate from xiso proxy
            xiso   = b.get("xiso", 0.0) or 0.0
            season_hr_rate = xiso * 0.22 if xiso > 0 else LEAGUE_HR_PA
            l5_rate = l5_hr / l5_ab if l5_ab > 0 else season_hr_rate

            # Recent momentum signal
            if l5_hr >= 3:
                tag, boost = "🔥 FIRE (3+ HR L5)", 0.08
            elif l5_hr == 2:
                tag, boost = "🔥 HOT (2 HR L5)", 0.05
            elif l5_hr == 1:
                tag, boost = "✓ ACTIVE (1 HR L5)", 0.02
            else:
                # Check near misses: if season hr_rate high but cold lately — "due"
                if season_hr_rate >= 0.038 and l5_hr == 0 and l5_ab >= 15:
                    tag, boost = "📈 DUE (0 HR L5 / elite profile)", 0.03
                else:
                    tag, boost = "", 0.0

            enriched_map[bid] = {"l5_hr": l5_hr, "l5_ab": l5_ab,
                                 "tag": tag, "boost": boost}
            time.sleep(0.08)
        except Exception:
            enriched_map[bid] = {"l5_hr": 0, "l5_ab": 0, "tag": "", "boost": 0.0}

    # Apply boosts and tags back to all results
    for r in results:
        for b in r["top_batters"]:
            info = enriched_map.get(b["batter_id"])
            if not info:
                continue
            b["recent_l5_hr"] = info["l5_hr"]
            b["hot_bat"]      = info["l5_hr"] >= 2
            if info["tag"]:
                tags = b.setdefault("tags", [])
                if info["tag"] not in tags:
                    tags.insert(0, info["tag"])
            if info["boost"] > 0:
                b["matchup_score"] = min(99.9,
                    b["matchup_score"] * (1.0 + info["boost"]))

    return results


def enrich_top_reads(results: list, game_date: str, top_n_pitchers: int = 6) -> list:
    """
    For the top N most-attackable pitchers, pull full per-batter season stats
    and game logs to compute real HR probability and HR Form %.
    Call this AFTER build_hr_attack_board() to add depth to the top reads.
    """
    season = int(game_date[:4])
    batter_hr_data      = load_savant_batter_hr(season)
    pitcher_arsenal     = load_savant_pitcher_arsenal(season)
    batter_pitch_splits = load_savant_batter_pitch_splits(season)
    savant_batting      = load_savant_batting(season)
    bat_track           = load_bat_tracking(season)

    for r in results[:top_n_pitchers]:
        enriched = []
        for b in r["top_batters"]:
            bid = b["batter_id"]
            try:
                full = analyze_batter_hr(
                    bid, b["batter_name"], 4,
                    r["pitcher_id"], r["pitcher_name"],
                    r["venue"], game_date, season,
                    batter_hr_data, r["vuln"],
                    savant_batting, bat_track,
                    pitcher_arsenal, batter_pitch_splits,
                )
                enriched.append(full)
                time.sleep(0.2)
            except Exception:
                enriched.append(b)
        enriched.sort(key=lambda x: -(x.get("hr_prob") or 0))
        r["top_batters"] = enriched

    return results


def enrich_with_h2h(results: list) -> list:
    """
    Post-build enrichment: adds career H2H (2020+) stats per batter vs their pitcher.
    Fires OWNS PITCHER / DOMINATED signals at ≥10 PA.
    Call after build_hr_attack_board() — makes ~1 API call per batter-pitcher pair (cached).
    """
    for r in results:
        pitcher_id = r["pitcher_id"]
        for b in r["top_batters"]:
            batter_id = b["batter_id"]
            try:
                h2h = get_h2h_stats(batter_id, pitcher_id)
            except Exception:
                h2h = {}
            h2h_signal = None
            if h2h.get("pa", 0) >= 10:
                if h2h.get("hr", 0) >= 2 and h2h.get("avg", 0) >= 0.280:
                    h2h_signal = (f"OWNS PITCHER ({h2h['hr']}HR·"
                                  f"{h2h['avg']:.3f}AVG in {h2h['pa']}PA)")
                elif h2h.get("avg", 0) < 0.200 and h2h.get("k_pct", 0) >= 28.0:
                    h2h_signal = (f"DOMINATED ({h2h['avg']:.3f}AVG·"
                                  f"{h2h['k_pct']:.0f}%K in {h2h['pa']}PA)")
            b["h2h"]       = h2h
            b["h2h_signal"] = h2h_signal
            if h2h_signal:
                tags = b.setdefault("tags", [])
                if h2h_signal not in tags:
                    tags.append(h2h_signal)
            time.sleep(0.08)
    return results


# ── Formatting ───────────────────────────────────────────────────────────────

def _fmt(val, fmt=".1f", suffix="", none_str="  -"):
    """Format a float metric or return none_str if zero/None."""
    if val is None or val == 0.0:
        return none_str
    try:
        return f"{val:{fmt}}{suffix}"
    except Exception:
        return none_str


def format_hr_attack_board(results: list, game_date: str) -> str:
    lines = []
    W = 90
    lines.append("=" * W)
    lines.append(f"  HR ATTACK BOARD — {game_date}")
    lines.append(f"  Pitcher Vulnerability: xwOBA_allowed + Barrel% + FB% + LA  |  "
                 f"Batter Score: BRL/BIP + Pull + SweetSpot + xISO")
    lines.append("=" * W)

    # ── Pitcher summary table ──
    lines.append(f"\n  {'PITCHER':<22} {'OPP':<5} {'VULN':<6} {'TIER':<14} "
                 f"{'BRL_ALL':<8} {'xwOBA_ALL':<10} {'FB%_ALL':<8} {'ERA'}")
    lines.append(f"  {'-'*80}")

    for r in results:
        v = r["vuln"]
        tier_sym = "★" if v["tier"] == "Attackable" else ("◎" if v["tier"] == "Neutral Lean" else "○")
        barrel   = f"{v['barrel_allowed']:.1f}%" if v['barrel_allowed'] else "  -  "
        xwoba    = f"{v['xwoba_allowed']:.3f}" if v['xwoba_allowed'] else "  -  "
        fb       = f"{v['fb_pct_allowed']:.1f}%" if v['fb_pct_allowed'] else "  -  "
        era      = f"{v['era']:.2f}" if v['era'] else "  -"
        stack_flag = "  🔥 GAME STACK" if r.get("stack_alert") else ""
        lines.append(
            f"  {r['pitcher_name']:<22} {r['opp_team']:<5} {v['score']:<6.1f}"
            f" {tier_sym} {v['tier']:<12} {barrel:<8} {xwoba:<10} {fb:<8} {era}{stack_flag}"
        )

    lines.append("\n" + "=" * W)
    lines.append("  BATTER MATCHUP REPORT  (BarrelScore · MatchupScore · xwOBAcon · SwStr% · HR/FB%)")
    lines.append("=" * W)

    for r in results:
        v = r["vuln"]
        tier_sym = "★" if v["tier"] == "Attackable" else ("◎" if v["tier"] == "Neutral Lean" else "○")
        ptag_str = "  [" + ", ".join(r["pitcher_tags"]) + "]" if r["pitcher_tags"] else ""

        p_throws = r.get("pitcher_throws", "R")
        hand_note = (f"  [LHP — vs LHB ×0.91 | vs RHB ×1.09]"
                     if p_throws == "L"
                     else f"  [RHP — vs LHB ×1.09 | vs RHB ×0.91]")

        lines.append(f"\n  ┌─ {r['pitcher_name']} ({r['pitcher_team']})  vs {r['opp_team']}"
                     f"  │  {r['game']}")
        lines.append(f"  │  Vuln: {v['score']:.1f}  {tier_sym} {v['tier']}{ptag_str}{hand_note}")
        lines.append(f"  │  Barrel Allowed: {v['barrel_allowed']:.1f}%  "
                     f"xwOBA: {v['xwoba_allowed'] or '-'}  "
                     f"xSLG: {v['xslg_allowed'] or '-'}  "
                     f"FB%: {v['fb_pct_allowed']:.1f}%  "
                     f"LA: {v['la_avg_allowed']:.1f}°  "
                     f"ERA: {v['era'] or '-'}")

        # Arm angle / velo tier for pitcher
        p_release = _pitcher_release_cache.get(str(r.get("pitcher_id", "")), {})
        p_arm_angle = p_release.get("arm_angle", 0.0)
        p_arm_slot  = _arm_slot_label(p_arm_angle) if p_arm_angle else ""
        p_velo_data = _pitcher_velo_cache.get(str(r.get("pitcher_id", "")), {})
        p_ff_velo   = _safe(p_velo_data.get("ff_velo")) or _safe(p_velo_data.get("fb_velo"))
        p_velo_tier = _velo_tier(p_ff_velo)
        arm_velo_str = ""
        if p_arm_slot:
            arm_velo_str += f"  │  Arm Slot: {p_arm_slot} ({p_arm_angle:.1f}°)"
        if p_velo_tier and p_ff_velo:
            arm_velo_str += f"  │  FB Velo: {p_velo_tier} ({p_ff_velo:.1f}mph)"
        if arm_velo_str:
            lines.append(arm_velo_str)

        arsenal_str = "  │  Arsenal: "
        for p in r["arsenal"]:
            arsenal_str += f"{p.get('pitch_name','?')} {p.get('usage_pct',0):.0f}%  "
        lines.append(arsenal_str.rstrip())

        if not r["top_batters"]:
            lines.append("  │  (no batter data)")
        else:
            lines.append(f"  │")
            # Header row 1: scores + probability
            lines.append(
                f"  │  {'BATTER':<22} {'H':<2} {'BSCORE':<7} {'MSCORE':<7} "
                f"{'HZS':<7} {'HR%':<6} {'ODDS':<8} {'ZF':<6} {'FORM':<6} {'NR':<3}"
            )
            # Header row 2: detailed stat columns
            lines.append(
                f"  │  {'':22}    "
                f"{'EV':<6} {'DIST':<5} {'BRL%':<6} {'PULL%':<6} {'FB%':<5} "
                f"{'SWEET%':<7} {'HH%':<6} {'xwOBA':<7} {'xwOBAcon':<9} "
                f"{'SwStr%':<7} {'HR/FB%':<7} {'ISO':<6} {'PulledBrl'}"
            )
            lines.append(f"  │  {'':22}    ★ HR EDGE=batter power vs pitch  ⚠ WEAK=batter struggles  ○ SUPPRESSOR=pitcher kills barrels")
            lines.append(f"  │  {'-'*112}")

            for b in r["top_batters"]:
                hand       = b.get("bats", "R")
                bscore_s   = f"{b.get('barrel_score', 0):.1f}"
                mscore_s   = f"{b.get('matchup_score', 0):.1f}"
                hzs_s      = f"{b.get('hr_zone_score', 0):.1f}"
                form_str   = (f"{b['hr_form_pct']}%{b['hr_form_trend']}"
                              if b.get("hr_form_pct") is not None else " N/A")
                nr_str     = str(b.get("near_hr_L10")) if b.get("near_hr_L10") is not None else "?"

                # Row 1: identity + scores + prob
                lines.append(
                    f"  │  {b['batter_name']:<22} {hand:<2} {bscore_s:<7} {mscore_s:<7}"
                    f" {hzs_s:<7} {b['hr_prob']:<6.1f}% {b['implied_odds']:<8}"
                    f" {b['zone_fit']:.3f}  {form_str:<6} {nr_str:<3}"
                )

                # Row 2: contact / power stats
                ev_s    = _fmt(b.get("exit_velo"),  ".1f")
                dist_s  = f"{int(b['avg_dist'])}" if b.get("avg_dist") else "  -"
                brl_s   = _fmt(b.get("brl_bip"),    ".1f", "%")
                pull_s  = _fmt(b.get("pull_pct"),   ".0f", "%")
                fb_s    = _fmt(b.get("fb_pct"),     ".0f", "%")
                sweet_s = _fmt(b.get("sweet_spot"), ".0f", "%")
                hh_s    = _fmt(b.get("hh_pct"),     ".0f", "%")
                xwoba_s = _fmt(b.get("xwoba"),      ".3f")
                xwcon_s = _fmt(b.get("xwoba_con"),  ".3f")
                swst_s  = _fmt(b.get("swstr_pct"),  ".1f", "%")
                hrfb_s  = _fmt(b.get("hr_fb_pct"),  ".1f", "%")
                iso_s   = _fmt(b.get("iso") or b.get("xiso"), ".3f")
                pbrl_s  = _fmt(b.get("pulled_brl"), ".1f")

                # Only include profile/power tags (not pitch edge tags — those go on row 3)
                base_tags  = [t for t in (b.get("tags") or [])
                              if not t.startswith("HR EDGE") and not t.startswith("WEAK")
                                 and not t.startswith("SUPPRESSED")]
                tag_str = " | ".join(base_tags) if base_tags else ""

                lines.append(
                    f"  │  {'':22}    "
                    f"{ev_s:<6} {dist_s:<5} {brl_s:<6} {pull_s:<6} {fb_s:<5} "
                    f"{sweet_s:<7} {hh_s:<6} {xwoba_s:<7} {xwcon_s:<9} "
                    f"{swst_s:<7} {hrfb_s:<7} {iso_s:<6} {pbrl_s}"
                    + (f"  ◄ {tag_str}" if tag_str else "")
                )

                # Row 3: pitch matchup edges / weak spots / suppressors / velo
                detail_parts = []
                if b.get("hr_edges"):
                    parts = [f"{e['pitch_type']}({e.get('b_xwoba',0):.3f}·{e.get('b_hh',0):.0f}%HH)"
                             for e in b["hr_edges"][:3]]
                    detail_parts.append("★ HR EDGE: " + " | ".join(parts))
                if b.get("weak_spots"):
                    parts = [f"{w['pitch_type']}({w.get('b_whiff',0):.0f}%WHF·{w.get('b_xwoba',0):.3f})"
                             for w in b["weak_spots"][:2]]
                    detail_parts.append("⚠ WEAK: " + " | ".join(parts))
                if b.get("suppressors") and not b.get("hr_edges"):
                    parts = [f"{s['pitch_type']}({s.get('p_xwoba_ag',0):.3f}·{s.get('p_put_away',0):.0f}%PA)"
                             for s in b["suppressors"][:2]]
                    detail_parts.append("○ SUPPRESS: " + " | ".join(parts))
                if b.get("velo_edge"):
                    detail_parts.append(f"⚡ {b['velo_edge']}")
                elif b.get("velo_signal"):
                    detail_parts.append(f"⚡ {b['velo_signal']}")
                if b.get("chase_signal"):
                    detail_parts.append(f"↯ {b['chase_signal']}")
                if b.get("count_seq_signal"):
                    detail_parts.append(f"⏱ {b['count_seq_signal']}")
                if b.get("h2h_signal"):
                    detail_parts.append(f"🆚 {b['h2h_signal']}")
                arm_slot = b.get("arm_slot", "")
                arm_mult = b.get("arm_mult", 1.0)
                if arm_slot and arm_mult != 1.0:
                    adj = "↓ deceptive" if arm_mult < 1.0 else "↑ batter-friendly"
                    detail_parts.append(f"〽 ARM: {arm_slot} ({adj} ×{arm_mult:.2f})")
                if b.get("velo_tier") and b.get("ff_velo", 0) > 0:
                    detail_parts.append(f"🔥 VELO: {b['velo_tier']} ({b['ff_velo']:.1f}mph)")

                if detail_parts:
                    lines.append(f"  │  {'':22}   {'  ·  '.join(detail_parts)}")

        lines.append("  └" + "─" * 80)

    lines.append("\n" + "=" * W)
    return "\n".join(lines)


def format_batter_spotlight(results: list, game_date: str, min_matchup_score: float = 60.0) -> str:
    """
    Batter-centric view: lists every batter above min_matchup_score across all games,
    ranked by matchup_score. Shows the full stat grid — not grouped by pitcher.
    """
    all_batters = []
    for r in results:
        for b in r["top_batters"]:
            if b.get("matchup_score", 0) >= min_matchup_score:
                all_batters.append({**b,
                    "game": r["game"],
                    "pitcher_name": r["pitcher_name"],
                    "pitcher_throws": r.get("pitcher_throws", "R"),
                    "vuln_score": r["vuln"]["score"],
                    "vuln_tier": r["vuln"]["tier"],
                })
    all_batters.sort(key=lambda x: -(x.get("matchup_score") or 0))

    if not all_batters:
        return f"No batters above MatchupScore {min_matchup_score:.0f} today."

    W = 90
    lines = []
    lines.append("=" * W)
    lines.append(f"  BATTER SPOTLIGHT — {game_date}  (MatchupScore ≥ {min_matchup_score:.0f})")
    lines.append(f"  Ranked by MatchupScore = HRScore×0.55 + ZoneFit×600×0.45")
    lines.append("=" * W)
    lines.append(
        f"\n  {'BATTER':<22} {'H':<2} {'MSCORE':<7} {'BSCORE':<7} {'HR%':<6} {'ODDS':<8} "
        f"{'ZF':<6} {'GAME':<12} {'PITCHER':<22} {'VULN':<5} {'TIER'}"
    )
    lines.append(
        f"  {'':22}    "
        f"{'EV':<6} {'DIST':<5} {'BRL%':<6} {'PULL%':<6} {'FB%':<5} "
        f"{'SWEET%':<7} {'HH%':<6} {'xwOBA':<7} {'xwOBAcon':<9} "
        f"{'SwStr%':<7} {'HR/FB%':<7} {'ISO':<6} {'PulledBrl'}"
    )
    lines.append(f"  {'-'*112}")

    for b in all_batters:
        hand       = b.get("bats", "R")
        mscore_s   = f"{b.get('matchup_score', 0):.1f}"
        bscore_s   = f"{b.get('barrel_score', 0):.1f}"
        form_str   = (f"{b['hr_form_pct']}%{b['hr_form_trend']}"
                      if b.get("hr_form_pct") is not None else " N/A")
        ptch_hand  = "L" if b.get("pitcher_throws") == "L" else "R"
        ptch_name  = f"{b['pitcher_name'][:20]} ({ptch_hand})"
        tier_sym   = "★" if b["vuln_tier"] == "Attackable" else ("◎" if b["vuln_tier"] == "Neutral Lean" else "○")

        lines.append(
            f"  {b['batter_name']:<22} {hand:<2} {mscore_s:<7} {bscore_s:<7}"
            f" {b['hr_prob']:<6.1f}% {b['implied_odds']:<8}"
            f" {b['zone_fit']:.3f}  {b['game']:<12} {ptch_name:<22} {b['vuln_score']:<5.1f} {tier_sym}{b['vuln_tier']}"
        )

        ev_s    = _fmt(b.get("exit_velo"),  ".1f")
        dist_s  = f"{int(b['avg_dist'])}" if b.get("avg_dist") else "  -"
        brl_s   = _fmt(b.get("brl_bip"),    ".1f", "%")
        pull_s  = _fmt(b.get("pull_pct"),   ".0f", "%")
        fb_s    = _fmt(b.get("fb_pct"),     ".0f", "%")
        sweet_s = _fmt(b.get("sweet_spot"), ".0f", "%")
        hh_s    = _fmt(b.get("hh_pct"),     ".0f", "%")
        xwoba_s = _fmt(b.get("xwoba"),      ".3f")
        xwcon_s = _fmt(b.get("xwoba_con"),  ".3f")
        swst_s  = _fmt(b.get("swstr_pct"),  ".1f", "%")
        hrfb_s  = _fmt(b.get("hr_fb_pct"),  ".1f", "%")
        iso_s   = _fmt(b.get("iso") or b.get("xiso"), ".3f")
        pbrl_s  = _fmt(b.get("pulled_brl"), ".1f")
        tag_str = " | ".join(b["tags"]) if b.get("tags") else ""

        lines.append(
            f"  {'':22}    "
            f"{ev_s:<6} {dist_s:<5} {brl_s:<6} {pull_s:<6} {fb_s:<5} "
            f"{sweet_s:<7} {hh_s:<6} {xwoba_s:<7} {xwcon_s:<9} "
            f"{swst_s:<7} {hrfb_s:<7} {iso_s:<6} {pbrl_s}"
            + (f"  ◄ {tag_str}" if tag_str else "")
        )
        lines.append("")

    lines.append("=" * W)
    return "\n".join(lines)


def format_park_fit_board(results: list, game_date: str, min_park_fit: float = 40.0) -> str:
    """
    Park Fit HR board — batter-centric view ranked by Park Fit score.

    Columns: Player | Team | Bats | Park Fit | Signal Lane | Discovery
             | Blast% | Barrel% | Pulled Air% | Pulled Brl% | HH% | LA | Pull Wall
    """
    all_batters = []
    for r in results:
        for b in r["top_batters"]:
            if b.get("park_fit", 0) >= min_park_fit:
                all_batters.append({
                    **b,
                    "team":          r["opp_team"],
                    "game":          r["game"],
                    "pitcher_name":  r["pitcher_name"],
                    "pitcher_throws": r.get("pitcher_throws", "R"),
                    "vuln_score":    r["vuln"]["score"],
                })
    all_batters.sort(key=lambda x: -(x.get("park_fit") or 0))

    W = 120
    lines = []
    lines.append("=" * W)
    lines.append(f"  PARK FIT HR BOARD — {game_date}  (Park Fit ≥ {min_park_fit:.0f})")
    lines.append(f"  Park Fit = Pull Wall Dist (40%) + Pulled Barrel Rate (30%) + Blast% (20%) + Pulled Air% (10%)")
    lines.append("=" * W)

    if not all_batters:
        lines.append(f"  No batters with Park Fit ≥ {min_park_fit:.0f} today.")
        return "\n".join(lines)

    # Header
    lines.append(
        f"\n  {'PLAYER':<22} {'TEAM':<5} {'H':<2} {'PARK FIT':<9} "
        f"{'SIGNAL LANE':<18} {'DISCOVERY':<18} "
        f"{'BLAST%':<7} {'BARREL%':<8} {'P.AIR%':<8} {'P.BRL%':<8} "
        f"{'HH%':<6} {'LA':<6} {'PULL WALL'}"
    )
    lines.append(f"  {'-'*118}")

    for b in all_batters:
        pf      = b.get("park_fit", 0.0)
        signal  = b.get("signal_lane", "No signal")
        disc    = b.get("discovery", "-")
        blast   = b.get("blast_pct", 0.0)
        barrel  = b.get("brl_bip", 0.0)
        p_air   = b.get("pulled_air_pct", 0.0)
        p_brl   = b.get("pulled_brl_pct", 0.0)
        hh      = b.get("hh_pct", 0.0)
        la      = b.get("la_avg", 0.0)
        wall    = b.get("pull_wall_label", "-")

        # Tier marker for Park Fit
        pf_marker = "★" if pf >= 65 else ("◆" if pf >= 50 else " ")

        blast_s  = f"{blast:.1f}%" if blast else "   -"
        barrel_s = f"{barrel:.1f}%" if barrel else "   -"
        p_air_s  = f"{p_air:.1f}%" if p_air else "   -"
        p_brl_s  = f"{p_brl:.1f}%" if p_brl else "   -"
        hh_s     = f"{hh:.1f}%" if hh else "  -"
        la_s     = f"{la:.1f}°" if la else "  -"

        lines.append(
            f"  {b['batter_name']:<22} {b['team']:<5} {b.get('bats','?'):<2} "
            f"{pf_marker}{pf:<8.1f} {signal:<18} {disc:<18} "
            f"{blast_s:<7} {barrel_s:<8} {p_air_s:<8} {p_brl_s:<8} "
            f"{hh_s:<6} {la_s:<6} {wall}"
        )

    lines.append("\n" + "=" * W)
    lines.append("  LEGEND:  ★ Park Fit ≥ 65  ◆ Park Fit ≥ 50")
    lines.append("  Signal Lane: 'Elite HR Profile' = HRScore≥65 AND ParkFit≥55")
    lines.append("  Discovery:   'Signal + park fit' = top tier  |  'Park-Fit Watch' = park favorable, profile building")
    lines.append("  Pulled Air% = % fly balls pulled (Statcast); Pulled Brl% = barrel rate × pull% proxy")
    lines.append("=" * W)
    return "\n".join(lines)
