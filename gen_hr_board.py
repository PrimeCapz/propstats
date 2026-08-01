import json
from collections import defaultdict

with open('/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad/hr_board_20260801.json') as f:
    hr_board = json.load(f)
with open('/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad/hitter_fantasy_20260801.json') as f:
    fantasy = json.load(f)

fantasy_lu = {str(b['batter_id']): b for b in fantasy}

PARK_INFO = {
    'Coors Field':               ('EXTREME HR PARK · +45% HR RATE', '#D4A017'),
    'Great American Ball Park':  ('HITTER-FRIENDLY · +20% HR RATE', '#22C55E'),
    'Yankee Stadium':            ('HITTER-FRIENDLY · +15% HR RATE', '#22C55E'),
    'Wrigley Field':             ('HITTER-FRIENDLY · +10% HR RATE', '#22C55E'),
    'Fenway Park':               ('HITTER-FRIENDLY · +8% HR RATE',  '#22C55E'),
    'Camden Yards':              ('HITTER-FRIENDLY · +8% HR RATE',  '#22C55E'),
    'Chase Field':               ('INDOOR VENUE · NO WEATHER',       '#5A7090'),
    'Tropicana Field':           ('INDOOR VENUE · NO WEATHER',       '#5A7090'),
    'Rogers Centre':             ('INDOOR VENUE · NO WEATHER',       '#5A7090'),
}

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

def build_tags(barrel, hard_hit, bat_spd, xwoba, avg_dist, form, edges, ptier, wt, ms, hr):
    T = []
    if   hard_hit >= 50: T.append(('BLASTS 50%+',    '#0EA5E9'))
    elif hard_hit >= 35: T.append(('BLASTS 35%+',    '#38BDF8'))

    if bat_spd >= 75:    T.append(('POWER PLAY',      '#F97316'))

    if barrel >= 14 and hard_hit >= 35:
        T.append(('BARREL + BLASTS',                  '#A855F7'))
    elif barrel >= 14:
        T.append((f'BARREL {barrel:.0f}%+',           '#C084FC'))
    elif barrel >= 10:
        T.append((f'BARREL {barrel:.0f}%+',           '#9333EA'))

    if edges:
        pts = '/'.join([e.split('(')[0] for e in edges[:2]])
        T.append((f'PITCH EDGE · {pts}',              '#06B6D4'))

    if   xwoba >= 0.450: T.append(('ELITE xwOBA',    '#10B981'))
    elif xwoba >= 0.390: T.append(('ELITE CONTACT',   '#34D399'))

    if   avg_dist >= 400: T.append(('MOONSHOT',       '#FBBF24'))
    elif avg_dist >= 375: T.append(('MINI MOONSHOT',  '#D4A017'))

    if   form in ('HOT','FIRE'): T.append(('HOT STREAK',  '#EF4444'))
    elif form == 'DUE':          T.append(('DUE FOR HR',   '#F59E0B'))

    if ptier == 'Attackable':    T.append(('SOFT MARKET POWER', '#84CC16'))

    if wt >= 50 and ms >= 70:    T.append(('PRIME OUTLIER',      '#D4A017'))
    elif wt >= 44 and hr >= 26:  T.append(('STRONG VALUE',        '#A3E635'))

    return T

def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

# ── Build picks ───────────────────────────────────────────────────────────────
all_picks, game_meta = [], {}

for ge in hr_board:
    game = ge['game']
    ptier = ge['vuln']['tier']
    pscore = ge['vuln']['score']

    for b in ge.get('top_batters', []):
        bid = str(b.get('batter_id',''))
        fb  = fantasy_lu.get(bid, {})
        proj= fb.get('proj',{})
        ars = fb.get('arsenal',{})

        hr   = b.get('hr_prob', 0)
        ms   = b.get('matchup_score', 0)
        wt   = round(hr*0.55 + (ms/100)*45, 1)

        barrel   = proj.get('barrel_pct', 0)
        hard_hit = proj.get('hard_hit', 0)
        xwoba    = proj.get('xwoba', 0)
        bat_spd  = fb.get('bat_speed', 0)
        avg_dist = fb.get('avg_dist', 0)
        form     = fb.get('form', '')
        edges    = ars.get('top_edges', [])
        venue    = fb.get('venue', '')
        bats     = fb.get('bats', 'R')
        team     = fb.get('team', '')
        fscore   = fb.get('fantasy_score', 50)
        mg       = fb.get('matchup', {}).get('grade', 40)
        composite= round(fscore*0.40 + mg*0.60, 1)

        if game not in game_meta and venue:
            game_meta[game] = {'venue': venue, 'pitcher': ge['pitcher_name'], 'ptier': ptier}

        tags = build_tags(barrel, hard_hit, bat_spd, xwoba, avg_dist,
                          form, edges, ptier, wt, ms, hr)
        grd, gbg, gfg = grade_info(composite, hr)

        all_picks.append({
            'name': b.get('batter_name',''), 'bats': bats, 'team': team,
            'hr': hr, 'ms': ms, 'wt': wt, 'composite': composite,
            'barrel': barrel, 'hard_hit': hard_hit, 'xwoba': xwoba,
            'bat_spd': bat_spd, 'form': form, 'tags': tags,
            'grade': grd, 'gbg': gbg, 'gfg': gfg,
            'game': game, 'venue': venue, 'pitcher': ge['pitcher_name'],
            'ptier': ptier,
        })

