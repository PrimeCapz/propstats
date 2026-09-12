#!/usr/bin/env python3
"""
Generate today's matchup card HTML.
Usage:
    python3 gen_matchup_card.py [YYYY-MM-DD]
Output:
    matchups_YYYYMMDD.html  (in current directory)
"""
import json, sys, os
from collections import defaultdict
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'propstats', 'backend'))

from baseball_engine import get_today_games
from hitter_fantasy_engine import build_hitter_fantasy_board
from hr_engine import build_hr_attack_board

GAME_DATE = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime('%Y-%m-%d')

print(f"Building matchup card for {GAME_DATE}…")
fantasy  = build_hitter_fantasy_board(GAME_DATE)
hr_board = build_hr_attack_board(GAME_DATE)

# HR probability lookup
hr_lookup = {}
for ge in hr_board:
    for b in ge.get('top_batters', []):
        bid = str(b.get('batter_id', ''))
        if bid:
            hr_lookup[bid] = {
                'hr_prob':       b.get('hr_prob', 0),
                'matchup_score': b.get('matchup_score', 0),
            }

for b in fantasy:
    mg = b['matchup']['grade']
    fs = b['fantasy_score']
    b['composite'] = round(fs * 0.40 + mg * 0.60, 1)
    b['hr_data']   = hr_lookup.get(str(b['batter_id']), {})

games_data    = defaultdict(lambda: defaultdict(list))
pitcher_names = {}

for b in fantasy:
    g, t = b['game_str'], b['team']
    games_data[g][t].append(b)
    if g not in pitcher_names:
        pitcher_names[g] = {}
    pitcher_names[g][b['opp']] = b['pitcher_name']

for game in games_data:
    for team in games_data[game]:
        games_data[game][team].sort(key=lambda x: x['composite'], reverse=True)

# ── Identity ──────────────────────────────────────────────────────────────────
TEAMS = {
    'NYY':{'bg':'#003087','name':'YANKEES'},  'CHC':{'bg':'#0E3386','name':'CUBS'},
    'PIT':{'bg':'#27251F','name':'PIRATES'},  'CIN':{'bg':'#C6011F','name':'REDS'},
    'PHI':{'bg':'#E81828','name':'PHILLIES'}, 'BAL':{'bg':'#DF4601','name':'ORIOLES'},
    'STL':{'bg':'#C41E3A','name':'CARDINALS'},'TOR':{'bg':'#134A8E','name':'BLUE JAYS'},
    'AZ' :{'bg':'#A71930','name':'D-BACKS'},  'CLE':{'bg':'#00385D','name':'GUARDIANS'},
    'CWS':{'bg':'#27251F','name':'WHITE SOX'},'TB' :{'bg':'#092C5C','name':'RAYS'},
    'MIA':{'bg':'#007BB0','name':'MARLINS'},  'NYM':{'bg':'#002D72','name':'METS'},
    'WSH':{'bg':'#AB0003','name':'NATIONALS'},'ATL':{'bg':'#CE1141','name':'BRAVES'},
    'TEX':{'bg':'#003278','name':'RANGERS'},  'HOU':{'bg':'#002D62','name':'ASTROS'},
    'KC' :{'bg':'#004687','name':'ROYALS'},   'COL':{'bg':'#333366','name':'ROCKIES'},
    'LAA':{'bg':'#BA0021','name':'ANGELS'},   'MIL':{'bg':'#12284B','name':'BREWERS'},
    'DET':{'bg':'#0C2340','name':'TIGERS'},   'ATH':{'bg':'#003831','name':'ATHLETICS'},
    'BOS':{'bg':'#BD3039','name':'RED SOX'},  'LAD':{'bg':'#005A9C','name':'DODGERS'},
    'MIN':{'bg':'#002B5C','name':'TWINS'},    'SEA':{'bg':'#0C2C56','name':'MARINERS'},
    'SF' :{'bg':'#27251F','name':'GIANTS'},   'SD' :{'bg':'#2F241D','name':'PADRES'},
}
TIER = {
    'S':{'bg':'#C8920A','text':'#fff'},
    'A':{'bg':'#2457CC','text':'#fff'},
    'B':{'bg':'#06956A','text':'#fff'},
    'C':{'bg':'#5C7080','text':'#fff'},
}

