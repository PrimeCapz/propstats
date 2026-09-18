import sys, os, json, time
sys.path.insert(0, "/home/user/propstats/propstats/backend")

GAME_DATE = "2026-09-01"
DS = "20260901"
SP = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"
os.makedirs(SP, exist_ok=True)

OUT_LINES = []

def banner(title):
    sep = "=" * 72
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)
    OUT_LINES.append(f"\n{sep}")
    OUT_LINES.append(f"  {title}")
    OUT_LINES.append(sep)

def out(line=""):
    print(line)
    OUT_LINES.append(line)

# ── K BOARD ───────────────────────────────────────────────────────────────
banner(f"PITCHER STRIKEOUT BOARD — {GAME_DATE}")
from k_engine import build_k_board, format_k_board
k_results = build_k_board(GAME_DATE)
out(f"  Pitchers analyzed: {len(k_results)}")
for r in k_results:
    ks   = r.get('k_score', {})
    proj = r.get('proj', {})
    form = r.get('recent_form', {})
    vt   = ks.get('velo_trend_label', '')
    rest = form.get('rest_label', '')
    tags = '  '.join(t for t in [vt, rest] if t)
    out(f"  {r['pitcher_name']:<28} score={ks.get('score',0):.1f} {ks.get('tier','?'):<12} "
        f"proj={proj.get('proj_k','?')} line={proj.get('line','?')} edge={proj.get('edge_vs_line','?')} "
        f"chase={ks.get('chase_pct',0):.1f}% ppa={ks.get('p_per_pa',0):.2f}"
        + (f"  [{tags}]" if tags else ""))
with open(f"{SP}/k_board_{DS}.json", "w") as f:
    json.dump(k_results, f, indent=2)

# ── WALK BOARD ────────────────────────────────────────────────────────────
banner(f"PITCHER WALK BOARD — {GAME_DATE}")
from walk_engine import build_walk_board, format_walk_board
w_results = build_walk_board(GAME_DATE)
out(f"  Pitchers analyzed: {len(w_results)}")
for r in w_results:
    tags = r.get('tags', '')
    out(f"  {r.get('pitcher_name','?'):<28} bb_score={r.get('bb_score',0):.1f} "
        f"proj={r.get('proj_bb','?')} line={r.get('line','?')}"
        + (f"  [{tags}]" if tags else ""))
with open(f"{SP}/walk_board_{DS}.json", "w") as f:
    json.dump(w_results, f, indent=2)

# ── HR BOARD ──────────────────────────────────────────────────────────────
banner(f"HR ATTACK BOARD — {GAME_DATE}")
from hr_engine import build_hr_attack_board, enrich_recent_hr_form
hr_results = build_hr_attack_board(GAME_DATE)
hr_results = enrich_recent_hr_form(hr_results, GAME_DATE, top_n=120)
out(f"  Pitcher matchups: {len(hr_results)}")
for r in hr_results[:12]:
    v    = r['vuln']
    w    = r.get('weather', {})
    l5   = v.get('l5_hr_label', '')
    tags = v.get('tags', [])
    batters_str = ', '.join(b['batter_name'] for b in r['top_batters'][:3])
    out(f"  {r['pitcher_name']:<24} {r['opp_team']:<5} vuln={v['score']:.1f} {v['tier']:<12} "
        f"wind={w.get('wind_mph',0):.0f}mph bonus={w.get('wind_bonus',0):+.0f}"
        + (f"  [{l5}]" if l5 else ""))
    out(f"    Targets: {batters_str}")
with open(f"{SP}/hr_board_{DS}.json", "w") as f:
    json.dump(hr_results, f, indent=2)

# ── NRFI BOARD ────────────────────────────────────────────────────────────
banner(f"NRFI BOARD — {GAME_DATE}")
from nrfi_engine import build_nrfi_board, format_nrfi_board
try:
    nrfi_results = build_nrfi_board(GAME_DATE)
    nrfi_text = format_nrfi_board(nrfi_results, GAME_DATE)
    out(nrfi_text)
    with open(f"{SP}/nrfi_{DS}.json", "w") as f:
        json.dump(nrfi_results, f, indent=2)
    with open(f"{SP}/nrfi_{DS}.txt", "w") as f:
        f.write(nrfi_text)
except Exception as e:
    out(f"  NRFI error: {e}")

# ── HITS BOARD ────────────────────────────────────────────────────────────
banner(f"HITS O/U 1.5 BOARD — {GAME_DATE}")
from hits_engine import build_hits_board, format_hits_board
try:
    hits_results = build_hits_board(GAME_DATE)
    hits_text = format_hits_board(hits_results, GAME_DATE)
    total_batters = sum(len(r.get('all_batters', [])) for r in hits_results)
    machines = sum(1 for r in hits_results for b in r.get('all_batters', []) if b.get('tier') == 'HIT MACHINE')
    out(f"  Pitchers: {len(hits_results)}  Batters: {total_batters}  HIT MACHINE: {machines}")
    for r in hits_results[:6]:
        hp = r.get('h_profile', {})
        out(f"  vs {r['pitcher_name']:<24} k%={r.get('pitcher_k_pct',0):.1f}  h_lbl={hp.get('h_label','')}")
        for b in r.get('top_batters', [])[:4]:
            proj = b.get('proj', {})
            hand = b.get('hand_label', '')
            out(f"    {b['batter_name']:<22} O1.5:{proj.get('p_2plus',0):.1f}%  {b['tier']:<14}"
                + (f"  [{hand}]" if hand else ""))
    with open(f"{SP}/hits_board_{DS}.txt", "w") as f:
        f.write(hits_text)
    with open(f"{SP}/hits_board_{DS}.json", "w") as f:
        json.dump([{k: v for k, v in r.items() if k != 'all_batters'} for r in hits_results], f, indent=2)
