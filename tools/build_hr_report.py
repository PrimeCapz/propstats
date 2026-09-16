#!/usr/bin/env python3
"""Print-ready HR + H2H report for the 2026-09-15 slate."""
import json, html

SP   = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"
DATE = "2026-09-15"
DS   = "20260915"
OUT  = f"{SP}/hr_report_{DS}.html"

hr = json.load(open(f"{SP}/hr_board_{DS}.json"))

def esc(s): return html.escape(str(s))

CK_LABEL = {"HEAVY CHALK": ("chalk-heavy", "HEAVY CHALK"), "CHALKY": ("chalk-mid", "CHALKY"),
            "BALANCED": ("chalk-bal", "BALANCED"), "LEVERAGE": ("chalk-lev", "LEVERAGE")}

def ck_pill(b):
    t = b.get("chalk_tier")
    if not t or t == "OUT":
        return ""
    cls, lbl = CK_LABEL.get(t, ("chalk-bal", t))
    return f'<span class="pill {cls}">{lbl}</span>'

def vuln_pill(v):
    cls = "v-attack" if v["tier"] == "Attackable" else "v-avoid" if v["tier"] == "Avoid" else "v-neutral"
    return f'<span class="pill {cls}">{v["tier"]} {v["score"]:.0f}</span>'

def form_bits(b):
    s = b.get("statcast", {}).get("L10", {})
    if not s:
        return '<span class="dim">no recent Statcast</span>'
    out = [f'{s["hr"]} HR', f'{s["near_hr"]} near']
    if s.get("max_ev"): out.append(f'{s["max_ev"]:.1f} max EV')
    if s.get("brl_pct"): out.append(f'{s["brl_pct"]:.0f}% brl')
    return " · ".join(out)

def ctx_line(b):
    """This hitter's season line in the three conditions that apply tonight."""
    sp = b.get("ctx_splits") or {}
    if not sp:
        return ""
    throws_lhp = "hand" in sp and sp["hand"].get("code") == "vl"
    names = {"hand": "vs LHP" if throws_lhp else "vs RHP",
             "time": ("day" if b.get("ctx_daynight") == "day" else "night") + " games",
             "site": "at home" if b.get("ctx_home") else "on the road"}
    bits = []
    for key in ("hand", "time", "site"):
        v = sp.get(key)
        if not v:
            continue
        cls = ""
        if not v["thin"] and abs(v["edge"]) >= 0.060:
            cls = ' class="ctx-up"' if v["edge"] > 0 else ' class="ctx-down"'
        thin = ' <span class="dim">thin</span>' if v["thin"] else ""
        bits.append(f'<span{cls}>{names[key]} <b>{v["ops"]:.3f}</b> OPS '
                    f'<span class="dim">({v["edge"]:+.3f} · {v["pa"]} PA · {v["hr"]} HR)</span>{thin}</span>')
    if not bits:
        return ""
    return f'<div class="bat-ctx"><span class="lbl">Tonight\'s context</span> {" · ".join(bits)}</div>'


def signal_tags(b):
    keep = [t for t in b.get("tags", [])
            if any(k in t for k in ("FIRE", "HOT", "HARD LUCK", "EV SURGE", "DUE", "OWNS", "DOMINATED"))]
    return "".join(f'<span class="tag">{esc(t)}</span>' for t in keep[:3])