def tier_for(c):
    if c >= 68: return 'S'
    if c >= 54: return 'A'
    if c >= 42: return 'B'
    return 'C'

def get_note(b):
    form  = b.get('form', '')
    tags  = ' '.join(b.get('tags', []))
    hr    = b['hr_data'].get('hr_prob', 0)
    arsen = b.get('arsenal', {})
    edges = [e.split('(')[0] for e in arsen.get('top_edges', [])[:2]]
    has_e = bool(edges)
    c     = b['composite']

    if   c >= 72:                    return 'Best Play Today'
    elif form == 'FIRE':             return 'On Absolute Fire'
    elif form == 'HOT' and hr >= 25: return 'Hot Hand + Big HR Upside'
    elif form == 'HOT' and has_e:    return 'Hot Streak + Pitch Edge'
    elif form == 'HOT':              return 'Hot Right Now'
    elif form == 'DUE' and hr >= 22: return 'Due For A Big One'
    elif form == 'DUE':              return 'Due Up'
    elif c >= 65 and hr >= 20:       return 'Prime Matchup + HR'
    elif c >= 65:                    return 'Prime Matchup'
    elif has_e and hr >= 20:         return 'Pitch Edge + HR Upside'
    elif has_e:                      return 'Good Pitch Edge'
    elif hr >= 26:                   return 'Real HR Upside'
    elif hr >= 18:                   return 'HR Threat'
    elif 'BARREL MACHINE' in tags:  return 'Barrel Machine'
    elif 'POWER + CONTACT' in tags: return 'Power Profile'
    else:                            return 'Contact Play'

def esc(s): return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
def last(n): parts = n.split(); return parts[-1] if parts else n

def player_html(b):
    t   = tier_for(b['composite'])
    td  = TIER[t]
    hr  = b['hr_data'].get('hr_prob', 0)
    xw  = b['proj'].get('xwoba', 0)
    pos = b.get('pos', '')
    return f'''\
<div class="player-row">
  <div class="tier-mark" style="background:{td["bg"]};color:{td["text"]}">{t}</div>
  <div class="player-body">
    <div class="player-name-line">
      <span class="pname">{esc(b["name"])}</span><span class="ppos"> {pos}</span>
    </div>
    <div class="player-note">{esc(get_note(b))}</div>
  </div>
  <div class="player-pills">
    {"".join([
      f'<span class="pill pill-hr">{hr:.0f}% HR</span>' if hr >= 15 else '',
      f'<span class="pill pill-xw">xwOBA {xw:.3f}</span>' if xw >= 0.370 else '',
      f'<span class="pill pill-score">{int(b["composite"])}</span>',
    ])}
  </div>
</div>'''

def card_html(game):
    away, home = game.split('@')
    at  = TEAMS.get(away, {'bg':'#222'})
    ht  = TEAMS.get(home, {'bg':'#222'})
    gp  = pitcher_names.get(game, {})
    ap  = gp.get(away, '—')
    hp  = gp.get(home, '—')
    venue = ''
    for t in [away, home]:
        for b in games_data[game].get(t, []):
            venue = b.get('venue', ''); break
        if venue: break

    away_rows = ''.join(player_html(p) for p in games_data[game].get(away, [])[:3])
    home_rows = ''.join(player_html(p) for p in games_data[game].get(home, [])[:3])
    venue_line = f'<div class="card-venue">{esc(venue)}</div>' if venue else ''

    return f'''\
<div class="game-card">
  <div class="card-header">
    <div class="team-half" style="background:{at["bg"]}">
      <div class="team-abbr">{away}</div>
      <div class="team-pitcher">SP: {esc(last(ap))}</div>
    </div>
    <div class="team-half" style="background:{ht["bg"]}">
      <div class="team-abbr">{home}</div>
      <div class="team-pitcher">SP: {esc(last(hp))}</div>
    </div>
    <div class="at-bubble">@</div>
  </div>
  <div class="card-body">
    <div class="team-col">{away_rows}</div>
    <div class="col-div"></div>
    <div class="team-col">{home_rows}</div>
  </div>
  {venue_line}
</div>'''

