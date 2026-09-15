"""
grade_engine.py — Score a saved HR board against what actually happened.

Results come from the MLB Stats API scoring plays (authoritative, free, and
already the source for schedules and lineups), so grading needs no new feed.

Two questions this answers:
  1. Calibration — when the model says 20%, do 20% of those bats go deep?
  2. Signal value — do the tags (HARD LUCK, FIRE, EV SURGE, DUE), the chalk
     tiers, and pitcher vulnerability actually separate hits from misses?

A board is only graded on batters who were in the lineup (or unknown), since a
benched bat is not a losing pick.
"""

import json
import os
import unicodedata
from datetime import datetime

from baseball_engine import _get, MLB_API

PROB_BUCKETS = [(0, 10), (10, 15), (15, 20), (20, 25), (25, 100)]
TRACKED_TAGS = ["HARD LUCK", "FIRE", "HOT", "EV SURGE", "DUE", "OWNS PITCHER", "DOMINATED"]


def _norm(name: str) -> str:
    """Fold accents and case so 'Luis García Jr.' matches 'Luis Garcia Jr.'."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", str(name))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace(".", "").replace("'", "").strip()


def fetch_actual_hrs(game_date: str) -> list:
    """Every home run hit on game_date: batter, pitcher, inning, game_pk."""
    data = _get(f"{MLB_API}/schedule", {
        "sportId": 1, "date": game_date, "hydrate": "scoringplays",
    }) or {}
    out = []
    for d in data.get("dates", []):
        for g in d.get("games", []):
            if g.get("status", {}).get("detailedState") not in ("Final", "Game Over", "Completed Early"):
                continue
            for p in g.get("scoringPlays", []):
                if p.get("result", {}).get("event") != "Home Run":
                    continue
                m = p.get("matchup", {})
                out.append({
                    "game_pk":     g.get("gamePk"),
                    "batter":      m.get("batter", {}).get("fullName", ""),
                    "batter_id":   m.get("batter", {}).get("id"),
                    "pitcher":     m.get("pitcher", {}).get("fullName", ""),
                    "pitcher_id":  m.get("pitcher", {}).get("id"),
                    "inning":      p.get("about", {}).get("inning"),
                    "description": p.get("result", {}).get("description", ""),
                })
    return out


def _rate(hits: int, n: int) -> float:
    return round(hits / n * 100, 1) if n else 0.0


def grade_board(board: list, actuals: list) -> dict:
    """Compare one HR board against the day's actual home runs."""
    hit_ids = {a["batter_id"] for a in actuals if a["batter_id"]}
    hit_names = {_norm(a["batter"]) for a in actuals}
    # Batters who homered off the specific starter they were projected against
    off_starter = {(a["batter_id"], a["pitcher_id"]) for a in actuals}

    seen, picks = set(), []
    for r in board:
        for b in r["top_batters"]:
            if b.get("in_lineup") is False or b["batter_id"] in seen:
                continue
            seen.add(b["batter_id"])
            hit = b["batter_id"] in hit_ids or _norm(b["batter_name"]) in hit_names
            picks.append({
                "batter":      b["batter_name"],
                "batter_id":   b["batter_id"],
                "game":        r["game"],
                "pitcher":     r["pitcher_name"],
                "hit":         hit,
                "off_starter": (b["batter_id"], r["pitcher_id"]) in off_starter,
                "prob":        b.get("hr_prob") or 0.0,
                "odds":        b.get("implied_odds", ""),
                "matchup_score": b.get("matchup_score") or 0.0,
                "zone":        b.get("hr_zone_score") or 0.0,
                "chalk_tier":  b.get("chalk_tier"),
                "vuln":        r["vuln"]["score"],
                "vuln_tier":   r["vuln"]["tier"],
                "order":       b.get("order"),
                "tags":        b.get("tags", []),
            })

    picks.sort(key=lambda x: -x["matchup_score"])
    n = len(picks)
    hits = sum(1 for p in picks if p["hit"])

    # Calibration: predicted vs observed inside each probability band
    calib = []
    for lo, hi in PROB_BUCKETS:
        grp = [p for p in picks if lo <= p["prob"] < hi]
        if not grp:
            continue
        exp = sum(p["prob"] for p in grp) / len(grp)
        obs = _rate(sum(1 for p in grp if p["hit"]), len(grp))
        calib.append({"bucket": f"{lo}-{hi}%", "n": len(grp),
                      "expected": round(exp, 1), "actual": obs,
                      "delta": round(obs - exp, 1)})

    # Do the top-ranked picks beat the field?
    topn = {f"top{k}": {"n": min(k, n), "hits": sum(1 for p in picks[:k] if p["hit"]),
                        "rate": _rate(sum(1 for p in picks[:k] if p["hit"]), min(k, n))}
            for k in (5, 10, 20, 50)}

    by_tag = {}
    for tag in TRACKED_TAGS:
        grp = [p for p in picks if any(tag in t for t in p["tags"])]
        if grp:
            by_tag[tag] = {"n": len(grp), "hits": sum(1 for p in grp if p["hit"]),
                           "rate": _rate(sum(1 for p in grp if p["hit"]), len(grp))}

    by_chalk = {}
    for tier in ("HEAVY CHALK", "CHALKY", "BALANCED", "LEVERAGE"):
        grp = [p for p in picks if p["chalk_tier"] == tier]
        if grp:
            by_chalk[tier] = {"n": len(grp), "hits": sum(1 for p in grp if p["hit"]),
                              "rate": _rate(sum(1 for p in grp if p["hit"]), len(grp))}

    by_vuln = {}
    for tier in ("Attackable", "Neutral Lean", "Avoid"):
        grp = [p for p in picks if p["vuln_tier"] == tier]
        if grp:
            by_vuln[tier] = {"n": len(grp), "hits": sum(1 for p in grp if p["hit"]),
                             "rate": _rate(sum(1 for p in grp if p["hit"]), len(grp))}

    board_ids = {p["batter_id"] for p in picks}
    missed = [a for a in actuals if a["batter_id"] not in board_ids]

    return {
        "n_picks": n,
        "n_hits": hits,
        "hit_rate": _rate(hits, n),
        "baseline_rate": _rate(len(actuals), max(1, n)),
        "actual_hr_count": len(actuals),
        "off_starter_hits": sum(1 for p in picks if p["off_starter"]),
        "calibration": calib,
        "top_n": topn,
        "by_tag": by_tag,
        "by_chalk": by_chalk,
        "by_vuln": by_vuln,
        "hits_detail": [p for p in picks if p["hit"]],
        "missed_entirely": missed,
        "picks": picks,
    }


