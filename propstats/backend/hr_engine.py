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
    PARK_FACTORS,
)

LEAGUE_HR_PA   = 0.034   # MLB avg HR/PA 2025-26
MARKET_VIG_BEP = 0.524


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


# ── Pitcher vulnerability ────────────────────────────────────────────────────

def _vuln_from_data(d: dict, era_fallback: float = 4.50) -> tuple:
    """Compute (score, tier) from a pitcher HR-vuln data dict."""
    barrel = _safe(d.get("barrel_allowed"))
    xwoba  = _safe(d.get("xwoba_allowed"))
    fb_pct = _safe(d.get("fb_pct_allowed"))
    la_avg = _safe(d.get("la_avg_allowed"))
    xslg   = _safe(d.get("xslg_allowed"))

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
        "la_avg_allowed": round(la_avg, 1),
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

    xwoba = _safe(d.get("xwoba_allowed"))
    barrel = _safe(d.get("barrel_allowed"))
    era = _safe(d.get("era"), 4.50)

    if xwoba > 0.350 and era > 4.50:
        tags.append("MEATBALL PITCHER")
    if barrel > 10.0:
        tags.append("HIGH BARREL RATE ALLOWED")

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

    s_brl    = _scale(brl_bip,    2.0,  7.0,  16.0)
    s_pull   = _scale(pull_pct,   25.0, 40.0, 55.0)
    s_sweet  = _scale(sweet_spot, 25.0, 34.0, 45.0)
    s_xiso   = _scale(xiso,       0.05, 0.14, 0.260)
    s_la     = _scale(la_avg,     4.0,  14.0, 24.0)
    s_hh     = _scale(hh_pct,     30.0, 43.0, 56.0)
    s_blast  = _scale(blast,      0.02, 0.04, 0.07) if blast else 0.0

    if hh_pct and blast:
        score = (s_brl * 0.32 + s_pull * 0.18 + s_sweet * 0.16
                 + s_xiso * 0.14 + s_la * 0.08 + s_hh * 0.08 + s_blast * 0.04)
    else:
        score = (s_brl * 0.35 + s_pull * 0.25 + s_sweet * 0.20
                 + s_xiso * 0.15 + s_la * 0.05)

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

    brl_bip  = _safe(d.get("brl_per_bip"))
    pull_pct = _safe(d.get("pull_pct"))
    fb_pct   = _safe(d.get("fb_pct"))
    la_avg   = _safe(d.get("la_avg"))
    sweet    = _safe(d.get("sweet_spot_pct"))
    xiso     = _safe(d.get("xiso"))
    xwoba    = _safe(d.get("xwoba"))
    hh_pct   = _safe(ev.get("hard_hit_pct"))
    exit_velo = _safe(ev.get("exit_velo"))        # avg EV from Savant batting
    avg_dist  = _safe(d.get("avg_distance"))       # season avg distance

    hr_score = _batter_hr_score(batter_hr_data, savant_batting, bat_track, batter_id)
    zone_fit = _zone_fit(batter_id, pitcher_id, batter_pitch_splits, pitcher_arsenal)

    # Use platoon-adjusted vuln score for this batter
    vuln_score = _hand_vuln_score(pitcher_vuln, bats, pitcher_throws)
    est_hr_pa = xiso * 0.22 if xiso > 0 else LEAGUE_HR_PA
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

    pulled_brl = round(brl_bip * pull_pct / 100, 1) if brl_bip and pull_pct else 0.0

    tags = []
    if brl_bip >= 10.0:
        tags.append("BARREL SIGNAL")
    if brl_bip >= 7.0 and pull_pct >= 40.0 and fb_pct >= 28.0:
        tags.append("AIR PULL")
    if hh_pct >= 45.0:
        tags.append("BLASTS")
    if sweet >= 38.0:
        tags.append("SWEET SPOT")

    return {
        "batter_id":    batter_id,
        "batter_name":  batter_name,
        "bats":         bats,
        "hr_score":     hr_score,
        "hr_prob":      prob,
        "implied_odds": odds,
        "zone_fit":     zone_fit,
        "hr_form_pct":  None,
        "hr_form_trend":"?",
        "near_hr_L10":  None,     # N/A in fast mode (no game log)
        "exit_velo":    round(exit_velo, 1) if exit_velo else None,
        "avg_dist":     round(avg_dist, 0) if avg_dist else None,
        "brl_bip":      brl_bip,
        "pull_pct":     pull_pct,
        "fb_pct":       fb_pct,
        "la_avg":       la_avg,
        "sweet_spot":   sweet,
        "xiso":         xiso,
        "xwoba":        xwoba,
        "pulled_brl":   pulled_brl,
        "park_hr_factor": park_hr,
        "vuln_used":    round(vuln_score, 1),   # which hand score was applied
        "venue":        venue_name,
        "tags":         tags,
        "pitcher_name": pitcher_name,
    }