# ── Sort games by interest (best composite first) ─────────────────────────────
def game_interest(game):
    best = 0
    for t in games_data[game]:
        for b in games_data[game][t][:1]:
            best = max(best, b['composite'])
    return best

ordered_games = sorted(games_data.keys(), key=game_interest, reverse=True)
cards = '\n'.join(card_html(g) for g in ordered_games)

date_display = datetime.strptime(GAME_DATE, '%Y-%m-%d').strftime('%B %-d, %Y')

CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#EEF1F6;--card:#FFF;--body-area:#F7F9FC;
  --txt:#0C1520;--txt2:#3A5068;--txt3:#7A90A6;
  --border:#D8E2EC;--score-bg:#0C1520;--score-txt:#FFF;--div:#D8E2EC;
}
@media(prefers-color-scheme:dark){:root{
  --bg:#07101C;--card:#0D1829;--body-area:#0B1524;
  --txt:#E0EAF5;--txt2:#7A9AB8;--txt3:#445A70;
  --border:#1A2E48;--score-bg:#E0EAF5;--score-txt:#07101C;--div:#1A2E48;
}}
:root[data-theme="dark"]{--bg:#07101C;--card:#0D1829;--body-area:#0B1524;--txt:#E0EAF5;--txt2:#7A9AB8;--txt3:#445A70;--border:#1A2E48;--score-bg:#E0EAF5;--score-txt:#07101C;--div:#1A2E48}
:root[data-theme="light"]{--bg:#EEF1F6;--card:#FFF;--body-area:#F7F9FC;--txt:#0C1520;--txt2:#3A5068;--txt3:#7A90A6;--border:#D8E2EC;--score-bg:#0C1520;--score-txt:#FFF;--div:#D8E2EC}
body{background:var(--bg);font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:var(--txt);-webkit-font-smoothing:antialiased}
.page-header{background:#07101C;color:#E0EAF5;text-align:center;padding:32px 16px 22px;border-bottom:3px solid #C8920A}
.page-eyebrow{font-family:"Arial Narrow","Helvetica Neue",Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:.18em;text-transform:uppercase;color:#C8920A;margin-bottom:6px}
.page-title{font-family:"Arial Narrow","Helvetica Neue",Arial,sans-serif;font-size:clamp(30px,7vw,56px);font-weight:900;letter-spacing:.05em;text-transform:uppercase;line-height:1}
.page-date{margin-top:6px;font-size:clamp(13px,2.5vw,17px);font-weight:500;color:#7A9AB8;letter-spacing:.04em}
.legend{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;gap:6px 16px;padding:11px 16px;background:#07101C;border-bottom:1px solid #1A2E48}
.legend-label{font-size:10px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#445A70}
.legend-item{display:flex;align-items:center;gap:5px;font-family:"SF Mono",Consolas,monospace;font-size:10px;color:#7A9AB8}
.lbadge{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:3px;font-weight:900;font-size:10px;font-family:"Arial Narrow",Arial,sans-serif}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:12px;padding:14px;max-width:1380px;margin:0 auto}
.game-card{background:var(--card);border-radius:8px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.10);border:1px solid var(--border);display:flex;flex-direction:column}
.card-header{display:grid;grid-template-columns:1fr 1fr;height:62px;position:relative;flex-shrink:0}
.team-half{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:6px 10px;gap:2px}
.team-abbr{font-family:"Arial Narrow","Helvetica Neue",Arial,sans-serif;font-size:22px;font-weight:900;color:#fff;letter-spacing:.04em;line-height:1;text-shadow:0 1px 3px rgba(0,0,0,.35)}
.team-pitcher{font-size:9px;font-weight:600;color:rgba(255,255,255,.65);letter-spacing:.04em;text-transform:uppercase;white-space:nowrap}
.at-bubble{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:22px;height:22px;background:#fff;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:900;color:#07101C;z-index:2;box-shadow:0 1px 6px rgba(0,0,0,.30)}
.card-body{display:flex;flex:1;background:var(--body-area)}
.team-col{flex:1;padding:10px 9px;display:flex;flex-direction:column;gap:8px;min-width:0}
.col-div{width:1px;background:var(--div);margin:8px 0;flex-shrink:0}
.player-row{display:flex;align-items:flex-start;gap:6px}
.tier-mark{width:17px;height:17px;border-radius:3px;display:flex;align-items:center;justify-content:center;font-family:"Arial Narrow","Helvetica Neue",Arial,sans-serif;font-size:11px;font-weight:900;flex-shrink:0;margin-top:1px}
.player-body{flex:1;min-width:0;display:flex;flex-direction:column;gap:2px}
.player-name-line{display:flex;align-items:baseline;gap:3px;flex-wrap:wrap}
.pname{font-size:12px;font-weight:700;color:var(--txt);line-height:1.2}
.ppos{font-size:10px;font-weight:500;color:var(--txt3)}
.player-note{font-size:10px;color:var(--txt2);line-height:1.35}
.player-pills{display:flex;flex-direction:column;align-items:flex-end;gap:3px;flex-shrink:0}
.pill{font-family:"SF Mono",Consolas,monospace;font-size:9px;font-weight:700;padding:2px 5px;border-radius:3px;white-space:nowrap;font-variant-numeric:tabular-nums}
.pill-score{background:var(--score-bg);color:var(--score-txt)}
.pill-hr{background:#C0282B;color:#fff}
.pill-xw{background:#1A3A8A;color:#C8D8F0}
.card-venue{font-size:9px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--txt3);text-align:center;padding:5px 8px;background:var(--card);border-top:1px solid var(--border)}
@media(max-width:480px){.grid{grid-template-columns:1fr;padding:10px;gap:10px}.pname{font-size:11px}.player-note{font-size:9.5px}}
"""

HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Today's Matchups — {date_display}</title>
<style>{CSS}</style>
</head>
<body>
<header class="page-header">
  <div class="page-eyebrow">PropStats Daily</div>
  <div class="page-title">Today's Matchups</div>
  <div class="page-date">{date_display}</div>
</header>
<div class="legend">
  <span class="legend-label">Tiers</span>
  <span class="legend-item"><span class="lbadge" style="background:#C8920A;color:#fff">S</span>Elite 68+</span>
  <span class="legend-item"><span class="lbadge" style="background:#2457CC;color:#fff">A</span>Plus 54–67</span>
  <span class="legend-item"><span class="lbadge" style="background:#06956A;color:#fff">B</span>Solid 42–53</span>
  <span class="legend-item"><span class="lbadge" style="background:#5C7080;color:#fff">C</span>Watch &lt;42</span>
  <span class="legend-label" style="margin-left:10px">Pills</span>
  <span class="legend-item"><span class="pill pill-hr" style="font-size:9px">HR%</span>HR prob</span>
  <span class="legend-item"><span class="pill pill-xw" style="font-size:9px">xwOBA</span>≥.370</span>
  <span class="legend-item"><span class="pill pill-score" style="font-size:9px">85</span>Composite</span>
</div>
<div class="grid">
{cards}
</div>
</body>
</html>"""

slug = GAME_DATE.replace('-', '')
out  = f'matchups_{slug}.html'
with open(out, 'w', encoding='utf-8') as f:
    f.write(HTML)

print(f"Done → {out}  ({len(HTML):,} bytes, {len(ordered_games)} games)")