# ── split table for a pitcher ────────────────────────────────────────────────
def split_rows(r):
    hp = r.get("hand_profile") or {}
    rows = ""
    for side in ("L", "R"):
        a = hp.get(side, {}).get("all", {})
        if not a or a.get("pa", 0) < 15:
            continue
        mix = ", ".join(f'{pt} {u["usage"]:.0f}%' for pt, u in list(a["usage"].items())[:4])
        hot = ' class="split-hot"' if (a["slg"] >= 0.450 or a["hr"] >= 3) else ""
        rows += (f'<tr{hot}><td>vs {side}HB</td><td>{a["pa"]}</td><td>{a["woba"]:.3f}</td>'
                 f'<td>{a["slg"]:.3f}</td><td>{a["hr"]}</td><td>{a["brl_pct"]:.1f}%</td>'
                 f'<td>{a["k_pct"]:.1f}%</td><td class="mix">{esc(mix)}</td></tr>')
    if not rows:
        return '<p class="dim small">No recent pitch-level sample for this starter.</p>'
    return (f'<table class="split"><thead><tr><th>Split</th><th>PA</th><th>wOBA</th><th>SLG</th>'
            f'<th>HR</th><th>Barrel</th><th>K%</th><th>Recent pitch mix</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')

def batter_rows(r):
    out, n = "", 0
    for b in sorted(r["top_batters"], key=lambda x: -x["matchup_score"]):
        if b.get("in_lineup") is False:
            continue
        n += 1
        if n > 3:
            break
        h2 = b.get("h2h") or {}
        h2s = (f'<span class="h2h-inline">H2H {h2["hr"]} HR / {h2["pa"]} PA · {h2.get("avg",0):.3f}</span>'
               if h2.get("pa", 0) >= 5 else "")
        edges = ", ".join(e["label"] for e in b.get("hr_edges", [])[:2]) or "—"
        out += f'''<div class="bat">
  <div class="bat-head">
    <span class="rank">{n}</span>
    <span class="bat-nm">{esc(b["batter_name"])}</span><span class="hand">{b["bats"]}</span>
    {ck_pill(b)}
    <span class="odds">{b["hr_prob"]:.1f}% <em>{esc(b.get("implied_odds",""))}</em></span>
  </div>
  <div class="bat-meta">zone {b["hr_zone_score"]:.0f} · park {b.get("park_hr_factor",1):.2f} · L10 {form_bits(b)} {h2s}</div>
  <div class="bat-edge"><span class="lbl">Pitch edges</span> {esc(edges)}</div>
  {ctx_line(b)}
  <div class="tags">{signal_tags(b)}</div>
</div>'''
    return out

games = {}
for r in hr:
    games.setdefault(r["game"], []).append(r)

# ── H2H ──────────────────────────────────────────────────────────────────────
h2h_rows = []
for r in hr:
    for b in r["top_batters"]:
        h = b.get("h2h") or {}
        if h.get("hr", 0) >= 1:
            h2h_rows.append((h["hr"], h["hr"] / h["pa"] * 100, b, r, h))
h2h_rows.sort(key=lambda x: (-x[0], -x[1]))

h2h_html = ""
for i, (nhr, rate, b, r, h) in enumerate(h2h_rows, 1):
    hi = ' class="h2h-top"' if i <= 10 else ""
    h2h_html += (f'<tr{hi}><td class="num">{i}</td><td><b>{esc(b["batter_name"])}</b> <span class="hand">{b["bats"]}</span></td>'
                 f'<td>{esc(r["pitcher_name"])}</td><td class="dim">{esc(r["game"])}</td>'
                 f'<td class="num strong">{nhr}</td><td class="num">{h["pa"]}</td><td class="num">{rate:.1f}%</td>'
                 f'<td class="num">{h.get("avg",0):.3f}</td><td class="num">{h.get("slg",0) or 0:.3f}</td>'
                 f'<td class="num">{h.get("ops",0) or 0:.3f}</td><td class="num">{h.get("k_pct",0) or 0:.0f}%</td>'
                 f'<td class="num">{b["hr_prob"]:.1f}%</td><td class="num">{esc(b.get("implied_odds",""))}</td>'
                 f'<td>{ck_pill(b)}</td></tr>')

n_h2h_any = sum(1 for r in hr for b in r["top_batters"] if (b.get("h2h") or {}).get("pa", 0) > 0)
attackable = [r for r in hr if r["vuln"]["tier"] == "Attackable"]

