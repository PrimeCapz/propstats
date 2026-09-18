import sys, os, json
sys.path.insert(0, "/home/user/propstats/propstats/backend")

GAME_DATE = "2026-08-02"
SP = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"

print(f"=== BUILDING HR BOARD {GAME_DATE} ===")
from hr_engine import build_hr_attack_board, enrich_recent_hr_form
hr_results = build_hr_attack_board(GAME_DATE)
print(f"  Raw: {len(hr_results)} pitcher matchups")
hr_results = enrich_recent_hr_form(hr_results, GAME_DATE, top_n=120)
print(f"  Enriched")
with open(f"{SP}/hr_board_20260802.json", "w") as f:
    json.dump(hr_results, f, indent=2)
print(f"  Saved hr_board_20260802.json")

print(f"\n=== BUILDING K BOARD {GAME_DATE} ===")
from k_engine import build_k_board
k_results = build_k_board(GAME_DATE)
print(f"  K results: {len(k_results)}")
with open(f"{SP}/k_board_20260802.json", "w") as f:
    json.dump(k_results, f, indent=2)
print(f"  Saved k_board_20260802.json")

print(f"\n=== BUILDING FANTASY BOARD {GAME_DATE} ===")
from hitter_fantasy_engine import build_hitter_fantasy_board
hf_results = build_hitter_fantasy_board(GAME_DATE)
print(f"  Fantasy results: {len(hf_results)}")
with open(f"{SP}/hitter_fantasy_20260802.json", "w") as f:
    json.dump(hf_results, f, indent=2)
print(f"  Saved hitter_fantasy_20260802.json")

print(f"\nDONE")
