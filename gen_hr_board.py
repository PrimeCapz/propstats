"""
HR Props Board generator.
Usage: python3 gen_hr_board.py [YYYY-MM-DD]
Outputs: hr_props_board_YYYYMMDD.html
"""
import json, sys, os
from collections import defaultdict
from datetime import date as _date

GAME_DATE = sys.argv[1] if len(sys.argv) > 1 else _date.today().isoformat()
DATE_LABEL = _date.fromisoformat(GAME_DATE).strftime('%B %-d, %Y')

SP = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"
DS = GAME_DATE.replace('-','')

with open(f"{SP}/hr_board_{DS}.json") as f:
    hr_board = json.load(f)
_fantasy_path = f"{SP}/hitter_fantasy_{DS}.json"
if not os.path.exists(_fantasy_path):
    _fantasy_path = f"{SP}/fantasy_board_{DS}.json"
with open(_fantasy_path) as f:
    fantasy = json.load(f)

fantasy_lu = {str(b['batter_id']): b for b in fantasy}

# Load savant batting for barrel/PA and EV50
sys.path.insert(0, '/home/user/propstats')
from propstats.backend import baseball_engine as be
savant_batting = be.load_savant_batting()

# ── Constants ──────────────────────────────────────────────────────────────────

PARK_INFO = {
    'Coors Field':               (1.27, 'EXTREME HR PARK', '#D4A017'),
    'Sutter Health Park':        (1.48, 'HITTER PARADISE',  '#D4A017'),
    'Great American Ball Park':  (1.22, 'HITTER FRIENDLY',  '#22C55E'),
    'Yankee Stadium':            (1.19, 'HITTER FRIENDLY',  '#22C55E'),
    'Guaranteed Rate Field':     (1.08, 'HITTER FRIENDLY',  '#22C55E'),
    'Minute Maid Park':          (1.08, 'HITTER FRIENDLY',  '#22C55E'),
    'Wrigley Field':             (1.07, 'HITTER FRIENDLY',  '#22C55E'),
    'Fenway Park':               (1.04, 'SLIGHT ADVANTAGE', '#84CC16'),
    'Oriole Park at Camden Yards':(1.08,'HITTER FRIENDLY',  '#22C55E'),
    'Rogers Centre':             (1.03, 'INDOOR NEUTRAL',   '#5A7090'),
    'Chase Field':               (1.02, 'INDOOR NEUTRAL',   '#5A7090'),
    'Tropicana Field':           (0.85, 'PARK SUPPRESSOR',  '#EF4444'),
    'Oracle Park':               (0.74, 'STRONG SUPPRESSOR','#EF4444'),
    'T-Mobile Park':             (0.91, 'PARK SUPPRESSOR',  '#EF4444'),
    'Petco Park':                (0.88, 'PARK SUPPRESSOR',  '#EF4444'),
    'Dodger Stadium':            (0.92, 'SLIGHT SUPPRESSOR','#F59E0B'),
    'loanDepot park':            (0.87, 'PARK SUPPRESSOR',  '#EF4444'),
    'Target Field':              (0.94, 'SLIGHT SUPPRESSOR','#F59E0B'),
    'Globe Life Field':          (0.91, 'SLIGHT SUPPRESSOR','#F59E0B'),
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def h2rgba(hx, a):
    h = hx.lstrip('#')
    r,g,b = int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)
    return f"rgba({r},{g},{b},{a})"

def tag_style(c):
    return f"background:{h2rgba(c,.13)};color:{c};border:1px solid {h2rgba(c,.30)}"

def to_american(pct):
    p = pct/100
    if p <= 0: return '+999'
    if p >= 0.5: return f'-{int(round((p/(1-p))*100))}'
    return f'+{int(round(((1-p)/p)*100))}'

def grade_info(composite, hr):
    if composite >= 72 or hr >= 38: return 'A+','#16A34A','#22C55E'
    if composite >= 60 or hr >= 26: return 'A', '#15803D','#22C55E'
    if composite >= 50 or hr >= 20: return 'B+','#0F766E','#2DD4BF'
    if composite >= 42:             return 'B', '#1D4ED8','#60A5FA'
    return 'C','#374151','#9CA3AF'