# ── Leaderboards + master table ───────────────────────────────────────────────
# A printed page cannot be re-sorted, so every sort worth having is pre-rendered:
# one leaderboard per metric, then one master table carrying every column.
pool, _seen = [], set()
for r in hr:
    for b in r["top_batters"]:
        if b.get("in_lineup") is False or b["batter_id"] in _seen:
            continue
        _seen.add(b["batter_id"])
        sc = b.get("statcast") or {}
        w10, w5 = sc.get("L10") or {}, sc.get("L5") or {}
        fd = b.get("form_delta") or {}
        h2 = b.get("h2h") or {}
        pool.append({
            "nm": b["batter_name"], "bats": b.get("bats", ""), "order": b.get("order"),
            "game": r["game"], "pit": r["pitcher_name"], "vuln": r["vuln"]["score"],
            "prob": b.get("hr_prob") or 0, "odds": b.get("implied_odds", ""),
            "tier": b.get("chalk_tier") or "", "zone": b.get("hr_zone_score") or 0,
            "parkfit": b.get("park_fit") or 0, "park": b.get("park_hr_factor") or 1,
            "brl": b.get("brl_bip") or 0, "hh": b.get("hh_pct") or 0,
            "iso": b.get("xiso") or 0, "xwoba": b.get("xwoba") or 0,
            "hrfb": b.get("hr_fb_pct") or 0, "la": b.get("la_avg") or 0,
            "ev": b.get("exit_velo") or 0,
            "ev10": w10.get("avg_ev") or 0, "maxev": w5.get("max_ev") or 0,
            "brl10": w10.get("brl_pct") or 0, "hr10": w10.get("hr"), "near": w10.get("near_hr"),
            "dev": fd.get("ev"), "dbrl": fd.get("brl_pct_rel"),
            "h2hpa": h2.get("pa") or 0, "h2hhr": h2.get("hr") or 0, "h2hops": h2.get("ops") or 0,
        })

LEADERBOARDS = [
    ("prob",    "Calibrated HR probability", "{:.1f}%", "the model's bottom line"),
    ("zone",    "Zone fit",                  "{:.0f}",  "how well he hits this pitcher's actual mix"),
    ("brl",     "Barrel rate, season",       "{:.1f}%", "fitted peak is the 11-14% band"),
    ("parkfit", "Park fit",                  "{:.0f}",  "strongest single feature in the model"),
    ("hrfb",    "HR per fly ball",           "{:.1f}%", "under 10% grades at 0.56x"),
    ("maxev",   "Max exit velo, last 5",     "{:.1f}",  "top-end power right now"),
    ("ev10",    "Average exit velo, last 10","{:.1f}",  "92+ grades at 1.61x"),
    ("near",    "Near-misses, last 10",      "{:.0f}",  "98+ mph, 20-35 deg, 360+ ft, not a HR"),
    ("hr10",    "Home runs, last 10",        "{:.0f}",  "current form"),
    ("dev",     "Exit velo vs own baseline", "{:+.1f}", "who is heating up"),
    ("iso",     "Expected ISO, season",      "{:.3f}",  "raw power"),
    ("h2hops",  "OPS vs tonight's starter",  "{:.3f}",  "8+ plate appearances only"),
]

def _lb(key, title, fmt, note, n=12):
    rows = [x for x in pool if x.get(key) is not None]
    if key == "h2hops":
        rows = [x for x in rows if x["h2hpa"] >= 8]
    rows = sorted(rows, key=lambda x: -(x[key] or 0))[:n]
    if not rows:
        return ""
    body = "".join(
        f'<tr><td class="num dim">{i}</td><td>{esc(x["nm"])}<span class="hand">{x["bats"]}</span></td>'
        f'<td class="dim">{esc(x["game"])}</td><td class="num strong">{fmt.format(x[key])}</td>'
        f'<td class="num">{x["prob"]:.1f}%</td></tr>'
        for i, x in enumerate(rows, 1))
    return (f'<div class="lb"><div class="lb-h">{title}</div><div class="lb-n">{note}</div>'
            f'<table class="lbt"><tbody>{body}</tbody></table></div>')

