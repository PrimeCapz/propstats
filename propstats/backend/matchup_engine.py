"""
Matchup Machine Engine
Pulls pitch-by-pitch Statcast data from Baseball Savant and generates:
  - Pitcher arsenal breakdown (pitch mix, velo, whiff%, CSW%, wOBA, HR rate)
  - Strike-zone heatmaps (per pitch type, frequency + result overlays)
  - Batter hot/cold zone charts (wOBA by zone vs RHP/LHP)
  - Full pitcher-vs-batter matchup card PNG
  - Grade algorithm: usage-weighted, league-normalized wOBA advantage
"""

import io
import time
import threading
import requests
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from scipy.ndimage import gaussian_filter

SAVANT = "https://baseballsavant.mlb.com/statcast_search/csv"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Strike zone boundaries (feet from center)
SZ_LEFT, SZ_RIGHT = -0.83, 0.83
SZ_BOT, SZ_TOP    =  1.50, 3.50
PLATE_W = 0.83 * 2

# Visual style
BG    = "#0f1117"
CARD  = "#1a1d2e"
TEXT  = "#e2e8f0"
MUTED = "#94a3b8"
GREEN = "#10b981"
RED   = "#ef4444"
YELLOW= "#f59e0b"
ACCENT= "#3b82f6"
ORANGE= "#f97316"

PITCH_COLORS = {
    "FF": "#ef4444",   # 4-seam: red
    "SI": "#f97316",   # sinker: orange
    "FC": "#f59e0b",   # cutter: yellow
    "SL": "#3b82f6",   # slider: blue
    "ST": "#8b5cf6",   # sweeper: purple
    "SV": "#8b5cf6",   # slurve: purple
    "CU": "#06b6d4",   # curve: cyan
    "KC": "#06b6d4",   # knuckle-curve: cyan
    "CH": "#10b981",   # changeup: green
    "FS": "#22d3ee",   # splitter: teal
    "FO": "#22d3ee",   # fork: teal
    "KN": "#94a3b8",   # knuckleball: muted
}

PITCH_ABBR = {
    "4-Seam Fastball":"FF","Sinker":"SI","Cutter":"FC","Slider":"SL",
    "Sweeper":"ST","Curveball":"CU","Knuckle Curve":"KC","Changeup":"CH",
    "Split-Finger":"FS","Forkball":"FO","Knuckleball":"KN","Slurve":"SV",
}

# ── League averages by pitch type (2024-25 Statcast population) ───────────────
# Used to normalize batter performance relative to league, not raw numbers.
LEAGUE_WOBA = {
    "FF": 0.373, "SI": 0.347, "FC": 0.332, "SL": 0.295, "ST": 0.282,
    "CU": 0.293, "KC": 0.288, "CH": 0.313, "FS": 0.278, "SV": 0.301,
    "FO": 0.278, "KN": 0.330,
}
LEAGUE_WOBA_DEFAULT = 0.320

LEAGUE_WHIFF = {
    "FF": 21.0, "SI": 17.5, "FC": 23.0, "SL": 33.0, "ST": 39.0,
    "CU": 31.5, "KC": 34.0, "CH": 29.5, "FS": 36.0, "SV": 31.0,
    "FO": 35.0, "KN": 20.0,
}
LEAGUE_WHIFF_DEFAULT = 25.0

LEAGUE_CSW_DEFAULT = 26.5  # called strike + whiff / total pitches

# ── Statcast response cache (TTL=4h, thread-safe) ─────────────────────────────
_SC_CACHE: dict = {}
_SC_LOCK  = threading.Lock()
_SC_TTL   = timedelta(hours=4)


# ── Data Fetching ──────────────────────────────────────────────────────────────