def build_tags(brl_pa, brl_bip, hh, bat_spd, xwoba, avg_dist, form,
               edges, ptier, wt, ms, hr, ev50, park_factor,
               persistent_due=False, ideal_setup=False,
               la_avg=None, gb_suppressor=False):
    T = []

    # Proven 2-day winning signals — surface first
    if ideal_setup:
        T.append(('IDEAL SETUP ✦', '#D4A017'))
    if persistent_due:
        T.append(('PERSISTENT DUE', '#F59E0B'))

    # Launch angle profile — key HR predictor (flag before contact quality)
    if la_avg is not None:
        if la_avg >= 21.0:
            T.append((f'LOFT HITTER {la_avg:.0f}°', '#10B981'))
        elif la_avg < 13.0:
            T.append((f'FLAT SWING {la_avg:.0f}°', '#EF4444'))

    # Pitcher GB suppressor warning — reduces HR upside even vs Attackable pitchers
    if gb_suppressor:
        T.append(('GB SUPPRESSOR', '#6B7280'))

    # Contact quality — barrel/PA is the primary signal
    if   brl_pa >= 25: T.append(('BARREL MACHINE',    '#D4A017'))
    elif brl_pa >= 17: T.append(('ELITE BARREL%',     '#A855F7'))
    elif brl_pa >= 12: T.append(('BARREL SIGNAL',     '#C084FC'))

    # Hard hit
    if   hh >= 55: T.append(('BLASTS 55%+',         '#0EA5E9'))
    elif hh >= 47: T.append(('BLASTS 47%+',         '#38BDF8'))

    # EV50 elite threshold
    if ev50 >= 105:   T.append(('EV50 ELITE',        '#F97316'))
    elif ev50 >= 102: T.append(('EV50 STRONG',       '#FB923C'))

    # K-rate risk: high brl/BIP but low brl/PA → lots of Ks
    if brl_pa > 0 and brl_bip > 0 and (brl_bip / brl_pa) > 2.2:
        T.append(('K-RATE RISK',   '#EF4444'))

    # Park amplifier tag
    if park_factor >= 1.20:  T.append(('PARK AMPLIFIED',  '#D4A017'))
    elif park_factor >= 1.07: T.append(('PARK BOOST',     '#84CC16'))
    elif park_factor <= 0.90: T.append(('PARK SUPPRESSOR','#EF4444'))

    # Pitcher edge
    if edges:
        pts = '/'.join([e.split('(')[0].strip() for e in edges[:2]])
        T.append((f'PITCH EDGE · {pts}',              '#06B6D4'))

    # xwOBA
    if   xwoba >= 0.450: T.append(('ELITE xwOBA',    '#10B981'))
    elif xwoba >= 0.390: T.append(('ELITE CONTACT',   '#34D399'))

    # Distance / moonshot
    if   avg_dist >= 400: T.append(('MOONSHOT POWER', '#FBBF24'))
    elif avg_dist >= 375: T.append(('LONG BALL RANGE','#D4A017'))

    # Form
    if   form in ('HOT','FIRE'): T.append(('HOT STREAK',  '#EF4444'))
    elif form == 'DUE':          T.append(('DUE FOR HR',   '#F59E0B'))

    # Pitcher market
    if ptier == 'Attackable':    T.append(('SOFT MARKET POWER', '#84CC16'))
    elif ptier == 'Avoid':       T.append(('TOUGH MATCHUP',     '#6B7280'))

    # Outlier classification
    if wt >= 50 and ms >= 70:    T.append(('PRIME OUTLIER',      '#D4A017'))
    elif wt >= 44 and hr >= 25:  T.append(('STRONG VALUE',        '#A3E635'))

    return T

def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

# ── Build picks ────────────────────────────────────────────────────────────────
all_picks, game_meta = [], {}