lb_html = "".join(_lb(k, t, f, n) for k, t, f, n in LEADERBOARDS)

# Context splits: who tonight's conditions help, and who they hurt
ctx_pool = []
for r in hr:
    for b in r["top_batters"]:
        if b.get("in_lineup") is False:
            continue
        for key, v in (b.get("ctx_splits") or {}).items():
            if v["thin"] or abs(v["edge"]) < 0.060:
                continue
            throws_lhp = (b.get("ctx_splits", {}).get("hand", {}) or {}).get("code") == "vl"
            label = {"hand": "vs LHP" if throws_lhp else "vs RHP",
                     "time": ("day" if b.get("ctx_daynight") == "day" else "night"),
                     "site": "home" if b.get("ctx_home") else "road"}[key]
            ctx_pool.append({"nm": b["batter_name"], "game": r["game"], "label": label,
                             "ops": v["ops"], "edge": v["edge"], "pa": v["pa"],
                             "prob": b.get("hr_prob") or 0})

def _ctx_tbl(rows, title, note):
    if not rows:
        return ""
    body = "".join(
        f'<tr><td class="num dim">{i}</td><td>{esc(x["nm"])}</td><td class="dim">{esc(x["game"])}</td>'
        f'<td class="dim">{esc(x["label"])}</td><td class="num strong">{x["ops"]:.3f}</td>'
        f'<td class="num">{x["edge"]:+.3f}</td><td class="num">{x["prob"]:.1f}%</td></tr>'
        for i, x in enumerate(rows[:14], 1))
    return (f'<div class="lb" style="grid-column:span 3"><div class="lb-h">{title}</div>'
            f'<div class="lb-n">{note}</div><table class="lbt"><tbody>{body}</tbody></table></div>')

ctx_html = (_ctx_tbl(sorted(ctx_pool, key=lambda x: -x["edge"]),
                     "Conditions in his favour tonight",
                     "season OPS in this exact context, against his own overall line — 40+ PA only")
            + _ctx_tbl(sorted(ctx_pool, key=lambda x: x["edge"]),
                       "Conditions against him tonight",
                       "same measure, the other direction — a reason to downgrade an otherwise good spot"))

MASTER = [("nm","Batter"),("bats","B"),("order","#"),("game","Game"),("pit","Pitcher"),
          ("prob","HR%"),("odds","Fair"),("zone","Zone"),("parkfit","PkFit"),("park","Park"),
          ("brl","Brl%"),("hh","HH%"),("iso","xISO"),("hrfb","HR/FB"),("la","LA"),
          ("ev10","EV10"),("maxev","MaxEV"),("dev","dEV"),("hr10","HR"),("near","Near"),
          ("h2hhr","H2H")]
def _cell(x, k):
    v = x.get(k)
    if v is None or v == "":
        return '<td class="num dim">·</td>'
    if k == "nm":
        return f'<td><b>{esc(v)}</b></td>'
    if k in ("bats", "game", "pit", "odds"):
        return f'<td>{esc(v)}</td>'
    if k == "order":
        return f'<td class="num">{v}</td>'
    if k in ("iso",):
        return f'<td class="num">{v:.3f}</td>'
    if k in ("park",):
        return f'<td class="num">{v:.2f}</td>'
    if k in ("prob", "brl", "hh", "hrfb", "la", "ev10", "maxev"):
        return f'<td class="num">{v:.1f}</td>'
    if k == "dev":
        cls = "up" if v > 0 else ("down" if v < 0 else "")
        return f'<td class="num {cls}">{v:+.1f}</td>'
    return f'<td class="num">{v:.0f}</td>' if isinstance(v, float) else f'<td class="num">{v}</td>'