def build_hr_attack_board(game_date: str) -> list:
    """
    Fast build: all data from pre-loaded Savant CSVs, one roster API call per team.
    No per-batter season stats calls — uses xISO-based HR rate proxy.
    Sorted by pitcher vulnerability score descending.
    """
    season = int(game_date[:4])
    games  = get_today_games(game_date)

    # Load all Savant data once (cached after first call)
    batter_hr_data      = load_savant_batter_hr(season)
    pitcher_hr_data     = load_savant_pitcher_hr(season)
    pitcher_hr_lhb      = load_savant_pitcher_hr_vs_hand(season, "L")
    pitcher_hr_rhb      = load_savant_pitcher_hr_vs_hand(season, "R")
    pitcher_arsenal     = load_savant_pitcher_arsenal(season)
    batter_pitch_splits = load_savant_batter_pitch_splits(season)
    savant_batting      = load_savant_batting(season)
    bat_track           = load_bat_tracking(season)

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
                # Rank by combined hr_score + zone_fit
                rank_key = entry["hr_score"] * 0.55 + (entry["zone_fit"] * 600) * 0.45
                batter_entries.append((rank_key, entry))

            batter_entries.sort(key=lambda x: -x[0])
            top_batters = [e for _, e in batter_entries[:5]]

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
            })

    results.sort(key=lambda x: -(x["vuln"]["score"]))
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


# ── Formatting ───────────────────────────────────────────────────────────────