for ge in hr_board:
    game   = ge['game']
    ptier  = ge['vuln']['tier']
    pscore = ge['vuln']['score']
    venue  = ge.get('venue', ge.get('park', ''))
    park_factor = ge.get('top_batters', [{}])[0].get('park_hr_factor', 1.0) if ge.get('top_batters') else 1.0

    for b in ge.get('top_batters', []):
        bid  = str(b.get('batter_id',''))
        fb   = fantasy_lu.get(bid, {})
        proj = fb.get('proj',{})
        ars  = fb.get('arsenal',{})

        # Pull from savant_batting for barrel/PA, EV50 — more accurate than proj
        sv = savant_batting.get(bid, {})

        hr    = b.get('hr_prob', 0)
        ms    = b.get('matchup_score', 0)
        wt_raw = round(hr*0.55 + (ms/100)*45, 1)
        # Avoid multiplier: Avoid tier → clean miss 83% of 2-day sample
        wt = round(wt_raw * 0.72, 1) if ptier == 'Avoid' else wt_raw

        brl_bip  = b.get('brl_bip', 0) or 0
        brl_pa   = sv.get('barrel_pct', 0) or proj.get('barrel_pct', 0) or brl_bip
        ev50     = sv.get('ev50', 0) or 0
        hh       = sv.get('hard_hit_pct', 0) or proj.get('hard_hit', 0) or 0
        bat_spd  = fb.get('bat_speed', 0) or 0
        avg_dist = sv.get('avg_hr_dist', 0) or fb.get('avg_dist', 0) or 0
        xwoba    = proj.get('xwoba', 0) or 0
        form     = fb.get('form', '')
        edges    = ars.get('top_edges', [])
        bats     = fb.get('bats', b.get('bats', 'R'))
        team     = fb.get('team', b.get('team', ''))
        fscore   = fb.get('fantasy_score', 50)
        pow_score = fb.get('power_score', 0)
        cnt_score = fb.get('contact_score', 0)
        proj_dk  = proj.get('proj_dk', 0) or 0
        proj_hits = proj.get('proj_hits', 0) or 0
        mg       = fb.get('matchup', {}).get('grade', 40)
        composite= round(fscore*0.40 + mg*0.60, 1)
        pf_row   = b.get('park_hr_factor', park_factor)

        # IDEAL SETUP: park amplifies ≥1.15 AND pitcher is not Avoid
        ideal_setup = pf_row >= 1.15 and ptier != 'Avoid'
        # Effective HR%: pessimistic — applies park suppression + Avoid discount
        eff_hr = round(hr * (pf_row if pf_row < 1.0 else 1.0) * (0.72 if ptier == 'Avoid' else 1.0), 1)

        # PERSISTENT DUE: 2+ near-miss games in last 3 (air contact, no HR)
        persistent_due = False
        try:
            bid_int = b.get('batter_id', 0)
            if bid_int:
                logs = be.get_batter_game_log(int(bid_int), 2026)
                if logs:
                    recent = logs[-3:]
                    near_cnt = sum(1 for g in recent if g.get('near_hr', 0) > 0)
                    persistent_due = near_cnt >= 2
        except Exception:
            pass

        if game not in game_meta:
            game_meta[game] = {'venue': venue, 'park_factor': pf_row}

        la_avg_batter   = b.get('la_avg') or 0
        gb_suppressor   = ge['vuln'].get('gb_suppressor', False)
        tags = build_tags(brl_pa, brl_bip, hh, bat_spd, xwoba, avg_dist,
                          form, edges, ptier, wt, ms, hr, ev50, pf_row,
                          persistent_due=persistent_due, ideal_setup=ideal_setup,
                          la_avg=la_avg_batter if la_avg_batter else None,
                          gb_suppressor=gb_suppressor)
        grd, gbg, gfg = grade_info(composite, hr)

        all_picks.append({
            'name': b.get('batter_name',''), 'bats': bats, 'team': team,
            'hr': hr, 'eff_hr': eff_hr, 'ms': ms, 'wt': wt, 'composite': composite,
            'brl_pa': brl_pa, 'brl_bip': brl_bip, 'ev50': ev50, 'hh': hh,
            'xwoba': xwoba, 'avg_dist': avg_dist, 'bat_spd': bat_spd,
            'la_avg': la_avg_batter, 'form': form, 'tags': tags,
            'grade': grd, 'gbg': gbg, 'gfg': gfg,
            'game': game, 'venue': venue, 'park_factor': pf_row,
            'pitcher': ge['pitcher_name'], 'pitcher_team': ge.get('pitcher_team', ''),
            'ptier': ptier, 'vuln': pscore,
            'gb_pct_allowed': ge['vuln'].get('gb_pct_allowed', 0),
            'gb_suppressor': gb_suppressor,
            'ideal_setup': ideal_setup, 'persistent_due': persistent_due,
            'pow_score': pow_score, 'cnt_score': cnt_score,
            'proj_dk': proj_dk, 'proj_hits': proj_hits, 'fscore': fscore,
        })