master_rows = "".join(
    "<tr>" + "".join(_cell(x, k) for k, _ in MASTER) + "</tr>"
    for x in sorted(pool, key=lambda y: -y["prob"]))
master_head = "".join(f"<th>{h}</th>" for _, h in MASTER)

game_html = ""
for game in sorted(games):
    game_html += f'<section class="game"><h3>{esc(game)}</h3>'
    for r in games[game]:
        w = r.get("weather", {})
        wx = " · ".join(x for x in [w.get("tag", ""), f'{w.get("temp_f",0):.0f}°F' if w.get("temp_f") else ""] if x)
        game_html += f'''<div class="side">
  <div class="side-head">
    <span class="team">{esc(r["opp_team"])}</span> <span class="dim">batting vs</span>
    <span class="pitcher">{esc(r["pitcher_name"])}</span> <span class="hand">{r["pitcher_throws"]}</span>
    {vuln_pill(r["vuln"])}
    <span class="venue">{esc(r["venue"])}{" · " + esc(wx) if wx else ""}</span>
  </div>
  {split_rows(r)}
  {batter_rows(r)}
</div>'''
    game_html += '</section>'

doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Home Run Report — September 15, 2026</title>
<style>
@page {{ size: Letter; margin: 14mm 12mm; }}
* {{ box-sizing: border-box; }}
body {{
  margin:0; background:#fff; color:#14181f;
  font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 9.5pt; line-height: 1.45;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}}
h1,h2,h3 {{ margin:0; text-wrap:balance; }}
.num, .odds, .split td, .h2h td.num {{ font-variant-numeric: tabular-nums; }}

