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
    load_savant_pitcher_k,
    get_h2h_stats,
    get_park_hr_factor,
    get_game_lineups,
    fetch_batter_statcast_events,
    fetch_pitcher_statcast_pitches,
    PARK_FACTORS,
    PULL_WALLS,
)
from datetime import timedelta

LEAGUE_HR_PA   = 0.034   # MLB avg HR/PA 2025-26
MARKET_VIG_BEP = 0.524

# Near-HR: a non-HR batted ball with HR-caliber speed/angle/carry
NEAR_HR_EV   = 98.0
NEAR_HR_LA   = (20.0, 35.0)
NEAR_HR_DIST = 360.0


def _prob_to_odds(prob: float) -> str:
    if prob >= 99.0:
        return "+100"
    p = max(0.001, prob / 100.0)
    return f"-{round((p / (1 - p)) * 100)}" if p >= 0.50 else f"+{round(((1 - p) / p) * 100)}"


def _expected_pa(order: int) -> float:
    return max(3.2, 4.6 - (order - 1) * 0.13)


def _is_barrel(ev: float, la: float) -> bool:
    # Statcast barrel: 98 mph at 26-30°, window widens ~1° per mph each side up to 116 mph
    if ev < 98.0:
        return False
    spread = min(ev, 116.0) - 98.0
    return (26.0 - spread) <= la <= (30.0 + spread)

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


# ── Pitcher L5 HR rate ───────────────────────────────────────────────────────

_pitcher_l5_cache: dict = {}  # {pitcher_id: {"hr_pg": float, "label": str}}


def _pitcher_l5_hr_rate(pitcher_id: int, season: int) -> dict:
    """
    HR allowed per game in last 5 starts.
    Returns {"hr_pg": float, "n": int, "label": str, "vuln_adjust": float}
    vuln_adjust > 1.0 = more vulnerable recently; < 1.0 = locked down.
    """
    key = (pitcher_id, season)
    if key in _pitcher_l5_cache:
        return _pitcher_l5_cache[key]
    default = {"hr_pg": None, "n": 0, "label": "", "vuln_adjust": 1.0}
    try:
        url = (f"{MLB_API}/people/{pitcher_id}/stats"
               f"?stats=gameLog&group=pitching&season={season}&sportId=1")
        data = _get(url) or {}
        splits = (data.get("stats") or [{}])[0].get("splits", [])
        starts = [s for s in splits
                  if _safe(s.get("stat", {}).get("inningsPitched")) >= 1.0][-5:]
        if not starts:
            _pitcher_l5_cache[key] = default
            return default
        n       = len(starts)
        total_hr = sum(int(_safe(s["stat"].get("homeRuns", 0))) for s in starts)
        hr_pg    = total_hr / n
        # Adjust: league avg ~1.1 HR/game allowed; high = vulnerable
        if hr_pg >= 2.0:
            label        = f"L5 HR VULN ({hr_pg:.1f}/G)"
            vuln_adjust  = 1.20
        elif hr_pg >= 1.4:
            label        = f"L5 HR ELEV ({hr_pg:.1f}/G)"
            vuln_adjust  = 1.10
        elif hr_pg == 0.0 and n >= 3:
            label        = f"L5 HR LOCK ({n}GS 0HR)"
            vuln_adjust  = 0.82
        elif hr_pg <= 0.4 and n >= 3:
            label        = f"L5 HR LOW ({hr_pg:.1f}/G)"
            vuln_adjust  = 0.90
        else:
            label       = ""
            vuln_adjust = 1.0
        result = {"hr_pg": round(hr_pg, 2), "n": n, "label": label, "vuln_adjust": vuln_adjust}
        _pitcher_l5_cache[key] = result
        return result
    except Exception:
        _pitcher_l5_cache[key] = default
        return default


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

# Minimum plate appearances before a handedness split is treated as evidence
# rather than noise. 150 of 802 pitchers on the 2026 vs-LHB board are under it.
HAND_SPLIT_MIN_PA = 40


def _vuln_tier(score: float) -> str:
    """Bucket a vulnerability score into its tier label."""
    if score > 63:
        return "Attackable"
    if score > 45:
        return "Neutral Lean"
    return "Avoid"


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

    return round(score, 1), _vuln_tier(score)


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

    # Handedness splits.
    #
    # A split is only evidence if the pitcher has actually faced that side. 150
    # of 802 pitchers on the 2026 vs-LHB leaderboard have under 40 PA, and the
    # engine could not tell "suppresses lefties" from "has barely faced lefties"
    # — a reliever with 4 PA vs LHB scored as an elite left-handed suppressor.
    # Below the floor the split is marked insufficient and blended toward the
    # pitcher's overall vulnerability in proportion to the sample we do have.
    lhb_score, lhb_tier = (None, None)
    rhb_score, rhb_tier = (None, None)
    lhb_pa = rhb_pa = 0
    lhb_thin = rhb_thin = False

    def _blend_split(split_data):
        """(score, tier, pa, thin) for one handedness split."""
        if not split_data:
            return None, None, 0, False
        raw_score, raw_tier = _vuln_from_data(split_data, era)
        spa = int(split_data.get("pa") or 0)
        if spa >= HAND_SPLIT_MIN_PA:
            return raw_score, raw_tier, spa, False
        # Weight the split by how much of the floor it reached; the rest of the
        # weight falls back to the pitcher's full-sample score.
        w = spa / HAND_SPLIT_MIN_PA if spa > 0 else 0.0
        blended = raw_score * w + score * (1.0 - w)
        return round(blended, 1), _vuln_tier(blended), spa, True

    if pitcher_hr_lhb:
        lhb_score, lhb_tier, lhb_pa, lhb_thin = _blend_split(pitcher_hr_lhb.get(pid, {}))
    if pitcher_hr_rhb:
        rhb_score, rhb_tier, rhb_pa, rhb_thin = _blend_split(pitcher_hr_rhb.get(pid, {}))

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
        "lhb_pa":         lhb_pa,
        "lhb_thin":       lhb_thin,
        "rhb_score":      rhb_score,
        "rhb_tier":       rhb_tier,
        "rhb_pa":         rhb_pa,
        "rhb_thin":       rhb_thin,
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
_pitcher_mlb_hand_splits_cache: dict = {}  # {pitcher_id: {vl: {slg, hr9, bb_pct}, vr: {...}}}


def _fetch_pitcher_hand_splits(pitcher_id: int, season: int) -> dict:
    """Fetch pitcher's LHB/RHB season splits from MLB API. Returns {vl: {...}, vr: {...}}."""
    ckey = f"{pitcher_id}_{season}"
    if ckey in _pitcher_mlb_hand_splits_cache:
        return _pitcher_mlb_hand_splits_cache[ckey]
    try:
        url = (f"{MLB_API}/people/{pitcher_id}/stats"
               f"?stats=statSplits&group=pitching&season={season}&sitCodes=vl,vr")
        data = _get(url)
        result = {}
        for sp in (data or {}).get("stats", [{}])[0].get("splits", []):
            code = sp.get("split", {}).get("code", "")
            st = sp.get("stat", {})
            bf = st.get("battersFaced", 0) or 1
            try:
                slg = float(st.get("slg") or 0)
            except (ValueError, TypeError):
                slg = 0.0
            result[code] = {
                "slg":    slg,
                "hr9":    float(st.get("homeRunsPer9") or 0),
                "bb_pct": round(st.get("baseOnBalls", 0) / bf * 100, 1),
                "bf":     bf,
            }
        _pitcher_mlb_hand_splits_cache[ckey] = result
        return result
    except Exception:
        return {}