all_picks.sort(key=lambda x: x['wt'], reverse=True)

# Group: games sorted by best pick, top 3 picks per game
game_order, game_picks, seen = [], defaultdict(list), set()
for p in all_picks:
    g = p['game']
    if g not in seen: game_order.append(g); seen.add(g)
    game_picks[g].append(p)

TOP_GAMES = 6

# ── HTML templates ─────────────────────────────────────────────────────────────
def tag_html(tags):
    parts = []
    for label, color in tags:
        s = tag_style(color)
        parts.append(f'<span class="tag" style="{s}">{esc(label)}</span>')
    return ''.join(parts)

def player_row_html(pick, rank_in_game):
    wt   = pick['wt']
    hr   = pick['hr']
    bats = pick['bats']
    name = pick['name']
    team = pick['team']
    grd  = pick['grade']
    gbg  = pick['gbg']
    gfg  = pick['gfg']
    odds = to_american(hr)
    tags = pick['tags']

    # Outlier stripe
    if wt >= 50:   stripe_col = '#D4A017'; row_cls = 'player-row outlier-prime'
    elif wt >= 43: stripe_col = '#2563EB'; row_cls = 'player-row outlier-strong'
    else:          stripe_col = '#1C2A3E'; row_cls = 'player-row'

    bats_label = 'LHB' if bats == 'L' else 'RHB'
    bats_cls   = 'badge-lhb' if bats == 'L' else 'badge-rhb'

    tag_block = tag_html(tags) if tags else ''

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
        <span class="grade-badge" style="background:{gbg};color:{gfg}">{grd}</span>
        <span class="prob-block"><span class="prob-pct">{hr:.1f}%</span><span class="prob-odds"> ({odds})</span></span>
      </div>
    </div>
    {f'<div class="tags-row">{tag_block}</div>' if tag_block else ''}
  </div>
</div>'''

def game_header_html(game):
    meta  = game_meta.get(game, {})
    venue = meta.get('venue', '')
    park_label, park_col = PARK_INFO.get(venue, ('STANDARD VENUE', '#5A7090'))
    park_html = f'<span class="park-pill" style="color:{park_col};border-color:{h2rgba(park_col,.30)}">{park_label}</span>' if park_col else ''
    away, home = game.split('@')
    return f'''\
<div class="game-hdr">
  <div class="game-hdr-left">
    <span class="game-teams">{away} <span class="at">@</span> {home}</span>
    <span class="hdr-dot">·</span>
    <span class="game-venue">{esc(venue)}</span>
  </div>
  <div class="game-hdr-right">{park_html}</div>