/* masthead */
.mast {{ border-bottom:3px solid #14181f; padding-bottom:10px; margin-bottom:14px; display:flex; align-items:flex-end; gap:14px; }}
.mast h1 {{ font-size:23pt; letter-spacing:-.6px; font-weight:800; }}
.mast .sub {{ font-size:9pt; color:#5b6472; margin-left:auto; text-align:right; line-height:1.35; }}
.mast .kicker {{ font-size:8pt; letter-spacing:1.6px; text-transform:uppercase; color:#b03a2e; font-weight:700; }}

h2 {{ font-size:12.5pt; letter-spacing:-.2px; margin:16px 0 7px; padding-bottom:4px; border-bottom:1.5px solid #14181f; }}
h3 {{ font-size:11pt; letter-spacing:.4px; margin:0 0 6px; color:#b03a2e; font-weight:800; }}
p {{ margin:0 0 7px; }}
.dim {{ color:#6b7381; }}
.small {{ font-size:8.4pt; }}

/* legend */
.legend {{ display:grid; grid-template-columns:repeat(2,1fr); gap:5px 16px; background:#f5f6f8; border:1px solid #dfe3e9; border-radius:5px; padding:9px 12px; font-size:8.4pt; margin-bottom:12px; }}
.legend b {{ color:#14181f; }}

/* key spots */
.spots {{ display:grid; grid-template-columns:repeat(2,1fr); gap:9px; margin-bottom:6px; }}
.spot {{ border:1px solid #dfe3e9; border-left:3px solid #b03a2e; border-radius:4px; padding:8px 11px; }}
.spot .t {{ font-weight:800; font-size:9.6pt; margin-bottom:2px; }}
.spot .w {{ font-size:8.4pt; color:#41485a; }}

/* pills */
.pill {{ font-size:7.2pt; font-weight:800; letter-spacing:.5px; padding:1.5px 6px; border-radius:9px; white-space:nowrap; border:1px solid; }}
.v-attack {{ background:#fdecea; color:#a32b1c; border-color:#e8a79d; }}
.v-neutral{{ background:#f3f4f6; color:#4b5563; border-color:#d5d9df; }}
.v-avoid  {{ background:#eef2fb; color:#3d5a9e; border-color:#bcc9e4; }}
.chalk-heavy{{ background:#fdecec; color:#b3261e; border-color:#eaa9a4; }}
.chalk-mid  {{ background:#fdf3e2; color:#95661a; border-color:#e8cf9f; }}
.chalk-bal  {{ background:#f3f4f6; color:#5b6472; border-color:#d5d9df; }}
.chalk-lev  {{ background:#e6f6ee; color:#1a7a4e; border-color:#a5dcc1; }}

/* game blocks */
.game {{ break-inside:avoid; margin-bottom:13px; }}
.side {{ break-inside:avoid; border:1px solid #e3e6eb; border-radius:5px; padding:8px 10px; margin-bottom:7px; }}
.side-head {{ display:flex; align-items:center; flex-wrap:wrap; gap:6px; margin-bottom:6px; }}
.team {{ font-weight:800; font-size:10.5pt; }}
.pitcher {{ font-weight:700; }}
.hand {{ font-size:7.6pt; color:#6b7381; border:1px solid #d5d9df; border-radius:3px; padding:0 3px; }}
.venue {{ margin-left:auto; font-size:8pt; color:#6b7381; }}

table.split {{ width:100%; border-collapse:collapse; font-size:8.2pt; margin-bottom:7px; }}
table.split th {{ text-align:left; font-weight:700; color:#5b6472; border-bottom:1px solid #dfe3e9; padding:2px 5px; }}
table.split td {{ padding:2px 5px; border-bottom:1px solid #f0f2f5; }}
table.split .mix {{ color:#6b7381; }}
tr.split-hot td {{ background:#fdf1ef; font-weight:600; }}

.bat {{ padding:5px 0 5px 8px; border-left:2px solid #e3e6eb; margin-bottom:4px; }}
.bat-head {{ display:flex; align-items:center; gap:6px; flex-wrap:wrap; }}
.rank {{ width:14px; height:14px; border-radius:50%; background:#14181f; color:#fff; font-size:7.4pt; font-weight:800; display:inline-flex; align-items:center; justify-content:center; }}
.bat-nm {{ font-weight:800; font-size:10pt; }}
.odds {{ margin-left:auto; font-weight:800; font-size:9.6pt; }}
.odds em {{ font-style:normal; color:#6b7381; font-weight:600; font-size:8.4pt; }}
.bat-meta, .bat-edge {{ font-size:8.2pt; color:#41485a; }}
.bat-edge .lbl {{ color:#6b7381; }}
.bat-ctx {{ font-size:8pt; color:#41485a; }}
.bat-ctx .lbl {{ color:#6b7381; }}
.ctx-up {{ color:#1a7a4e; font-weight:600; }}
.ctx-down {{ color:#b3261e; font-weight:600; }}
.h2h-inline {{ background:#fdf3e2; border:1px solid #e8cf9f; border-radius:3px; padding:0 4px; font-weight:700; color:#95661a; }}
.tags {{ margin-top:2px; }}
.tag {{ display:inline-block; font-size:7.4pt; background:#f3f4f6; border:1px solid #dfe3e9; border-radius:3px; padding:0 4px; margin-right:3px; color:#41485a; }}

/* h2h */
table.h2h {{ width:100%; border-collapse:collapse; font-size:8.2pt; }}
table.h2h th {{ text-align:left; background:#14181f; color:#fff; font-weight:700; padding:4px 5px; font-size:7.6pt; letter-spacing:.3px; }}
table.h2h td {{ padding:3px 5px; border-bottom:1px solid #eceef2; }}
table.h2h td.num {{ text-align:right; }}
table.h2h td.strong {{ font-weight:800; }}
tr.h2h-top td {{ background:#fbfcfd; }}
tr.h2h-top td.strong {{ color:#b3261e; }}
.pagebreak {{ break-before:page; }}
.lb-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px 12px; }}
.lb {{ break-inside:avoid; border:1px solid #e3e6eb; border-radius:4px; padding:6px 8px; }}
.lb-h {{ font-weight:800; font-size:9pt; letter-spacing:-.1px; }}
.lb-n {{ font-size:7.4pt; color:#6b7381; margin-bottom:3px; }}
table.lbt {{ width:100%; border-collapse:collapse; font-size:7.8pt; }}
table.lbt td {{ padding:1.5px 3px; border-bottom:1px solid #f2f4f7; }}
table.lbt td.num {{ text-align:right; }}
table.lbt td.strong {{ font-weight:800; }}
.tbl-wide {{ overflow-x:auto; }}
table.master {{ width:100%; border-collapse:collapse; font-size:7.2pt; }}
table.master th {{ background:#14181f; color:#fff; font-weight:700; padding:3px 3px; text-align:right;
  font-size:6.8pt; letter-spacing:.2px; position:sticky; top:0; }}
table.master th:nth-child(-n+5) {{ text-align:left; }}
table.master td {{ padding:2px 3px; border-bottom:1px solid #eef0f4; text-align:right; white-space:nowrap; }}
table.master td:nth-child(-n+5) {{ text-align:left; }}
table.master tr:nth-child(even) td {{ background:#fafbfc; }}
footer {{ margin-top:14px; padding-top:7px; border-top:1px solid #dfe3e9; font-size:7.6pt; color:#6b7381; }}
</style></head><body>

<div class="mast">
  <div>
    <div class="kicker">PropStats · MLB Home Run Board</div>
    <h1>Home Run Report</h1>
  </div>
  <div class="sub">
    <b>Tuesday, September 15, 2026</b><br>
    {len(games)} games · {len(hr)} starters · {sum(len(r["top_batters"]) for r in hr)} batters scored<br>
    Lineups not yet posted — roster-based
  </div>
</div>

<h2>How to read this</h2>
<div class="legend">
  <div><b>Vuln 0–100</b> — pitcher HR vulnerability. <b>Attackable</b> &gt;63, Neutral 45–63, Avoid &lt;45.</div>
  <div><b>Zone</b> — how well the batter hits <i>this</i> pitcher's actual pitch mix, weighted to his handedness.</div>
  <div><b>Chalk tier</b> — how <i>public</i> a play is (price + board rank + name), not how good. Leverage = live but under-bet.</div>
  <div><b>Near</b> — batted balls ≥98 mph at 20–35° travelling ≥360 ft that stayed in the park. Bad luck, not bad contact.</div>
  <div><b>Splits</b> — the starter's last ~45 days of pitch-level data, separated by batter hand. Shaded rows = the side he is getting hurt on.</div>
  <div><b>Park</b> — venue HR factor for that batter's pull side. 1.48 (Sutter Health) is extreme; 0.72 (Oracle) suppresses.</div>
</div>

<h2>The spots that matter</h2>
<div class="spots">
  <div class="spot"><div class="t">SEA @ ATH — Jeffrey Springs (61)</div><div class="w">Best HR environment on the slate: park factor <b>1.48</b> with a 10 mph wind out to centre. Springs has allowed <b>.476 wOBA / .733 SLG and 4 HR in 37 PA to left-handers</b>. Three of the day's five shortest prices are here.</div></div>
  <div class="spot"><div class="t">COL @ DET — Mason Adams (81)</div><div class="w">Most vulnerable arm on the board, tagged HIGH BARREL RATE ALLOWED — but read the split: <b>.495 wOBA / .808 SLG, 3 HR, 22% barrel to righties</b> versus .329/.370 to lefties. The listed Detroit bats are all left-handed.</div></div>
  <div class="spot"><div class="t">PIT @ CHC — Shota Imanaga (58)</div><div class="w">Tagged <b>L5 HR ELEV (1.6 per game)</b> and giving up .423/.625 with 4 HR in 43 PA to lefties, 7 more to righties. Wrigley with a 10 mph wind.</div></div>
  <div class="spot"><div class="t">LAA @ WSH — Yusei Kikuchi (57)</div><div class="w">Allowing <b>.394 wOBA / .612 SLG with 4 HR in 56 PA to right-handers</b>. James Wood posts a perfect zone score of 100 from the other side.</div></div>
</div>
<p class="small dim">Attackable starters tonight: {", ".join(f'{esc(r["pitcher_name"])} ({r["game"]}, {r["vuln"]["score"]:.0f})' for r in attackable)}.</p>

<h2>Head-to-head: batters who have homered off tonight's starter</h2>
<p class="small">Of the <b>{n_h2h_any}</b> batters on this board who have faced their opposing starter before, <b>{len(h2h_rows)}</b> have taken him deep. Career data from 2020 onward. Small samples are noisy — a 2-for-7 is a curiosity, a 4-for-45 with real slug is a pattern — so weigh the PA column alongside the rate. The single clearest signal below is that <b>five Atlanta hitters have combined for 15 home runs off Aaron Nola</b>, and two of them (Riley, Harris II) are priced as leverage rather than chalk.</p>
<table class="h2h">
<thead><tr><th></th><th>Batter</th><th>vs Starter</th><th>Game</th><th style="text-align:right">HR</th><th style="text-align:right">PA</th><th style="text-align:right">HR/PA</th><th style="text-align:right">AVG</th><th style="text-align:right">SLG</th><th style="text-align:right">OPS</th><th style="text-align:right">K%</th><th style="text-align:right">Model</th><th style="text-align:right">Odds</th><th>Tier</th></tr></thead>
<tbody>{h2h_html}</tbody></table>

<h2 class="pagebreak">Leaderboards — the same board sorted every way that matters</h2>
<p class="small dim">Each list is the top 12 on one metric, with the model's probability alongside so you can see where a
category leader actually lands. A name that tops several of these is a genuine fit; one that tops a single list is a
one-dimensional case. Lineup-confirmed hitters only.</p>
<div class="lb-grid">{lb_html}</div>

<h2>Tonight's conditions — who they help and who they hurt</h2>
<p class="small dim">Every hitter carries three season splits that apply to this specific game: how he hits the
starter's handedness, how he hits in day or night games, and how he hits at home or on the road. Shown against his own
overall line, so <b>+0.090</b> means this version of him is 90 OPS points better than his season average. Splits under
40 plate appearances are excluded — they move around too much to mean anything.</p>
<div class="lb-grid">{ctx_html}</div>

<h2 class="pagebreak">Master table — every hitter, every column</h2>
<p class="small dim">Sorted by calibrated probability. Scan any column to re-rank by eye:
Zone is fit against this pitcher's mix, PkFit is park fit, dEV is exit velocity against the hitter's own season
baseline, Near is 98+ mph balls at 20-35 degrees that stayed in, H2H is career home runs off tonight's starter.</p>
<div class="tbl-wide"><table class="master"><thead><tr>{master_head}</tr></thead><tbody>{master_rows}</tbody></table></div>

<h2 class="pagebreak">Game by game — top 3 hitters per team</h2>
<p class="small dim">Ranked by matchup score, which blends the batter's power profile, his fit against this pitcher's actual mix, and the pitcher's vulnerability. Probabilities are Poisson-derived; odds shown are the model's fair price, not a book's.</p>
{game_html}

<footer>
  PropStats HR engine · Statcast pitch-level data via Baseball Savant, schedule and head-to-head via the MLB Stats API.
  Splits cover each starter's last ~45 days. Generated {esc(DATE)} before lineups posted — confirm the batting order before betting.
  Model prices are fair-value estimates and carry no vig; they are not a betting recommendation.
</footer>
</body></html>'''

open(OUT, "w").write(doc)
print(f"Written {OUT} ({len(doc)//1024}KB) · {len(h2h_rows)} H2H rows · {len(games)} games")
