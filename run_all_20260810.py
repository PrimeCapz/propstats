import sys, os, json, time
sys.path.insert(0, "/home/user/propstats/propstats/backend")

GAME_DATE = "2026-08-10"
DS = "20260810"
SP = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"
os.makedirs(SP, exist_ok=True)

print(f"=== BUILDING K BOARD {GAME_DATE} ===")
from k_engine import build_k_board
k_results = build_k_board(GAME_DATE)
print(f"  K results: {len(k_results)} pitchers")
for r in k_results:
    ks = r.get('k_score', {})
    proj = r.get('proj', {})
    form = r.get('recent_form', {})
    print(f"  {r['pitcher_name']:<28} score={ks.get('score',0):.1f} tier={ks.get('tier','?'):<12} "
          f"proj={proj.get('proj_k','?')} line={proj.get('line','?')} edge={proj.get('edge_vs_line','?')} "
          f"putaway={ks.get('putaway_pct',0):.1f}% ppa={ks.get('p_per_pa',0):.2f} surge={form.get('k_surge',False)}")
with open(f"{SP}/k_board_{DS}.json", "w") as f:
    json.dump(k_results, f, indent=2)
print(f"  Saved k_board_{DS}.json")

print(f"\n=== BUILDING WALK BOARD {GAME_DATE} ===")
from walk_engine import build_walk_board
w_results = build_walk_board(GAME_DATE)
print(f"  Walk results: {len(w_results)} pitchers")
for r in w_results:
    print(f"  {r.get('pitcher_name','?'):<28} bb_score={r.get('bb_score',0):.1f} proj={r.get('proj_bb','?')} line={r.get('line','?')}")
with open(f"{SP}/walk_board_{DS}.json", "w") as f:
    json.dump(w_results, f, indent=2)
print(f"  Saved walk_board_{DS}.json")

print(f"\n=== BUILDING HR BOARD {GAME_DATE} ===")
from hr_engine import build_hr_attack_board, enrich_recent_hr_form
hr_results = build_hr_attack_board(GAME_DATE)
print(f"  Raw: {len(hr_results)} pitcher matchups")
hr_results = enrich_recent_hr_form(hr_results, GAME_DATE, top_n=120)
print(f"  Enriched")
for r in hr_results[:10]:
    v = r['vuln']
    w = r.get('weather', {})
    batters_str = ', '.join(b['batter_name'] for b in r['top_batters'][:3])
    print(f"  {r['pitcher_name']:<24} {r['opp_team']:<5} vuln={v['score']:.1f} {v['tier']:<12} "
          f"wind={w.get('wind_mph',0):.0f}mph comp={w.get('wind_component_cf',0):+.0f} bonus={w.get('wind_bonus',0):+.0f}")
    print(f"    Top batters: {batters_str}")
with open(f"{SP}/hr_board_{DS}.json", "w") as f:
    json.dump(hr_results, f, indent=2)
print(f"  Saved hr_board_{DS}.json")

print(f"\n=== BUILDING HITTER FANTASY BOARD {GAME_DATE} ===")
from hitter_fantasy_engine import build_hitter_fantasy_board
hf_results = build_hitter_fantasy_board(GAME_DATE)
print(f"  Fantasy results: {len(hf_results)} batters")
for r in hf_results[:10]:
    print(f"  {r.get('name','?'):<24} fscore={r.get('fantasy_score',0):.1f} "
          f"proj_dk={r.get('proj',{}).get('proj_dk',0):.1f} "
          f"matchup={r.get('matchup',{}).get('grade',0):.0f}")
with open(f"{SP}/hitter_fantasy_{DS}.json", "w") as f:
    json.dump(hf_results, f, indent=2)
print(f"  Saved hitter_fantasy_{DS}.json")

print(f"\n=== ALL BOARDS COMPLETE ===")
print(f"Date: {GAME_DATE}")
print(f"K starters: {len(k_results)}")
print(f"Walk starters: {len(w_results)}")
print(f"HR matchups: {len(hr_results)}")
print(f"Fantasy batters: {len(hf_results)}")