all_picks.sort(key=lambda x: x['wt'], reverse=True)

# Group: games sorted by best pick, top 3 picks per game
game_order, game_picks, seen = [], defaultdict(list), set()
for p in all_picks:
    g = p['game']
    if g not in seen: game_order.append(g); seen.add(g)
    game_picks[g].append(p)

TOP_GAMES = 7

# ── HTML helpers ───────────────────────────────────────────────────────────────
def tag_html(tags):
    parts = []
    for label, color in tags:
        s = tag_style(color)
        parts.append(f'<span class="tag" style="{s}">{esc(label)}</span>')
    return ''.join(parts)

def metric_pill(label, val, highlight=False):
    hl = 'color:#DDE6F0;' if highlight else 'color:#5A7090;'
    return f'<span class="metric-pill" style="{hl}">{label} <b>{val}</b></span>'

def player_row_html(pick):
    wt        = pick['wt']
    hr        = pick['hr']
    eff       = pick.get('eff_hr', hr)
    bats      = pick['bats']
    name      = pick['name']
    team      = pick['team']
    pitcher   = pick.get('pitcher', '')
    grd       = pick['grade']
    gbg       = pick['gbg']
    gfg       = pick['gfg']
    odds      = to_american(hr)
    tags      = pick['tags']
    brl       = pick['brl_pa']
    ev50      = pick['ev50']
    hh        = pick['hh']
    pf        = pick['park_factor']
    pow_score = pick.get('pow_score', 0)
    proj_dk   = pick.get('proj_dk', 0)
    proj_hits = pick.get('proj_hits', 0)

    # Outlier stripe
    if wt >= 50:   stripe_col = '#D4A017'; row_cls = 'player-row outlier-prime'
    elif wt >= 43: stripe_col = '#2563EB'; row_cls = 'player-row outlier-strong'
    else:          stripe_col = '#1C2A3E'; row_cls = 'player-row'

    bats_label = 'LHB' if bats == 'L' else 'RHB'
    bats_cls   = 'badge-lhb' if bats == 'L' else 'badge-rhb'

    tag_block  = tag_html(tags) if tags else ''

    brl_hi  = brl >= 17
    ev50_hi = ev50 >= 103
    hh_hi   = hh >= 50

    metrics = ''
    if brl > 0:      metrics += metric_pill('Brl/PA', f'{brl:.1f}%', brl_hi)
    if ev50 > 0:     metrics += metric_pill('EV50', f'{ev50:.1f}', ev50_hi)
    if hh > 0:       metrics += metric_pill('HH%', f'{hh:.1f}%', hh_hi)
    if pow_score > 0:
        ps_hi = pow_score >= 80
        metrics += metric_pill('PwrScore', f'{pow_score:.0f}', ps_hi)
    if proj_hits > 0:
        metrics += metric_pill('projH', f'{proj_hits:.2f}', proj_hits >= 1.0)
    if proj_dk > 0:
        metrics += metric_pill('DK', f'{proj_dk:.1f}', proj_dk >= 10.0)
    if pf != 1.0:
        pf_col = '#D4A017' if pf >= 1.20 else ('#22C55E' if pf >= 1.07 else ('#EF4444' if pf <= 0.90 else '#5A7090'))
        metrics += f'<span class="metric-pill" style="color:{pf_col}">Park ×{pf:.2f}</span>'
    # Effective HR% — show when park suppression or Avoid penalty reduces it materially
    if abs(eff - hr) >= 0.5:
        metrics += metric_pill('Eff HR%', f'{eff:.1f}%', False)

    return f'''\
<div class="{row_cls}">
  <div class="stripe" style="background:{stripe_col}"></div>
  <div class="row-inner">
    <div class="row-top">
      <div class="name-area">
        <span class="pname">{esc(name)}</span>
        <span class="bats-badge {bats_cls}">{bats_label}</span>
        <span class="hr-pill">◉ HR</span>
      </div>
      <div class="row-right">
        <span class="team-tag">{esc(team)}</span>
        {f'<span class="vs-pitcher">vs {esc(pitcher)}</span>' if pitcher else ''}
        <span class="grade-badge" style="background:{gbg};color:{gfg}">{grd}</span>
        <span class="prob-block"><span class="prob-pct">{hr:.1f}%</span><span class="prob-odds"> ({odds})</span></span>
      </div>
    </div>
    {f'<div class="metrics-row">{metrics}</div>' if metrics else ''}
    {f'<div class="tags-row">{tag_block}</div>' if tag_block else ''}
  </div>
</div>'''