def format_hr_attack_board(results: list, game_date: str) -> str:
    lines = []
    lines.append("=" * 76)
    lines.append(f"  HR ATTACK BOARD — {game_date}")
    lines.append(f"  Pitcher Vulnerability Score: xwOBA_allowed + Barrel% + FB% + LA allowed")
    lines.append(f"  Batter HR Score: BRL/BIP (35%) + Pull% (25%) + SweetSpot (20%) + xISO (15%)")
    lines.append("=" * 76)

    # Summary table
    lines.append(f"\n  {'PITCHER':<22} {'OPP':<5} {'SCORE':<7} {'TIER':<14} "
                 f"{'BRL_ALL':<8} {'xwOBA_ALL':<10} {'FB%_ALL':<8} {'ERA'}")
    lines.append(f"  {'-'*74}")

    for r in results:
        v = r["vuln"]
        tier_sym = "★" if v["tier"] == "Attackable" else ("◎" if v["tier"] == "Neutral Lean" else "○")
        barrel   = f"{v['barrel_allowed']:.1f}%" if v['barrel_allowed'] else "  -  "
        xwoba    = f"{v['xwoba_allowed']:.3f}" if v['xwoba_allowed'] else "  -  "
        fb       = f"{v['fb_pct_allowed']:.1f}%" if v['fb_pct_allowed'] else "  -  "
        era      = f"{v['era']:.2f}" if v['era'] else "  -"
        lines.append(
            f"  {r['pitcher_name']:<22} {r['opp_team']:<5} {v['score']:<7.1f}"
            f" {tier_sym} {v['tier']:<12} {barrel:<8} {xwoba:<10} {fb:<8} {era}"
        )

    lines.append("\n" + "=" * 76)
    lines.append("  TOP READS PER PITCHER")
    lines.append("=" * 76)

    for r in results:
        v = r["vuln"]
        tier_sym = "★" if v["tier"] == "Attackable" else ("◎" if v["tier"] == "Neutral Lean" else "○")
        ptag_str = "  [" + ", ".join(r["pitcher_tags"]) + "]" if r["pitcher_tags"] else ""

        lines.append(f"\n  ┌─ {r['pitcher_name']} ({r['pitcher_team']})  vs {r['opp_team']}"
                     f"  │  {r['game']}")
        p_throws = r.get("pitcher_throws", "R")
        if p_throws == "L":
            # LHP: same-hand LHB suppressed, opposite-hand RHB boosted
            hand_note = f"  [LHP — vs LHB ×0.91 | vs RHB ×1.09]"
        else:
            # RHP: same-hand RHB suppressed, opposite-hand LHB boosted
            hand_note = f"  [RHP — vs LHB ×1.09 | vs RHB ×0.91]"
        lines.append(f"  │  Vuln: {v['score']:.1f}  {tier_sym} {v['tier']}{ptag_str}{hand_note}")
        lines.append(f"  │  Barrel Allowed: {v['barrel_allowed']:.1f}%  "
                     f"xwOBA: {v['xwoba_allowed'] or '-'}  "
                     f"xSLG: {v['xslg_allowed'] or '-'}  "
                     f"FB%: {v['fb_pct_allowed']:.1f}%  "
                     f"LA: {v['la_avg_allowed']:.1f}°  "
                     f"ERA: {v['era'] or '-'}")

        # Arsenal
        arsenal_str = "  │  Arsenal: "
        for p in r["arsenal"]:
            arsenal_str += f"{p.get('pitch_name','?')} {p.get('usage_pct',0):.0f}%  "
        lines.append(arsenal_str.rstrip())

        if not r["top_batters"]:
            lines.append("  │  (no batter data)")
        else:
            lines.append(f"  │")
            lines.append(f"  │  {'BATTER':<22} {'H':<2} {'SCORE':<6} {'HR%':<7} {'ODDS':<8} "
                         f"{'ZF':<6} {'FORM':<7} {'NR':<3} {'EV':<5} {'DIST':<6} "
                         f"{'BRL':<5} {'PULL':<5} TAGS")
            lines.append(f"  │  {'-'*108}")
            for b in r["top_batters"]:
                tag_str  = " | ".join(b["tags"]) if b["tags"] else ""
                form_str = (f"{b['hr_form_pct']}%{b['hr_form_trend']}"
                            if b.get("hr_form_pct") is not None else " N/A")
                brl_str  = f"{b['brl_bip']:.1f}%" if b.get('brl_bip') else "  - "
                pull_str = f"{b['pull_pct']:.0f}%" if b.get('pull_pct') else "  - "
                ev_str   = f"{b['exit_velo']:.1f}" if b.get("exit_velo") else "  - "
                dist_str = f"{int(b['avg_dist'])}" if b.get("avg_dist") else "  - "
                nr_str   = str(b.get("near_hr_L10")) if b.get("near_hr_L10") is not None else " ?"
                hand     = b.get("bats", "R")
                lines.append(
                    f"  │  {b['batter_name']:<22} {hand:<2} {b['hr_score']:<6.1f}"
                    f" {b['hr_prob']:<7.1f}% {b['implied_odds']:<8}"
                    f" {b['zone_fit']:.3f}  {form_str:<7} {nr_str:<3} {ev_str:<5} {dist_str:<6}"
                    f" {brl_str:<5} {pull_str:<5} {tag_str}"
                )

        lines.append("  └" + "─" * 74)

    lines.append("\n" + "=" * 76)
    return "\n".join(lines)