</div>'''

# ── Assemble board ─────────────────────────────────────────────────────────────
rows_html = ''
for game in game_order[:TOP_GAMES]:
    rows_html += game_header_html(game)
    for pick in game_picks[game][:3]:
        rows_html += player_row_html(pick, 0)

# ── Full page ──────────────────────────────────────────────────────────────────
HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HR Props Board — Aug 1, 2026</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{
  background:#090D14;
  color:#DDE6F0;
  font-family:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
  min-height:100vh;
}}

/* ── Page header ── */
.page-hdr{{
  padding:20px 20px 0;
  max-width:900px;
  margin:0 auto;
}}
.page-eyebrow{{
  font-size:10px;
  font-weight:700;
  letter-spacing:.18em;
  text-transform:uppercase;
  color:#3B5270;
  margin-bottom:6px;
}}
.page-title{{
  font-size:clamp(20px,4vw,26px);
  font-weight:800;
  color:#DDE6F0;
  letter-spacing:-.01em;
  line-height:1.1;
}}
.page-sub{{
  margin-top:4px;
  font-size:12px;
  color:#3B5270;
}}

/* ── Legend ── */
.legend{{
  display:flex;
  flex-wrap:wrap;
  gap:12px;
  padding:14px 20px;
  max-width:900px;
  margin:0 auto;
  border-bottom:1px solid #1A2A3E;
}}
.legend-item{{
  display:flex;
  align-items:center;
  gap:5px;
  font-size:10px;
  color:#3B5270;
}}
.legend-stripe{{
  width:3px;height:14px;border-radius:2px;
}}
.legend-label{{font-weight:600}}

/* ── Board ── */
.board{{
  max-width:900px;
  margin:0 auto;
  padding:0 0 32px;
}}

/* ── Game header ── */
.game-hdr{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:12px;
  padding:8px 20px;
  background:#060910;
  border-top:1px solid #1A2A3E;
  border-bottom:1px solid #1A2A3E;
  margin-top:16px;
}}
.game-hdr:first-child{{margin-top:0}}
.game-hdr-left{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}}
.game-teams{{
  font-size:13px;
  font-weight:800;
  color:#8AA8C8;
  letter-spacing:.02em;
}}
.at{{color:#3B5270;font-weight:400}}
.hdr-dot{{color:#2A3A50;font-size:10px}}
.game-venue{{font-size:10px;color:#3B5270;font-weight:500}}
.park-pill{{
  font-size:9px;
  font-weight:700;
  letter-spacing:.06em;
  text-transform:uppercase;
  padding:2px 8px;
  border-radius:3px;
  border:1px solid;
}}

/* ── Player rows ── */
.player-row{{
  display:flex;
  align-items:stretch;
  border-bottom:1px solid #111B28;
  position:relative;
  transition:background .1s;
}}
.player-row:hover{{background:#0D1828}}
.player-row.outlier-prime{{background:#0D1520}}
.player-row.outlier-prime:hover{{background:#111C2A}}
.player-row.outlier-strong:hover{{background:#0C1828}}

.stripe{{
  width:3px;
  flex-shrink:0;
  align-self:stretch;
}}

.row-inner{{
  flex:1;
  padding:11px 16px 10px;
  min-width:0;
}}

.row-top{{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:8px;
  min-width:0;
}}

.name-area{{
  display:flex;
  align-items:center;
  gap:7px;
  min-width:0;
  flex:1;
}}
.pname{{
  font-size:14px;
  font-weight:700;
  color:#E4EBF5;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}}
.bats-badge{{
  font-size:9px;
  font-weight:700;
  padding:2px 5px;
  border-radius:3px;
  letter-spacing:.04em;
  flex-shrink:0;
}}
.badge-lhb{{background:rgba(37,99,235,.20);color:#60A5FA;border:1px solid rgba(37,99,235,.35)}}
.badge-rhb{{background:rgba(234,88,12,.18);color:#FB923C;border:1px solid rgba(234,88,12,.30)}}
.hr-pill{{
  background:rgba(22,163,74,.20);
  color:#4ADE80;
  border:1px solid rgba(22,163,74,.35);
  font-size:9px;
  font-weight:700;
  padding:2px 6px;
  border-radius:10px;
  letter-spacing:.03em;
  flex-shrink:0;
}}

/* ── Right side ── */
.row-right{{
  display:flex;
  align-items:center;
  gap:10px;
  flex-shrink:0;
}}
.team-tag{{
  font-size:11px;
  font-weight:700;
  color:#5A7090;
  letter-spacing:.06em;
  min-width:28px;
  text-align:right;
}}
.grade-badge{{
  font-size:11px;
  font-weight:800;
  width:30px;
  height:22px;
  border-radius:4px;
  display:flex;
  align-items:center;
  justify-content:center;
  letter-spacing:.02em;
}}
.prob-block{{
  min-width:110px;
  text-align:right;
}}
.prob-pct{{
  font-family:"SF Mono",Consolas,"Liberation Mono",monospace;
  font-size:15px;
  font-weight:700;
  color:#22C55E;
  font-variant-numeric:tabular-nums;
}}
.prob-odds{{
  font-family:"SF Mono",Consolas,"Liberation Mono",monospace;
  font-size:12px;
  font-weight:600;
  color:#166534;
  font-variant-numeric:tabular-nums;
}}

/* ── Tags ── */
.tags-row{{
  display:flex;
  flex-wrap:wrap;
  gap:5px;
  margin-top:7px;
}}
.tag{{
  font-size:9px;
  font-weight:700;
  letter-spacing:.05em;
  text-transform:uppercase;
  padding:2px 7px;
  border-radius:3px;
  white-space:nowrap;
}}

@media(max-width:580px){{
  .prob-block{{min-width:80px}}
  .prob-pct{{font-size:13px}}
  .row-inner{{padding:9px 12px}}
  .pname{{font-size:13px}}
  .team-tag,.grade-badge{{display:none}}
}}
</style>
</head>
<body>

<div class="page-hdr">
  <div class="page-eyebrow">PropStats · HR Props</div>
  <div class="page-title">Today's Home Run Board</div>
  <div class="page-sub">August 1, 2026 &nbsp;·&nbsp; Ranked by quality-adjusted score (matchup × power profile)</div>
</div>

<div class="legend">
  <div class="legend-item">
    <div class="legend-stripe" style="background:#D4A017"></div>
    <span class="legend-label">Prime Outlier</span><span>weighted ≥ 50</span>
  </div>
  <div class="legend-item">
    <div class="legend-stripe" style="background:#2563EB"></div>
    <span class="legend-label">Strong Value</span><span>weighted ≥ 43</span>
  </div>
  <div class="legend-item">
    <div class="legend-stripe" style="background:#1A2A3E"></div>
    <span class="legend-label">Solid</span>
  </div>
</div>

<div class="board">
{rows_html}
</div>

</body>
</html>"""

out = '/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad/hr_props_board_20260801.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)
print(f"Written {len(HTML):,} bytes → {out}")
# Quick spot check
import re
rows = re.findall(r'class="pname">(.*?)<', HTML)
probs= re.findall(r'class="prob-pct">(.*?)<', HTML)
for name, prob in zip(rows, probs):
    print(f"  {name:<24} {prob}")