def game_header_html(game):
    meta  = game_meta.get(game, {})
    venue = meta.get('venue', '')
    pf    = meta.get('park_factor', 1.0)

    info  = PARK_INFO.get(venue)
    if info:
        _, park_label, park_col = info
        pf_display = f'×{pf:.2f}'
        park_html = (f'<span class="park-pill" style="color:{park_col};'
                     f'border-color:{h2rgba(park_col,.30)}">'
                     f'{park_label} {pf_display}</span>')
    else:
        park_html = ''

    away, home = game.split('@')
    # Collect unique pitchers from all picks for this game (preserves insertion order)
    seen_pitchers: dict = {}
    for p in game_picks[game]:
        pname = p.get('pitcher', '')
        if pname and pname not in seen_pitchers:
            seen_pitchers[pname] = (
                pname,
                p.get('pitcher_team', ''),
                p.get('ptier', ''),
                p.get('gb_suppressor', False),
                p.get('gb_pct_allowed', 0),
            )
    pitcher_parts = []
    for pname, pteam, ptier, gb_sup, gb_pct_v in seen_pitchers.values():
        ptier_col = '#84CC16' if ptier == 'Attackable' else ('#EF4444' if ptier == 'Avoid' else '#5A7090')
        gb_note   = ' GB⬇' if gb_sup else ''
        team_part = f' ({esc(pteam)})' if pteam else ''
        label     = f'{esc(pname)}{team_part} · {esc(ptier)}{gb_note}'
        pitcher_parts.append(f'<span class="pitcher-tag" style="color:{ptier_col}">{label}</span>')
    if len(pitcher_parts) > 1:
        pitcher_html = '<span class="pitcher-sep"> ↔ </span>'.join(pitcher_parts)
    elif pitcher_parts:
        pitcher_html = pitcher_parts[0]
    else:
        pitcher_html = ''

    return f'''\
<div class="game-hdr">
  <div class="game-hdr-left">
    <span class="game-teams">{away} <span class="at">@</span> {home}</span>
    <span class="hdr-dot">·</span>
    <span class="game-venue">{esc(venue)}</span>
    {pitcher_html}
  </div>
  <div class="game-hdr-right">{park_html}</div>
</div>'''

# ── Assemble board ─────────────────────────────────────────────────────────────
rows_html = ''
for game in game_order[:TOP_GAMES]:
    rows_html += game_header_html(game)
    for pick in game_picks[game][:3]:
        rows_html += player_row_html(pick)

# ── Full page ──────────────────────────────────────────────────────────────────
HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HR Props Board — {DATE_LABEL}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:#090D14;color:#DDE6F0;
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;min-height:100vh;
}}