def _quick_batter_entry(batter_id: int, batter_name: str, bats: str,
                        pitcher_id: int, pitcher_name: str, venue_name: str,
                        pitcher_vuln: dict, pitcher_throws: str,
                        batter_hr_data: dict, savant_batting: dict,
                        bat_track: dict, pitcher_arsenal: dict,
                        batter_pitch_splits: dict,
                        pitcher_mlb_splits: dict = None) -> dict:
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

    # Pitcher MLB hand-split bonus: actual season SLG allowed by batter hand
    hand_split_bonus = 0.0
    hand_split_tag   = None
    if pitcher_mlb_splits and bats in ("L", "R"):
        hand_code  = "vl" if bats == "L" else "vr"
        other_code = "vr" if bats == "L" else "vl"
        my_slg    = pitcher_mlb_splits.get(hand_code, {}).get("slg", 0.0)
        other_slg = pitcher_mlb_splits.get(other_code, {}).get("slg", 0.0)
        my_bf     = pitcher_mlb_splits.get(hand_code, {}).get("bf", 0)
        if my_bf >= 50 and my_slg > 0 and (my_slg - other_slg) >= 0.04:
            hand_split_bonus = min(10.0, (my_slg - other_slg - 0.04) * 80)
            hand_label = "LHB" if bats == "L" else "RHB"
            hand_split_tag = f"HAND SPLIT: vs{hand_label} SLG .{int(my_slg*1000):03d}"
            matchup_score = min(100.0, matchup_score + hand_split_bonus)

    # Power elite bonus: elite raw power gets floor boost regardless of pitcher tier
    # Catches Murakami-type (20%+ barrel, 55%+ HH) in neutral matchups
    power_elite_bonus = 0.0
    if brl_bip >= 14.0 and hh_pct >= 52.0 and exit_velo >= 92.0:
        power_elite_bonus = 7.0
        matchup_score = min(100.0, matchup_score + power_elite_bonus)
    elif brl_bip >= 12.0 and hh_pct >= 50.0:
        power_elite_bonus = 4.0
        matchup_score = min(100.0, matchup_score + power_elite_bonus)

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
    # Handedness-split park factor (LHB vs RHB pull-side distances)
    park_hr    = get_park_hr_factor(venue_name, bats)
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
    if hand_split_tag:
        tags.append(hand_split_tag)
    if power_elite_bonus >= 7.0:
        tags.append(f"POWER ELITE (brl={brl_bip:.1f}% hh={hh_pct:.1f}% ev={exit_velo:.1f})")
    elif power_elite_bonus >= 4.0:
        tags.append(f"POWER STRONG (brl={brl_bip:.1f}% hh={hh_pct:.1f}%)")

    return {
        "batter_id":      batter_id,
        "batter_name":    batter_name,
        "bats":           bats,
        "hr_score":       hr_score,
        "barrel_score":   round(barrel_score, 1),
        "matchup_score":  round(matchup_score, 1),
        "hr_prob":        prob,
        "implied_odds":   odds,
        "hr_lam":         round(lam, 4),
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
        "hand_split_bonus":  round(hand_split_bonus, 1),
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
    pitcher_k_data        = load_savant_pitcher_k(season)

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
            ptags        = _pitcher_tags(pitcher_id, pitcher_hr_data, pitcher_arsenal)
            mlb_hand_splits = _fetch_pitcher_hand_splits(pitcher_id, season)
            l5_hr_data      = _pitcher_l5_hr_rate(pitcher_id, season)
            if l5_hr_data.get("label"):
                ptags.append(l5_hr_data["label"])
            # Apply L5 HR vuln adjustment to pitcher's composite score
            if l5_hr_data.get("vuln_adjust", 1.0) != 1.0:
                adj_score = min(100.0, max(0.0,
                    vuln["score"] * l5_hr_data["vuln_adjust"]))
                vuln = dict(vuln)
                vuln["score"]     = round(adj_score, 1)
                vuln["l5_hr_adj"] = l5_hr_data["vuln_adjust"]
                vuln["l5_hr_label"] = l5_hr_data.get("label", "")
                # Re-tier after adjustment
                if adj_score > 63:
                    vuln["tier"] = "Attackable"
                elif adj_score > 45:
                    vuln["tier"] = "Neutral Lean"
                else:
                    vuln["tier"] = "Avoid"
            else:
                vuln["l5_hr_adj"]   = 1.0
                vuln["l5_hr_label"] = l5_hr_data.get("label", "")
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
                    mlb_hand_splits,
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

                # Dome park HR suppressor: controlled air suppresses ball flight regardless of batter profile
                if w_data.get("dome"):
                    entry["matchup_score"] = max(0.0, entry["matchup_score"] - 8.0)
                    entry["dome_penalty"] = -8.0
                    entry.setdefault("tags", [])
                    dome_tag = "DOME PARK (-8 HR)"
                    if dome_tag not in entry["tags"]:
                        entry["tags"].insert(0, dome_tag)
                else:
                    entry["dome_penalty"] = 0.0
                entry["is_dome"] = w_data.get("dome", False)

                # Soft Arm Lock: submarine/sidearm pitcher + soft velo + no weak spots
                # + multiple HR edges + walk-heavy pitcher = repeatable power spot.
                # Joc Pederson vs Ryan Johnson 8/11 was the prototype: 1HR + 3BB.
                p_arm_slot  = entry.get("arm_slot", "")
                p_arm_mult  = entry.get("arm_mult", 1.0)
                p_ff_velo   = entry.get("ff_velo", 0.0)
                p_hr_edges  = entry.get("hr_edges", [])
                p_weak_spots= entry.get("weak_spots", [])
                p_bb_pct    = (pitcher_k_data.get(str(pitcher_id), {}) or {}).get("bb_pct", 0.0) or 0.0
                batter_bats = entry.get("bats", "R") or "R"
                opp_platoon_slg = 0.0
                # Determine same-hand platoon SLG (we don't have live platoon here,
                # but arm_mult >= 1.02 already encodes the opposite-hand advantage;
                # use it as a proxy to confirm favorable platoon)
                soft_arm_lock = (
                    p_arm_slot in ("Submarine", "Sidearm")
                    and p_arm_mult >= 1.02
                    and 0 < p_ff_velo < 92.0
                    and len(p_hr_edges) >= 2
                    and len(p_weak_spots) == 0
                    and p_bb_pct >= 9.5   # WALK THREAT threshold
                )
                if soft_arm_lock:
                    entry["matchup_score"] = min(99.9, entry["matchup_score"] + 8.0)
                    entry.setdefault("tags", [])
                    lock_tag = "🔒 SOFT ARM LOCK (+8)"
                    if lock_tag not in entry["tags"]:
                        entry["tags"].insert(0, lock_tag)
                entry["soft_arm_lock"] = soft_arm_lock

                # Rank by matchup_score — already includes vuln + zone fit + hr profile
                rank_key = entry["matchup_score"]
                batter_entries.append((rank_key, entry))

            batter_entries.sort(key=lambda x: -x[0])
            top_batters = [e for _, e in batter_entries[:12]]

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


def _statcast_window(events: list, n_games: int) -> dict:
    """Aggregate a batter's Statcast rows over their last n_games distinct game dates."""
    dates = sorted({e["game_date"] for e in events if e["game_date"]})
    keep  = set(dates[-n_games:])
    rows  = [e for e in events if e["game_date"] in keep]
    games = len(keep)
    pa    = sum(1 for e in rows if e["is_pa"])
    bbe   = [e for e in rows if e["in_play"] and e["launch_speed"] > 0]
    hr    = sum(1 for e in rows if e["events"] == "home_run")
    barrels  = sum(1 for e in bbe if _is_barrel(e["launch_speed"], e["launch_angle"]))
    hard_hit = sum(1 for e in bbe if e["launch_speed"] >= 95.0)
    near = [e for e in bbe
            if e["events"] != "home_run"
            and e["launch_speed"] >= NEAR_HR_EV
            and NEAR_HR_LA[0] <= e["launch_angle"] <= NEAR_HR_LA[1]
            and e["hit_distance"] >= NEAR_HR_DIST]
    dist_rows = [e["hit_distance"] for e in bbe if e["hit_distance"] > 0]
    return {
        "games":     games,
        "pa":        pa,
        "pa_pg":     round(pa / games, 2) if games else 0.0,
        "bbe":       len(bbe),
        "hr":        hr,
        "near_hr":   len(near),
        "barrels":   barrels,
        "brl_pct":   round(barrels / len(bbe) * 100, 1) if bbe else 0.0,
        "hh_pct":    round(hard_hit / len(bbe) * 100, 1) if bbe else 0.0,
        "avg_ev":    round(sum(e["launch_speed"] for e in bbe) / len(bbe), 1) if bbe else 0.0,
        "max_ev":    round(max((e["launch_speed"] for e in bbe), default=0.0), 1),
        "avg_dist":  round(sum(dist_rows) / len(dist_rows), 0) if dist_rows else 0.0,
        "avg_la":    round(sum(e["launch_angle"] for e in bbe) / len(bbe), 1) if bbe else 0.0,
    }


# Plate grid: 5 columns of 0.5 ft across, 5 rows of 0.6 ft up, catcher's view.
# Middle 3x3 approximates the strike zone; the outer ring is chase territory.
ZONE_X = (-1.25, 1.25)
ZONE_Z = (1.00, 4.00)
ZONE_N = 5


def _zone_grid(events: list) -> list:
    """
    Per-location damage for one batter: a 5x5 grid of swing outcomes.

    Each cell carries how often the ball was put in play there, the average exit
    velocity, mean xwOBA on contact, and home runs — enough to show where a
    hitter does damage and where he can be beaten.
    """
    cells = [{"n": 0, "ev": 0.0, "xw": 0.0, "hr": 0, "swings": 0, "whiffs": 0}
             for _ in range(ZONE_N * ZONE_N)]
    xw_lo, xw_hi = ZONE_X
    z_lo, z_hi = ZONE_Z
    xstep = (xw_hi - xw_lo) / ZONE_N
    zstep = (z_hi - z_lo) / ZONE_N

    for e in events:
        px, pz = e.get("plate_x"), e.get("plate_z")
        if px is None or pz is None or (px == 0.0 and pz == 0.0):
            continue
        col = int((px - xw_lo) / xstep)
        row = int((z_hi - pz) / zstep)          # row 0 = top of the zone
        if not (0 <= col < ZONE_N and 0 <= row < ZONE_N):
            continue
        c = cells[row * ZONE_N + col]
        if e.get("is_swing"):
            c["swings"] += 1
        if e.get("is_whiff"):
            c["whiffs"] += 1
        if e.get("in_play") and e.get("launch_speed", 0) > 0:
            c["n"] += 1
            c["ev"] += e["launch_speed"]
            c["xw"] += e.get("xwoba") or 0.0
            if e.get("events") == "home_run":
                c["hr"] += 1

    out = []
    for c in cells:
        out.append({
            "n": c["n"],
            "ev": round(c["ev"] / c["n"], 1) if c["n"] else None,
            "xwoba": round(c["xw"] / c["n"], 3) if c["n"] else None,
            "hr": c["hr"],
            "whiff": round(c["whiffs"] / c["swings"] * 100, 1) if c["swings"] >= 3 else None,
            "swings": c["swings"],
        })
    return out


_HIT_EVENTS = {"single", "double", "triple", "home_run"}
_TB_VALUE = {"single": 1, "double": 2, "triple": 3, "home_run": 4}


def _game_log(events: list, n_games: int = 5) -> list:
    """Per-game batting line for the last n games, derived from pitch-level rows."""
    dates = sorted({e["game_date"] for e in events if e["game_date"]})
    out = []
    for d in dates[-n_games:]:
        rows = [e for e in events if e["game_date"] == d]
        pa = [e for e in rows if e["is_pa"]]
        bbe = [e for e in rows if e["in_play"] and e["launch_speed"] > 0]
        hits = [e for e in pa if e["events"] in _HIT_EVENTS]
        dist = [e["hit_distance"] for e in bbe if e["hit_distance"] > 0]
        out.append({
            "date": d[5:],
            "pa": len(pa),
            "ab": sum(1 for e in pa if e["events"] not in _NON_AB),
            "h": len(hits),
            "hr": sum(1 for e in pa if e["events"] == "home_run"),
            "tb": sum(_TB_VALUE.get(e["events"], 0) for e in pa),
            "bb": sum(1 for e in pa if e["events"] in ("walk", "intent_walk")),
            "k": sum(1 for e in pa if e["events"] in ("strikeout", "strikeout_double_play")),
            "bbe": len(bbe),
            "avg_ev": round(sum(e["launch_speed"] for e in bbe) / len(bbe), 1) if bbe else None,
            "max_ev": round(max((e["launch_speed"] for e in bbe), default=0), 1) or None,
            "best_dist": int(max(dist)) if dist else None,
            "hard": sum(1 for e in bbe if e["launch_speed"] >= 95.0),
        })
    return out


def enrich_statcast_recent(results: list, game_date: str, top_n: int = 120,
                           lookback_days: int = 30) -> list:
    """
    Post-build: pull pitch-level Statcast rows for the top-N batters and attach
    rolling L5/L10/L15 windows (EV, max EV, distance, barrels, near-HR) plus the
    batter's hardest non-HR balls. Tags HARD LUCK (near-HRs without HRs) and
    EV SURGE (110+ mph recently); fills hr_form_pct / near_hr_L10 / avg_dist.
    """
    gd    = datetime.strptime(game_date, "%Y-%m-%d").date()
    start = (gd - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end   = (gd - timedelta(days=1)).strftime("%Y-%m-%d")

    all_entries = []
    for r in results:
        for b in r["top_batters"]:
            all_entries.append((b["matchup_score"], b["batter_id"], b))
    all_entries.sort(key=lambda x: -x[0])

    seen: set = set()
    to_enrich: list = []
    for ms, bid, b in all_entries:
        if bid in seen:
            continue
        if len(to_enrich) < top_n or ms >= 35.0:
            seen.add(bid)
            to_enrich.append(bid)

    sc_map: dict = {}
    for bid in to_enrich:
        try:
            events = fetch_batter_statcast_events(bid, start, end)
        except Exception:
            events = []
        if not events:
            continue
        w5, w10, w15 = (_statcast_window(events, n) for n in (5, 10, 15))
        dates_l10 = set(sorted({e["game_date"] for e in events})[-10:])
        hard_luck = sorted(
            (e for e in events
             if e["game_date"] in dates_l10 and e["in_play"] and e["launch_speed"] >= 95.0
             and e["events"] != "home_run" and e["launch_angle"] >= 15.0),
            key=lambda e: -e["launch_speed"])[:3]
        sc_map[bid] = {
            "L5": w5, "L10": w10, "L15": w15,
            "zone_grid": _zone_grid(events),
            "zone_window_days": lookback_days,
            "game_log": _game_log(events, 5),
            "hard_luck_hits": [{
                "date": e["game_date"][5:], "ev": e["launch_speed"],
                "la": e["launch_angle"], "dist": int(e["hit_distance"]),
                "result": e["events"] or "in play", "pitch": e["pitch_type"],
            } for e in hard_luck],
        }
        time.sleep(0.25)

    for r in results:
        for b in r["top_batters"]:
            sc = sc_map.get(b["batter_id"])
            if not sc:
                continue
            w5, w10, w15 = sc["L5"], sc["L10"], sc["L15"]
            b["statcast"]      = sc
            b["near_hr_L5"]    = w5["near_hr"]
            b["near_hr_L10"]   = w10["near_hr"]
            b["recent_ev_L10"] = w10["avg_ev"]
            b["max_ev_L5"]     = w5["max_ev"]
            b["pa_pg_L5"]      = w5["pa_pg"]
            if w15["avg_dist"] and not b.get("avg_dist"):
                b["avg_dist"] = w15["avg_dist"]

            # Recent form vs this batter's own season baseline — the swing in
            # form matters more than the absolute number for a one-game bet.
            season_ev  = b.get("exit_velo") or 0.0
            season_brl = b.get("brl_bip") or 0.0
            season_hh  = b.get("hh_pct") or 0.0
            season_la  = b.get("la_avg") or 0.0
            d = {}
            if season_ev and w10["avg_ev"]:
                d["ev"] = round(w10["avg_ev"] - season_ev, 1)
            if season_brl and w10["brl_pct"]:
                d["brl_pct_rel"] = round((w10["brl_pct"] - season_brl) / season_brl * 100, 1)
            if season_hh and w10["hh_pct"]:
                d["hh_pct_rel"] = round((w10["hh_pct"] - season_hh) / season_hh * 100, 1)
            if season_la and w10["avg_la"]:
                d["la"] = round(w10["avg_la"] - season_la, 1)
            if w5["max_ev"] and b.get("max_ev_season"):
                d["max_ev"] = round(w5["max_ev"] - b["max_ev_season"], 1)
            b["form_delta"] = d
            b["heating_up"] = bool(d.get("ev", 0) >= 2.0 and d.get("brl_pct_rel", 0) >= 15.0)
            if b["heating_up"]:
                tg = b.setdefault("tags", [])
                tg.insert(0, f"📈 HEATING (EV {d['ev']:+.1f} · brl {d['brl_pct_rel']:+.0f}%)")

            season_rate = (b.get("xiso") or 0.0) * 0.22 or LEAGUE_HR_PA
            l10_rate    = w10["hr"] / w10["pa"] if w10["pa"] else season_rate
            ratio       = l10_rate / season_rate if season_rate else 1.0
            b["hr_form_pct"]   = min(99, max(1, int(ratio * 65)))
            b["hr_form_trend"] = "↑" if ratio >= 1.30 else ("↓" if ratio <= 0.70 else "→")

            tags = b.setdefault("tags", [])
            boost = 0.0
            if w10["near_hr"] >= 2 and w10["hr"] <= 1:
                tags.insert(0, f"💥 HARD LUCK ({w10['near_hr']} near-HR L10 / {w10['hr']} HR)")
                boost += 0.04
            if w5["max_ev"] >= 110.0:
                tags.insert(0, f"🚀 EV SURGE ({w5['max_ev']:.0f} mph max L5)")
                boost += 0.02
            if w10["bbe"] >= 15 and w10["brl_pct"] >= 15.0:
                tags.append(f"BARREL RUN ({w10['brl_pct']:.0f}% brl L10)")
            if boost:
                b["matchup_score"] = min(99.9, b["matchup_score"] * (1.0 + boost))
    return results


_TB = {"single": 1, "double": 2, "triple": 3, "home_run": 4}
_NON_AB = {"walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt",
           "catcher_interf", "sac_fly_double_play", "sac_bunt_double_play"}


def _pitcher_hand_split(rows: list) -> dict:
    """Aggregate a pitcher's Statcast rows (already filtered to one batter side)."""
    pa_rows = [r for r in rows if r["is_pa"]]
    pa   = len(pa_rows)
    ab   = sum(1 for r in pa_rows if r["events"] not in _NON_AB)
    hits = sum(1 for r in pa_rows if r["events"] in _TB)
    tb   = sum(_TB.get(r["events"], 0) for r in pa_rows)
    hr   = sum(1 for r in pa_rows if r["events"] == "home_run")
    k    = sum(1 for r in pa_rows if r["events"] in ("strikeout", "strikeout_double_play"))
    bb   = sum(1 for r in pa_rows if r["events"] in ("walk", "intent_walk"))
    swings = sum(1 for r in rows if r["is_swing"])
    whiffs = sum(1 for r in rows if r["is_whiff"])
    bbe  = [r for r in rows if r["in_play"] and r["launch_speed"] > 0]
    hh   = sum(1 for r in bbe if r["launch_speed"] >= 95.0)
    brl  = sum(1 for r in bbe if _is_barrel(r["launch_speed"], r["launch_angle"]))
    wnum = sum(r["woba_value"] for r in pa_rows)
    wden = sum(r["woba_denom"] for r in pa_rows)
    xw   = [r["xwoba"] for r in bbe if r["xwoba"] > 0]
    ba   = hits / ab if ab else 0.0
    slg  = tb / ab if ab else 0.0

    usage: dict = {}
    total = sum(1 for r in rows if r["pitch_type"])
    for pt in {r["pitch_type"] for r in rows if r["pitch_type"]}:
        prow = [r for r in rows if r["pitch_type"] == pt]
        p_sw = sum(1 for r in prow if r["is_swing"])
        p_wh = sum(1 for r in prow if r["is_whiff"])
        two_k = [r for r in prow if r["strikes"] == 2]
        put   = sum(1 for r in two_k if r["events"] in ("strikeout", "strikeout_double_play"))
        p_bbe = [r for r in prow if r["in_play"] and r["launch_speed"] > 0]
        usage[pt] = {
            "usage":    round(len(prow) / total * 100, 1) if total else 0.0,
            "n":        len(prow),
            "whiff":    round(p_wh / p_sw * 100, 1) if p_sw else 0.0,
            "put_away": round(put / len(two_k) * 100, 1) if two_k else 0.0,
            "hh":       round(sum(1 for r in p_bbe if r["launch_speed"] >= 95) / len(p_bbe) * 100, 1) if p_bbe else 0.0,
            "hr":       sum(1 for r in prow if r["events"] == "home_run"),
        }
    return {
        "pitches": len(rows), "pa": pa, "ab": ab, "bf": pa,
        "ba": round(ba, 3), "slg": round(slg, 3), "iso": round(slg - ba, 3),
        "woba": round(wnum / wden, 3) if wden else 0.0,
        "xwoba_con": round(sum(xw) / len(xw), 3) if xw else 0.0,
        "hr": hr, "hr_pct": round(hr / pa * 100, 1) if pa else 0.0,
        "k_pct": round(k / pa * 100, 1) if pa else 0.0,
        "bb_pct": round(bb / pa * 100, 1) if pa else 0.0,
        "whiff_pct": round(whiffs / swings * 100, 1) if swings else 0.0,
        "hh_pct": round(hh / len(bbe) * 100, 1) if bbe else 0.0,
        "brl_pct": round(brl / len(bbe) * 100, 1) if bbe else 0.0,
        "bbe": len(bbe),
        "usage": dict(sorted(usage.items(), key=lambda kv: -kv[1]["usage"])),
    }


def _pitcher_zone_grid(rows: list) -> list:
    """
    Where a pitcher lives and where he gets hurt, on the same 5x5 plate grid as
    the hitters. Location share says how often he puts the ball in each cell;
    xwOBA and home runs say what happens when he does.
    """
    cells = [{"n": 0, "xw": 0.0, "hr": 0, "bbe": 0, "ev": 0.0,
              "swings": 0, "whiffs": 0} for _ in range(ZONE_N * ZONE_N)]
    x_lo, x_hi = ZONE_X
    z_lo, z_hi = ZONE_Z
    xstep = (x_hi - x_lo) / ZONE_N
    zstep = (z_hi - z_lo) / ZONE_N
    total = 0

    for e in rows:
        px, pz = e.get("plate_x"), e.get("plate_z")
        if px is None or pz is None or (px == 0.0 and pz == 0.0):
            continue
        col = int((px - x_lo) / xstep)
        row = int((z_hi - pz) / zstep)
        if not (0 <= col < ZONE_N and 0 <= row < ZONE_N):
            continue
        c = cells[row * ZONE_N + col]
        c["n"] += 1
        total += 1
        if e.get("is_swing"):
            c["swings"] += 1
        if e.get("is_whiff"):
            c["whiffs"] += 1
        if e.get("in_play") and e.get("launch_speed", 0) > 0:
            c["bbe"] += 1
            c["ev"] += e["launch_speed"]
            c["xw"] += e.get("xwoba") or 0.0
            if e.get("events") == "home_run":
                c["hr"] += 1

    out = []
    for c in cells:
        out.append({
            "pitches": c["n"],
            "loc_pct": round(c["n"] / total * 100, 1) if total else 0.0,
            "bbe": c["bbe"],
            "xwoba": round(c["xw"] / c["bbe"], 3) if c["bbe"] else None,
            "ev": round(c["ev"] / c["bbe"], 1) if c["bbe"] else None,
            "hr": c["hr"],
            "whiff": round(c["whiffs"] / c["swings"] * 100, 1) if c["swings"] >= 3 else None,
        })
    return out


def _pitcher_hand_profile(rows: list, recent_starts: int = 3) -> dict:
    """{'L': {'all': split, 'recent': split, 'games': n}, 'R': {...}} by batter side."""
    dates  = sorted({r["game_date"] for r in rows if r["game_date"]})
    recent = set(dates[-recent_starts:])
    out = {}
    for side in ("L", "R"):
        side_rows = [r for r in rows if r["stand"] == side]
        out[side] = {
            "games":  len({r["game_date"] for r in side_rows}),
            "all":    _pitcher_hand_split(side_rows),
            "recent": _pitcher_hand_split([r for r in side_rows if r["game_date"] in recent]),
            "zone_grid": _pitcher_zone_grid(side_rows),
        }
    out["games_total"] = len(dates)
    out["recent_dates"] = sorted(recent)
    return out


def enrich_pitcher_hand_mix(results: list, game_date: str, lookback_days: int = 45,
                            min_pitches_per_side: int = 60) -> list:
    """
    Post-build: pull each starter's recent pitch-level Statcast rows, build vLHB/vRHB
    profiles (usage by pitch, whiff, put-away, BA/SLG/ISO/wOBA, HR, K%, BB%), then
    re-run every batter's pitch-type analysis using the usage the pitcher actually
    shows that batter's side. hr_zone_score is replaced and matchup_score shifted by
    the zone delta at its 0.30 model weight. Tags HAND MIX when a top pitch differs
    >= 8 points between sides.
    """
    gd    = datetime.strptime(game_date, "%Y-%m-%d").date()
    start = (gd - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end   = (gd - timedelta(days=1)).strftime("%Y-%m-%d")
    season = gd.year
    batter_pitch_splits = load_savant_batter_pitch_splits(season)
    pitcher_arsenal     = load_savant_pitcher_arsenal(season)
    bat_track           = load_bat_tracking(season)

    profiles: dict = {}
    for r in results:
        pid = r["pitcher_id"]
        if pid in profiles:
            continue
        try:
            rows = fetch_pitcher_statcast_pitches(pid, start, end)
        except Exception:
            rows = []
        profiles[pid] = _pitcher_hand_profile(rows) if rows else None
        time.sleep(0.25)

    for r in results:
        prof = profiles.get(r["pitcher_id"])
        r["hand_profile"] = prof
        if not prof:
            continue
        base_arsenal = pitcher_arsenal.get(str(r["pitcher_id"]), [])
        throws = r.get("pitcher_throws", "R")

        # Sides where the recent sample is big enough to trust the mix
        side_usage = {}
        for side in ("L", "R"):
            sp = prof[side]["all"]
            if sp["pitches"] >= min_pitches_per_side:
                side_usage[side] = {pt: u["usage"] for pt, u in sp["usage"].items()}

        # Flag pitches whose usage swings materially by side
        swing_tags = []
        if "L" in side_usage and "R" in side_usage:
            for pt in set(side_usage["L"]) | set(side_usage["R"]):
                ul, ur = side_usage["L"].get(pt, 0.0), side_usage["R"].get(pt, 0.0)
                if abs(ul - ur) >= 8.0 and max(ul, ur) >= 15.0:
                    swing_tags.append(f"{pt} {ul:.0f}%vL/{ur:.0f}%vR")
        r["hand_mix_swings"] = swing_tags

        for b in r["top_batters"]:
            if b.get("hand_usage_applied"):
                continue
            bats = b.get("bats", "R")
            side = ("L" if throws == "R" else "R") if bats == "S" else bats
            usage = side_usage.get(side)
            if not usage or not base_arsenal:
                continue
            adjusted = []
            for p in base_arsenal:
                q = dict(p)
                q["usage_pct"] = usage.get(p["pitch_type"], 0.0)
                adjusted.append(q)
            # Pitches the pitcher throws to this side but Savant's season arsenal lacks
            known = {p["pitch_type"] for p in base_arsenal}
            for pt, pct in usage.items():
                if pt not in known and pct >= 5.0:
                    adjusted.append({"pitch_type": pt, "pitch_name": pt, "usage_pct": pct})

            pa = _hr_pitch_analysis(b["batter_id"], r["pitcher_id"], batter_pitch_splits,
                                    {str(r["pitcher_id"]): adjusted},
                                    pitcher_velo_data=_pitcher_velo_cache,
                                    bat_track_data=bat_track)
            old_zone = b.get("hr_zone_score", 0.0) or 0.0
            new_zone = pa["hr_zone_score"]
            b["hr_zone_score_season"] = old_zone
            b["hr_zone_score"]  = new_zone
            b["hr_edges"]       = pa["hr_edges"]
            b["weak_spots"]     = pa["weak_spots"]
            b["suppressors"]    = pa["suppressors"]
            b["pitch_table"]    = pa["pitch_table"]
            b["hand_usage_applied"] = side
            b["matchup_score"]  = min(99.9, max(0.0, b["matchup_score"] + 0.30 * (new_zone - old_zone)))

            tags = b.setdefault("tags", [])
            tags[:] = [t for t in tags if not t.startswith(("HR EDGE:", "WEAK:", "SUPPRESSED:"))]
            if pa["hr_edges"]:
                tags.append(f"HR EDGE: {' '.join(e['pitch_type'] for e in pa['hr_edges'][:2])}")
            if pa["weak_spots"]:
                tags.append(f"WEAK: {' '.join(w['pitch_type'] for w in pa['weak_spots'][:2])}")
            if pa["suppressors"] and not pa["hr_edges"]:
                tags.append(f"SUPPRESSED: {pa['suppressors'][0]['pitch_type']}")
            if swing_tags:
                tags.append(f"HAND MIX v{side}HB: " + ", ".join(swing_tags[:2]))
        r["top_batters"].sort(key=lambda x: (x.get("in_lineup") is False, -x["matchup_score"]))
    return results


# ── Calibration ───────────────────────────────────────────────────────────────
# Multipliers below are anchored to measured hit-rate lift over a 12-slate,
# 2,721-pick sample (base rate 10.9%). Lifts are damped toward 1.0 because the
# per-signal samples are small; see grade_engine.py to re-measure.
#
#   signal          n     rate    lift    applied
#   OWNS PITCHER    13    30.8%   2.83x   1.55
#   FIRE (3+ L5)    51    21.6%   1.98x   1.40
#   HARD LUCK       50    20.0%   1.84x   1.35
#   EV SURGE       118    16.1%   1.48x   1.18
#   DUE            289    15.6%   1.43x   1.15
#   HOT (2 L5)     154    12.3%   1.13x   1.06
#   DOMINATED       21     4.8%   0.44x   0.65
#
# Pitcher vulnerability measured only 1.14x from Attackable to Avoid, so its
# multiplier range is compressed from the original 0.40–1.70 to 0.88–1.14.
SIGNAL_MULTS = [
    ("OWNS PITCHER", 1.55),
    ("🔥 FIRE",      1.40),
    ("HARD LUCK",    1.35),
    ("EV SURGE",     1.18),
    ("DUE",          1.15),
    ("🔥 HOT",       1.06),
    ("DOMINATED",    0.65),
]
# ---------------------------------------------------------------------------
# On the slate-level HR environment (tested, not modelled)
# ---------------------------------------------------------------------------
# Board hit rate tracks league HR/game at r = 0.865, so the day's run
# environment is the single largest unexplained term in this model. Two
# candidate fixes have now been tested and both failed:
#
#   1. Air density / ball carry (see weather_engine.carry_index). Over 102
#      outdoor games: absolute r = +0.087, park-relative r = -0.118, and the
#      thickest-air quartile produced MORE home runs than the thinnest.
#   2. A trailing league HR/game window, i.e. "the league is cold this week".
#      Over 29 slates (Aug 20 - Sep 17, mean 2.237 HR/game, sd 0.404) the
#      trailing mean ANTI-correlates with the next slate at every window:
#      3-slate r = -0.109, 5-slate -0.072, 7-slate -0.181, 10-slate -0.317.
#      Out-of-sample MAE never beats an expanding season constant by more than
#      noise (best: 5-slate 0.327 vs 0.344).
#
# The practical consequence is that a run of low-HR days is mean reversion, not
# a trend to extrapolate, and the base rate should stay a season constant.
# Do not add a "league is cold" multiplier without out-of-sample evidence.

CAL_SHRINK_KNEE = 0.15   # probabilities above this are pulled toward the knee
CAL_SHRINK_RATE = 0.55   # observed 20-25% band ran ~6 pts hot, 25%+ ran far hotter
CAL_MAX_SIGNAL  = 2.10   # cap stacked signals so one bat cannot run away

# Bucketed multipliers fitted on 1,632 graded picks across six slates and damped
# toward 1.0 by sample size (n/(n+60)). Leave-one-slate-out, ranking by the
# resulting score took the top-20 hit rate from 16.7% to 20.8%, beating the old
# ranking on five of six held-out days.
#
# Park fit turned out to be the strongest single feature in the whole model
# (0.44x at the bottom, 1.52x at the top) despite previously only feeding a
# display tag. HR/FB rate and lineup slot were similarly under-used. Barrel rate
# is deliberately non-monotonic: the 11-14% band outperforms the 17%+ band,
# which is a small and streaky group.
FIT_MULTS = {
    "park_fit":  [(0, 30, 0.44), (30, 50, 0.91), (50, 70, 1.44), (70, 1e9, 1.52)],
    "hr_fb_pct": [(0, 10, 0.56), (10, 14, 0.97), (14, 18, 1.53), (18, 1e9, 1.10)],
    "brl_bip":   [(0, 8, 0.79), (8, 11, 0.76), (11, 14, 1.66), (14, 17, 1.41), (17, 1e9, 0.91)],
    "ev10":      [(0, 86, 0.94), (86, 89, 1.26), (89, 92, 1.27), (92, 1e9, 1.61)],
    "zone":      [(0, 20, 0.82), (20, 45, 1.20), (45, 70, 1.41), (70, 1e9, 1.16)],
    "vuln":      [(0, 25, 0.88), (25, 45, 1.02), (45, 63, 1.11), (63, 1e9, 1.04)],
    "park":      [(0, 0.92, 0.92), (0.92, 1.02, 0.87), (1.02, 1.12, 0.99), (1.12, 1e9, 1.26)],
}
ORDER_MULTS = [(1, 3, 1.53), (3, 6, 1.31), (6, 10, 0.90)]
# Scales the geometric mean so predicted probability matches observed frequency.
# Ranking is unchanged by this constant (it is a monotonic transform), so it is
# tuned purely for calibration: at 0.80 the mean prediction is 11.1% against a
# 10.8% base rate and weighted calibration error is 0.32 points, versus 2.15
# before the feature fit and 2.63 before any calibration.
FEAT_SPREAD = 0.80


def _bucket_mult(table: list, val) -> float:
    if val is None:
        return 1.0
    for lo, hi, m in table:
        if lo <= val < hi:
            return m
    return 1.0


def calibrate_probabilities(results: list) -> list:
    """
    Final pipeline pass: rebuild hr_prob from weighted components now that tags,
    Statcast form, H2H and lineup slots are all attached.

        lam = hr_rate_per_pa x expected_PA x vuln x park x zone x signals

    Component weights come from grade_engine measurements rather than intuition:
    signal tags earn real multipliers, pitcher vulnerability is demoted, and the
    top of the distribution is shrunk because it ran consistently hot.

    Keeps the pre-calibration value in hr_prob_raw so the shift stays auditable.
    """
    for r in results:
        vuln = r["vuln"]["score"]
        for b in r["top_batters"]:
            xiso = b.get("xiso") or 0.0
            base_rate = (xiso * 0.22) if xiso > 0 else LEAGUE_HR_PA
            exp_pa = _expected_pa(b["order"]) if b.get("order") else 4.0
            ev10 = ((b.get("statcast") or {}).get("L10") or {}).get("avg_ev")

            parts = {
                "park_fit":  _bucket_mult(FIT_MULTS["park_fit"], b.get("park_fit")),
                "hr_fb_pct": _bucket_mult(FIT_MULTS["hr_fb_pct"], b.get("hr_fb_pct")),
                "brl_bip":   _bucket_mult(FIT_MULTS["brl_bip"], b.get("brl_bip")),
                "ev10":      _bucket_mult(FIT_MULTS["ev10"], ev10),
                "zone":      _bucket_mult(FIT_MULTS["zone"], b.get("hr_zone_score")),
                "vuln":      _bucket_mult(FIT_MULTS["vuln"], vuln),
                "park":      _bucket_mult(FIT_MULTS["park"], b.get("park_hr_factor")),
            }
            order_mult = 1.0
            if b.get("order"):
                for lo, hi, m in ORDER_MULTS:
                    if lo <= b["order"] < hi:
                        order_mult = m
                        break

            tags = b.get("tags", [])
            sig_mult, fired = 1.0, []
            for needle, mult in SIGNAL_MULTS:
                if any(needle in t for t in tags):
                    sig_mult *= mult
                    fired.append(needle)
            sig_mult = min(sig_mult, CAL_MAX_SIGNAL)

            # Each multiplier was fitted marginally against the same base rate,
            # and the features are strongly correlated — a hitter with good park
            # fit also tends to carry high barrel and HR/FB rates. Multiplying
            # them would count that shared signal seven times over and push
            # probabilities past 50%. The geometric mean keeps the ordering the
            # leave-one-slate-out test validated while restoring a sane scale.
            feat_mult = math.exp(
                sum(math.log(m) for m in parts.values()) / len(parts)
            ) * FEAT_SPREAD

            lam = base_rate * exp_pa * feat_mult * order_mult * sig_mult
            prob = 1.0 - math.exp(-max(lam, 0.0005))

            # Shrink the top end: the 20%+ bands ran 6-18 points hot when graded
            if prob > CAL_SHRINK_KNEE:
                prob = CAL_SHRINK_KNEE + (prob - CAL_SHRINK_KNEE) * CAL_SHRINK_RATE

            pct = round(prob * 100, 1)
            b["hr_prob_raw"]   = b.get("hr_prob")
            b["hr_prob"]       = pct
            b["implied_odds"]  = _prob_to_odds(pct)
            b["hr_lam"]        = round(lam, 4)
            b["cal_signals"]   = fired
            b["cal_sig_mult"]  = round(sig_mult, 3)
            b["cal_parts"]     = {k: round(v, 3) for k, v in parts.items()}
            b["cal_order_mult"] = order_mult
    return results


MARQUEE_BATS = {
    "Shohei Ohtani", "Aaron Judge", "Mookie Betts", "Freddie Freeman",
    "Ronald Acuña Jr.", "Ronald Acuna Jr.", "Mike Trout", "Juan Soto",
    "Bryce Harper", "Yordan Alvarez", "Kyle Schwarber", "Vladimir Guerrero Jr.",
    "Fernando Tatis Jr.", "Manny Machado", "Pete Alonso", "Corey Seager",
    "Bobby Witt Jr.", "Elly De La Cruz", "Julio Rodríguez", "Cal Raleigh",
    "Rafael Devers", "José Ramírez", "Francisco Lindor", "Matt Olson",
    "Bryan Reynolds", "Oneil Cruz", "Riley Greene", "Gunnar Henderson",
    "Adley Rutschman", "James Wood", "Jackson Merrill", "Paul Skenes",
}


LEVERAGE_MODEL_CUT = 0.15   # must sit in the model's top 15% to qualify at all
LEVERAGE_MIN_GAP   = 0.05   # and the crowd must rank it at least this much lower


def tag_chalk_levels(results: list) -> list:
    """
    Label how public each play is, and flag the ones the crowd is underrating.

    An earlier version tagged anything with a long price and no marquee name as
    LEVERAGE. Graded over 986 such picks it returned a 0.80x lift — below the
    base rate — because a long price usually just means a bad hitter. Low
    profile on its own is not an edge.

    Leverage is now a disagreement measure: the play has to rank in the model's
    top 15% *and* sit meaningfully lower in a crowd-facing ranking (price plus
    marquee status). That version graded 16.3% against a 10.4% base, a 1.57x
    lift on roughly 9% of the board.

    The other tiers stay descriptive rather than predictive — marquee bats in
    the model's top 20% hit 15.0% versus 14.2% for everyone else, so fading
    chalk for its own sake has no measurable edge.
    """
    live = [(b, r) for r in results for b in r["top_batters"]
            if b.get("in_lineup") is not False]
    if not live:
        return results
    n = len(live)

    by_model = sorted(live, key=lambda x: -(x[0].get("hr_prob") or 0.0))
    model_rank = {id(b): i / n for i, (b, _) in enumerate(by_model)}

    # What a bettor scanning a board sees: the price, plus the name they know.
    def crowd_key(pair):
        b = pair[0]
        return -((b.get("hr_prob") or 0.0) * 0.75 +
                 (30.0 if b["batter_name"] in MARQUEE_BATS else 0.0))
    by_crowd = sorted(live, key=crowd_key)
    crowd_rank = {id(b): i / n for i, (b, _) in enumerate(by_crowd)}

    for b, _r in live:
        mr, cr = model_rank[id(b)], crowd_rank[id(b)]
        gap = cr - mr                       # positive: model rates it above the crowd
        marquee = b["batter_name"] in MARQUEE_BATS
        public = (1.0 - cr) * 100.0         # 100 = most public play on the slate

        if mr <= LEVERAGE_MODEL_CUT and gap >= LEVERAGE_MIN_GAP:
            tier, badge = "LEVERAGE", "💎"
        elif public >= 85 or (marquee and public >= 70):
            tier, badge = "HEAVY CHALK", "🔒"
        elif public >= 65:
            tier, badge = "CHALKY", "⚠️"
        else:
            tier, badge = "BALANCED", "○"

        b["chalk_score"]  = round(public, 1)
        b["chalk_tier"]   = tier
        b["chalk_badge"]  = badge
        b["is_marquee"]   = marquee
        b["model_rank"]   = round(mr, 4)
        b["crowd_rank"]   = round(cr, 4)
        b["leverage_gap"] = round(gap, 4)

    for r in results:
        for b in r["top_batters"]:
            if b.get("in_lineup") is False:
                b.setdefault("chalk_score", None)
                b.setdefault("chalk_tier", "OUT")
                b.setdefault("chalk_badge", "")
                b.setdefault("is_marquee", b["batter_name"] in MARQUEE_BATS)
    return results


CTX_CODES = "vl,vr,d,n,h,a"
CTX_MIN_PA = 40          # below this a split is noise
CTX_EDGE_OPS = 0.060     # OPS gap that counts as a real lean either way


def _fetch_batter_context_splits(batter_id: int, season: int) -> dict:
    """Season splits by pitcher hand, day/night, and home/away — one API call."""
    data = _get(f"{MLB_API}/people/{batter_id}/stats", {
        "stats": "statSplits", "group": "hitting", "season": season,
        "sportId": 1, "sitCodes": CTX_CODES,
    })
    out = {}
    for s in (data or {}).get("stats", [{}])[0].get("splits", []):
        code = s.get("split", {}).get("code", "")
        st = s.get("stat", {})
        pa = st.get("plateAppearances", 0) or 0
        if not code or pa == 0:
            continue
        try:
            out[code] = {
                "pa": pa,
                "ba": float(st.get("avg") or 0),
                "obp": float(st.get("obp") or 0),
                "slg": float(st.get("slg") or 0),
                "ops": float(st.get("ops") or 0),
                "hr": st.get("homeRuns", 0) or 0,
                "hr_pa": round((st.get("homeRuns", 0) or 0) / pa * 100, 1),
            }
        except (TypeError, ValueError):
            continue
    return out


def enrich_context_splits(results: list, game_date: str, top_n: int = 150) -> list:
    """
    Attach the season splits that actually apply to tonight's game.

    A hitter's overall line hides which version of him shows up: some wake up
    against left-handers, some only hit in daylight, some are different players
    on the road. This pulls vs-LHP / vs-RHP, day / night and home / away, then
    keeps the three that match this particular game — the starter's hand, the
    first-pitch time, and which dugout he is in — so the context reads as one
    sentence rather than a table of everything.

    Splits under 40 plate appearances are carried but marked thin, and a gap of
    60 OPS points against the hitter's own overall line is flagged as an edge.
    """
    season = int(game_date[:4])
    games = {g["game_pk"]: g for g in get_today_games(game_date)}
    daynight, home_team = {}, {}
    try:
        sched = _get(f"{MLB_API}/schedule", {"sportId": 1, "date": game_date}) or {}
        for d in sched.get("dates", []):
            for g in d.get("games", []):
                daynight[g.get("gamePk")] = (g.get("dayNight") or "night").lower()
    except Exception:
        pass

    ranked = sorted(
        ((b, r) for r in results for b in r["top_batters"]
         if b.get("in_lineup") is not False),
        key=lambda x: -(x[0].get("matchup_score") or 0))
    seen, order = set(), []
    for b, r in ranked:
        if b["batter_id"] not in seen and len(order) < top_n:
            seen.add(b["batter_id"])
            order.append(b["batter_id"])
    want = set(order)

    cache = {}
    for bid in order:
        try:
            cache[bid] = _fetch_batter_context_splits(bid, season)
        except Exception:
            cache[bid] = {}
        time.sleep(0.08)

    for r in results:
        dn = daynight.get(r.get("game_pk"), "night")
        # the batting side is whichever team the pitcher is not on
        bats_home = r.get("pitcher_side") == "away"
        throws = r.get("pitcher_throws", "R")
        for b in r["top_batters"]:
            sp = cache.get(b["batter_id"])
            if not sp:
                continue
            overall_ops = max((v["ops"] for v in sp.values() if v["pa"] >= CTX_MIN_PA), default=0)
            base = (sp.get("vr", {}).get("ops", 0) * sp.get("vr", {}).get("pa", 0)
                    + sp.get("vl", {}).get("ops", 0) * sp.get("vl", {}).get("pa", 0))
            tot_pa = sp.get("vr", {}).get("pa", 0) + sp.get("vl", {}).get("pa", 0)
            season_ops = round(base / tot_pa, 3) if tot_pa else overall_ops

            picked = {}
            for label, code in (("hand", "vl" if throws == "L" else "vr"),
                                ("time", "d" if dn == "day" else "n"),
                                ("site", "h" if bats_home else "a")):
                v = sp.get(code)
                if not v:
                    continue
                picked[label] = dict(v, code=code,
                                     thin=v["pa"] < CTX_MIN_PA,
                                     edge=round(v["ops"] - season_ops, 3))

            b["ctx_splits"] = picked
            b["ctx_season_ops"] = season_ops
            b["ctx_daynight"] = dn
            b["ctx_home"] = bats_home

            notes = []
            for label, v in picked.items():
                if v["thin"] or abs(v["edge"]) < CTX_EDGE_OPS:
                    continue
                name = {"hand": f"vs {'LHP' if throws == 'L' else 'RHP'}",
                        "time": f"{dn} games", "site": "at home" if bats_home else "on the road"}[label]
                notes.append(f"{name} {v['ops']:.3f} OPS ({v['edge']:+.3f}, {v['pa']} PA)")
            b["ctx_notes"] = notes
    return results


def enrich_lineups(results: list, game_date: str) -> list:
    """
    Post-build: attach confirmed batting order, rescale HR prob by expected PA
    for the slot, and flag batters not in the posted lineup. Before lineups post,
    every batter keeps order=None and in_lineup=None.
    """
    try:
        lineups = get_game_lineups(game_date) or {}
    except Exception:
        lineups = {}

    for r in results:
        opp_side = "home" if r.get("pitcher_side") == "away" else "away"
        lineup   = lineups.get(r.get("game_pk"), {}).get(opp_side, {})
        r["lineup_confirmed"] = bool(lineup)
        for b in r["top_batters"]:
            order = lineup.get(str(b["batter_id"]))
            b["order"] = order
            if not lineup:
                b["in_lineup"] = None
                continue
            b["in_lineup"] = order is not None
            if order is None:
                b.setdefault("tags", []).insert(0, "NOT IN LINEUP")
                continue
            prob = b.get("hr_prob") or 0.0
            lam  = b.get("hr_lam") or (-math.log(1.0 - min(prob, 99.0) / 100.0) if prob else 0.0)
            if lam <= 0:
                continue
            exp_pa = _expected_pa(order)
            lam2   = lam / 4.0 * exp_pa
            b["exp_pa"]       = round(exp_pa, 1)
            b["hr_prob"]      = round((1.0 - math.exp(-lam2)) * 100, 1)
            b["implied_odds"] = _prob_to_odds(b["hr_prob"])
        if lineup:
            r["top_batters"].sort(key=lambda x: (x.get("in_lineup") is False, -x["matchup_score"]))
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


# ---------------------------------------------------------------------------
# Stale probable-pitcher detection
# ---------------------------------------------------------------------------
# Boards are built hours before first pitch and then used at game time. When a
# team changes its starter in between, the board keeps scoring every hitter
# against a pitcher who is not pitching, and says nothing about it.
#
# This cost a real read on 2026-09-16: the BAL@NYM board carried Robert Stock
# for New York, but the actual starter was Xzavion Curry — a reliever with 8
# appearances and 0 starts, who then gave up four home runs to exactly the
# Baltimore hitters the board had ranked. The matchup data was wrong; the bats
# were right. The correct handling is to flag the game and widen the estimate,
# not to leave stale numbers sitting there looking authoritative.

from baseball_engine import PEN_HR_MULT

BULLPEN_GS_RATIO = 0.25   # < this share of appearances started ⇒ treat as a pen arm
BULLPEN_MIN_APPEARANCES = 4


def _pitcher_role(pitcher_id: int, season: int) -> dict:
    """Classify a pitcher as a starter or a bullpen/opener arm."""
    try:
        data = _get(f"{MLB_API}/people/{pitcher_id}", {
            "hydrate": f"stats(group=[pitching],type=[season],season={season})",
        }) or {}
        people = data.get("people") or []
        for grp in (people[0].get("stats") or []) if people else []:
            for sp in grp.get("splits", []):
                st = sp.get("stat", {})
                g  = st.get("gamesPlayed") or 0
                gs = st.get("gamesStarted") or 0
                if not g:
                    continue
                ratio = gs / g
                return {
                    "games": g, "starts": gs, "gs_ratio": round(ratio, 3),
                    "ip": st.get("inningsPitched"),
                    "is_bullpen": ratio < BULLPEN_GS_RATIO and g >= BULLPEN_MIN_APPEARANCES,
                }
    except Exception:
        pass
    return {"games": 0, "starts": 0, "gs_ratio": None, "ip": None, "is_bullpen": False}


def enrich_probable_check(results: list, game_date: str) -> list:
    """Re-check every board entry against the live probable pitcher.

    Sets on each entry:
      probable_stale   — the starter changed since the board was built
      probable_live    — {id, name} actually announced
      bullpen_game     — the listed starter is a pen arm / opener
      probable_note    — one line explaining what to do about it

    A stale or bullpen start widens hr_prob toward the batter's own
    park-and-form baseline instead of trusting the dead matchup terms: the
    matchup multiplier is pulled halfway back to neutral, which keeps strong
    bats ranked while removing the false precision of the wrong arm.
    """
    season = int(game_date[:4])
    try:
        live = _get(f"{MLB_API}/schedule", {
            "sportId": 1, "date": game_date, "hydrate": "probablePitcher",
        }) or {}
    except Exception:
        return results

    probables = {}
    for d in live.get("dates", []):
        for g in d.get("games", []):
            pk = g.get("gamePk")
            for side in ("away", "home"):
                pp = (g.get("teams", {}).get(side, {}) or {}).get("probablePitcher") or {}
                if pp.get("id"):
                    probables[(pk, side)] = {"id": pp["id"], "name": pp.get("fullName", "")}

    for r in results:
        key = (r.get("game_pk"), r.get("pitcher_side"))
        cur = probables.get(key)
        r["probable_stale"] = False
        r["bullpen_game"]   = False
        r["probable_note"]  = ""
        if not cur:
            continue

        r["probable_live"] = cur
        stale = cur["id"] != r.get("pitcher_id")
        role  = _pitcher_role(cur["id"], season)
        r["bullpen_game"] = bool(role.get("is_bullpen"))
        r["probable_role"] = role

        if not stale and not r["bullpen_game"]:
            continue

        r["probable_stale"] = stale
        if stale and r["bullpen_game"]:
            r["probable_note"] = (
                f"STARTER CHANGED to {cur['name']} — bullpen game "
                f"({role['starts']}/{role['games']} GS). Matchup terms below are for "
                f"{r.get('pitcher_name')} and no longer apply; lean on the bats."
            )
        elif stale:
            r["probable_note"] = (
                f"STARTER CHANGED: {r.get('pitcher_name')} → {cur['name']}. "
                f"Matchup terms are stale."
            )
        else:
            r["probable_note"] = (
                f"BULLPEN GAME: {cur['name']} has {role['starts']} starts in "
                f"{role['games']} appearances. Expect multiple arms."
            )

        # Neutralize the terms that belong to the pitcher who is not pitching.
        # cal_parts splits cleanly: park_fit / hr_fb_pct / brl_bip / ev10 / park
        # are properties of the batter and the venue and stay valid, while zone
        # (batter's fit against THIS arm's locations) and vuln (THIS arm's
        # HR-vulnerability) are now meaningless. Reset those two to 1.0 and
        # recompute the geometric mean rather than guessing at a haircut.
        pen_mult = PEN_HR_MULT if r["bullpen_game"] else 1.0
        for b in r["top_batters"]:
            prob = b.get("hr_prob") or 0.0
            parts = b.get("cal_parts") or {}
            if prob <= 0:
                continue
            b["hr_prob_prestale"] = prob

            if parts:
                dead = [k for k in ("zone", "vuln") if k in parts]
                if dead:
                    neutral_parts = dict(parts)
                    for k in dead:
                        neutral_parts[k] = 1.0
                    old_feat = math.exp(sum(math.log(max(v, 1e-6)) for v in parts.values()) / len(parts))
                    new_feat = math.exp(sum(math.log(max(v, 1e-6)) for v in neutral_parts.values()) / len(neutral_parts))
                    lam = (b.get("hr_lam") or 0.0) * (new_feat / old_feat) * pen_mult
                    if lam > 0:
                        p_new = 1.0 - math.exp(-lam)
                        if p_new > CAL_SHRINK_KNEE:
                            p_new = CAL_SHRINK_KNEE + (p_new - CAL_SHRINK_KNEE) * CAL_SHRINK_RATE
                        b["hr_lam"] = round(lam, 4)
                        b["hr_prob"] = round(p_new * 100, 1)
                        b["cal_parts"] = {k: round(v, 3) for k, v in neutral_parts.items()}
            else:
                b["hr_prob"] = round(prob * pen_mult, 1)

            b["implied_odds"] = _prob_to_odds(b["hr_prob"])
            b.setdefault("tags", []).insert(0, "⚠️ PITCHER TBD" if stale else "⚠️ BULLPEN GAME")
    return results