def _fetch_statcast(player_id: int, player_type: str, season: int,
                    date_from: str = None, date_to: str = None) -> pd.DataFrame:
    """
    Pull pitch-by-pitch Statcast data with 4-hour in-process cache.
    player_type: "pitcher" or "batter"
    """
    if not date_from:
        date_from = f"{season}-03-01"
    if not date_to:
        date_to = date.today().strftime("%Y-%m-%d")

    cache_key = (player_id, player_type, season, date_from)
    with _SC_LOCK:
        if cache_key in _SC_CACHE:
            df, ts = _SC_CACHE[cache_key]
            if datetime.now() - ts < _SC_TTL:
                return df

    param_key = "pitchers_lookup[]" if player_type == "pitcher" else "batters_lookup[]"
    params = {
        "all": "true",
        "player_type": player_type,
        param_key: player_id,
        "hfSea": f"{season}|",
        "hfGT": "R|",
        "type": "details",
        "min_pitches": "0",
        "min_results": "0",
        "game_date_gt": date_from,
        "game_date_lt": date_to,
    }
    try:
        r = requests.get(SAVANT, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        if not r.text.strip() or r.text.strip().startswith("No results"):
            df = pd.DataFrame()
        else:
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = df.columns.str.strip()
            for col in ["plate_x","plate_z","release_speed","release_spin_rate",
                        "launch_speed","launch_angle","woba_value","woba_denom",
                        "bat_speed","pfx_x","pfx_z","zone","spin_axis","delta_run_exp"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
    except Exception as e:
        print(f"Statcast fetch error ({player_type} {player_id}): {e}")
        df = pd.DataFrame()

    with _SC_LOCK:
        _SC_CACHE[cache_key] = (df, datetime.now())
    return df


def get_pitcher_statcast(pitcher_id: int, season: int = None,
                         days_back: int = 60) -> pd.DataFrame:
    season = season or datetime.now().year
    date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    return _fetch_statcast(pitcher_id, "pitcher", season, date_from)


def get_batter_statcast(batter_id: int, season: int = None,
                        days_back: int = 60) -> pd.DataFrame:
    season = season or datetime.now().year
    date_from = (date.today() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    return _fetch_statcast(batter_id, "batter", season, date_from)


# ── Arsenal Analysis ──────────────────────────────────────────────────────────

def _stuff_grade(whiff_pct: float, csw_pct: float, woba: float | None,
                 pitch_type: str) -> str:
    """Single-letter stuff grade for a pitch based on whiff, CSW, and wOBA allowed."""
    league_whiff = LEAGUE_WHIFF.get(pitch_type, LEAGUE_WHIFF_DEFAULT)
    league_woba  = LEAGUE_WOBA.get(pitch_type, LEAGUE_WOBA_DEFAULT)
    whiff_above  = whiff_pct - league_whiff   # positive = better than avg
    woba_above   = (woba or league_woba) - league_woba  # negative = better than avg
    score = whiff_above / 5.0 - woba_above / 0.030
    if score >= 2.5:   return "A+"
    if score >= 1.2:   return "A"
    if score >= 0.3:   return "B"
    if score >= -0.5:  return "C"
    if score >= -1.5:  return "D"
    return "F"


def calc_arsenal(df: pd.DataFrame) -> list:
    """
    Returns list of dicts per pitch type, sorted by usage%.
    Adds: hr_rate, stuff_grade, plus_minus_woba (vs league avg).
    """
    if df.empty:
        return []

    results = []
    total = len(df)

    for pt, grp in df.groupby("pitch_type"):
        if not pt or str(pt).strip() == "":
            continue
        count = len(grp)
        pct   = count / total * 100
        name  = (grp["pitch_name"].mode().iloc[0]
                 if "pitch_name" in grp.columns and not grp["pitch_name"].isna().all()
                 else pt)

        velos = grp["release_speed"].dropna()
        velo  = float(velos.mean()) if len(velos) else 0

        spins = grp["release_spin_rate"].dropna()
        spin  = float(spins.mean()) if len(spins) else 0

        swings      = grp[grp["description"].isin(["swinging_strike","foul","hit_into_play",
                                                     "foul_tip","swinging_strike_blocked","foul_bunt"])]
        whiff_count = grp[grp["description"].isin(["swinging_strike","swinging_strike_blocked","foul_tip"])]
        called_str  = grp[grp["description"] == "called_strike"]
        whiff_pct   = len(whiff_count) / len(swings) * 100 if len(swings) else 0
        csw_pct     = (len(whiff_count) + len(called_str)) / count * 100 if count else 0

        in_zone  = grp[grp["type"].isin(["S","X"])]
        zone_pct = len(in_zone) / count * 100 if count else 0

        in_play  = grp[grp["type"] == "X"]
        hits     = in_play[in_play["events"].isin(["single","double","triple","home_run"])]
        hrs_hit  = in_play[in_play["events"] == "home_run"]
        ba       = len(hits) / len(in_play) if len(in_play) > 0 else None
        hr_rate  = len(hrs_hit) / len(in_play) if len(in_play) > 0 else None

        woba_vals  = grp["woba_value"].dropna()
        woba_denom = grp["woba_denom"].dropna() if "woba_denom" in grp.columns else pd.Series()
        woba       = float(woba_vals.sum() / len(woba_denom)) if len(woba_denom) > 0 else None

        pfx_x = float(grp["pfx_x"].dropna().mean() * 12) if "pfx_x" in grp.columns else 0
        pfx_z = float(grp["pfx_z"].dropna().mean() * 12) if "pfx_z" in grp.columns else 0

        league_w = LEAGUE_WOBA.get(str(pt), LEAGUE_WOBA_DEFAULT)
        woba_pm  = round((woba - league_w), 3) if woba is not None else None

        results.append({
            "pitch_type":   str(pt),
            "pitch_name":   str(name),
            "count":        int(count),
            "pct":          round(pct, 1),
            "velo":         round(velo, 1),
            "spin":         int(spin),
            "whiff_pct":    round(whiff_pct, 1),
            "csw_pct":      round(csw_pct, 1),
            "zone_pct":     round(zone_pct, 1),
            "ba":           round(ba, 3) if ba is not None else None,
            "woba":         round(woba, 3) if woba is not None else None,
            "woba_vs_avg":  woba_pm,        # negative = better than avg (pitcher perspective)
            "hr_rate":      round(hr_rate, 3) if hr_rate is not None else None,
            "pfx_x":        round(pfx_x, 1),
            "pfx_z":        round(pfx_z, 1),
            "stuff_grade":  _stuff_grade(whiff_pct, csw_pct, woba, str(pt)),
            "color":        PITCH_COLORS.get(str(pt), "#94a3b8"),
        })

    return sorted(results, key=lambda x: -x["count"])


def calc_pitcher_summary(df: pd.DataFrame, arsenal: list) -> dict:
    """Top-level pitcher metrics from the statcast data."""
    if df.empty:
        return {}
    total = len(df)
    whiffs = df[df["description"].isin(["swinging_strike","swinging_strike_blocked"])].shape[0]
    swings = df[df["description"].isin(["swinging_strike","foul","hit_into_play",
                                         "foul_tip","swinging_strike_blocked","foul_bunt"])].shape[0]
    called = df[df["description"] == "called_strike"].shape[0]
    in_play= df[df["type"] == "X"]
    hrs    = in_play[in_play["events"] == "home_run"].shape[0]
    hits   = in_play[in_play["events"].isin(["single","double","triple","home_run"])].shape[0]
    zone   = df[df["type"].isin(["S","X"])].shape[0]

    woba_vals  = df["woba_value"].dropna()
    woba_denom = df["woba_denom"].dropna() if "woba_denom" in df.columns else pd.Series()
    woba = float(woba_vals.sum() / len(woba_denom)) if len(woba_denom) > 0 else None

    top_pitch = arsenal[0]["pitch_name"] if arsenal else "?"
    avg_velo  = arsenal[0]["velo"] if arsenal else 0

    return {
        "total_pitches":  total,
        "whiff_pct":      round(whiffs / swings * 100, 1) if swings else 0,
        "csw_pct":        round((whiffs + called) / total * 100, 1) if total else 0,
        "zone_pct":       round(zone / total * 100, 1) if total else 0,
        "hr_allowed":     int(hrs),
        "hits_allowed":   int(hits),
        "woba_against":   round(woba, 3) if woba is not None else None,
        "primary_pitch":  top_pitch,
        "fb_velo":        avg_velo,
        "pitch_mix":      {a["pitch_name"]: a["pct"] for a in arsenal},
    }


def calc_batter_vs_pitch_types(batter_df: pd.DataFrame, arsenal: list) -> list:
    """
    For each pitch type the pitcher throws, compute batter's performance:
    - wOBA, BA, whiff%, chase%, in-zone contact%
    - woba_vs_avg: batter's wOBA minus league avg for that pitch type
    - small_sample: True when PA < 20 (results are noisy)
    """
    if batter_df.empty or not arsenal:
        return []
    results = []
    for a in arsenal:
        pt  = a["pitch_type"]
        grp = batter_df[batter_df["pitch_type"] == pt]
        if grp.empty:
            results.append({
                "pitch_type": pt, "pitch_name": a["pitch_name"],
                "pa": 0, "ba": None, "woba": None, "woba_vs_avg": None,
                "whiff_pct": None, "chase_pct": None, "iz_contact_pct": None,
                "small_sample": True, "color": a["color"], "pct": a["pct"],
            })
            continue

        total_pa = len(grp)
        swings   = grp[grp["description"].isin(["swinging_strike","foul","hit_into_play",
                                                 "foul_tip","swinging_strike_blocked","foul_bunt"])]
        whiffs   = grp[grp["description"].isin(["swinging_strike","swinging_strike_blocked","foul_tip"])]

        # Chase: out-of-zone swings / out-of-zone pitches
        out_zone = grp[~grp["zone"].isin([1,2,3,4,5,6,7,8,9])]
        chases   = out_zone[out_zone["description"].isin(["swinging_strike","foul","hit_into_play",
                                                           "foul_tip","swinging_strike_blocked"])]

        # In-zone contact: swings on zone 1-9 that made contact
        in_zone  = grp[grp["zone"].isin([1,2,3,4,5,6,7,8,9])]
        iz_swing = in_zone[in_zone["description"].isin(["swinging_strike","foul","hit_into_play",
                                                         "foul_tip","swinging_strike_blocked","foul_bunt"])]
        iz_contact = iz_swing[iz_swing["description"].isin(["foul","hit_into_play","foul_bunt","foul_tip"])]

        in_play  = grp[grp["type"] == "X"]
        hits     = in_play[in_play["events"].isin(["single","double","triple","home_run"])]
        hrs      = in_play[in_play["events"] == "home_run"]

        ba_val   = len(hits) / len(in_play) if len(in_play) else None
        hr_rate  = len(hrs) / len(in_play)  if len(in_play) else None

        woba_vals  = grp["woba_value"].dropna()
        woba_denom = (grp["woba_denom"].dropna()
                      if "woba_denom" in grp.columns else pd.Series())
        woba_val   = float(woba_vals.sum() / len(woba_denom)) if len(woba_denom) > 0 else None

        league_w   = LEAGUE_WOBA.get(pt, LEAGUE_WOBA_DEFAULT)
        woba_pm    = round(woba_val - league_w, 3) if woba_val is not None else None

        results.append({
            "pitch_type":    pt,
            "pitch_name":    a["pitch_name"],
            "pa":            total_pa,
            "ba":            round(ba_val, 3)  if ba_val   is not None else None,
            "hr_rate":       round(hr_rate, 3) if hr_rate  is not None else None,
            "woba":          round(woba_val, 3) if woba_val is not None else None,
            "woba_vs_avg":   woba_pm,       # positive = batter beats league avg on this pitch
            "whiff_pct":     round(len(whiffs)/len(swings)*100, 1)    if len(swings)  else None,
            "chase_pct":     round(len(chases)/len(out_zone)*100, 1)  if len(out_zone) else None,
            "iz_contact_pct":round(len(iz_contact)/len(iz_swing)*100,1) if len(iz_swing) else None,
            "small_sample":  total_pa < 20,
            "color":         a["color"],
            "pct":           a["pct"],
        })
    return results


# ── Zone Grid Analysis ────────────────────────────────────────────────────────

# Zone layout (MLB zones 1-9 in zone, 11-14 corners, 13-14 off plate top/bot)
ZONE_POSITIONS = {
    1: (-0.55, 2.90), 2: (0.0, 2.90), 3: (0.55, 2.90),
    4: (-0.55, 2.20), 5: (0.0, 2.20), 6: (0.55, 2.20),
    7: (-0.55, 1.65), 8: (0.0, 1.65), 9: (0.55, 1.65),
    11:(-1.1,  2.90), 12:(1.1,  2.90),
    13:(-1.1,  1.65), 14:(1.1,  1.65),
}

def calc_zone_woba(df: pd.DataFrame) -> dict:
    """Return {zone: woba} for pitches grouped by zone."""
    if df.empty or "zone" not in df.columns:
        return {}
    result = {}
    for z, grp in df.groupby("zone"):
        woba_vals  = grp["woba_value"].dropna()
        woba_denom = grp["woba_denom"].dropna() if "woba_denom" in grp.columns else pd.Series()
        if len(woba_denom) > 0:
            result[int(z)] = round(float(woba_vals.sum() / len(woba_denom)), 3)
    return result


# ── Heatmap Generation ────────────────────────────────────────────────────────

def _make_heatmap_ax(ax, df: pd.DataFrame, title: str = "",
                     show_sz: bool = True, batter_hand: str = "R",
                     result_filter: str = "all") -> None:
    """
    Draw a pitch location density heatmap on ax.
    result_filter: "all" | "whiff" | "contact" | "hr"
    """
    ax.set_facecolor(CARD)
    ax.set_xlim(-2.0, 2.0)
    ax.set_ylim(0.5, 4.5)
    ax.set_aspect("equal")
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    if df.empty or "plate_x" not in df.columns:
        ax.text(0, 2.5, "No data", ha="center", va="center", color=MUTED, fontsize=9)
        if title:
            ax.set_title(title, fontsize=9, color=TEXT, pad=4)
        return

    # Apply result filter
    if result_filter == "whiff":
        sub = df[df["description"].isin(["swinging_strike","swinging_strike_blocked"])]
    elif result_filter == "contact":
        sub = df[df["type"] == "X"]
    elif result_filter == "hr":
        sub = df[df["events"] == "home_run"]
    else:
        sub = df

    locs = sub[["plate_x","plate_z"]].dropna()
    locs = locs[(locs["plate_x"].between(-2.5, 2.5)) & (locs["plate_z"].between(0, 5))]

    if len(locs) >= 5:
        # Build 2D histogram then smooth
        xbins = np.linspace(-2.0, 2.0, 40)
        zbins = np.linspace(0.5, 4.5, 40)
        H, xedges, zedges = np.histogram2d(locs["plate_x"], locs["plate_z"],
                                            bins=[xbins, zbins])
        H = gaussian_filter(H.T, sigma=1.8)
        cmap = plt.cm.get_cmap("RdYlBu_r")
        ax.pcolormesh(xedges, zedges, H, cmap=cmap, alpha=0.82, shading="auto")

    # Strike zone box
    if show_sz:
        sz = mpatches.FancyBboxPatch(
            (SZ_LEFT, SZ_BOT), PLATE_W, SZ_TOP - SZ_BOT,
            boxstyle="square,pad=0", linewidth=1.5,
            edgecolor="white", facecolor="none", zorder=5
        )
        ax.add_patch(sz)
        # Inner grid lines
        for x in [-0.28, 0.28]:
            ax.plot([x, x], [SZ_BOT, SZ_TOP], color="white", linewidth=0.5, alpha=0.4, zorder=5)
        for z in [2.17, 2.83]:
            ax.plot([SZ_LEFT, SZ_RIGHT], [z, z], color="white", linewidth=0.5, alpha=0.4, zorder=5)

    # Plate triangle
    plate_y = 1.1
    ax.plot([-0.71, 0.71], [plate_y, plate_y], color=MUTED, linewidth=1.5, zorder=5)
    ax.plot([-0.71, 0.0, 0.71], [plate_y, plate_y-0.3, plate_y], color=MUTED, linewidth=1.5, zorder=5)

    # Pitch count
    ax.text(-1.85, 4.2, f"n={len(locs)}", fontsize=7.5, color=MUTED, zorder=6)

    if title:
        ax.set_title(title, fontsize=8.5, color=TEXT, pad=4, fontweight="bold")

    # Batter stance indicator
    stance = "RHB →" if batter_hand == "R" else "← LHB"
    ax.text(0.0, 0.65, stance, ha="center", fontsize=7, color=MUTED)


def generate_pitcher_zone_png(df: pd.DataFrame,
                               arsenal: list,
                               batter_hand: str = "R") -> bytes:
    """
    Multi-panel heatmap: one panel per pitch type + an 'all pitches' overview.
    Returns PNG bytes.
    """
    if batter_hand in ("L", "LHB"):
        df = df[df["stand"] == "L"] if "stand" in df.columns else df
    else:
        df = df[df["stand"] == "R"] if "stand" in df.columns else df

    n_pitch = min(len(arsenal), 6)
    n_cols  = min(n_pitch + 1, 4)
    n_rows  = (n_pitch + 2) // n_cols

    fig_w = n_cols * 2.8
    fig_h = n_rows * 3.2 + 0.5

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(fig_w, fig_h), facecolor=BG)
    if n_rows == 1 and n_cols == 1:
        axes = [[axes]]
    elif n_rows == 1:
        axes = [axes]
    axes_flat = [ax for row in axes for ax in (row if hasattr(row, "__iter__") else [row])]

    # First panel: all pitches
    _make_heatmap_ax(axes_flat[0], df, title="All Pitches", batter_hand=batter_hand)

    # One panel per pitch type
    for i, a in enumerate(arsenal[:n_pitch]):
        pt_df = df[df["pitch_type"] == a["pitch_type"]] if "pitch_type" in df.columns else pd.DataFrame()
        lbl   = f"{a['pitch_name']} ({a['pct']:.0f}%)\n{a['velo']:.1f} mph  CSW {a['csw_pct']:.0f}%"
        _make_heatmap_ax(axes_flat[i+1], pt_df, title=lbl, batter_hand=batter_hand)
        # Color bar on first axis for reference
        c = PITCH_COLORS.get(a["pitch_type"], "#94a3b8")
        axes_flat[i+1].text(1.85, 4.2, "●", color=c, fontsize=10, zorder=7)

    # Hide unused axes
    for ax in axes_flat[n_pitch+1:]:
        ax.set_visible(False)

    fig.suptitle(f"Pitch Location Heatmap — vs {'RHB' if batter_hand=='R' else 'LHB'}",
                 fontsize=10, color=TEXT, y=1.01)
    fig.patch.set_facecolor(BG)
    plt.tight_layout(pad=0.4)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_batter_zone_png(batter_df: pd.DataFrame,
                              pitcher_hand: str = "R") -> bytes:
    """
    3×3 zone grid showing batter wOBA by zone vs RHP or LHP.
    Red = hot (high wOBA), blue = cold (low wOBA).
    """
    if pitcher_hand in ("L", "LHP"):
        sub = batter_df[batter_df["p_throws"] == "L"] if "p_throws" in batter_df.columns else batter_df
    else:
        sub = batter_df[batter_df["p_throws"] == "R"] if "p_throws" in batter_df.columns else batter_df

    zone_woba = calc_zone_woba(sub)

    fig, ax = plt.subplots(1, 1, figsize=(3.5, 4.2), facecolor=BG)
    ax.set_facecolor(CARD)
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(0.8, 4.0)
    ax.set_aspect("equal")
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    for spine in ax.spines.values():
        spine.set_visible(False)

    # Strike zone outline
    sz = mpatches.FancyBboxPatch(
        (SZ_LEFT, SZ_BOT), PLATE_W, SZ_TOP - SZ_BOT,
        boxstyle="square,pad=0", linewidth=1.5,
        edgecolor="white", facecolor="none", zorder=5
    )
    ax.add_patch(sz)

    woba_vals = list(zone_woba.values())
    vmin = min(woba_vals) if woba_vals else 0.200
    vmax = max(woba_vals) if woba_vals else 0.450
    cmap = plt.cm.get_cmap("RdYlBu_r")

    ZONE_BOXES = {
        1: (SZ_LEFT, 2.83, 0.55, 0.67),
        2: (-0.28,   2.83, 0.55, 0.67),
        3: (0.28,    2.83, 0.55, 0.67),
        4: (SZ_LEFT, 2.17, 0.55, 0.67),
        5: (-0.28,   2.17, 0.55, 0.67),
        6: (0.28,    2.17, 0.55, 0.67),
        7: (SZ_LEFT, 1.50, 0.55, 0.67),
        8: (-0.28,   1.50, 0.55, 0.67),
        9: (0.28,    1.50, 0.55, 0.67),
    }
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    for zone_id, (x, z, w, h) in ZONE_BOXES.items():
        woba = zone_woba.get(zone_id)
        color = cmap(norm(woba)) if woba is not None else "#1e2235"
        rect = mpatches.FancyBboxPatch((x, z), w, h, boxstyle="square,pad=0.01",
                                        linewidth=0.5, edgecolor="#374151",
                                        facecolor=color, zorder=3)
        ax.add_patch(rect)
        if woba is not None:
            txt_color = "black" if woba > (vmin + vmax) / 2 else "white"
            ax.text(x + w/2, z + h/2, f".{int(woba*1000):03d}",
                    ha="center", va="center", fontsize=9, fontweight="bold",
                    color=txt_color, zorder=4)
        else:
            ax.text(x + w/2, z + h/2, "—", ha="center", va="center",
                    fontsize=9, color=MUTED, zorder=4)

    # Plate
    ax.plot([-0.71, 0.71], [1.1, 1.1], color=MUTED, linewidth=1.5, zorder=5)
    ax.plot([-0.71, 0.0, 0.71], [1.1, 0.8, 1.1], color=MUTED, linewidth=1.5, zorder=5)

    side = "vs RHP" if pitcher_hand == "R" else "vs LHP"
    ax.set_title(f"Batter wOBA by Zone  {side}", fontsize=9, color=TEXT, pad=6, fontweight="bold")
    ax.text(0, 0.95, f"n={len(sub)} pitches", ha="center", fontsize=7.5, color=MUTED)

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=140, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def generate_matchup_summary_png(pitcher_name: str, batter_name: str,
                                  arsenal: list, b_vs_pt: list,
                                  pitcher_summary: dict,
                                  matchup_grade: str,
                                  edge_note: str) -> bytes:
    """
    Compact summary card: pitch mix bar + batter performance table + grade.
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), facecolor=BG)
    fig.suptitle(f"Matchup Machine  —  {pitcher_name}  vs  {batter_name}",
                 fontsize=12, fontweight="bold", color=TEXT, y=0.98)

    # Left: Pitcher pitch mix horizontal bar
    ax_l = axes[0]
    ax_l.set_facecolor(CARD)
    ax_l.set_title(f"{pitcher_name} — Arsenal", fontsize=10, color=TEXT, pad=6)
    labels = [f"{a['pitch_name']} ({a['pct']:.0f}%)" for a in arsenal]
    values = [a["pct"] for a in arsenal]
    colors = [PITCH_COLORS.get(a["pitch_type"], "#94a3b8") for a in arsenal]
    y_pos  = np.arange(len(labels))
    bars = ax_l.barh(y_pos, values, color=colors, height=0.6, alpha=0.85)
    ax_l.set_yticks(y_pos)
    ax_l.set_yticklabels(labels, fontsize=9)
    ax_l.set_xlabel("Usage %", fontsize=9, color=MUTED)
    ax_l.invert_yaxis()
    ax_l.tick_params(colors=MUTED)
    for bar, a in zip(bars, arsenal):
        ax_l.text(bar.get_width()+0.3, bar.get_y()+bar.get_height()/2,
                  f"{a['velo']:.0f} mph  W:{a['whiff_pct']:.0f}%  CSW:{a['csw_pct']:.0f}%",
                  va="center", fontsize=7.5, color=TEXT)
    ax_l.set_xlim(0, max(values)*1.45 if values else 50)

    # Right: Batter vs each pitch type table
    ax_r = axes[1]
    ax_r.set_facecolor(CARD)
    ax_r.set_axis_off()
    ax_r.set_title(f"{batter_name} vs Arsenal", fontsize=10, color=TEXT, pad=6)

    headers = ["Pitch", "Usage", "PA", "BA", "wOBA", "Whiff%", "Chase%"]
    col_x   = [0.01, 0.28, 0.38, 0.48, 0.58, 0.70, 0.83]
    for j, h in enumerate(headers):
        ax_r.text(col_x[j], 0.95, h, fontsize=8, fontweight="bold",
                  color=MUTED, transform=ax_r.transAxes, va="top")
    ax_r.plot([0.01,0.99],[0.91,0.91], color="#2d3748", linewidth=0.8, transform=ax_r.transAxes)

    for i, b in enumerate(b_vs_pt):
        y = 0.87 - i * 0.115
        c_dot = PITCH_COLORS.get(b["pitch_type"], "#94a3b8")
        ax_r.text(col_x[0]-0.01, y, "●", color=c_dot, fontsize=8,
                  transform=ax_r.transAxes, va="top")
        ax_r.text(col_x[0]+0.03, y, b["pitch_name"][:14], fontsize=8,
                  color=TEXT, transform=ax_r.transAxes, va="top")
        ax_r.text(col_x[1], y, f"{b['pct']:.0f}%", fontsize=8,
                  color=MUTED, transform=ax_r.transAxes, va="top")
        ax_r.text(col_x[2], y, str(b["pa"]) if b["pa"] else "–", fontsize=8,
                  color=MUTED, transform=ax_r.transAxes, va="top")
        # wOBA / BA coloring
        for xi, val, lo, hi in [
            (col_x[3], b["ba"],      0.200, 0.350),
            (col_x[4], b["woba"],    0.250, 0.420),
            (col_x[5], b["whiff_pct"],15,   40),
            (col_x[6], b["chase_pct"],20,  38),
        ]:
            if val is not None:
                if isinstance(val, float) and val < 1:
                    txt = f".{int(val*1000):03d}"
                else:
                    txt = f"{val:.0f}%" if isinstance(val, float) and val > 1 else str(val)
                # Color: high wOBA/BA = red, low = green; high whiff/chase = green, low = red
                if xi in (col_x[3], col_x[4]):
                    norm = (val - lo) / (hi - lo) if hi > lo else 0.5
                    c = RED if norm > 0.6 else GREEN if norm < 0.3 else TEXT
                else:
                    norm = (val - lo) / (hi - lo) if hi > lo else 0.5
                    c = GREEN if norm > 0.6 else RED if norm < 0.3 else TEXT
                ax_r.text(xi, y, txt, fontsize=8, color=c,
                          transform=ax_r.transAxes, va="top")
            else:
                ax_r.text(xi, y, "–", fontsize=8, color=MUTED,
                          transform=ax_r.transAxes, va="top")

    # Grade badge
    grade_c = {"A+":YELLOW,"A":GREEN,"A-":GREEN,"B+":ACCENT,"B":ACCENT,
                "C":MUTED,"D":RED,"F":RED}.get(matchup_grade, MUTED)
    rect = FancyBboxPatch((0.01,0.01),0.22,0.18,boxstyle="round,pad=0.01",
                          linewidth=2,edgecolor=grade_c,facecolor="#1e2235",
                          transform=ax_r.transAxes,zorder=3)
    ax_r.add_patch(rect)
    ax_r.text(0.12,0.06,f"Grade: {matchup_grade}",fontsize=11,fontweight="bold",
              color=grade_c,transform=ax_r.transAxes,va="bottom",ha="center",zorder=4)
    ax_r.text(0.55,0.04,edge_note,fontsize=8,color=TEXT,
              transform=ax_r.transAxes,va="bottom",ha="left",wrap=True,zorder=4)

    plt.tight_layout(pad=0.6)
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    buf.seek(0)
    return buf.read()


# ── Matchup Grade ─────────────────────────────────────────────────────────────

def grade_matchup(arsenal: list, b_vs_pt: list, pitcher_summary: dict) -> tuple[str, str]:
    """
    Usage-weighted, league-normalized matchup grade (batter perspective).

    Core idea: for each pitch the pitcher throws, measure how much the batter's
    wOBA vs that pitch deviates from league average, weighted by pitcher's usage
    of that pitch and confidence based on sample size.

    pitcher CSW vs league avg shifts the baseline (elite K pitcher starts at a
    deficit for the batter regardless of pitch-type matchup).

    Returns (grade, edge_note):
      A+ = strong batter advantage, F = pitcher dominates.
    """
    if not arsenal:
        return ("C", "Insufficient Statcast data")

    b_lookup     = {b["pitch_type"]: b for b in b_vs_pt}
    total_usage  = sum(a["pct"] for a in arsenal) or 1.0

    weighted_score  = 0.0
    covered_weight  = 0.0
    best_pitch_name = None
    best_delta      = -99.0
    worst_pitch_name= None
    worst_delta     =  99.0

    for a in arsenal:
        pt           = a["pitch_type"]
        usage_w      = a["pct"] / total_usage      # 0→1, sums to 1
        b            = b_lookup.get(pt, {})
        b_woba       = b.get("woba")
        b_pa         = b.get("pa", 0)
        b_whiff      = b.get("whiff_pct")
        league_woba  = LEAGUE_WOBA.get(pt, LEAGUE_WOBA_DEFAULT)
        league_whiff = LEAGUE_WHIFF.get(pt, LEAGUE_WHIFF_DEFAULT)

        if b_woba is not None and b_pa >= 5:
            confidence = min(b_pa / 25.0, 1.0)   # full confidence at 25 PA
            woba_delta = b_woba - league_woba
            # Scale: ±0.050 wOBA = ±1 unit.  Cap at ±3 to avoid outliers dominating.
            units = max(-3.0, min(3.0, woba_delta / 0.050))
            weighted_score += usage_w * confidence * units
            covered_weight += usage_w * confidence

            if woba_delta > best_delta:
                best_delta = woba_delta
                best_pitch_name = a["pitch_name"]
            if woba_delta < worst_delta:
                worst_delta = woba_delta
                worst_pitch_name = a["pitch_name"]

            # Bonus/penalty from whiff rate vs this pitch
            if b_whiff is not None and b_pa >= 10:
                whiff_delta = b_whiff - league_whiff
                # high batter whiff = pitcher edge
                weighted_score -= usage_w * confidence * max(-1.5, min(1.5, whiff_delta / 8.0))
        else:
            covered_weight += usage_w * 0.05   # tiny credit so coverage doesn't stay 0

    # Pitcher's overall CSW vs league (26.5%) — shifts baseline regardless of matchup
    p_csw     = pitcher_summary.get("csw_pct", LEAGUE_CSW_DEFAULT)
    csw_delta = p_csw - LEAGUE_CSW_DEFAULT
    csw_adj   = max(-0.8, min(0.8, -csw_delta / 5.0))  # high CSW = pitcher edge
    final_score = weighted_score + csw_adj

    # Build edge note
    notes = []
    if best_pitch_name and best_delta > 0.025:
        notes.append(f"Batter hits {best_pitch_name} well")
    if worst_pitch_name and worst_delta < -0.025:
        pct_str = ""
        for a in arsenal:
            if a["pitch_name"] == worst_pitch_name:
                b_d = b_lookup.get(a["pitch_type"], {})
                wh  = b_d.get("whiff_pct")
                pct_str = f" ({wh:.0f}% K)" if wh else ""
                break
        notes.append(f"Primary weakness: {worst_pitch_name}{pct_str}")
    if p_csw >= 31:
        notes.append(f"Elite pitcher CSW ({p_csw:.0f}%)")
    elif p_csw <= 22:
        notes.append(f"Contact-allowing pitcher (CSW {p_csw:.0f}%)")

    # Grade map: continuous score → letter grade
    if   final_score >= 1.8:  grade = "A+"
    elif final_score >= 1.1:  grade = "A"
    elif final_score >= 0.5:  grade = "A-"
    elif final_score >= 0.15: grade = "B+"
    elif final_score >= -0.1: grade = "B"
    elif final_score >= -0.4: grade = "C"
    elif final_score >= -0.9: grade = "D"
    else:                     grade = "F"

    edge_note = " · ".join(notes[:2]) if notes else "Neutral matchup"
    return grade, edge_note


# ── Master Matchup Function ───────────────────────────────────────────────────

def build_matchup(pitcher_id: int, batter_id: int,
                  season: int = None, days_back: int = 60) -> dict:
    """
    Full matchup analysis. Returns JSON-serialisable dict.
    """
    season = season or datetime.now().year
    pitcher_df = get_pitcher_statcast(pitcher_id, season, days_back)
    batter_df  = get_batter_statcast(batter_id, season, days_back)

    arsenal  = calc_arsenal(pitcher_df)
    p_summ   = calc_pitcher_summary(pitcher_df, arsenal)
    b_vs_pt  = calc_batter_vs_pitch_types(batter_df, arsenal)
    grade, note = grade_matchup(arsenal, b_vs_pt, p_summ)

    # H2H (batter appears in pitcher's data)
    h2h = pd.DataFrame()
    if not pitcher_df.empty and "batter" in pitcher_df.columns:
        h2h = pitcher_df[pitcher_df["batter"] == batter_id]

    h2h_summary = {}
    if not h2h.empty:
        ip = h2h[h2h["type"] == "X"]
        hits = ip[ip["events"].isin(["single","double","triple","home_run"])]
        h2h_summary = {
            "pa":   int(len(h2h)),
            "hits": int(len(hits)),
            "hr":   int(len(ip[ip["events"] == "home_run"])),
            "k":    int(len(h2h[h2h["events"] == "strikeout"])),
            "ba":   round(len(hits)/len(ip), 3) if len(ip) else None,
        }

    return {
        "pitcher_id":      pitcher_id,
        "batter_id":       batter_id,
        "season":          season,
        "days_back":       days_back,
        "arsenal":         arsenal,
        "pitcher_summary": p_summ,
        "batter_vs_pitch": b_vs_pt,
        "h2h":             h2h_summary,
        "grade":           grade,
        "edge_note":       note,
        "pitcher_pitches": int(len(pitcher_df)),
        "batter_pitches":  int(len(batter_df)),
    }