/* ── Page header ── */
.page-hdr{{padding:20px 20px 0;max-width:960px;margin:0 auto}}
.page-eyebrow{{font-size:10px;font-weight:700;letter-spacing:.18em;
  text-transform:uppercase;color:#3B5270;margin-bottom:6px}}
.page-title{{font-size:clamp(20px,4vw,26px);font-weight:800;color:#DDE6F0;
  letter-spacing:-.01em;line-height:1.1}}
.page-sub{{margin-top:4px;font-size:12px;color:#3B5270}}

/* ── Legend ── */
.legend{{display:flex;flex-wrap:wrap;gap:12px;padding:14px 20px;
  max-width:960px;margin:0 auto;border-bottom:1px solid #1A2A3E}}
.legend-item{{display:flex;align-items:center;gap:5px;font-size:10px;color:#3B5270}}
.legend-stripe{{width:3px;height:14px;border-radius:2px}}
.legend-label{{font-weight:600}}

/* ── Board ── */
.board{{max-width:960px;margin:0 auto;padding:0 0 40px}}

/* ── Game header ── */
.game-hdr{{
  display:flex;align-items:center;justify-content:space-between;gap:12px;
  padding:8px 20px;background:#060910;
  border-top:1px solid #1A2A3E;border-bottom:1px solid #1A2A3E;margin-top:16px
}}
.game-hdr:first-child{{margin-top:0}}
.game-hdr-left{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.game-teams{{font-size:13px;font-weight:800;color:#DDE6F0;letter-spacing:.02em}}
.at{{color:#3B5270;font-weight:400}}
.hdr-dot{{color:#1A2A3E}}
.game-venue{{font-size:11px;color:#3B5270}}
.pitcher-tag{{font-size:10px;font-weight:600;letter-spacing:.04em}}
.pitcher-sep{{font-size:10px;color:#3B5270;font-weight:400}}
.park-pill{{
  font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
  padding:2px 7px;border:1px solid;border-radius:999px
}}

/* ── Player row ── */
.player-row{{position:relative;display:flex;border-bottom:1px solid #0F1925}}
.stripe{{width:3px;flex-shrink:0}}
.row-inner{{flex:1;padding:10px 16px 10px 12px;min-width:0}}
.row-top{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
.name-area{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;min-width:0}}
.pname{{font-size:14px;font-weight:700;color:#DDE6F0;white-space:nowrap}}
.bats-badge{{font-size:9px;font-weight:700;letter-spacing:.06em;
  padding:2px 6px;border-radius:3px}}
.badge-lhb{{background:rgba(14,165,233,.15);color:#0EA5E9;border:1px solid rgba(14,165,233,.3)}}
.badge-rhb{{background:rgba(168,85,247,.15);color:#A855F7;border:1px solid rgba(168,85,247,.3)}}
.hr-pill{{font-size:10px;font-weight:700;color:#3B5270;letter-spacing:.04em}}
.row-right{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
.team-tag{{font-size:11px;font-weight:600;color:#3B5270}}
.vs-pitcher{{font-size:10px;font-weight:600;color:#5A7090;white-space:nowrap}}
.grade-badge{{font-size:11px;font-weight:800;padding:2px 8px;border-radius:4px}}
.prob-block{{display:flex;align-items:baseline;gap:2px}}
.prob-pct{{font-size:17px;font-weight:800;color:#DDE6F0;font-variant-numeric:tabular-nums}}
.prob-odds{{font-size:11px;color:#3B5270;font-variant-numeric:tabular-nums}}

/* ── Metrics row ── */
.metrics-row{{
  display:flex;flex-wrap:wrap;gap:6px;margin-top:6px
}}
.metric-pill{{
  font-size:10px;font-weight:500;
  background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.07);
  border-radius:4px;padding:2px 7px;
  font-variant-numeric:tabular-nums;
}}
.metric-pill b{{font-weight:700}}

/* ── Tags row ── */
.tags-row{{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}}
.tag{{font-size:9px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  padding:2px 7px;border-radius:4px}}

/* ── Outlier rows ── */
.outlier-prime .pname{{color:#F5C842}}
.outlier-prime .prob-pct{{color:#F5C842}}
.outlier-strong .pname{{color:#93C5FD}}

/* ── Footer note ── */
.foot{{max-width:960px;margin:0 auto;padding:0 20px 24px;
  font-size:10px;color:#1E3050;line-height:1.6}}
</style>
</head>
<body>
<div class="page-hdr">
  <div class="page-eyebrow">Baseball Analytics · HR Props</div>
  <div class="page-title">HR Props Board — {DATE_LABEL}</div>
  <div class="page-sub">Weighted Score = HR% × 0.55 + (Matchup/100) × 45 · Avoid pitcher = ×0.72 penalty · Eff HR% adjusts for park + Avoid · Brl/PA from Statcast · EV50 = 50th pct exit velocity</div>
</div>

<div class="legend">
  <div class="legend-item">
    <div class="legend-stripe" style="background:#D4A017"></div>
    <span class="legend-label">PRIME OUTLIER</span><span>wt ≥ 50</span>
  </div>
  <div class="legend-item">
    <div class="legend-stripe" style="background:#2563EB"></div>
    <span class="legend-label">STRONG</span><span>wt ≥ 43</span>
  </div>
  <div class="legend-item" style="margin-left:8px;color:#D4A017;font-weight:700;font-size:10px">
    IDEAL SETUP ✦
    <span style="font-weight:400;color:#3B5270">= Park ≥×1.15 + Non-Avoid pitcher (4/6 HRs over 2 days)</span>
  </div>
  <div class="legend-item">
    <span style="color:#F59E0B;font-weight:700;font-size:10px">PERSISTENT DUE</span>
    <span>= 2+ near-miss games in last 3 (air contact, no HR)</span>
  </div>
  <div class="legend-item">
    <span style="color:#6B7280;font-weight:700;font-size:10px">AVOID PENALTY</span>
    <span>= wt × 0.72 when pitcher tier = Avoid (83% clean-miss rate)</span>
  </div>
  <div class="legend-item">
    <span style="color:#D4A017;font-weight:700;font-size:10px">Brl/PA ≥ 17%</span>
    <span>= Elite barrel rate (per PA, not per BIP)</span>
  </div>
  <div class="legend-item">
    <span style="color:#F97316;font-weight:700;font-size:10px">EV50 ≥ 105</span>
    <span>= Power floor elite</span>
  </div>
  <div class="legend-item">
    <span style="color:#EF4444;font-weight:700;font-size:10px">K-RATE RISK</span>
    <span>= High Brl/BIP but low Brl/PA → heavy strikeouts</span>
  </div>
</div>

<div class="board">{rows_html}</div>

<div class="foot">
  Barrel/PA = barrels per plate appearance (Statcast leaderboard) — a strikeout-adjusted contact quality metric.
  Brl/BIP = barrels per ball in play — ignores strikeout rate, inflated for high-K hitters.
  EV50 = 50th percentile exit velocity — separates consistent hard contact from peak-only hitters.
  Park ×factor from PARK_FACTORS table; ×1.27+ = Coors/Sutter Health (significant HR amplifier).
  K-RATE RISK fires when Brl/BIP ÷ Brl/PA &gt; 2.2, indicating the player needs too many PAs to reach barrel opportunity.
  AVOID PENALTY: Weighted score multiplied by ×0.72 when pitcher tier = Avoid — derived from 2-day sample (5 of 6 clean misses were Avoid matchups).
  IDEAL SETUP: Park ×1.15+ AND non-Avoid pitcher — produced 4 of 6 HRs over the 2-day 8/1–8/2 sample.
  PERSISTENT DUE: Batter had near-miss air contact in 2+ of last 3 games without clearing the wall — regression candidate.
  Eff HR%: Effective probability adjusted downward for park suppression and/or Avoid pitcher; shown only when &gt;0.5% below raw HR%.
</div>
</body>
</html>"""

out_path = f"/home/user/propstats/hr_props_board_{DS}.html"
with open(out_path, 'w') as f:
    f.write(HTML)

print(f"Wrote {out_path} ({len(HTML):,} bytes)")
print(f"Top picks:")
for p in all_picks[:8]:
    flags = []
    if p['brl_pa'] >= 17: flags.append(f"Brl/PA {p['brl_pa']:.1f}%")
    if p['ev50'] >= 103:  flags.append(f"EV50 {p['ev50']:.1f}")
    if p['park_factor'] >= 1.20: flags.append(f"Park×{p['park_factor']:.2f}")
    print(f"  {p['name']:<22} wt={p['wt']:.1f} HR={p['hr']:.1f}% ms={p['ms']:.1f} | {' | '.join(flags) or '—'}")