def grade_date(game_date: str, board_path: str) -> dict:
    if not os.path.exists(board_path):
        raise FileNotFoundError(board_path)
    board = json.load(open(board_path))
    actuals = fetch_actual_hrs(game_date)
    res = grade_board(board, actuals)
    res["date"] = game_date
    res["graded_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return res


def format_grade(res: dict) -> str:
    L = []
    L.append("=" * 76)
    L.append(f"  HR BOARD GRADE — {res['date']}")
    L.append("=" * 76)
    L.append(f"  {res['actual_hr_count']} home runs hit league-wide")
    L.append(f"  Board carried {res['n_picks']} rostered batters; {res['n_hits']} homered "
             f"({res['hit_rate']}%) — {res['off_starter_hits']} off the projected starter")
    L.append("")
    L.append("  RANK CUTOFFS (does ranking higher actually help?)")
    for k, v in res["top_n"].items():
        L.append(f"    {k:<6} {v['hits']:>3}/{v['n']:<4} {v['rate']:>5.1f}%")
    L.append("")
    L.append("  CALIBRATION (predicted vs observed)")
    L.append(f"    {'bucket':<10}{'n':>5}{'exp':>8}{'act':>8}{'delta':>8}")
    for c in res["calibration"]:
        L.append(f"    {c['bucket']:<10}{c['n']:>5}{c['expected']:>7.1f}%{c['actual']:>7.1f}%{c['delta']:>+8.1f}")
    if res["by_chalk"]:
        L.append("")
        L.append("  BY CHALK TIER")
        for t, v in res["by_chalk"].items():
            L.append(f"    {t:<13}{v['hits']:>3}/{v['n']:<4} {v['rate']:>5.1f}%")
    if res["by_vuln"]:
        L.append("")
        L.append("  BY PITCHER VULNERABILITY")
        for t, v in res["by_vuln"].items():
            L.append(f"    {t:<13}{v['hits']:>3}/{v['n']:<4} {v['rate']:>5.1f}%")
    if res["by_tag"]:
        L.append("")
        L.append("  BY SIGNAL TAG")
        for t, v in sorted(res["by_tag"].items(), key=lambda kv: -kv[1]["rate"]):
            L.append(f"    {t:<14}{v['hits']:>3}/{v['n']:<4} {v['rate']:>5.1f}%")
    L.append("")
    L.append("  BOARD HITS (top 25 by rank)")
    for p in sorted(res["hits_detail"], key=lambda x: -x["matchup_score"])[:25]:
        star = "*" if p["off_starter"] else " "
        L.append(f"   {star} {p['batter']:<24}{p['game']:<9}{p['prob']:>5.1f}% {p['odds']:>6} "
                 f"vuln={p['vuln']:>3.0f} {p['chalk_tier'] or '':<12}")
    L.append(f"\n  * = homered off the projected starter")
    L.append(f"  {len(res['missed_entirely'])} home runs came from batters not on the board")
    return "\n".join(L)


if __name__ == "__main__":
    import sys
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    path = sys.argv[2] if len(sys.argv) > 2 else f"hr_board_{date.replace('-','')}.json"
    print(format_grade(grade_date(date, path)))
