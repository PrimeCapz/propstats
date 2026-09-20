#!/usr/bin/env python3
"""
run_slate.py — Build every board for a date and write them to an output directory.

The daily pipeline used to be an ad-hoc script rewritten each morning, and that
cost us: enrich_context_splits, tag_chalk_levels and calibrate_probabilities
were added to the engine but left out of one day's runner, so the boards shipped
with stale probabilities and nobody noticed until grading. The enrichment order
matters and belongs in version control, not in a scratchpad file.

Order is load-bearing:
  build → recent form → statcast windows → hand mix → h2h → context splits
        → lineups → probable check → calibrate → chalk tiers

calibrate_probabilities must run after lineups (it reads the batting slot) and
after every enrichment that can add a signal tag (it reads them for multipliers).
enrich_probable_check runs before calibration so a dead matchup is neutralized
before the probabilities are set.

Usage:
  python3 run_slate.py [YYYY-MM-DD] [--out DIR] [--skip-hr-enrich]
"""

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "propstats", "backend"))

from hr_engine import (
    build_hr_attack_board, enrich_recent_hr_form, enrich_statcast_recent,
    enrich_pitcher_hand_mix, enrich_with_h2h, enrich_context_splits,
    enrich_lineups, enrich_probable_check, calibrate_probabilities,
    tag_chalk_levels, enrich_stack_probability,
)
from k_engine import build_k_board
from walk_engine import build_walk_board
from nrfi_engine import build_nrfi_board
from hits_engine import build_hits_board
from tb_engine import build_tb_board
from f5_engine import build_f5_board
from batter_k_engine import build_batter_k_board
from hitter_fantasy_engine import build_hitter_fantasy_board


def _step(label, fn, *a, **kw):
    t0 = time.time()
    try:
        out = fn(*a, **kw)
        n = len(out) if hasattr(out, "__len__") else "?"
        print(f"  ✓ {label:<28} {n} rows   {time.time()-t0:5.1f}s", flush=True)
        return out
    except Exception as e:
        print(f"  ✗ {label:<28} {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return None


def build_hr(game_date, skip_enrich=False):
    """The HR board plus its enrichment chain, in the order the engine expects."""
    board = _step("hr board", build_hr_attack_board, game_date)
    if not board:
        return None
    if skip_enrich:
        return board
    for label, fn in [
        ("recent hr form",    enrich_recent_hr_form),
        ("statcast windows",  enrich_statcast_recent),
        ("pitcher hand mix",  enrich_pitcher_hand_mix),
        ("context splits",    enrich_context_splits),
        ("lineups",           enrich_lineups),
        ("probable check",    enrich_probable_check),
    ]:
        res = _step(label, fn, board, game_date)
        if res is not None:
            board = res
    for label, fn in [("h2h", enrich_with_h2h),
                      ("calibrate", calibrate_probabilities),
                      ("chalk tiers", tag_chalk_levels),
                      ("stack prob", enrich_stack_probability)]:
        res = _step(label, fn, board)
        if res is not None:
            board = res
    return board


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", nargs="?", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=".")
    ap.add_argument("--skip-hr-enrich", action="store_true",
                    help="build the raw HR board only (fast, for debugging)")
    args = ap.parse_args()

    d, ds = args.date, args.date.replace("-", "")
    os.makedirs(args.out, exist_ok=True)
    print(f"SLATE {d}\n" + "=" * 56, flush=True)

    boards = {
        f"hr_board_{ds}.json":       build_hr(d, args.skip_hr_enrich),
        f"k_board_{ds}.json":        _step("k board", build_k_board, d),
        f"walk_board_{ds}.json":     _step("walk board", build_walk_board, d),
        f"nrfi_{ds}.json":           _step("nrfi board", build_nrfi_board, d),
        f"hits_board_{ds}.json":     _step("hits board", build_hits_board, d),
        f"tb_board_{ds}.json":       _step("tb board", build_tb_board, d),
        f"f5_board_{ds}.json":       _step("f5 board", build_f5_board, d),
        f"batter_k_{ds}.json":       _step("batter k board", build_batter_k_board, d),
        f"hitter_fantasy_{ds}.json": _step("hitter fantasy", build_hitter_fantasy_board, d),
    }

    print("=" * 56, flush=True)
    failed = []
    for name, data in boards.items():
        if data is None:
            failed.append(name)
            continue
        path = os.path.join(args.out, name)
        with open(path, "w") as f:
            json.dump(data, f)
        print(f"  wrote {path}", flush=True)

    if failed:
        print(f"\n  {len(failed)} board(s) FAILED: {', '.join(failed)}", flush=True)
        return 1
    print(f"\n  SLATE COMPLETE — {d}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