except Exception as e:
    import traceback; traceback.print_exc()
    out(f"  Hits error: {e}")

# ── TOTAL BASES BOARD ─────────────────────────────────────────────────────
banner(f"TOTAL BASES BOARD — {GAME_DATE}")
from tb_engine import build_tb_board, format_tb_board
try:
    tb_results = build_tb_board(GAME_DATE)
    tb_text = format_tb_board(tb_results)
    machines = sum(1 for r in tb_results if r.get('tier') == 'XB MACHINE')
    out(f"  Batters: {len(tb_results)}  XB MACHINE: {machines}")
    for r in [x for x in tb_results if x.get('tier') == 'XB MACHINE'][:8]:
        out(f"  {r['batter_name']:<22} vs {r['opp_sp_name']:<24} "
            f"O2.5:{r.get('p3',0):.1f}%  [{r.get('conf','')}]  "
            f"xSLG:{r.get('xslg',0):.3f}  ISO:{r.get('iso',0):.3f}")
    with open(f"{SP}/tb_board_{DS}.txt", "w") as f:
        f.write(tb_text)
    with open(f"{SP}/tb_board_{DS}.json", "w") as f:
        json.dump(tb_results, f, indent=2)
except Exception as e:
    import traceback; traceback.print_exc()
    out(f"  TB error: {e}")

# ── F5 BOARD ──────────────────────────────────────────────────────────────
banner(f"FIRST 5 INNINGS BOARD — {GAME_DATE}")
from f5_engine import build_f5_board, format_f5_board
try:
    f5_results = build_f5_board(GAME_DATE)
    f5_text = format_f5_board(f5_results)
    out(f"  Games: {len(f5_results)}")
    for r in f5_results:
        out(f"  {r['away_abbr']}@{r['home_abbr']}  λ:{r['lam_total']:.2f}  "
            f"O4.5:{r['p_o4']:.1f}%  [{r['total_conf']}]  "
            f"{r['sp_away_name'].split()[-1]}({r['away_era_l5']:.2f}) vs "
            f"{r['sp_home_name'].split()[-1]}({r['home_era_l5']:.2f})"
            + (f"  [{r['away_rest']}]" if r.get('away_rest') else "")
            + (f"  [{r['home_rest']}]" if r.get('home_rest') else ""))
    with open(f"{SP}/f5_board_{DS}.txt", "w") as f:
        f.write(f5_text)
    with open(f"{SP}/f5_board_{DS}.json", "w") as f:
        json.dump(f5_results, f, indent=2)
except Exception as e:
    import traceback; traceback.print_exc()
    out(f"  F5 error: {e}")

# ── BATTER K BOARD ────────────────────────────────────────────────────────
banner(f"BATTER STRIKEOUT BOARD — {GAME_DATE}")
from batter_k_engine import build_batter_k_board, format_batter_k_board
try:
    bk_results = build_batter_k_board(GAME_DATE)
    bk_text = format_batter_k_board(bk_results)
    machines = sum(1 for r in bk_results if r.get('tier') == 'K MACHINE')
    contacts = sum(1 for r in bk_results if r.get('tier') == 'CONTACT')
    out(f"  Batters: {len(bk_results)}  K MACHINE: {machines}  CONTACT: {contacts}")
    for r in [x for x in bk_results if x.get('tier') == 'K MACHINE'][:8]:
        out(f"  {r['batter_name']:<22} vs {r['opp_sp_name']:<24} "
            f"O1.5:{r.get('p2',0):.1f}%  [{r.get('conf','')}]  "
            f"K%:{r.get('k_pct',0):.1f}  Chase:{r.get('chase',0):.1f}")
    with open(f"{SP}/batter_k_{DS}.txt", "w") as f:
        f.write(bk_text)
    with open(f"{SP}/batter_k_{DS}.json", "w") as f:
        json.dump(bk_results, f, indent=2)
except Exception as e:
    import traceback; traceback.print_exc()
    out(f"  Batter K error: {e}")

# ── HITTER FANTASY ────────────────────────────────────────────────────────
banner(f"HITTER FANTASY BOARD — {GAME_DATE}")
from hitter_fantasy_engine import build_hitter_fantasy_board
try:
    hf_results = build_hitter_fantasy_board(GAME_DATE)
    out(f"  Batters: {len(hf_results)}")
    for r in hf_results[:8]:
        out(f"  {r.get('name','?'):<24} fscore={r.get('fantasy_score',0):.1f} "
            f"proj_dk={r.get('proj',{}).get('proj_dk',0):.1f}")
    with open(f"{SP}/hitter_fantasy_{DS}.json", "w") as f:
        json.dump(hf_results, f, indent=2)
except Exception as e:
    out(f"  Fantasy error: {e}")

# ── SUMMARY ───────────────────────────────────────────────────────────────
banner(f"SLATE COMPLETE — {GAME_DATE}")
out(f"  K board:        {len(k_results)} pitchers")
out(f"  Walk board:     {len(w_results)} pitchers")
out(f"  HR board:       {len(hr_results)} matchups")
try: out(f"  NRFI board:     {len(nrfi_results)} games")
except: pass
try: out(f"  Hits board:     {len(hits_results)} pitcher slots")
except: pass
try: out(f"  TB board:       {len(tb_results)} batter rows")
except: pass
try: out(f"  F5 board:       {len(f5_results)} games")
except: pass
try: out(f"  Batter K board: {len(bk_results)} batter rows")
except: pass
out(f"\n  Files saved to: {SP}")

with open(f"{SP}/full_slate_{DS}.txt", "w") as f:
    f.write("\n".join(OUT_LINES))
out(f"  Full output: {SP}/full_slate_{DS}.txt")
