#!/usr/bin/env python3
"""Build HTML artifact for 2026-09-16 MLB slate."""
import json, os, math

SP = "/tmp/claude-0/-home-user-propstats/4a29f92c-2ab2-55a2-aa2c-327f896f1d05/scratchpad"
DATE = "2026-09-16"
DS = "20260916"
OUT = f"{SP}/slate_{DS}.html"

def load(name):
    p = f"{SP}/{name}_{DS}.json"
    if os.path.exists(p):
        return json.load(open(p))
    return []

k_board = load("k_board")
hr_board = load("hr_board")
nrfi_board = load("nrfi")
f5_board = load("f5_board")
hits_board = load("hits_board")
tb_board = load("tb_board")
bk_board = load("batter_k")
fan_board = load("hitter_fantasy")
walk_board = load("walk_board")

# ── helpers ──────────────────────────────────────────────────────────────────

def esc_attr(s):
    return str(s).replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")

def pct_bar(val, max_val=100, color="var(--accent)"):
    w = min(100, max(0, val / max_val * 100))
    return f'<div class="bar-wrap"><div class="bar-fill" style="width:{w:.0f}%;background:{color}"></div></div>'

def pitch_dropdown(arsenal, label="Pitch Arsenal"):
    if not arsenal:
        return ""
    rows = ""
    for p in arsenal:
        wh = p.get("whiff_pct", 0)
        pa = p.get("put_away_pct", 0)
        xw = p.get("xwoba_against", 0)
        hh = p.get("hard_hit_pct", 0)
        rv = p.get("run_value_per100", 0)
        rv_cls = "pos-num" if rv > 0 else "neg-num" if rv < 0 else ""
        rows += f"""<tr>
          <td class="ptype">{p.get('pitch_name','?')}</td>
          <td>{p.get('usage_pct',0):.0f}%</td>
          <td>{wh:.0f}%</td>
          <td>{pa:.0f}%</td>
          <td>{xw:.3f}</td>
          <td>{hh:.0f}%</td>
          <td class="{rv_cls}">{rv:+.1f}</td>
        </tr>"""
    return f"""<details class="pitch-drop">
  <summary>{label} ({len(arsenal)} pitches)</summary>
  <table class="pitch-tbl">
    <thead><tr><th>Pitch</th><th>Usage</th><th>Whiff%</th><th>PutAway%</th><th>xwOBA</th><th>HH%</th><th>RV/100</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</details>"""

def batter_pitch_dropdown(pitch_table, label="vs Pitcher Arsenal"):
    if not pitch_table:
        return ""
    rows = ""
    for p in pitch_table:
        xw = p.get("b_xwoba", 0)
        hh = p.get("b_hh", 0)
        wh = p.get("b_whiff", 0)
        rv = p.get("b_rv100", 0)
        row_cls = ""
        if xw >= 0.420 and hh >= 45:
            row_cls = ' class="hot-row"'
        elif xw <= 0.250:
            row_cls = ' class="cold-row"'
        rv_cls = "pos-num" if rv > 0 else "neg-num" if rv < 0 else ""
        rows += f"""<tr{row_cls}>
          <td class="ptype">{p.get('pitch_type','?')}</td>
          <td>{p.get('usage',0):.0f}%</td>
          <td class="pos-num">{xw:.3f}</td>
          <td>{hh:.0f}%</td>
          <td>{wh:.0f}%</td>
          <td class="{rv_cls}">{rv:+.1f}</td>
        </tr>"""
    return f"""<details class="pitch-drop">
  <summary>{label} ({len(pitch_table)} pitches)</summary>
  <table class="pitch-tbl">
    <thead><tr><th>Pitch</th><th>Usage</th><th>xwOBA</th><th>HH%</th><th>Whiff%</th><th>RV/100</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</details>"""

def lineup_badge(b):
    order = b.get("order")
    if b.get("in_lineup") is False:
        return '<span class="slot-badge slot-out">OUT</span>'
    if order:
        return f'<span class="slot-badge slot-in">#{order}</span>'
    return ""

def statcast_block(b):
    sc = b.get("statcast")
    if not sc:
        return ""
    w10 = sc["L10"]
    near_cls = "hl-hot" if w10["near_hr"] >= 2 else ""
    line = (f'<div class="sc-line">L10: EV <b>{w10["avg_ev"]:.1f}</b> · max <b>{w10["max_ev"]:.1f}</b>'
            f' · <b>{w10["hr"]}</b> HR · <b class="{near_cls}">{w10["near_hr"]}</b> near'
            f' · brl <b>{w10["brl_pct"]:.0f}%</b> · {w10["pa_pg"]:.1f} PA/G</div>')
    rows = ""
    for k in ("L5", "L10", "L15"):
        w = sc[k]
        rows += (f'<tr><td class="ptype">{k}</td><td>{w["games"]}</td><td>{w["pa_pg"]:.1f}</td>'
                 f'<td>{w["bbe"]}</td><td>{w["hr"]}</td><td class="{"hl-hot" if w["near_hr"]>=2 else ""}">{w["near_hr"]}</td>'
                 f'<td>{w["brl_pct"]:.0f}%</td><td>{w["hh_pct"]:.0f}%</td><td>{w["avg_ev"]:.1f}</td>'
                 f'<td>{w["max_ev"]:.1f}</td><td>{w["avg_dist"]:.0f}</td></tr>')
    hl = ""
    if sc.get("hard_luck_hits"):
        items = "".join(
            f'<li><span class="hl-date">{h["date"]}</span> {h["ev"]:.1f} mph / {h["la"]:.0f}° / {h["dist"]} ft'
            f' <span class="hl-res">{h["result"].replace("_"," ")}{" · " + h["pitch"] if h["pitch"] else ""}</span></li>'
            for h in sc["hard_luck_hits"])
        hl = f'<div class="hl-label">Hardest non-HR balls L10</div><ul class="hl-list">{items}</ul>'
    return f"""{line}<details class="pitch-drop">
  <summary>Recent Statcast windows</summary>
  <table class="pitch-tbl sc-tbl">
    <thead><tr><th>Win</th><th>G</th><th>PA/G</th><th>BBE</th><th>HR</th><th>Near</th><th>Brl%</th><th>HH%</th><th>EV</th><th>Max</th><th>Dist</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>{hl}
</details>"""

def chalk_badge(b):
    t = b.get("chalk_tier")
    if not t or t == "OUT":
        return ""
    cls = {"HEAVY CHALK": "ck-heavy", "CHALKY": "ck-chalky",
           "BALANCED": "ck-bal", "LEVERAGE": "ck-lev"}.get(t, "ck-bal")
    return (f'<span class="ck {cls}" title="Chalk score {b.get("chalk_score")}/100 — '
            f'how public this play is, not how good">{b.get("chalk_badge","")} {t}</span>')

def build_leverage_strip():
    seen, lev, heavy = set(), [], []
    for g in hr_board:
        for b in g["top_batters"]:
            if b.get("in_lineup") is False or b["batter_name"] in seen:
                continue
            if not b.get("chalk_tier") or b["chalk_tier"] == "OUT":
                continue
            seen.add(b["batter_name"])
            entry = (b.get("matchup_score", 0), b, g)
            if b["chalk_tier"] == "LEVERAGE" and b.get("hr_prob", 0) >= 10.0:
                lev.append(entry)
            elif b["chalk_tier"] == "HEAVY CHALK":
                heavy.append(entry)
    lev.sort(key=lambda x: -x[0]); heavy.sort(key=lambda x: -x[0])
    if not lev and not heavy:
        return ""
    def col(title, rows, note):
        h = f'<div class="due-col"><div class="due-title">{title}</div><div class="ck-note">{note}</div>'
        for _, b, g in rows[:8]:
            s = b.get("statcast", {}).get("L10", {})
            extra = f'{s.get("hr","-")}HR/{s.get("near_hr","-")}nr' if s else ""
            h += (f'<div class="due-row">{lineup_badge(b)}<span class="batter-nm">{b["batter_name"]}</span>'
                  f'<span class="due-meta">{g["game"]} · {extra}</span>'
                  f'<span class="due-num">{b["hr_prob"]:.1f}% {b.get("implied_odds","")}</span></div>')
        return h + '</div>'
    html = '<div class="due-strip">'
    if lev:   html += col("💎 Leverage — live bats the field is not on", lev, "model prob ≥10% with a low public profile")
    if heavy: html += col("🔒 Heavy chalk — everyone is here", heavy, "short price and/or marquee name; still may be correct")
    return html + '</div>'

def _split_cell(key, val):
    fav_b = {"ba": 0.270, "slg": 0.450, "iso": 0.180, "woba": 0.340, "xwoba_con": 0.400,
             "hr_pct": 4.0, "bb_pct": 10.0, "hh_pct": 42.0, "brl_pct": 9.0}
    fav_p = {"ba": 0.220, "slg": 0.350, "iso": 0.110, "woba": 0.290, "xwoba_con": 0.330,
             "k_pct": 27.0, "whiff_pct": 30.0, "hr_pct": 1.5, "bb_pct": 5.5, "hh_pct": 32.0, "brl_pct": 5.0}
    cls = ""
    if key in fav_b and val >= fav_b[key]:
        cls = "fav-b"
    elif key in ("k_pct", "whiff_pct") and val >= fav_p[key]:
        cls = "fav-p"
    elif key in fav_p and key not in ("k_pct", "whiff_pct") and val <= fav_p[key]:
        cls = "fav-p"
    fmt = f"{val:.3f}" if key in ("ba", "slg", "iso", "woba", "xwoba_con") else (f"{val:.1f}%" if key.endswith("_pct") else f"{val}")
    return f'<td class="{cls}">{fmt}</td>'

def pitcher_splits_block(g):
    prof = g.get("hand_profile")
    if not prof:
        return ""
    chips = ""
    for side in ("L", "R"):
        u = prof[side]["all"]["usage"]
        items = "".join(f'<span class="chip">{pt} {d["usage"]:.0f}%</span>' for pt, d in u.items() if d["usage"] >= 3.0)
        chips += f'<div class="chip-row"><span class="chip-lbl">vs {side}HB</span>{items or "<span class=chip-lbl>no sample</span>"}</div>'
    swings = g.get("hand_mix_swings") or []
    swing_html = f'<div class="mix-note">Mix shifts by side: {" · ".join(swings)}</div>' if swings else ""
    cols = ["pa", "ba", "woba", "slg", "iso", "hr", "hr_pct", "bb_pct", "whiff_pct", "k_pct", "hh_pct", "brl_pct"]
    hdr = "".join(f"<th>{h}</th>" for h in ["Split", "PA", "BA", "wOBA", "SLG", "ISO", "HR", "HR%", "BB%", "Whiff%", "K%", "HH%", "Brl%"])
    rows = ""
    for label, side, win in (("vLHB", "L", "all"), ("vRHB", "R", "all"), ("vLHB L3", "L", "recent"), ("vRHB L3", "R", "recent")):
        s = prof[side][win]
        if s["pa"] == 0:
            continue
        cells = f'<td class="ptype">{label}</td><td>{s["pa"]}</td>' + "".join(_split_cell(k, s[k]) for k in cols[1:])
        rows += f"<tr>{cells}</tr>"
    return f"""{chips}{swing_html}<details class="pitch-drop">
  <summary>Splits vs LHB / RHB — last {prof["games_total"]} G (L3 = {", ".join(d[5:] for d in prof["recent_dates"])})</summary>
  <div class="tbl-scroll"><table class="pitch-tbl sc-tbl"><thead><tr>{hdr}</tr></thead><tbody>{rows}</tbody></table></div>
  <div class="legend"><span class="fav-b">green</span> favors batter · <span class="fav-p">red</span> favors pitcher</div>
</details>"""

BOARD_COLS = [
    ("batter",  "Batter",  "txt",  None,          "Hitter, with lineup slot when posted"),
    ("game",    "Game",    "txt",  None,          "Matchup"),
    ("pitcher", "Pitcher", "txt",  None,          "Opposing starter"),
    ("prob",    "HR%",     "num",  (5, 28),       "Calibrated probability of a home run"),
    ("odds",    "Fair",    "txt",  None,          "Model fair price, no vig"),
    ("match",   "Match",   "num",  (20, 90),      "Composite matchup score"),
    ("zone",    "Zone",    "num",  (0, 100),      "Fit vs this pitcher's actual mix, by hand"),
    ("vuln",    "Vuln",    "num",  (0, 80),       "Pitcher HR vulnerability"),
    ("park",    "Park",    "num",  (0.75, 1.35),  "Venue HR factor for this batter's pull side"),
    ("iso",     "xISO",    "num",  (0.10, 0.32),  "Expected isolated power, season"),
    ("xwoba",   "xwOBA",   "num",  (0.28, 0.44),  "Expected wOBA, season"),
    ("brl",     "Brl%",    "num",  (5, 20),       "Barrels per batted ball, season"),
    ("hh",      "HH%",     "num",  (30, 58),      "Hard-hit rate, season"),
    ("ev",      "EV",      "num",  (86, 95),      "Average exit velocity, season"),
    ("ev10",    "EV L10",  "num",  (84, 98),      "Average exit velocity, last 10 games"),
    ("dev",     "ΔEV",     "num",  (-4, 6),       "Recent EV minus season EV"),
    ("dbrl",    "ΔBrl",    "num",  (-40, 60),     "Recent barrel rate vs season, percent change"),
    ("maxev",   "Max EV",  "num",  (100, 116),    "Hardest ball struck in the last 5 games"),
    ("hr10",    "HR",      "num",  (0, 5),        "Home runs, last 10 games"),
    ("near",    "Near",    "num",  (0, 4),        "Near-misses: 98+ mph, 20-35 deg, 360+ ft, not a HR"),
    ("h2hhr",   "H2H",     "num",  (0, 4),        "Career home runs off tonight's starter"),
    ("sigs",    "Signals", "txt",  None,          "Measured lifts: OWNS 2.9x · FIRE 1.9x · HARD LUCK 1.6x · DUE 1.5x · SURGE 1.2x · DOMINATED 0.8x"),
]

# Short codes with their graded lift, so a signal reads as a number not a mood
SIGNAL_CHIPS = [
    ("OWNS PITCHER", "OWNS", "sg-owns", "2.9x"),
    ("🔥 FIRE",      "FIRE", "sg-fire", "1.9x"),
    ("HARD LUCK",    "LUCK", "sg-luck", "1.6x"),
    ("HEATING",      "HEAT", "sg-heat", ""),
    ("DUE",          "DUE",  "sg-due",  "1.5x"),
    ("EV SURGE",     "SURGE","sg-surge","1.2x"),
    ("🔥 HOT",       "HOT",  "sg-hot",  "1.2x"),
    ("DOMINATED",    "DOM",  "sg-dom",  "0.8x"),
]

def signal_chips(tags):
    out = ""
    for needle, code, cls, lift in SIGNAL_CHIPS:
        if any(needle in t for t in tags):
            out += f'<span class="sg {cls}" title="{code} — graded lift {lift or "n/a"}">{code}</span>'
    return out

FASTBALLS = {"FF", "SI", "FC"}
BREAKING  = {"SL", "CU", "ST", "KC", "SV"}
OFFSPEED  = {"CH", "FS", "FO"}

def pitcher_archetype(g, side):
    """Describe the arm in words, from the mix he actually throws to this side."""
    hp = (g.get("hand_profile") or {}).get(side, {}).get("all", {})
    usage = hp.get("usage") or {}
    if not usage:
        return None
    fam = {"fastball": 0.0, "breaking": 0.0, "offspeed": 0.0}
    for pt, u in usage.items():
        if pt in FASTBALLS:   fam["fastball"] += u["usage"]
        elif pt in BREAKING:  fam["breaking"] += u["usage"]
        elif pt in OFFSPEED:  fam["offspeed"] += u["usage"]
    top = max(fam, key=fam.get)
    lead = max(usage.items(), key=lambda kv: kv[1]["usage"])
    b0 = g["top_batters"][0] if g["top_batters"] else {}
    velo, arm = b0.get("ff_velo") or 0, b0.get("arm_slot") or ""
    bits = []
    if fam["fastball"] >= 55:   bits.append("fastball-heavy")
    elif fam["breaking"] >= 45: bits.append("breaking-ball-heavy")
    elif fam["offspeed"] >= 30: bits.append("offspeed-heavy")
    else:                        bits.append("mixed-arsenal")
    if velo >= 96:   bits.append("premium velocity")
    elif velo >= 94: bits.append("above-average velocity")
    elif 0 < velo < 92: bits.append("soft-tossing")
    if arm in ("Submarine", "Sidearm"): bits.append(arm.lower())
    k = hp.get("k_pct") or 0
    if k >= 28:   bits.append("high strikeout")
    elif 0 < k <= 16: bits.append("pitch-to-contact")
    return {"label": ", ".join(bits), "fam": fam, "lead": lead[0],
            "lead_usage": round(lead[1]["usage"], 0), "velo": velo, "arm": arm,
            "k": hp.get("k_pct"), "bb": hp.get("bb_pct"), "brl": hp.get("brl_pct"),
            "woba": hp.get("woba"), "slg": hp.get("slg"), "hr": hp.get("hr"), "pa": hp.get("pa")}

def hitter_archetype(b):
    """Describe the bat in words, from his season batted-ball profile."""
    brl, hh = b.get("brl_bip") or 0, b.get("hh_pct") or 0
    la, pull = b.get("la_avg") or 0, b.get("pull_pct") or 0
    k = b.get("swstr_pct") or 0
    bits = []
    if brl >= 13 and hh >= 48:  bits.append("elite power")
    elif brl >= 10:             bits.append("real power")
    elif brl < 7:               bits.append("contact-first")
    if la >= 18:                bits.append("uppercut")
    elif 0 < la < 10:           bits.append("flat swing")
    if pull >= 44:              bits.append("heavy pull")
    elif 0 < pull <= 32:        bits.append("uses the whole field")
    if k >= 30:                 bits.append("swing-and-miss")
    elif 0 < k <= 18:           bits.append("rarely whiffs")
    return ", ".join(bits) or "balanced profile"

def batter_vs_families(b):
    """How this hitter does against each pitch family, weighted by what he'll see."""
    fam = {"fastball": [0.0, 0.0], "breaking": [0.0, 0.0], "offspeed": [0.0, 0.0]}
    for row in (b.get("pitch_table") or []):
        pt, u, xw = row.get("pitch_type"), row.get("usage") or 0, row.get("b_xwoba")
        if not u or xw is None:
            continue
        key = "fastball" if pt in FASTBALLS else ("breaking" if pt in BREAKING else
              ("offspeed" if pt in OFFSPEED else None))
        if key:
            fam[key][0] += u * xw
            fam[key][1] += u
    return {k: {"xwoba": round(v[0] / v[1], 3), "usage": round(v[1], 0)}
            for k, v in fam.items() if v[1] >= 5}

def _heat(val, lo, hi):
    if val is None:
        return ""
    t = max(0.0, min(1.0, (val - lo) / (hi - lo))) if hi != lo else 0.5
    # cold blue -> neutral -> hot red, matching the tone of the rest of the page
    if t < 0.5:
        a = t / 0.5
        return f"background:rgba(74,158,255,{0.22*(1-a):.3f})"
    a = (t - 0.5) / 0.5
    return f"background:rgba(240,82,82,{0.30*a:.3f})"

def build_board_tab():
    rows, seen = [], set()
    for g in hr_board:
        for b in g["top_batters"]:
            if b.get("in_lineup") is False or b["batter_id"] in seen:
                continue
            seen.add(b["batter_id"])
            sc = b.get("statcast", {}) or {}
            w10, w5 = sc.get("L10", {}), sc.get("L5", {})
            fd = b.get("form_delta", {}) or {}
            h2 = b.get("h2h") or {}
            rows.append({
                "batter": b["batter_name"], "bats": b.get("bats", ""), "order": b.get("order"),
                "game": g["game"], "pitcher": g["pitcher_name"],
                "prob": b.get("hr_prob"), "odds": b.get("implied_odds", ""),
                "match": b.get("matchup_score"), "zone": b.get("hr_zone_score"),
                "vuln": g["vuln"]["score"], "park": b.get("park_hr_factor"),
                "iso": b.get("xiso"), "xwoba": b.get("xwoba"), "brl": b.get("brl_bip"),
                "hh": b.get("hh_pct"), "ev": b.get("exit_velo"),
                "ev10": w10.get("avg_ev") or None, "dev": fd.get("ev"),
                "dbrl": fd.get("brl_pct_rel"), "maxev": w5.get("max_ev") or None,
                "hr10": w10.get("hr"), "near": w10.get("near_hr"),
                "h2hhr": h2.get("hr") if h2.get("pa") else None,
                "chalk": b.get("chalk_tier") or "", "badge": b.get("chalk_badge", ""),
                "tags": [t for t in b.get("tags", []) if any(k in t for k in
                         ("FIRE", "HOT", "HARD LUCK", "EV SURGE", "DUE", "OWNS", "DOMINATED", "HEATING"))][:2],
                "all_tags": b.get("tags", []),
                "sig_rank": round((b.get("cal_sig_mult") or 1.0) * 100),
                "pgrid": (g.get("hand_profile") or {}).get(
                    b.get("hand_usage_applied") or (b.get("bats") if b.get("bats") in ("L", "R") else "R"),
                    {}).get("zone_grid"),
                "bgrid": sc.get("zone_grid"),
                "log": sc.get("game_log"),
                "w5": sc.get("L5"), "w15": sc.get("L15"),
                "ctx": b.get("ctx_splits"), "ctx_night": b.get("ctx_daynight"),
                "ctx_home": b.get("ctx_home"), "bats": b.get("bats", ""),
                "edges": [e["label"] for e in b.get("hr_edges", [])][:3],
                "weak": [w["label"] for w in b.get("weak_spots", [])][:2],
                "h2h": (lambda h: h if h.get("pa") else None)(b.get("h2h") or {}),
                "sig": b.get("cal_signals", []),
                "arch_p": pitcher_archetype(g, b.get("hand_usage_applied") or
                                            (b.get("bats") if b.get("bats") in ("L", "R") else "R")),
                "arch_b": hitter_archetype(b),
                "fams": batter_vs_families(b),
                "side": b.get("hand_usage_applied") or b.get("bats", "R"),
            })
    rows.sort(key=lambda r: -(r["prob"] or 0))

    head = "".join(
        f'<th data-col="{c}" data-type="{t}" title="{esc_attr(tip)}">{lbl}<span class="sort-ar"></span></th>'
        for c, lbl, t, _, tip in BOARD_COLS)

    body = ""
    for r in rows:
        tds = ""
        for c, _lbl, typ, rng, _tip in BOARD_COLS:
            v = r.get(c)
            if c == "batter":
                slot = f'<span class="slot-badge slot-in">#{r["order"]}</span>' if r.get("order") else ""
                tds += (f'<td class="sticky-col" data-v="{r["batter"]}">{slot}<b>{r["batter"]}</b>'
                        f'<span class="hand">{r["bats"]}</span> {r["badge"]}</td>')
            elif c == "sigs":
                chips = signal_chips(r.get("all_tags") or [])
                tds += f'<td class="sig-cell" data-v="{r.get("sig_rank", 0)}">{chips}</td>'
            elif typ == "txt":
                tds += f'<td data-v="{v or ""}">{v or ""}</td>'
            elif v is None:
                tds += '<td data-v="-999" class="dim">·</td>'
            else:
                fmt = f"{v:.3f}" if c in ("iso", "xwoba") else (f"{v:.2f}" if c == "park" else
                      (f"{v:+.1f}" if c in ("dev",) else (f"{v:+.0f}%" if c == "dbrl" else
                      (f"{v:.0f}" if c in ("vuln", "match", "zone", "hr10", "near", "h2hhr") else f"{v:.1f}"))))
                tds += f'<td data-v="{v}" style="{_heat(v, rng[0], rng[1])}">{fmt}</td>'
        detail = json.dumps({k: r.get(k) for k in
                             ("batter", "bats", "game", "pitcher", "log", "w5", "w15",
                              "ctx", "ctx_night", "ctx_home", "edges", "weak", "h2h", "sig",
                              "prob", "odds", "order", "arch_p", "arch_b", "fams", "side",
                              "brl", "hh", "iso", "zone", "bgrid", "pgrid", "all_tags")},
                             separators=(",", ":"))
        body += (f'<tr class="brow" data-chalk="{r["chalk"]}" data-detail=\'{esc_attr(detail)}\'>{tds}</tr>'
                 f'<tr class="drow" hidden><td colspan="{len(BOARD_COLS)}"></td></tr>')

    return f'''<div class="board-wrap">
  <div class="board-bar">
    <span class="board-title">Full board — {len(rows)} hitters</span>
    <span class="board-hint">Click a column to sort · <b>click a player to open his last 5 games</b></span>
    <span class="board-filters">
      <button class="fbtn active" data-f="all">All</button>
      <button class="fbtn" data-f="LEVERAGE">💎 Leverage</button>
      <button class="fbtn" data-f="BALANCED">○ Balanced</button>
      <button class="fbtn" data-f="CHALKY">⚠️ Chalky</button>
      <button class="fbtn" data-f="HEAVY CHALK">🔒 Chalk</button>
    </span>
  </div>
  <div class="board-scroll"><table class="board-tbl" id="bigboard">
    <thead><tr>{head}</tr></thead><tbody>{body}</tbody>
  </table></div>
</div>'''

def build_lookup_tab():
    """Searchable per-hitter matchup card: heat zone, form windows, arsenal, H2H."""
    players = {}
    for g in hr_board:
        hp = g.get("hand_profile") or {}
        for b in g["top_batters"]:
            key = b["batter_name"]
            if key in players and players[key].get("_ms", 0) >= (b.get("matchup_score") or 0):
                continue
            sc = b.get("statcast") or {}
            side = b.get("hand_usage_applied") or (b.get("bats") if b.get("bats") in ("L", "R") else "R")
            sp = (hp.get(side, {}) or {}).get("all", {}) if hp else {}
            h2 = b.get("h2h") or {}
            players[key] = {
                "_ms": b.get("matchup_score") or 0,
                "nm": key, "bats": b.get("bats", ""), "team": g["opp_team"],
                "game": g["game"], "venue": g["venue"], "order": b.get("order"),
                "inlu": b.get("in_lineup"),
                "pit": g["pitcher_name"], "pthrows": g.get("pitcher_throws", ""),
                "vuln": g["vuln"]["score"], "vtier": g["vuln"]["tier"],
                "prob": b.get("hr_prob"), "odds": b.get("implied_odds", ""),
                "ms": round(b.get("matchup_score") or 0, 1),
                "zone": b.get("hr_zone_score"), "park": b.get("park_hr_factor"),
                "chalk": b.get("chalk_tier"), "badge": b.get("chalk_badge", ""),
                "sig": b.get("cal_signals", []), "sigmult": b.get("cal_sig_mult"),
                "tags": b.get("tags", [])[:8],
                "season": {"iso": b.get("xiso"), "xwoba": b.get("xwoba"), "brl": b.get("brl_bip"),
                           "hh": b.get("hh_pct"), "ev": b.get("exit_velo"), "la": b.get("la_avg"),
                           "fb": b.get("fb_pct"), "pull": b.get("pull_pct"),
                           "sweet": b.get("sweet_spot"), "hrfb": b.get("hr_fb_pct")},
                "w": {k: sc.get(k) for k in ("L5", "L10", "L15") if sc.get(k)},
                "delta": b.get("form_delta") or {},
                "grid": sc.get("zone_grid"),
                "hardluck": sc.get("hard_luck_hits") or [],
                "ptable": b.get("pitch_table") or [],
                "edges": [e["label"] for e in b.get("hr_edges", [])],
                "weak": [w["label"] for w in b.get("weak_spots", [])],
                "sidemix": {"side": side, "pa": sp.get("pa"), "woba": sp.get("woba"),
                            "slg": sp.get("slg"), "hr": sp.get("hr"), "k": sp.get("k_pct"),
                            "bb": sp.get("bb_pct"), "brl": sp.get("brl_pct"),
                            "usage": {pt: u["usage"] for pt, u in list((sp.get("usage") or {}).items())[:6]}},
                "h2h": {"pa": h2.get("pa"), "hr": h2.get("hr"), "h": h2.get("h"), "bb": h2.get("bb"),
                        "k": h2.get("k"), "avg": h2.get("avg"), "obp": h2.get("obp"),
                        "slg": h2.get("slg"), "ops": h2.get("ops")} if h2.get("pa") else None,
                "arm": b.get("arm_slot"), "armmult": b.get("arm_mult"),
                "wall": b.get("pull_wall_label"), "lane": b.get("signal_lane"),
            }
    for p in players.values():
        p.pop("_ms", None)
    names = sorted(players.keys())
    data = json.dumps(players, separators=(",", ":"))
    opts = "".join(f'<option value="{esc_attr(n)}"></option>' for n in names)
    return f'''<div class="lk-wrap">
  <div class="lk-search">
    <input id="lk-input" list="lk-names" placeholder="Type a hitter — e.g. McGonigle, Judge, Elly" autocomplete="off">
    <datalist id="lk-names">{opts}</datalist>
    <span class="lk-count">{len(names)} hitters on this slate</span>
  </div>
  <div id="lk-card" class="lk-card"><div class="lk-empty">Search a hitter to see the full matchup: heat zone, recent form against his own baseline, the arsenal he'll face, and any head-to-head history.</div></div>
</div>
<script id="lk-data" type="application/json">{data}</script>'''


def build_matchup_tab():
    """
    Any batter on the slate against any starter on the slate.

    Ships two compact tables — each hitter's performance by pitch type and each
    pitcher's arsenal split by batter hand — and recomputes the matchup in the
    browser with the same math the engine uses, so a pairing that isn't on
    today's schedule can still be evaluated.
    """
    bat, pit = {}, {}
    for g in hr_board:
        hp = g.get("hand_profile") or {}
        pname = g["pitcher_name"]
        if pname not in pit:
            usage = {}
            for side in ("L", "R"):
                a = (hp.get(side, {}) or {}).get("all", {})
                for ptype, u in (a.get("usage") or {}).items():
                    usage.setdefault(ptype, {})[side] = round(u["usage"], 1)
            eff = {}
            for p in g.get("arsenal", []) or []:
                eff[p["pitch_type"]] = {"xw": p.get("xwoba_against"), "pa": p.get("put_away_pct"),
                                        "wh": p.get("whiff_pct"), "us": p.get("usage_pct")}
            sides = {}
            for side in ("L", "R"):
                a = (hp.get(side, {}) or {}).get("all", {})
                if a.get("pa"):
                    sides[side] = {"pa": a["pa"], "woba": a["woba"], "slg": a["slg"], "hr": a["hr"],
                                   "k": a["k_pct"], "bb": a["bb_pct"], "brl": a["brl_pct"]}
            pit[pname] = {"nm": pname, "throws": g.get("pitcher_throws", "R"),
                          "vuln": g["vuln"]["score"], "vtier": g["vuln"]["tier"],
                          "team": g["pitcher_team"], "game": g["game"],
                          "usage": usage, "eff": eff, "sides": sides,
                          "arm": g["top_batters"][0].get("arm_slot") if g["top_batters"] else None,
                          "tags": g.get("pitcher_tags", [])[:4]}
        for b in g["top_batters"]:
            nm = b["batter_name"]
            if nm in bat:
                continue
            splits = {}
            for r in (b.get("pitch_table") or []):
                splits[r["pitch_type"]] = {"xw": r.get("b_xwoba"), "hh": r.get("b_hh"), "wh": r.get("b_whiff")}
            sc = b.get("statcast") or {}
            bat[nm] = {"nm": nm, "bats": b.get("bats", "R"), "team": g["opp_team"],
                       "iso": b.get("xiso"), "xwoba": b.get("xwoba"), "brl": b.get("brl_bip"),
                       "hh": b.get("hh_pct"), "ev": b.get("exit_velo"), "la": b.get("la_avg"),
                       "splits": splits, "grid": sc.get("zone_grid"),
                       "tags": [t for t in b.get("tags", []) if any(k in t for k in
                                ("FIRE", "HOT", "HARD LUCK", "EV SURGE", "DUE", "HEATING"))][:4],
                       "w10": (sc.get("L10") or {}).get("hr"), "near": (sc.get("L10") or {}).get("near_hr"),
                       "maxev": (sc.get("L5") or {}).get("max_ev")}
    bopts = "".join(f'<option value="{esc_attr(n)}"></option>' for n in sorted(bat))
    popts = "".join(f'<option value="{esc_attr(n)}"></option>' for n in sorted(pit))
    return f'''<div class="lk-wrap">
  <div class="mm-bar">
    <div class="mm-field"><label>Batter</label>
      <input id="mm-bat" list="mm-bats" placeholder="Any hitter on the slate" autocomplete="off"></div>
    <div class="mm-vs">vs</div>
    <div class="mm-field"><label>Pitcher</label>
      <input id="mm-pit" list="mm-pits" placeholder="Any starter on the slate" autocomplete="off"></div>
    <button id="mm-go" class="fbtn active">Evaluate</button>
  </div>
  <datalist id="mm-bats">{bopts}</datalist>
  <datalist id="mm-pits">{popts}</datalist>
  <div class="zone-legend" style="max-width:720px">Pairs any of the {len(bat)} hitters with any of the {len(pit)} starters, including
  matchups that are not on today's schedule. Zone fit, pitch edges and the home-run probability are recomputed from
  the hitter's performance by pitch type and the mix that pitcher actually throws to his side.</div>
  <div id="mm-out" class="lk-card"></div>
</div>
<script id="mm-bat-data" type="application/json">{json.dumps(bat, separators=(",", ":"))}</script>
<script id="mm-pit-data" type="application/json">{json.dumps(pit, separators=(",", ":"))}</script>'''


def build_due_strip():
    seen, hard, surge = set(), [], []
    for g in hr_board:
        for b in g["top_batters"]:
            sc = b.get("statcast")
            if not sc or b.get("in_lineup") is False or b["batter_name"] in seen:
                continue
            seen.add(b["batter_name"])
            w10, w5 = sc["L10"], sc["L5"]
            if w10["near_hr"] >= 2 and w10["hr"] <= 1:
                hard.append((w10["near_hr"], w10["max_ev"], b, g))
            if w5["max_ev"] >= 110.0:
                surge.append((w5["max_ev"], b, g))
    hard.sort(key=lambda x: (-x[0], -x[1]))
    surge.sort(key=lambda x: -x[0])
    if not hard and not surge:
        return ""
    html = '<div class="due-strip">'
    if hard:
        html += '<div class="due-col"><div class="due-title">💥 Hard Luck — near-HRs without the HR (L10)</div>'
        for n, mx, b, g in hard[:8]:
            html += (f'<div class="due-row">{lineup_badge(b)}<span class="batter-nm">{b["batter_name"]}</span>'
                     f'<span class="due-meta">{g["game"]} vs {g["pitcher_name"]}</span>'
                     f'<span class="due-num">{n} near · max {mx:.0f}</span></div>')
        html += '</div>'
    if surge:
        html += '<div class="due-col"><div class="due-title">🚀 EV Surge — 110+ mph in last 5</div>'
        for mx, b, g in surge[:8]:
            html += (f'<div class="due-row">{lineup_badge(b)}<span class="batter-nm">{b["batter_name"]}</span>'
                     f'<span class="due-meta">{g["game"]} vs {g["pitcher_name"]}</span>'
                     f'<span class="due-num">{mx:.1f} mph</span></div>')
        html += '</div>'
    html += '</div>'
    return html

def tier_badge(tier):
    cls = {
        "K ELITE": "badge-elite",
        "K Threat": "badge-threat",
        "Manageable": "badge-manage",
        "DATA SPARSE": "badge-sparse",
        "Attackable": "badge-attack",
        "Neutral Lean": "badge-neutral",
        "Avoid": "badge-avoid",
    }.get(tier, "badge-neutral")
    return f'<span class="badge {cls}">{tier}</span>'

def outs_verdict(p):
    rf = p.get("recent_form", {})
    proj = p.get("proj", {})
    ip_avg = rf.get("recent_ip_pg", 0) or 0
    recent_era = rf.get("recent_era", 99) or 99
    early_hook = rf.get("early_hook_risk", False)
    ppa = rf.get("p_per_pa", 0) or 0
    n_starts = rf.get("n_starts", 0)
    start_logs = rf.get("start_logs", [])
    last_pc = 0
    ip_vals = []
    for s in start_logs:
        ip_str = str(s.get("ip","0"))
        try:
            parts = ip_str.split(".")
            ip_dec = int(parts[0]) + (int(parts[1]) / 3 if len(parts) > 1 else 0)
            ip_vals.append(ip_dec)
        except:
            pass
        pc = s.get("pitches", 0)
        if pc > last_pc:
            last_pc = pc

    ip_std = 0
    if len(ip_vals) >= 2:
        mean = sum(ip_vals) / len(ip_vals)
        ip_std = math.sqrt(sum((x - mean) ** 2 for x in ip_vals) / len(ip_vals))

    fade_flags = []
    trust_flags = []

    if last_pc >= 105:
        fade_flags.append("HIGH PC")
    elif last_pc <= 95 and last_pc > 0:
        trust_flags.append("LOW PC")

    if ppa >= 4.20:
        fade_flags.append("HIGH PPA")

    if early_hook:
        fade_flags.append("EARLY HOOK RISK")

    if ip_avg < 5.0 and n_starts >= 2:
        fade_flags.append("SHORT AVG")
    elif ip_avg >= 6.5:
        trust_flags.append("DEEP STARTER")

    if ip_std > 1.5 and len(ip_vals) >= 3:
        fade_flags.append("VOLATILE IP")
    elif ip_std <= 0.8 and len(ip_vals) >= 3:
        trust_flags.append("CONSISTENT IP")

    if recent_era <= 2.50 and n_starts >= 2:
        trust_flags.append("HOT ERA")

    nf = len(fade_flags)
    nt = len(trust_flags)

    if nf >= 2 or (nf == 1 and ip_avg < 5.5):
        verdict = "FADE"
        v_cls = "v-fade"
    elif nt >= 2 and nf == 0:
        verdict = "TRUST"
        v_cls = "v-trust"
    elif nt >= 1 and nf == 0:
        verdict = "LEAN TRUST"
        v_cls = "v-lean-trust"
    elif nf == 1 and nt >= 1:
        verdict = "MIXED"
        v_cls = "v-mixed"
    else:
        verdict = "NEUTRAL"
        v_cls = "v-neutral"

    return verdict, v_cls, fade_flags, trust_flags, ip_avg, ip_std, recent_era, last_pc, ppa

# ── build games tab ────────────────────────────────────────────────────────────

def build_games_tab():
    # index by game string
    k_idx = {}
    for p in k_board:
        g = p["game"]
        k_idx.setdefault(g, []).append(p)

    hr_idx = {}
    for g in hr_board:
        hr_idx.setdefault(g["game"], []).append(g)

    nrfi_idx = {}
    for n in nrfi_board:
        nrfi_idx[n["game"]] = n

    f5_idx = {}
    for f in f5_board:
        gstr = f"{f['away_abbr']}@{f['home_abbr']}"
        f5_idx[gstr] = f

    # gather unique games
    games = []
    seen = set()
    for p in k_board:
        if p["game"] not in seen:
            games.append(p["game"])
            seen.add(p["game"])

    html = '<div class="games-grid">'
    for game in games:
        pitchers = k_idx.get(game, [])
        nrfi = nrfi_idx.get(game, {})
        nr = nrfi.get("nrfi", {})
        f5 = f5_idx.get(game, {})
        hr_games = hr_idx.get(game, [])

        nrfi_verdict = nr.get("verdict", "—")
        nrfi_score = nr.get("score", 0)
        nrfi_conf = nr.get("confidence", "")
        nrfi_cls = "yrfi-badge" if nrfi_verdict == "YRFI" else "nrfi-badge" if nrfi_verdict == "NRFI" else "neut-badge"

        lam = f5.get("lam_total", 0)
        p_o4 = f5.get("p_o4", 0)
        f5_call = ""
        if p_o4 >= 70:
            f5_call = f"OVER 4.5 ({p_o4:.0f}%)"
            f5_cls = "f5-over"
        elif p_o4 <= 30:
            f5_call = f"UNDER 4.5 ({100-p_o4:.0f}%)"
            f5_cls = "f5-under"
        else:
            f5_call = f"LEAN OVER ({p_o4:.0f}%)" if p_o4 > 50 else f"LEAN UNDER ({100-p_o4:.0f}%)"
            f5_cls = "f5-lean"

        html += f'<div class="game-card">'
        html += f'<div class="game-header"><span class="game-title">{game}</span>'
        if lam > 0:
            html += f'<span class="lam-badge">λ {lam:.2f}</span>'
        html += '</div>'

        # NRFI row
        html += f'<div class="game-row"><span class="row-label">1st Inn</span>'
        html += f'<span class="badge {nrfi_cls}">{nrfi_verdict}</span>'
        if nrfi_score > 0:
            html += f'<span class="score-val">{nrfi_score:.0f}/100 {nrfi_conf}</span>'
        html += '</div>'

        # F5 row
        if lam > 0:
            html += f'<div class="game-row"><span class="row-label">F5</span>'
            html += f'<span class="{f5_cls}">{f5_call}</span></div>'

        # Pitchers
        for p in pitchers:
            ks = p["k_score"]
            verdict, v_cls, fade_flags, trust_flags, ip_avg, ip_std, recent_era, last_pc, ppa = outs_verdict(p)
            proj = p["proj"]
            edge = proj.get("edge_vs_line", 0)
            k_call = f"OVER {proj['line']}" if edge > 0.5 else f"UNDER {proj['line']}" if edge < -0.5 else f"PASS ({proj['line']})"
            k_call_cls = "k-over" if edge > 0.5 else "k-under" if edge < -0.5 else "k-pass"

            html += f'<div class="pitcher-block">'
            html += f'<div class="pitcher-name-row">'
            html += f'<span class="pitcher-nm">{p["pitcher_name"]}</span>'
            html += f'<span class="pitcher-tm">({p["pitcher_team"]})</span>'
            html += tier_badge(ks["tier"])
            html += f'<span class="badge {v_cls}">{verdict}</span>'
            html += '</div>'
            html += f'<div class="pitcher-stats">'
            html += f'K proj <b>{proj["proj_k"]:.1f}</b> line <b>{proj["line"]}</b> → <span class="{k_call_cls}">{k_call}</span>'
            html += f' | IP avg <b>{ip_avg:.1f}</b>'
            if recent_era > 0:
                html += f' | ERA (L3) <b>{recent_era:.2f}</b>'
            html += '</div>'
            if fade_flags:
                html += f'<div class="flag-row fade-flags">⚠ {" · ".join(fade_flags)}</div>'
            if trust_flags:
                html += f'<div class="flag-row trust-flags">✓ {" · ".join(trust_flags)}</div>'
            html += pitch_dropdown(ks.get("top_whiff_pitches", []), "Pitcher Arsenal")
            html += '</div>'

        # HR targets
        if hr_games:
            top_hr = []
            for hg in hr_games:
                for b in [x for x in hg["top_batters"] if x.get("in_lineup") is not False][:2]:
                    top_hr.append((b["hr_score"], b["batter_name"], b.get("tags", [])[:2], hg["vuln"]["tier"]))
            top_hr.sort(reverse=True)
            if top_hr:
                html += '<div class="hr-targets-label">HR Targets</div>'
                for score, name, tags, vuln in top_hr[:4]:
                    tag_str = " · ".join(t[:30] for t in tags)
                    html += f'<div class="hr-target-row"><span class="hr-score-badge">{score:.0f}</span> <span class="batter-nm">{name}</span><span class="vuln-lbl">vs {vuln}</span></div>'
                    if tag_str:
                        html += f'<div class="hr-tag-row">{tag_str}</div>'

        html += '</div>'  # game-card
    html += '</div>'  # games-grid
    return html

# ── K tab ──────────────────────────────────────────────────────────────────────

def build_k_tab():
    html = '<div class="board-grid">'
    for p in k_board:
        ks = p["k_score"]
        proj = p["proj"]
        rf = p["recent_form"]
        edge = proj.get("edge_vs_line", 0)
        edge_cls = "pos-num" if edge > 0 else "neg-num"
        over_pct = proj.get("over_pct", 0)
        score = ks["score"]
        score_color = f"hsl({min(120,int(score*1.2))},70%,50%)"

        html += f'<div class="board-card">'
        html += f'<div class="card-header">'
        html += f'<span class="pitcher-nm">{p["pitcher_name"]}</span>'
        html += f'<span class="game-lbl">{p["game"]}</span>'
        html += tier_badge(ks["tier"])
        html += '</div>'

        html += f'<div class="score-row">'
        html += f'<div class="score-circle" style="border-color:{score_color}">{score:.0f}</div>'
        html += f'<div class="proj-block">'
        html += f'<div>Proj: <b>{proj["proj_k"]:.1f}K</b> | Line: <b>{proj["line"]}</b> | Edge: <span class="{edge_cls}">{edge:+.1f}</span></div>'
        html += f'<div>Over: <b>{over_pct:.0f}%</b> | swStr: <b>{ks["swstr_pct"]:.1f}%</b> | K%: <b>{ks["k_pct"]:.1f}%</b></div>'
        html += f'<div>{rf.get("form_label","")}</div>'
        html += '</div></div>'

        html += pitch_dropdown(ks.get("top_whiff_pitches", []))
        html += '</div>'
    html += '</div>'
    return html

# ── Outs tab ───────────────────────────────────────────────────────────────────

def build_outs_tab():
    rows = []
    for p in k_board:
        verdict, v_cls, fade_flags, trust_flags, ip_avg, ip_std, recent_era, last_pc, ppa = outs_verdict(p)
        rows.append((verdict, v_cls, fade_flags, trust_flags, ip_avg, ip_std, recent_era, last_pc, ppa, p))

    order = {"FADE": 0, "MIXED": 1, "NEUTRAL": 2, "LEAN TRUST": 3, "TRUST": 4}
    rows.sort(key=lambda x: order.get(x[0], 2))

    html = '<div class="board-grid">'
    for verdict, v_cls, fade_flags, trust_flags, ip_avg, ip_std, recent_era, last_pc, ppa, p in rows:
        ks = p["k_score"]
        proj = p["proj"]
        rf = p["recent_form"]
        logs = rf.get("start_logs", [])

        html += f'<div class="board-card outs-card">'
        html += f'<div class="card-header">'
        html += f'<span class="pitcher-nm">{p["pitcher_name"]}</span>'
        html += f'<span class="game-lbl">{p["game"]}</span>'
        html += f'<span class="badge {v_cls}">{verdict}</span>'
        html += '</div>'

        html += f'<div class="outs-stats">'
        html += f'IP avg: <b>{ip_avg:.1f}</b>'
        if ip_std > 0:
            html += f' (±{ip_std:.1f})'
        if recent_era > 0:
            html += f' | ERA(L3): <b>{recent_era:.2f}</b>'
        if last_pc > 0:
            html += f' | Last PC: <b>{last_pc}</b>'
        if ppa > 0:
            html += f' | P/PA: <b>{ppa:.2f}</b>'
        html += '</div>'

        if fade_flags:
            html += f'<div class="flag-row fade-flags">⚠ {" · ".join(fade_flags)}</div>'
        if trust_flags:
            html += f'<div class="flag-row trust-flags">✓ {" · ".join(trust_flags)}</div>'

        if logs:
            html += '<div class="start-logs">'
            for s in logs:
                html += f'<span class="start-log">{s["date"]}: {s["ip"]}IP {s.get("er",0)}ER {s.get("k",0)}K {s.get("pitches",0)}p</span>'
            html += '</div>'

        html += pitch_dropdown(ks.get("top_whiff_pitches", []))
        html += '</div>'
    html += '</div>'
    return html

# ── HR tab ─────────────────────────────────────────────────────────────────────

def _best_prob(g):
    live = [b.get("hr_prob") or 0 for b in g["top_batters"] if b.get("in_lineup") is not False]
    return max(live) if live else 0

def build_hr_tab():
    html = build_leverage_strip()
    html += build_due_strip()
    html += '<div class="board-grid">'
    # Ordered by the best calibrated bat in each matchup. Pitcher vulnerability
    # graded at only a 1.07x lift, so it no longer decides what you see first.
    for g in sorted(hr_board, key=_best_prob, reverse=True):
        v = g["vuln"]
        vuln_score = v["score"]
        vuln_cls = "badge-attack" if v["tier"] == "Attackable" else "badge-avoid" if v["tier"] == "Avoid" else "badge-neutral"

        html += f'<div class="board-card">'
        html += f'<div class="card-header">'
        html += f'<span class="pitcher-nm">{g["pitcher_name"]}</span>'
        html += f'<span class="game-lbl">{g["game"]}</span>'
        html += f'<span class="badge {vuln_cls}">{v["tier"]} ({vuln_score:.0f})</span>'
        html += '</div>'

        if g.get("lineup_confirmed"):
            html += '<div class="lineup-note">✓ lineup confirmed · prob scaled to slot</div>'
        html += pitch_dropdown(g.get("arsenal", []), "Pitcher Arsenal (season)")
        html += pitcher_splits_block(g)

        shown = 0
        for b in g["top_batters"]:
            if b.get("in_lineup") is False:
                continue
            if shown >= 5:
                break
            shown += 1
            hr_sc = b["hr_score"]
            hr_color = f"hsl({min(120,int(hr_sc*1.2))},70%,48%)"
            html += f'<div class="batter-row">'
            html += f'<div class="batter-row-header">'
            html += f'<span class="hr-score-badge" style="border-color:{hr_color}">{hr_sc:.0f}</span>'
            html += lineup_badge(b)
            html += f'<span class="batter-nm">{b["batter_name"]}</span>'
            html += f'<span class="bats-lbl">({b["bats"]})</span>'
            html += chalk_badge(b)
            if b.get("hr_prob", 0) > 0:
                html += f'<span class="prob-lbl">{b["hr_prob"]:.1f}% <span class="odds-lbl">{b.get("implied_odds","")}</span></span>'
            html += '</div>'
            html += f'<div class="batter-stats">'
            html += f'xwOBA: <b>{b.get("xwoba",0):.3f}</b> | HH%: <b>{b.get("hh_pct",0):.0f}%</b> | Barrel: <b>{b.get("brl_bip",0):.1f}%</b>'
            if b.get("hr_form_pct") is not None:
                html += f' | Form: <b>{b["hr_form_pct"]}%{b.get("hr_form_trend","")}</b>'
            html += '</div>'
            html += statcast_block(b)
            tags = b.get("tags", [])
            if tags:
                html += f'<div class="tag-row">{" · ".join(tags[:6])}</div>'
            side = b.get("hand_usage_applied")
            html += batter_pitch_dropdown(b.get("pitch_table", []),
                                          f"vs Arsenal ({side}HB mix, recent)" if side else "vs Pitcher Arsenal")
            html += '</div>'

        html += '</div>'
    html += '</div>'
    return html

# ── NRFI tab ───────────────────────────────────────────────────────────────────

def build_nrfi_tab():
    # sort: STRONG YRFI first, then LEAN YRFI, NEUTRAL, LEAN NRFI, STRONG NRFI
    def sort_key(n):
        nr = n["nrfi"]
        s = nr["score"]
        return -s if nr["verdict"] == "YRFI" else s

    sorted_nrfi = sorted(nrfi_board, key=sort_key)

    html = '<div class="board-grid">'
    for n in sorted_nrfi:
        nr = n["nrfi"]
        score = nr["score"]
        verdict = nr["verdict"]
        conf = nr["confidence"]
        v_cls = "yrfi-card" if verdict == "YRFI" else "nrfi-card" if verdict == "NRFI" else "neut-card"
        badge_cls = "yrfi-badge" if verdict == "YRFI" else "nrfi-badge" if verdict == "NRFI" else "neut-badge"

        sp_a = n.get("sp_away", {})
        sp_h = n.get("sp_home", {})
        off_a = n.get("off_away", {})
        off_h = n.get("off_home", {})

        html += f'<div class="board-card {v_cls}">'
        html += f'<div class="card-header">'
        html += f'<span class="game-title">{n["game"]}</span>'
        html += f'<span class="badge {badge_cls}">{verdict}</span>'
        html += f'<span class="score-val">{score:.0f}/100</span>'
        html += f'<span class="conf-lbl">{conf}</span>'
        html += '</div>'

        comps = nr.get("components", {})
        html += f'<div class="nrfi-pitchers">'
        for team, sp, off, rest in [
            (n["away_team"], sp_a, off_a, n.get("rest_label_away","")),
            (n["home_team"], sp_h, off_h, n.get("rest_label_home",""))
        ]:
            era1 = sp.get("era_1st", 0)
            label = sp.get("label", "")
            r_pg = off.get("r_1st_pg", off.get("r_pg", 0))
            html += f'<div class="nrfi-pitcher-row">'
            html += f'<span class="pitcher-nm">{team}:</span>'
            html += f'<span class="nrfi-era">1st ERA: <b>{era1:.2f}</b></span>'
            if label:
                html += f'<span class="sp-label">{label}</span>'
            if rest:
                html += f'<span class="rest-lbl">{rest}</span>'
            html += '</div>'
        html += '</div>'

        html += f'<div class="nrfi-comps">'
        for k2, v2 in comps.items():
            html += f'<span class="comp-chip">{k2}: {v2:.0f}</span>'
        html += '</div>'

        html += '</div>'
    html += '</div>'
    return html

# ── Hits tab ───────────────────────────────────────────────────────────────────

def build_hits_tab():
    all_batters = []
    for g in hits_board:
        for b in g["top_batters"]:
            all_batters.append((b["hit_score"], b, g))
    all_batters.sort(key=lambda x: x[0], reverse=True)

    html = '<div class="board-grid">'
    for score, b, g in all_batters[:30]:
        tier = b.get("tier", "")
        tier_cls = "badge-elite" if "ELITE" in tier else "badge-threat" if "PLUS" in tier else "badge-manage"
        proj = b.get("proj", {})

        html += f'<div class="board-card hits-card">'
        html += f'<div class="card-header">'
        html += f'<span class="batter-nm">{b["batter_name"]}</span>'
        html += f'<span class="bats-lbl">({b["bats"]})</span>'
        html += f'<span class="game-lbl">vs {g["pitcher_name"]} ({g["game"]})</span>'
        html += f'<span class="badge {tier_cls}">{score:.0f}</span>'
        html += '</div>'

        html += f'<div class="hit-stats">'
        html += f'xBA: <b>{b.get("xba",0):.3f}</b>'
        html += f' | xSLG: <b>{b.get("xslg",0):.3f}</b>'
        if proj.get("proj_hits"):
            html += f' | Proj Hits: <b>{proj["proj_hits"]:.2f}</b>'
        html += f' | {b.get("hand_label","")}'
        html += '</div>'

        tags = b.get("tags", [])
        if tags:
            html += f'<div class="tag-row">{" · ".join(tags[:4])}</div>'

        html += '</div>'
    html += '</div>'
    return html

# ── F5 tab ─────────────────────────────────────────────────────────────────────

def build_f5_tab():
    # sort by edge strength
    def f5_sort(f):
        p4 = f.get("p_o4", 50)
        return -abs(p4 - 50)

    sorted_f5 = sorted(f5_board, key=f5_sort)

    html = '<div class="board-grid">'
    for f in sorted_f5:
        game = f"{f['away_abbr']}@{f['home_abbr']}"
        lam = f.get("lam_total", 0)
        p4 = f.get("p_o4", 50)
        p3 = f.get("p_o3", 0)
        p5 = f.get("p_o5", 0)
        edge = f.get("sp_edge", "EVEN")

        if p4 >= 70:
            call = f"OVER 4.5"
            call_cls = "f5-over"
        elif p4 <= 30:
            call = f"UNDER 4.5"
            call_cls = "f5-under"
        elif p4 > 50:
            call = f"LEAN OVER 4.5"
            call_cls = "f5-lean"
        else:
            call = f"LEAN UNDER 4.5"
            call_cls = "f5-lean"

        html += f'<div class="board-card">'
        html += f'<div class="card-header">'
        html += f'<span class="game-title">{game}</span>'
        html += f'<span class="{call_cls} badge-f5">{call}</span>'
        html += f'<span class="lam-badge">λ {lam:.2f}</span>'
        html += '</div>'

        html += f'<div class="f5-probs">'
        html += f'P(O3.5): <b>{p3:.0f}%</b> | P(O4.5): <b>{p4:.0f}%</b> | P(O5.5): <b>{p5:.0f}%</b>'
        html += '</div>'

        html += f'<div class="f5-pitchers">'
        for side, sp_name, era, ip, k_pct, label in [
            (f["away_abbr"], f["sp_away_name"], f["away_era_l5"], f["away_avg_ip"], f["away_k_pct"], f.get("away_label","")),
            (f["home_abbr"], f["sp_home_name"], f["home_era_l5"], f["home_avg_ip"], f["home_k_pct"], f.get("home_label",""))
        ]:
            html += f'<div class="f5-pitcher"><b>{side}</b> {sp_name}: ERA {era:.2f} | {ip:.1f}IP avg | K%: {k_pct:.0f}% {label}</div>'
        html += '</div>'

        html += '</div>'
    html += '</div>'
    return html

# ── Fantasy tab ────────────────────────────────────────────────────────────────

def build_fantasy_tab():
    top = sorted(fan_board, key=lambda x: x.get("fantasy_score",0), reverse=True)[:25]

    html = '<div class="board-grid">'
    for b in top:
        score = b.get("fantasy_score", 0)
        proj = b.get("proj", {})
        matchup = b.get("matchup", {})
        form = b.get("form", "")
        form_cls = "hot-form" if form == "HOT" else "cold-form" if form == "COLD" else ""

        html += f'<div class="board-card fan-card">'
        html += f'<div class="card-header">'
        html += f'<span class="batter-nm">{b["name"]}</span>'
        html += f'<span class="pos-lbl">{b.get("pos","")}</span>'
        html += f'<span class="game-lbl">{b.get("team","")} vs {b.get("opp","")} ({b.get("game_str","")})</span>'
        html += f'<span class="fan-score">{score:.1f}</span>'
        if form:
            html += f'<span class="{form_cls} form-badge">{form}</span>'
        html += '</div>'

        html += f'<div class="fan-stats">'
        html += f'DK: <b>{proj.get("proj_dk",0):.1f}</b>'
        html += f' | PP: <b>{proj.get("proj_pp",0):.1f}</b>'
        html += f' | Hits: <b>{proj.get("proj_hits",0):.2f}</b>'
        html += f' | TB: <b>{proj.get("proj_tb",0):.2f}</b>'
        html += f' | HR: <b>{proj.get("proj_hr",0):.3f}</b>'
        html += '</div>'

        html += f'<div class="fan-stats">'
        html += f'Contact: <b>{b.get("contact_score",0):.0f}</b>'
        html += f' | Power: <b>{b.get("power_score",0):.0f}</b>'
        html += f' | OBP: <b>{b.get("obp_score",0):.0f}</b>'
        matchup_tier = matchup.get("tier", "")
        if matchup_tier:
            html += f' | Matchup: <b>{matchup_tier}</b>'
        html += '</div>'

        tags = b.get("tags", [])
        if tags:
            html += f'<div class="tag-row">{" · ".join(str(t) for t in tags[:4])}</div>'

        html += '</div>'
    html += '</div>'
    return html

# ── Parlays tab ────────────────────────────────────────────────────────────────

def build_parlays_tab():
    # Generate parlays from best edges
    k_overs = [(p["proj"]["edge_vs_line"], p["pitcher_name"], p["proj"]["line"], p["game"])
               for p in k_board if p["proj"].get("edge_vs_line", 0) > 0.5]
    k_overs.sort(reverse=True)

    k_unders = [(abs(p["proj"]["edge_vs_line"]), p["pitcher_name"], p["proj"]["line"], p["game"])
                for p in k_board if p["proj"].get("edge_vs_line", 0) < -0.5]
    k_unders.sort(reverse=True)

    nrfi_strong = [(n["nrfi"]["score"], n["game"], n["nrfi"]["verdict"])
                   for n in nrfi_board if n["nrfi"]["confidence"] == "STRONG"]
    nrfi_strong.sort(reverse=True)

    f5_overs = [(f["p_o4"], f"{f['away_abbr']}@{f['home_abbr']}", f["lam_total"])
                for f in f5_board if f.get("p_o4", 0) >= 65]
    f5_overs.sort(reverse=True)

    parlays = []

    # Parlay 1: Top K overs
    if len(k_overs) >= 3:
        legs = [f"{n} OVER {l}K ({g})" for _, n, l, g in k_overs[:3]]
        parlays.append(("K OVER STACK", legs, "3-leg"))

    # Parlay 2: Top K unders
    if len(k_unders) >= 3:
        legs = [f"{n} UNDER {l}K ({g})" for _, n, l, g in k_unders[:3]]
        parlays.append(("K UNDER STACK", legs, "3-leg"))

    # Parlay 3: NRFI strong
    if len(nrfi_strong) >= 2:
        legs = [f"{g} {v}" for _, g, v in nrfi_strong[:3]]
        parlays.append(("NRFI/YRFI STRONG PICKS", legs, "2-3 leg"))

    # Parlay 4: F5 overs
    if len(f5_overs) >= 2:
        legs = [f"{g} F5 OVER 4.5 (λ{lam:.2f})" for _, g, lam in f5_overs[:3]]
        parlays.append(("F5 TOTAL OVERS", legs, "2-3 leg"))

    # Parlay 5: Mixed elite plays
    legs5 = []
    if k_overs:
        legs5.append(f"{k_overs[0][1]} OVER {k_overs[0][2]}K")
    if nrfi_strong:
        legs5.append(f"{nrfi_strong[0][1]} {nrfi_strong[0][2]}")
    if f5_overs:
        legs5.append(f"{f5_overs[0][1]} F5 OVER 4.5")
    if len(legs5) >= 2:
        parlays.append(("ELITE VALUE PARLAY", legs5, "SGP-style"))

    # Parlay 6: K under + NRFI (low-scoring game)
    legs6 = []
    if k_unders:
        legs6.append(f"{k_unders[0][1]} UNDER {k_unders[0][2]}K")
    nrfi_only = [(s, g, v) for s, g, v in nrfi_strong if v == "NRFI"]
    if nrfi_only:
        legs6.append(f"{nrfi_only[0][1]} NRFI")
    if len(legs6) >= 2:
        parlays.append(("LOW-SCORING GAME PLAY", legs6, "Correlated"))

    # Parlay 7: HR targets in attackable games
    hr_targets = []
    for g in hr_board:
        live = [x for x in g["top_batters"] if x.get("in_lineup") is not False]
        if g["vuln"]["tier"] == "Attackable" and live:
            b = live[0]
            hr_targets.append((b["hr_score"], b["batter_name"], g["game"]))
    hr_targets.sort(reverse=True)
    if len(hr_targets) >= 3:
        legs7 = [f"{n} HR ({g})" for _, n, g in hr_targets[:3]]
        parlays.append(("HR ATTACK STACK", legs7, "3-leg"))

    # Parlay 8: Fantasy value + K over
    legs8 = []
    if fan_board:
        top_fan = sorted(fan_board, key=lambda x: x.get("fantasy_score",0), reverse=True)
        legs8.append(f"{top_fan[0]['name']} DK value ({top_fan[0]['team']} vs {top_fan[0]['opp']})")
    if k_overs:
        legs8.append(f"{k_overs[0][1]} OVER {k_overs[0][2]}K")
    if len(legs8) >= 2:
        parlays.append(("FANTASY + K COMBO", legs8, "DFS & betting"))

    html = '<div class="parlay-grid">'
    for i, (title, legs, leg_type) in enumerate(parlays, 1):
        html += f'<div class="parlay-card">'
        html += f'<div class="parlay-header"><span class="parlay-num">{i:02d}</span><span class="parlay-title">{title}</span><span class="leg-type">{leg_type}</span></div>'
        html += '<ul class="parlay-legs">'
        for leg in legs:
            html += f'<li>{leg}</li>'
        html += '</ul>'
        html += '</div>'

    html += '</div>'
    return html

# ── MAIN ────────────────────────────────────────────────────────────────────────

games_html = build_games_tab()
k_html = build_k_tab()
outs_html = build_outs_tab()
hr_html = build_hr_tab()
board_html = build_board_tab()
lookup_html = build_lookup_tab()
matchup_html = build_matchup_tab()
nrfi_html = build_nrfi_tab()
hits_html = build_hits_tab()
f5_html = build_f5_tab()
fantasy_html = build_fantasy_tab()
parlays_html = build_parlays_tab()

page = f"""<title>PropStats Sep 16</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Sans+Condensed:wght@400;500;600;700&display=swap">
<style>
/* ── tokens · trading desk ────────────────────────────────────────────
   Near-black ground, square corners, gold as the only accent. Semantic
   green/red stay separate from that accent so state reads on its own. */
:root {{
  --bg: #08090b;
  --surface: #0d0f13;
  --surface2: #12151a;
  --border: #1e2228;
  --line: #14171c;
  --text: #e6e8eb;
  --muted: #6b7480;
  --accent: #e0a83d;
  --green: #35c08a;
  --red: #e0564b;
  --yellow: #e0a83d;
  --orange: #d98548;
  --badge-bg: #12151a;
}}
@media (prefers-color-scheme: light) {{
  :root:not([data-theme="dark"]) {{
    --bg: #f4f2ee;
    --surface: #fffefb;
    --surface2: #eceae4;
    --border: #d6d2c8;
    --line: #e4e1d9;
    --text: #17181a;
    --muted: #6d6a63;
    --accent: #9a6b12;
    --green: #1d7a55;
    --red: #b03a2e;
    --yellow: #9a6b12;
    --orange: #a35f27;
    --badge-bg: #eceae4;
  }}
}}
:root[data-theme="light"] {{
  --bg: #f4f2ee;
  --surface: #fffefb;
  --surface2: #eceae4;
  --border: #d6d2c8;
  --line: #e4e1d9;
  --text: #17181a;
  --muted: #6d6a63;
  --accent: #9a6b12;
  --green: #1d7a55;
  --red: #b03a2e;
  --yellow: #9a6b12;
  --orange: #a35f27;
  --badge-bg: #eceae4;
}}

*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'IBM Plex Sans','IBM Plex Sans Condensed',system-ui,sans-serif;background:var(--bg);color:var(--text);font-size:13.5px;line-height:1.5}}
code,pre,.mono{{font-family:'IBM Plex Mono','DM Mono',ui-monospace,monospace}}

/* ── header ── */
.site-header{{background:var(--surface);border-bottom:1px solid var(--border);padding:14px 20px;display:flex;align-items:center;gap:16px}}
.site-logo{{font-size:22px;font-weight:700;letter-spacing:-0.5px;color:var(--accent)}}
.site-date{{font-size:12px;color:var(--muted);font-family:'DM Mono',monospace}}
.header-stats{{margin-left:auto;display:flex;gap:16px;font-size:12px;color:var(--muted)}}

/* ── tabs ── */
.tab-nav{{display:flex;gap:2px;padding:0 12px;background:var(--surface);border-bottom:1px solid var(--border);overflow-x:auto}}
.tab-btn{{padding:10px 16px;border:none;background:transparent;color:var(--muted);font-family:'IBM Plex Sans Condensed',sans-serif;font-size:13px;font-weight:500;cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap;transition:color 0.15s}}
.tab-btn:hover{{color:var(--text)}}
.tab-btn.active{{color:var(--accent);border-bottom-color:var(--accent)}}
.tab-content{{display:none;padding:16px}}
.tab-content.active{{display:block}}

/* ── cards / grids ── */
.board-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.games-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(380px,1fr));gap:12px}}
.board-card{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:14px;display:flex;flex-direction:column;gap:8px}}

/* ── card header ── */
.card-header{{display:flex;align-items:center;flex-wrap:wrap;gap:6px}}
.game-header{{display:flex;align-items:center;gap:8px;padding:0 0 8px;border-bottom:1px solid var(--border)}}
.game-title{{font-size:15px;font-weight:700;font-family:'DM Mono',monospace;color:var(--accent)}}
.game-lbl{{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace}}
.pitcher-nm{{font-weight:600;font-size:14px}}
.pitcher-tm{{font-size:11px;color:var(--muted)}}
.batter-nm{{font-weight:600}}
.bats-lbl{{font-size:11px;color:var(--muted)}}
.pos-lbl{{font-size:11px;background:var(--badge-bg);padding:1px 5px;border-radius:3px;color:var(--muted)}}
.lam-badge{{font-family:'DM Mono',monospace;font-size:11px;background:var(--surface2);border:1px solid var(--border);padding:2px 6px;border-radius:2px;margin-left:auto}}

/* ── badges ── */
.badge{{font-size:10px;font-weight:600;padding:2px 7px;border-radius:2px;font-family:'DM Mono',monospace;letter-spacing:0.3px;white-space:nowrap}}
.badge-elite{{background:#1a3a4a;color:#4ab8ff;border:1px solid #4ab8ff30}}
.badge-threat{{background:#1a3a2a;color:#3ecf6e;border:1px solid #3ecf6e30}}
.badge-manage{{background:#2a2a1a;color:#c8b82a;border:1px solid #c8b82a30}}
.badge-sparse{{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}}
.badge-attack{{background:#3a1a1a;color:#f05252;border:1px solid #f0525230}}
.badge-avoid{{background:#1a1a3a;color:#7a8aff;border:1px solid #7a8aff30}}
.badge-neutral{{background:var(--badge-bg);color:var(--muted);border:1px solid var(--border)}}
.v-fade{{background:#3a1a1a;color:#f05252;border:1px solid #f0525230}}
.v-trust{{background:#1a3a2a;color:#3ecf6e;border:1px solid #3ecf6e30}}
.v-lean-trust{{background:#1e3028;color:#3ecf6e;border:1px solid #3ecf6e20}}
.v-mixed{{background:#2a2a1a;color:#f5c542;border:1px solid #f5c54230}}
.v-neutral{{background:var(--badge-bg);color:var(--muted);border:1px solid var(--border)}}
.yrfi-badge{{background:#3a1a1a;color:#f05252;border:1px solid #f0525230}}
.nrfi-badge{{background:#1a3a2a;color:#3ecf6e;border:1px solid #3ecf6e30}}
.neut-badge{{background:var(--badge-bg);color:var(--muted);border:1px solid var(--border)}}

/* ── score circle ── */
.score-row{{display:flex;gap:12px;align-items:flex-start}}
.score-circle{{width:52px;height:52px;border-radius:50%;border:2px solid var(--accent);display:flex;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:16px;font-weight:500;flex-shrink:0}}
.proj-block{{flex:1;font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:3px}}

/* ── pitch dropdowns ── */
details.pitch-drop{{margin-top:4px}}
details.pitch-drop summary{{font-size:11px;color:var(--accent);cursor:pointer;list-style:none;padding:3px 0}}
details.pitch-drop summary::-webkit-details-marker{{display:none}}
details.pitch-drop summary::before{{content:"▸ ";font-size:10px}}
details.pitch-drop[open] summary::before{{content:"▾ "}}
.pitch-tbl{{width:100%;border-collapse:collapse;font-size:11px;margin-top:4px;font-family:'DM Mono',monospace}}
.pitch-tbl th{{background:var(--surface2);color:var(--muted);font-weight:500;padding:3px 6px;text-align:right;border-bottom:1px solid var(--border)}}
.pitch-tbl th:first-child{{text-align:left}}
.pitch-tbl td{{padding:3px 6px;border-bottom:1px solid var(--border)40;text-align:right}}
.pitch-tbl td:first-child{{text-align:left}}
.ptype{{color:var(--text);font-weight:500}}
.hot-row{{background:#1a3a2a}}
.cold-row{{background:#2a1a1a}}

/* ── flags ── */
.flag-row{{font-size:11px;padding:3px 6px;border-radius:2px;font-family:'DM Mono',monospace}}
.fade-flags{{background:#2a1a1a;color:#f05252}}
.trust-flags{{background:#1a2a1a;color:#3ecf6e}}

/* ── start logs ── */
.start-logs{{display:flex;flex-wrap:wrap;gap:4px;margin-top:2px}}
.start-log{{font-size:10px;font-family:'DM Mono',monospace;background:var(--surface2);border:1px solid var(--border);padding:2px 6px;border-radius:2px;color:var(--muted)}}

/* ── game card ── */
.game-card{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:14px;display:flex;flex-direction:column;gap:6px}}
.game-row{{display:flex;align-items:center;gap:8px;padding:3px 0}}
.row-label{{font-size:11px;color:var(--muted);min-width:52px;font-family:'DM Mono',monospace}}
.score-val{{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace}}
.conf-lbl{{font-size:10px;color:var(--muted)}}

.pitcher-block{{border-top:1px solid var(--border);padding-top:8px;display:flex;flex-direction:column;gap:4px}}
.pitcher-name-row{{display:flex;align-items:center;flex-wrap:wrap;gap:5px}}
.pitcher-stats{{font-size:12px;color:var(--muted)}}
.k-over{{color:var(--green);font-weight:600}}
.k-under{{color:var(--red);font-weight:600}}
.k-pass{{color:var(--muted)}}

.hr-targets-label{{font-size:11px;color:var(--muted);font-weight:600;border-top:1px solid var(--border);padding-top:6px;margin-top:2px}}
.hr-target-row{{display:flex;align-items:center;gap:6px;font-size:12px}}
.hr-score-badge{{font-family:'DM Mono',monospace;font-size:11px;border:1px solid var(--accent);border-radius:2px;padding:1px 5px;color:var(--accent)}}
.vuln-lbl{{font-size:10px;color:var(--muted);margin-left:auto}}
.hr-tag-row{{font-size:10px;color:var(--muted);padding-left:32px}}

/* ── batter row (HR tab) ── */
.batter-row{{border-top:1px solid var(--border)20;padding-top:6px;display:flex;flex-direction:column;gap:3px}}
.batter-row-header{{display:flex;align-items:center;gap:6px}}
.batter-stats{{font-size:12px;color:var(--muted)}}
.tag-row{{font-size:10px;color:var(--muted)}}
.slot-badge{{font-family:'DM Mono',monospace;font-size:10px;padding:1px 5px;border-radius:3px;border:1px solid var(--border)}}
.slot-in{{color:var(--accent);border-color:var(--accent)}}
.slot-out{{color:var(--muted);text-decoration:line-through}}
.prob-lbl{{margin-left:auto;font-family:'DM Mono',monospace;font-size:12px;font-weight:500}}
.odds-lbl{{color:var(--muted);font-size:10px}}
.lineup-note{{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace}}
.sc-line{{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace}}
.sc-line b{{color:var(--text)}}
.hl-hot{{color:#f0a030;font-weight:600}}
.hl-label{{font-size:10px;color:var(--muted);margin-top:6px;text-transform:uppercase;letter-spacing:0.4px}}
.hl-list{{margin:3px 0 0;padding-left:0;list-style:none;font-size:11px;font-family:'DM Mono',monospace;display:flex;flex-direction:column;gap:2px}}
.hl-date{{color:var(--muted);margin-right:4px}}
.hl-res{{color:var(--muted)}}
.due-strip{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;margin-bottom:14px}}
.due-col{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:10px 12px}}
.due-title{{font-size:12px;font-weight:700;margin-bottom:6px}}
.due-row{{display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 0;border-top:1px solid var(--border)}}
.due-meta{{color:var(--muted);font-size:10px}}
.due-num{{margin-left:auto;font-family:'DM Mono',monospace;font-size:11px;color:#f0a030}}
.chip-row{{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-top:4px}}
.chip-lbl{{font-size:10px;color:var(--muted);font-family:'DM Mono',monospace;margin-right:2px}}
.chip{{font-size:10px;font-family:'DM Mono',monospace;background:var(--badge-bg);border:1px solid var(--border);border-radius:2px;padding:1px 7px}}
.mix-note{{font-size:10px;color:#f0a030;font-family:'DM Mono',monospace;margin-top:3px}}
.tbl-scroll{{overflow-x:auto}}
.fav-b{{color:#3ecf6e}}
.fav-p{{color:#f05252}}
.legend{{font-size:10px;color:var(--muted);margin-top:4px}}
.ck{{font-size:9px;font-family:'DM Mono',monospace;padding:1px 6px;border-radius:2px;letter-spacing:0.3px;white-space:nowrap;border:1px solid}}
.ck-heavy{{background:#3a1a1a;color:#f07070;border-color:#f0707040}}
.ck-chalky{{background:#3a2e1a;color:#e0a83a;border-color:#e0a83a40}}
.ck-bal{{background:var(--badge-bg);color:var(--muted);border-color:var(--border)}}
.ck-lev{{background:#12332a;color:#3ecf9e;border-color:#3ecf9e40}}
.ck-note{{font-size:10px;color:var(--muted);margin-bottom:4px}}
.board-wrap{{background:var(--surface);border:1px solid var(--border);border-radius:2px;overflow:hidden;box-shadow:none}}
.board-bar{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:11px 14px;border-bottom:1px solid var(--border);background:var(--surface2)}}
.board-title{{font-weight:700;font-size:14.5px;letter-spacing:-.2px}}
.board-hint{{font-size:11px;color:var(--muted)}}
.board-filters{{margin-left:auto;display:flex;gap:4px}}
.fbtn{{font-size:11px;font-family:'DM Mono',monospace;background:var(--surface2);color:var(--muted);border:1px solid var(--border);border-radius:2px;padding:3px 10px;cursor:pointer}}
.fbtn:hover{{color:var(--text)}}
.fbtn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.board-scroll{{overflow:auto;max-height:78vh}}
table.board-tbl{{border-collapse:separate;border-spacing:0;width:100%;font-size:11.5px;font-family:'DM Mono',monospace;font-variant-numeric:tabular-nums}}
table.board-tbl th{{position:sticky;top:0;z-index:3;background:var(--surface2);color:var(--muted);font-family:'IBM Plex Sans Condensed',sans-serif;font-size:11px;font-weight:600;letter-spacing:.3px;text-align:right;padding:7px 8px;border-bottom:1px solid var(--border);cursor:pointer;white-space:nowrap;user-select:none}}
table.board-tbl th:hover{{color:var(--text)}}
table.board-tbl th[data-col="batter"],table.board-tbl th[data-col="game"],table.board-tbl th[data-col="pitcher"]{{text-align:left}}
table.board-tbl th[data-col="batter"]{{left:0;z-index:4}}
table.board-tbl td{{padding:6px 8px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}}
table.board-tbl td.sticky-col{{position:sticky;left:0;z-index:2;background:var(--surface);text-align:left;min-width:215px;border-right:1px solid var(--border)}}
table.board-tbl tr.brow:hover td{{background:var(--surface2)}}
table.board-tbl tr.brow:hover td.sticky-col{{background:var(--surface2);box-shadow:inset 2px 0 0 var(--border)}}
table.board-tbl td.dim{{color:var(--muted)}}
.sort-ar{{display:inline-block;width:9px;color:var(--accent)}}
.mini-tags{{display:flex;gap:3px;flex-wrap:wrap;margin-top:2px}}
.mini-tag{{font-size:9px;font-family:'IBM Plex Sans Condensed',sans-serif;background:var(--badge-bg);border:1px solid var(--border);border-radius:2px;padding:0 4px;color:var(--muted)}}
.sig-cell{{text-align:left!important;white-space:nowrap}}
.sg{{display:inline-block;font-family:'IBM Plex Mono',monospace;font-size:8.5px;font-weight:600;letter-spacing:.5px;
  padding:1px 4px;margin-right:3px;border:1px solid;border-radius:1px;line-height:1.35}}
.sg-owns{{color:var(--accent);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 14%,transparent)}}
.sg-fire{{color:var(--red);border-color:var(--red);background:color-mix(in srgb,var(--red) 12%,transparent)}}
.sg-luck{{color:var(--orange);border-color:var(--orange);background:color-mix(in srgb,var(--orange) 12%,transparent)}}
.sg-heat{{color:var(--green);border-color:var(--green);background:color-mix(in srgb,var(--green) 12%,transparent)}}
.sg-due,.sg-surge,.sg-hot{{color:var(--muted);border-color:var(--border)}}
.sg-dom{{color:var(--muted);border-color:var(--border);text-decoration:line-through}}
.zrow{{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:13px;margin-top:10px}}
.zbox h6{{margin:0 0 5px;font-size:9px;letter-spacing:1.2px;text-transform:uppercase;color:var(--muted);font-weight:600}}
.zgrid{{display:grid;grid-template-columns:repeat(5,1fr);gap:2px;max-width:190px}}
.zcell{{aspect-ratio:1.18;display:flex;flex-direction:column;align-items:center;justify-content:center;
  font-family:'IBM Plex Mono',monospace;line-height:1.05;border-radius:1px}}
.zcell b{{font-size:9.5px;font-weight:600}}
.zcell i{{font-style:normal;font-size:7px;opacity:.6}}
.zcell.inz{{outline:1.5px solid var(--text);outline-offset:-1.5px}}
.zcap{{font-size:10px;color:var(--muted);margin-top:5px;line-height:1.45;max-width:200px}}
tr.brow{{cursor:pointer}}
tr.brow.open td{{background:var(--surface2)!important;border-bottom-color:var(--accent)}}
tr.brow.open td.sticky-col{{background:var(--surface2)!important;box-shadow:inset 2px 0 0 var(--accent)}}
tr.drow > td{{padding:0;background:var(--surface2)}}
.dwrap{{padding:12px 14px;border-bottom:2px solid var(--accent)}}
.dhead{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;font-size:13px;margin-bottom:8px}}
.dprob{{margin-left:auto;font-family:'DM Mono',monospace;color:var(--accent);font-weight:500}}
.dgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:14px}}
.dgrid h5{{margin:0 0 4px;font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:600}}
table.dtbl{{width:100%;border-collapse:collapse;font-size:11px;font-family:'DM Mono',monospace;font-variant-numeric:tabular-nums}}
table.dtbl th{{text-align:right;color:var(--muted);font-weight:600;padding:2px 5px;border-bottom:1px solid var(--border);font-size:10px}}
table.dtbl th:first-child,table.dtbl td:first-child{{text-align:left}}
table.dtbl td{{text-align:right;padding:2px 5px;border-bottom:1px solid var(--border)}}
.dctx{{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.6}}
.dctx b{{color:var(--text)}}
.dname{{font-size:15px;font-weight:700;letter-spacing:-.2px}}
.dodds{{margin-left:6px;font-size:11px;color:var(--muted)}}
.pill-row{{display:flex;flex-wrap:wrap;gap:5px;margin:-2px 0 10px}}
.pill-ctx{{font-size:10.5px;font-family:'DM Mono',monospace;background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:2px 9px}}
.pill-ctx.ctx-up{{border-color:#3ecf6e55;background:#3ecf6e12;color:#3ecf6e}}
.pill-ctx.ctx-down{{border-color:#f0525255;background:#f0525212;color:#f05252}}
.pill-ctx b{{color:inherit}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin-bottom:12px}}
.chart{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:8px 10px 6px}}
.chead{{display:flex;justify-content:space-between;align-items:baseline;font-size:10.5px;margin-bottom:6px}}
.chead span:first-child{{font-weight:700;color:var(--text)}}
.chits{{color:var(--muted);font-family:'DM Mono',monospace;font-size:9.5px}}
.cbody{{position:relative;display:flex;align-items:flex-end;gap:5px;height:92px;padding-bottom:14px}}
.cline{{position:absolute;left:0;right:0;height:0;border-top:1px dashed var(--accent);opacity:.8;z-index:2;margin-bottom:14px}}
.cline span{{position:absolute;right:0;top:-12px;font-size:8.5px;font-family:'DM Mono',monospace;color:var(--accent);background:var(--surface);padding:0 3px}}
.cbar{{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;position:relative}}
.cval{{font-size:9.5px;font-family:'DM Mono',monospace;color:var(--muted);margin-bottom:2px;line-height:1}}
.cval.over{{color:#3ecf6e;font-weight:600}}
.ctrack{{width:100%;flex:1;display:flex;align-items:flex-end;min-height:0}}
.cfill{{width:100%;border-radius:3px 3px 0 0}}
.cdate{{position:absolute;bottom:-14px}}
.cfill.over{{background:linear-gradient(180deg,#3ecf6e,#2a9d55)}}
.cfill.under{{background:var(--border)}}
.cdate{{font-size:8.5px;color:var(--muted);margin-top:3px;font-family:'DM Mono',monospace}}
.lk-wrap{{display:flex;flex-direction:column;gap:12px}}
.lk-search{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
#lk-input{{flex:1;min-width:260px;max-width:440px;background:var(--surface);border:1px solid var(--border);border-radius:2px;color:var(--text);font-family:'IBM Plex Sans Condensed',sans-serif;font-size:15px;padding:10px 14px}}
#lk-input:focus{{outline:none;border-color:var(--accent)}}
.lk-count{{font-size:11px;color:var(--muted);font-family:'DM Mono',monospace}}
.lk-card{{min-height:120px}}
.lk-empty{{color:var(--muted);font-size:13px;background:var(--surface);border:1px dashed var(--border);border-radius:2px;padding:26px;text-align:center;max-width:620px}}
.lk-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px;align-items:start}}
.lk-panel{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:12px 14px}}
.lk-panel h4{{margin:0 0 8px;font-size:12px;letter-spacing:.5px;text-transform:uppercase;color:var(--muted);font-weight:600}}
.lk-hero{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:14px 16px;margin-bottom:12px}}
.lk-name{{font-size:24px;font-weight:700;letter-spacing:-.4px}}
.lk-sub{{font-size:13px;color:var(--muted);margin-top:2px}}
.lk-headrow{{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}}
.lk-prob{{margin-left:auto;text-align:right}}
.lk-prob .v{{font-family:'DM Mono',monospace;font-size:28px;font-weight:500;color:var(--accent);line-height:1}}
.lk-prob .o{{font-size:12px;color:var(--muted);font-family:'DM Mono',monospace}}
.zone-wrap{{display:flex;gap:14px;flex-wrap:wrap;align-items:flex-start}}
.zone{{display:grid;grid-template-columns:repeat(5,42px);grid-template-rows:repeat(5,34px);gap:2px}}
.zcell{{border-radius:3px;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:'DM Mono',monospace;font-size:10px;border:1px solid transparent;color:#0d1117}}
.zcell.inzone{{border-color:var(--text)}}
.zcell .zv{{font-weight:600;font-size:11px}}
.zcell .zn{{font-size:8px;opacity:.75}}
.zcell.empty{{background:var(--surface2);color:var(--muted)}}
.zone-legend{{font-size:10px;color:var(--muted);max-width:190px;line-height:1.5}}
.zone-modes{{display:flex;gap:4px;margin-bottom:6px;flex-wrap:wrap}}
.zmode{{font-size:10px;font-family:'DM Mono',monospace;background:var(--surface2);border:1px solid var(--border);border-radius:2px;padding:2px 9px;cursor:pointer;color:var(--muted)}}
.zmode.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
table.lk-tbl{{width:100%;border-collapse:collapse;font-size:11.5px;font-family:'DM Mono',monospace;font-variant-numeric:tabular-nums}}
table.lk-tbl th{{text-align:right;color:var(--muted);font-weight:600;padding:3px 5px;border-bottom:1px solid var(--border);font-size:10px}}
table.lk-tbl th:first-child,table.lk-tbl td:first-child{{text-align:left}}
table.lk-tbl td{{text-align:right;padding:3px 5px;border-bottom:1px solid var(--border)}}
.up{{color:#3ecf6e}} .down{{color:#f05252}}
.lk-kv{{display:flex;justify-content:space-between;font-size:12px;padding:2px 0;border-bottom:1px solid var(--border)}}
.lk-kv span:last-child{{font-family:'DM Mono',monospace}}
.lk-tags{{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}}
.lk-tag{{font-size:10px;background:var(--badge-bg);border:1px solid var(--border);border-radius:3px;padding:1px 6px;color:var(--muted)}}
.mm-bar{{display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;margin-bottom:4px}}
.mm-field{{display:flex;flex-direction:column;gap:3px}}
.mm-field label{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:var(--muted);font-weight:600}}
.mm-field input{{min-width:240px;background:var(--surface);border:1px solid var(--border);border-radius:2px;color:var(--text);font-family:'IBM Plex Sans Condensed',sans-serif;font-size:14px;padding:9px 12px}}
.mm-field input:focus{{outline:none;border-color:var(--accent)}}
.mm-vs{{font-family:'DM Mono',monospace;color:var(--muted);padding-bottom:10px}}
#mm-go{{padding:9px 18px;font-size:13px;border-radius:2px}}

/* ── outs card ── */
.outs-stats{{font-size:12px;color:var(--muted)}}

/* ── NRFI ── */
.nrfi-pitchers{{display:flex;flex-direction:column;gap:3px}}
.nrfi-pitcher-row{{display:flex;align-items:center;gap:6px;font-size:12px;flex-wrap:wrap}}
.nrfi-era{{color:var(--muted)}}
.sp-label{{font-size:10px;color:var(--orange)}}
.rest-lbl{{font-size:10px;color:var(--muted)}}
.nrfi-comps{{display:flex;flex-wrap:wrap;gap:4px}}
.comp-chip{{font-size:10px;font-family:'DM Mono',monospace;background:var(--surface2);border:1px solid var(--border);padding:2px 5px;border-radius:2px;color:var(--muted)}}
.yrfi-card{{border-color:#f0525220}}
.nrfi-card{{border-color:#3ecf6e20}}
.neut-card{{}}

/* ── F5 ── */
.f5-over{{color:var(--green);font-weight:600}}
.f5-under{{color:var(--red);font-weight:600}}
.f5-lean{{color:var(--yellow)}}
.badge-f5{{font-size:11px;padding:3px 8px}}
.f5-probs{{font-size:12px;color:var(--muted);font-family:'DM Mono',monospace}}
.f5-pitchers{{display:flex;flex-direction:column;gap:3px}}
.f5-pitcher{{font-size:12px;color:var(--muted)}}

/* ── Hits ── */
.hit-stats{{font-size:12px;color:var(--muted)}}

/* ── Fantasy ── */
.fan-card{{}}
.fan-score{{font-family:'DM Mono',monospace;font-size:18px;font-weight:500;color:var(--accent);margin-left:auto}}
.fan-stats{{font-size:12px;color:var(--muted)}}
.hot-form{{background:#1a3a2a;color:#3ecf6e;font-size:10px;padding:2px 6px;border-radius:2px;font-weight:700}}
.cold-form{{background:#2a1a1a;color:#f05252;font-size:10px;padding:2px 6px;border-radius:2px;font-weight:700}}
.form-badge{{}}

/* ── Parlays ── */
.parlay-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:12px}}
.parlay-card{{background:var(--surface);border:1px solid var(--border);border-radius:2px;padding:14px}}
.parlay-header{{display:flex;align-items:center;gap:8px;margin-bottom:10px}}
.parlay-num{{font-family:'DM Mono',monospace;font-size:20px;font-weight:500;color:var(--accent);min-width:32px}}
.parlay-title{{font-weight:700;font-size:13px}}
.leg-type{{font-size:10px;color:var(--muted);margin-left:auto;background:var(--surface2);padding:2px 6px;border-radius:2px}}
.parlay-legs{{list-style:none;display:flex;flex-direction:column;gap:5px}}
.parlay-legs li{{font-size:12px;color:var(--muted);padding:5px 10px;background:var(--surface2);border-radius:2px;border-left:2px solid var(--accent)}}

/* ── number coloring ── */
.pos-num{{color:var(--green)}}
.neg-num{{color:var(--red)}}
b{{color:var(--text)}}
</style>

<div class="site-header">
  <div class="site-logo">PropStats</div>
  <div class="site-date mono">Sep 16, 2026 · MLB Slate</div>
  <div class="header-stats">
    <span>{len(k_board)} pitchers</span>
    <span>{len(nrfi_board)} games (NRFI)</span>
    <span>{len(f5_board)} F5 games</span>
    <span>{len(fan_board)} batters</span>
  </div>
</div>

<div class="tab-nav">
  <button class="tab-btn active" onclick="showTab('games')">Games</button>
  <button class="tab-btn" onclick="showTab('strikeouts')">Strikeouts</button>
  <button class="tab-btn" onclick="showTab('outs')">Outs</button>
  <button class="tab-btn" onclick="showTab('hr')">HR Attack</button>
  <button class="tab-btn" onclick="showTab('board')">Big Board</button>
  <button class="tab-btn" onclick="showTab('lookup')">Lookup</button>
  <button class="tab-btn" onclick="showTab('matchup')">Matchup Machine</button>
  <button class="tab-btn" onclick="showTab('nrfi')">NRFI / YRFI</button>
  <button class="tab-btn" onclick="showTab('hits')">Hits</button>
  <button class="tab-btn" onclick="showTab('f5')">F5</button>
  <button class="tab-btn" onclick="showTab('fantasy')">Fantasy</button>
  <button class="tab-btn" onclick="showTab('parlays')">Parlays</button>
</div>

<div id="games" class="tab-content active">{games_html}</div>
<div id="strikeouts" class="tab-content">{k_html}</div>
<div id="outs" class="tab-content">{outs_html}</div>
<div id="hr" class="tab-content">{hr_html}</div>
<div id="board" class="tab-content">{board_html}</div>
<div id="lookup" class="tab-content">{lookup_html}</div>
<div id="matchup" class="tab-content">{matchup_html}</div>
<div id="nrfi" class="tab-content">{nrfi_html}</div>
<div id="hits" class="tab-content">{hits_html}</div>
<div id="f5" class="tab-content">{f5_html}</div>
<div id="fantasy" class="tab-content">{fantasy_html}</div>
<div id="parlays" class="tab-content">{parlays_html}</div>

<script>
function showTab(id) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  event.target.classList.add('active');
}}

(function () {{
  const bRaw = document.getElementById('mm-bat-data'), pRaw = document.getElementById('mm-pit-data');
  if (!bRaw || !pRaw) return;
  const BAT = JSON.parse(bRaw.textContent), PIT = JSON.parse(pRaw.textContent);
  const out = document.getElementById('mm-out');
  const bi = document.getElementById('mm-bat'), pi = document.getElementById('mm-pit');
  const f = (v, d) => (v === null || v === undefined) ? '·' : (+v).toFixed(d);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));

  function heat(v, lo, hi) {{
    if (v === null || v === undefined) return '';
    const t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    return t < 0.5 ? `background:rgba(74,158,255,${{(0.35*(1-t*2)).toFixed(3)}})`
                   : `background:rgba(240,82,82,${{(0.55*((t-0.5)*2)).toFixed(3)}})`;
  }}

  // Mirrors hr_engine._hr_pitch_analysis and calibrate_probabilities
  function evaluate(b, p) {{
    const side = b.bats === 'S' ? (p.throws === 'R' ? 'L' : 'R') : b.bats;
    let raw = 0, weak = 0;
    const rows = [], edges = [], weaks = [];
    const types = new Set([...Object.keys(p.usage || {{}}), ...Object.keys(p.eff || {{}})]);
    types.forEach(pt => {{
      const u = (p.usage[pt] && p.usage[pt][side] !== undefined) ? p.usage[pt][side]
              : (p.eff[pt] ? p.eff[pt].us : 0);
      if (!u || u < 1) return;
      const s = b.splits[pt] || {{}};
      const e = p.eff[pt] || {{}};
      const xw = s.xw, hh = s.hh, wh = s.wh;
      if (xw !== null && xw !== undefined) {{
        const excess = Math.max(0, xw - 0.320);
        const hhMult = hh ? 1 + Math.max(0, hh - 40) / 100 : 1;
        raw += (u / 100) * excess * hhMult;
        if (u >= 12 && wh >= 28 && xw < 0.290) {{
          weak += (u / 100) * (0.290 - xw);
          weaks.push(`${{pt}} (${{f(wh,0)}}% whiff · ${{f(xw,3)}})`);
        }}
        if (u >= 12 && (xw >= 0.380 || hh >= 45)) edges.push(`${{pt}} (${{f(xw,3)}} xwOBA · ${{f(hh,0)}}% HH)`);
      }}
      rows.push({{pt, u, xw, hh, wh, pxw: e.xw, ppa: e.pa}});
    }});
    rows.sort((a, b2) => b2.u - a.u);
    const zone = Math.max(0, Math.min(100, (raw - weak * 0.5) * 800));

    const baseRate = (b.iso > 0 ? b.iso * 0.22 : 0.034);
    const vulnMult = 0.88 + (p.vuln / 100) * 0.26;
    const zoneMult = 0.92 + zone / 100 * 0.22;
    let lam = baseRate * 4.0 * vulnMult * zoneMult;       // neutral park, 4 PA
    let prob = 1 - Math.exp(-Math.max(lam, 0.0005));
    if (prob > 0.15) prob = 0.15 + (prob - 0.15) * 0.55;
    const pct = prob * 100;
    const odds = pct >= 50 ? '-' + Math.round(pct / (100 - pct) * 100)
                           : '+' + Math.round((100 - pct) / pct * 100);
    return {{side, zone, rows, edges, weaks, pct, odds, vulnMult, zoneMult}};
  }}

  function render() {{
    const b = BAT[bi.value], p = PIT[pi.value];
    if (!b || !p) {{
      out.innerHTML = '<div class="lk-empty">Pick a hitter and a pitcher, then hit Evaluate.</div>';
      return;
    }}
    const r = evaluate(b, p);
    const sp = p.sides[r.side] || {{}};
    const same = b.bats !== 'S' && b.bats === p.throws;
    const ptRows = r.rows.map(x =>
      `<tr><td>${{x.pt}}</td><td>${{f(x.u,0)}}%</td><td style="${{heat(x.xw,0.25,0.55)}}">${{f(x.xw,3)}}</td>`
      + `<td>${{f(x.hh,0)}}%</td><td>${{f(x.wh,0)}}%</td><td>${{f(x.pxw,3)}}</td><td>${{f(x.ppa,0)}}%</td></tr>`).join('');
    const grid = b.grid;
    let zoneCells = '';
    if (grid) {{
      for (let i = 0; i < 25; i++) {{
        const c = grid[i] || {{}}, rw = Math.floor(i/5), cl = i%5;
        const inz = rw>=1&&rw<=3&&cl>=1&&cl<=3 ? ' inzone' : '';
        zoneCells += (c.xwoba === null || c.xwoba === undefined)
          ? `<div class="zcell empty${{inz}}">·</div>`
          : `<div class="zcell${{inz}}" style="${{heat(c.xwoba,0.200,0.600)}}"><span class="zv">${{f(c.xwoba,3)}}</span><span class="zn">${{c.n}}</span></div>`;
      }}
    }}
    out.innerHTML = `
      <div class="lk-hero">
        <div class="lk-headrow">
          <div>
            <div class="lk-name">${{esc(b.nm)}} <span class="hand">${{b.bats}}</span>
              <span class="dim" style="font-weight:400">vs</span> ${{esc(p.nm)}} <span class="hand">${{p.throws}}</span></div>
            <div class="lk-sub">${{esc(b.team)}} bat vs ${{esc(p.team)}} arm · vulnerability ${{f(p.vuln,0)}} <i>${{esc(p.vtier)}}</i>
              · ${{same ? 'same-handed' : 'platoon edge to the hitter'}} · mix shown is what he throws to ${{r.side}}HB
              <br><span class="dim">Neutral park and 4 plate appearances assumed — this is the matchup in isolation, not a game projection.</span></div>
          </div>
          <div class="lk-prob"><div class="v">${{f(r.pct,1)}}%</div><div class="o">${{r.odds}} fair · zone ${{f(r.zone,0)}}</div></div>
        </div>
        <div class="lk-tags">${{(b.tags||[]).map(t=>`<span class="lk-tag">${{esc(t)}}</span>`).join('')}}
          ${{(p.tags||[]).map(t=>`<span class="lk-tag">SP: ${{esc(t)}}</span>`).join('')}}</div>
      </div>
      <div class="lk-grid">
        <div class="lk-panel" style="grid-column:1/-1"><h4>Pitch-by-pitch — ${{esc(p.nm)}}'s mix to ${{r.side}}HB</h4>
          ${{ptRows ? `<table class="lk-tbl"><thead><tr><th>Pitch</th><th>Usage</th><th>His xwOBA</th><th>His HH%</th>
             <th>His whiff%</th><th>xwOBA allowed</th><th>Put-away</th></tr></thead><tbody>${{ptRows}}</tbody></table>`
            : '<div class="zone-legend">No overlapping pitch data for this pair.</div>'}}
          ${{r.edges.length ? `<div class="zone-legend" style="margin-top:6px"><b>Edges:</b> ${{r.edges.map(esc).join(' · ')}}</div>` : ''}}
          ${{r.weaks.length ? `<div class="zone-legend"><b>Weak spots:</b> ${{r.weaks.map(esc).join(' · ')}}</div>` : ''}}
        </div>
        ${{grid ? `<div class="lk-panel"><h4>${{esc(b.nm)}} — damage by location</h4>
          <div class="zone">${{zoneCells}}</div>
          <div class="zone-legend" style="margin-top:6px">xwOBA on contact, last 30 days. Catcher's view.</div></div>` : ''}}
        <div class="lk-panel"><h4>${{esc(p.nm)}} vs ${{r.side}}HB — recent</h4>
          <div class="lk-kv"><span>Sample</span><span>${{sp.pa ?? '·'}} PA</span></div>
          <div class="lk-kv"><span>wOBA / SLG</span><span>${{f(sp.woba,3)}} / ${{f(sp.slg,3)}}</span></div>
          <div class="lk-kv"><span>HR allowed</span><span>${{sp.hr ?? '·'}}</span></div>
          <div class="lk-kv"><span>K% / BB%</span><span>${{f(sp.k,1)}}% / ${{f(sp.bb,1)}}%</span></div>
          <div class="lk-kv"><span>Barrel% allowed</span><span>${{f(sp.brl,1)}}%</span></div>
          <div class="lk-kv"><span>Arm slot</span><span>${{esc(p.arm || '·')}}</span></div>
        </div>
        <div class="lk-panel"><h4>${{esc(b.nm)}} — profile</h4>
          <div class="lk-kv"><span>xISO</span><span>${{f(b.iso,3)}}</span></div>
          <div class="lk-kv"><span>xwOBA</span><span>${{f(b.xwoba,3)}}</span></div>
          <div class="lk-kv"><span>Barrel / Hard-hit</span><span>${{f(b.brl,1)}}% / ${{f(b.hh,1)}}%</span></div>
          <div class="lk-kv"><span>Exit velo / Launch</span><span>${{f(b.ev,1)}} / ${{f(b.la,1)}}°</span></div>
          <div class="lk-kv"><span>L10 HR / near-HR</span><span>${{b.w10 ?? '·'}} / ${{b.near ?? '·'}}</span></div>
          <div class="lk-kv"><span>Max EV L5</span><span>${{f(b.maxev,1)}}</span></div>
        </div>
      </div>`;
  }}
  document.getElementById('mm-go').addEventListener('click', render);
  [bi, pi].forEach(el => el.addEventListener('change', () => {{ if (BAT[bi.value] && PIT[pi.value]) render(); }}));
  render();
}})();

(function () {{
  const raw = document.getElementById('lk-data');
  if (!raw) return;
  const DB = JSON.parse(raw.textContent);
  const input = document.getElementById('lk-input');
  const card = document.getElementById('lk-card');
  let current = null, zmode = 'xwoba';

  const f = (v, d) => (v === null || v === undefined) ? '·' : (+v).toFixed(d);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));
  const sign = v => (v === null || v === undefined) ? '' :
    `<span class="${{v > 0 ? 'up' : (v < 0 ? 'down' : '')}}">${{v > 0 ? '+' : ''}}${{(+v).toFixed(1)}}</span>`;

  // Heat scale: cold blue through neutral to hot red, tuned per metric
  const SCALE = {{
    xwoba: [0.200, 0.600, 3, 'xwOBA on contact'],
    ev:    [82,    102,   1, 'average exit velocity'],
    hr:    [0,     4,     0, 'home runs'],
    whiff: [10,    55,    1, 'whiff% on swings'],
  }};

  function heat(v, lo, hi, invert) {{
    if (v === null || v === undefined) return '';
    let t = Math.max(0, Math.min(1, (v - lo) / (hi - lo)));
    if (invert) t = 1 - t;
    const c = t < 0.5
      ? `rgba(74,158,255,${{(0.55 * (1 - t * 2)).toFixed(3)}})`
      : `rgba(240,82,82,${{(0.85 * ((t - 0.5) * 2)).toFixed(3)}})`;
    return `background:${{c}}`;
  }}

  function zoneHTML(grid) {{
    if (!grid) return '<div class="zone-legend">No pitch-level sample for this hitter in the last 30 days.</div>';
    const [lo, hi, dec, label] = SCALE[zmode];
    const invert = zmode === 'whiff';           // whiffing a lot is bad for the hitter
    let cells = '';
    for (let i = 0; i < 25; i++) {{
      const c = grid[i] || {{}};
      const r = Math.floor(i / 5), col = i % 5;
      const inzone = r >= 1 && r <= 3 && col >= 1 && col <= 3 ? ' inzone' : '';
      const v = c[zmode];
      const n = zmode === 'whiff' ? c.swings : c.n;
      if (v === null || v === undefined) {{
        cells += `<div class="zcell empty${{inzone}}">·</div>`;
      }} else {{
        cells += `<div class="zcell${{inzone}}" style="${{heat(v, lo, hi, invert)}}" title="${{label}} ${{f(v,dec)}} on ${{n}}">`
              +  `<span class="zv">${{zmode === 'hr' ? v : f(v, dec)}}</span><span class="zn">${{n}}</span></div>`;
      }}
    }}
    return `<div class="zone-wrap"><div>
      <div class="zone-modes">
        ${{['xwoba','ev','hr','whiff'].map(m => `<span class="zmode${{m===zmode?' active':''}}" data-z="${{m}}">${{
          {{xwoba:'xwOBA', ev:'Exit velo', hr:'HR', whiff:'Whiff%'}}[m]}}</span>`).join('')}}
      </div>
      <div class="zone">${{cells}}</div>
    </div>
    <div class="zone-legend">Catcher's view — top row is up in the zone, right column is inside to a right-handed hitter.
    The outlined 3×3 is the strike zone; the outer ring is chase territory.
    Small number is the sample in that cell. Red is damage, blue is weakness (reversed for whiff%).</div></div>`;
  }}

  function windowRows(w, delta) {{
    const keys = ['L5','L10','L15'].filter(k => w[k]);
    if (!keys.length) return '<div class="zone-legend">No recent Statcast window.</div>';
    let rows = keys.map(k => {{
      const d = w[k];
      return `<tr><td>${{k}}</td><td>${{d.games}}</td><td>${{d.pa}}</td><td>${{d.bbe}}</td><td>${{d.hr}}</td>`
           + `<td>${{d.near_hr}}</td><td>${{f(d.brl_pct,0)}}%</td><td>${{f(d.hh_pct,0)}}%</td>`
           + `<td>${{f(d.avg_ev,1)}}</td><td>${{f(d.max_ev,1)}}</td><td>${{f(d.avg_dist,0)}}</td></tr>`;
    }}).join('');
    const d = delta || {{}};
    const dl = [];
    if (d.ev !== undefined) dl.push(`EV ${{sign(d.ev)}} mph`);
    if (d.brl_pct_rel !== undefined) dl.push(`Barrel ${{sign(d.brl_pct_rel)}}%`);
    if (d.hh_pct_rel !== undefined) dl.push(`Hard-hit ${{sign(d.hh_pct_rel)}}%`);
    if (d.la !== undefined) dl.push(`Launch ${{sign(d.la)}}°`);
    return `<table class="lk-tbl"><thead><tr><th>Win</th><th>G</th><th>PA</th><th>BBE</th><th>HR</th>
      <th>Near</th><th>Brl</th><th>HH</th><th>EV</th><th>Max</th><th>Dist</th></tr></thead><tbody>${{rows}}</tbody></table>
      ${{dl.length ? `<div class="zone-legend" style="margin-top:6px">Last 10 vs his own season baseline — ${{dl.join(' · ')}}</div>` : ''}}`;
  }}

  function render(p) {{
    if (!p) return;
    current = p;
    const s = p.season || {{}}, m = p.sidemix || {{}}, h = p.h2h;
    const slot = p.order ? `#${{p.order}}` : (p.inlu === false ? 'not in lineup' : 'lineup TBD');
    const mix = Object.entries(m.usage || {{}}).map(([k, v]) => `${{k}} ${{v.toFixed(0)}}%`).join(' · ');
    const pt = (p.ptable || []).map(r =>
      `<tr><td>${{r.pitch_type}}</td><td>${{f(r.usage,0)}}%</td><td style="${{heat(r.b_xwoba,0.25,0.55)}}">${{f(r.b_xwoba,3)}}</td>`
      + `<td>${{f(r.b_hh,0)}}%</td><td>${{f(r.b_whiff,0)}}%</td><td>${{f(r.p_xwoba_ag,3)}}</td><td>${{f(r.p_put_away,0)}}%</td></tr>`).join('');
    const hl = (p.hardluck || []).map(x =>
      `<div class="lk-kv"><span>${{x.date}} · ${{esc(x.result)}}${{x.pitch ? ' · ' + x.pitch : ''}}</span>
       <span>${{f(x.ev,1)}} mph · ${{f(x.la,0)}}° · ${{x.dist}} ft</span></div>`).join('');

    card.innerHTML = `
      <div class="lk-hero">
        <div class="lk-headrow">
          <div>
            <div class="lk-name">${{esc(p.nm)}} <span class="hand">${{p.bats}}</span> ${{p.badge || ''}}</div>
            <div class="lk-sub">${{esc(p.team)}} · ${{esc(p.game)}} · ${{slot}} — facing <b>${{esc(p.pit)}}</b> (${{p.pthrows}}),
              vulnerability ${{f(p.vuln,0)}} <i>${{esc(p.vtier)}}</i> · ${{esc(p.venue)}}</div>
          </div>
          <div class="lk-prob"><div class="v">${{f(p.prob,1)}}%</div><div class="o">${{esc(p.odds)}} fair · ${{esc(p.chalk || '')}}</div></div>
        </div>
        <div class="lk-tags">${{(p.tags || []).map(t => `<span class="lk-tag">${{esc(t)}}</span>`).join('')}}</div>
      </div>
      <div class="lk-grid">
        <div class="lk-panel" style="grid-column:1/-1">
          <h4>Damage by location — last 30 days</h4>
          ${{zoneHTML(p.grid)}}
        </div>
        <div class="lk-panel" style="grid-column:1/-1">
          <h4>Recent form</h4>
          ${{windowRows(p.w || {{}}, p.delta)}}
        </div>
        <div class="lk-panel">
          <h4>Season profile</h4>
          <div class="lk-kv"><span>xISO</span><span>${{f(s.iso,3)}}</span></div>
          <div class="lk-kv"><span>xwOBA</span><span>${{f(s.xwoba,3)}}</span></div>
          <div class="lk-kv"><span>Barrel / BIP</span><span>${{f(s.brl,1)}}%</span></div>
          <div class="lk-kv"><span>Hard-hit</span><span>${{f(s.hh,1)}}%</span></div>
          <div class="lk-kv"><span>Exit velo</span><span>${{f(s.ev,1)}} mph</span></div>
          <div class="lk-kv"><span>Launch angle</span><span>${{f(s.la,1)}}°</span></div>
          <div class="lk-kv"><span>Fly ball / Pull</span><span>${{f(s.fb,0)}}% / ${{f(s.pull,0)}}%</span></div>
          <div class="lk-kv"><span>HR per fly ball</span><span>${{f(s.hrfb,1)}}%</span></div>
          <div class="lk-kv"><span>Pull-side wall</span><span>${{esc(p.wall || '·')}}</span></div>
        </div>
        <div class="lk-panel">
          <h4>What he'll see — ${{esc(p.pit)}} vs ${{m.side || '?'}}HB</h4>
          <div class="lk-kv"><span>Recent sample</span><span>${{m.pa || '·'}} PA</span></div>
          <div class="lk-kv"><span>wOBA / SLG allowed</span><span>${{f(m.woba,3)}} / ${{f(m.slg,3)}}</span></div>
          <div class="lk-kv"><span>HR allowed</span><span>${{m.hr ?? '·'}}</span></div>
          <div class="lk-kv"><span>K% / BB%</span><span>${{f(m.k,1)}}% / ${{f(m.bb,1)}}%</span></div>
          <div class="lk-kv"><span>Barrel% allowed</span><span>${{f(m.brl,1)}}%</span></div>
          <div class="lk-kv"><span>Arm slot</span><span>${{esc(p.arm || '·')}} ${{p.armmult ? '×' + f(p.armmult,2) : ''}}</span></div>
          ${{mix ? `<div class="zone-legend" style="margin-top:6px">Mix to this side: ${{mix}}</div>` : ''}}
        </div>
        <div class="lk-panel" style="grid-column:1/-1">
          <h4>Pitch-by-pitch matchup</h4>
          ${{pt ? `<table class="lk-tbl"><thead><tr><th>Pitch</th><th>Usage</th><th>His xwOBA</th><th>His HH%</th>
            <th>His whiff%</th><th>xwOBA allowed</th><th>Put-away</th></tr></thead><tbody>${{pt}}</tbody></table>`
            : '<div class="zone-legend">No arsenal overlap data.</div>'}}
          ${{p.edges.length ? `<div class="zone-legend" style="margin-top:6px"><b>Edges:</b> ${{p.edges.map(esc).join(', ')}}</div>` : ''}}
          ${{p.weak.length ? `<div class="zone-legend"><b>Weak spots:</b> ${{p.weak.map(esc).join(', ')}}</div>` : ''}}
        </div>
        ${{h ? `<div class="lk-panel"><h4>Career vs ${{esc(p.pit)}}</h4>
          <div class="lk-kv"><span>PA</span><span>${{h.pa}}</span></div>
          <div class="lk-kv"><span>Hits / HR</span><span>${{h.h}} / ${{h.hr}}</span></div>
          <div class="lk-kv"><span>BB / K</span><span>${{h.bb}} / ${{h.k}}</span></div>
          <div class="lk-kv"><span>AVG / OBP / SLG</span><span>${{f(h.avg,3)}} / ${{f(h.obp,3)}} / ${{f(h.slg,3)}}</span></div>
          <div class="lk-kv"><span>OPS</span><span>${{f(h.ops,3)}}</span></div></div>` : ''}}
        ${{hl ? `<div class="lk-panel"><h4>Hardest balls that stayed in — last 10</h4>${{hl}}</div>` : ''}}
      </div>`;

    card.querySelectorAll('.zmode').forEach(el => el.addEventListener('click', () => {{
      zmode = el.dataset.z; render(current);
    }}));
  }}

  function tryRender(v) {{
    if (DB[v]) return render(DB[v]);
    const hit = Object.keys(DB).find(k => k.toLowerCase().includes(String(v).toLowerCase()));
    if (hit && String(v).length >= 3) render(DB[hit]);
  }}
  input.addEventListener('change', e => tryRender(e.target.value));
  input.addEventListener('input', e => {{ if (DB[e.target.value]) tryRender(e.target.value); }});
  input.addEventListener('keydown', e => {{ if (e.key === 'Enter') tryRender(e.target.value); }});
}})();

(function () {{
  const tbl = document.getElementById('bigboard');
  if (!tbl) return;
  const tbody = tbl.tBodies[0];
  let sortCol = 'prob', sortDesc = true;

  function paint() {{
    tbl.querySelectorAll('th').forEach(th => {{
      const ar = th.querySelector('.sort-ar');
      if (ar) ar.textContent = th.dataset.col === sortCol ? (sortDesc ? '▼' : '▲') : '';
    }});
  }}

  tbl.querySelectorAll('th').forEach((th, idx) => {{
    th.addEventListener('click', () => {{
      const col = th.dataset.col;
      // numeric columns open descending (best first), text opens ascending
      if (sortCol === col) {{ sortDesc = !sortDesc; }}
      else {{ sortCol = col; sortDesc = th.dataset.type === 'num'; }}
      const num = th.dataset.type === 'num';
      // Sort the player rows only, carrying each detail row along with its parent.
      const pairs = Array.from(tbody.querySelectorAll('tr.brow')).map(r => {{
        const d = r.nextElementSibling;
        return [r, (d && d.classList.contains('drow')) ? d : null];
      }});
      pairs.sort(([a], [b]) => {{
        const av = a.cells[idx].dataset.v, bv = b.cells[idx].dataset.v;
        let r;
        if (num) {{
          const x = parseFloat(av), y = parseFloat(bv);
          const xn = Number.isNaN(x), yn = Number.isNaN(y);
          if (xn && yn) r = 0;            // keep missing values together at the bottom
          else if (xn) return 1;
          else if (yn) return -1;
          else r = x - y;
        }} else {{
          r = String(av || '').localeCompare(String(bv || ''));
        }}
        return sortDesc ? -r : r;
      }});
      pairs.forEach(([r, d]) => {{ tbody.appendChild(r); if (d) tbody.appendChild(d); }});
      paint();
    }});
  }});

  document.querySelectorAll('.fbtn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      document.querySelectorAll('.fbtn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.dataset.f;
      Array.from(tbody.rows).forEach(r => {{
        if (r.classList.contains('drow')) {{ r.hidden = true; return; }}
        r.hidden = !(f === 'all' || r.dataset.chalk === f);
        r.classList.remove('open');
      }});
    }});
  }});

  // Click a player row to open his recent form underneath it
  const f1 = (v, d) => (v === null || v === undefined) ? '·' : (+v).toFixed(d);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));

  // PrizePicks-style column chart: one bar per game, dashed line at the threshold.
  // `floor` lifts the baseline for rate stats — an exit-velo chart drawn from zero
  // makes 108 and 112 look identical, so those start just under the line instead.
  function chart(log, key, label, line, fmt, floor) {{
    if (!log || !log.length) return '';
    const vals = log.map(g => g[key] ?? 0);
    const base = floor !== undefined ? floor : 0;
    const top = Math.max(line * 1.25, ...vals) * 1.08;
    const span = Math.max(top - base, 0.001);
    const pct = v => Math.max(4, Math.min(100, (v - base) / span * 100));
    const bars = log.map((g, i) => {{
      const v = vals[i], over = v > line;
      return `<div class="cbar" title="${{g.date}} — ${{fmt ? fmt(v) : v}}">
        <div class="cval ${{over ? 'over' : ''}}">${{v ? (fmt ? fmt(v) : v) : '–'}}</div>
        <div class="ctrack"><div class="cfill ${{over ? 'over' : 'under'}}" style="height:${{v ? pct(v) : 2}}%"></div></div>
        <div class="cdate">${{g.date}}</div></div>`;
    }}).join('');
    const hits = vals.filter(v => v > line).length;
    return `<div class="chart">
      <div class="chead"><span>${{label}}</span>
        <span class="chits">${{hits}}/${{log.length}} over ${{fmt ? fmt(line) : line}}</span></div>
      <div class="cbody">
        <div class="cline" style="bottom:${{pct(line)}}%"><span>${{fmt ? fmt(line) : line}}</span></div>
        ${{bars}}
      </div>
    </div>`;
  }}

  // Plate grids: his damage, the pitcher's location, and where the two collide
  function zgrid(mode, bg, pg) {{
    let out = '';
    for (let i = 0; i < 25; i++) {{
      const b = (bg || [])[i] || {{}}, q = (pg || [])[i] || {{}};
      const r = Math.floor(i / 5), c = i % 5;
      const inz = (r >= 1 && r <= 3 && c >= 1 && c <= 3) ? ' inz' : '';
      let t = null, lab = '—', sub = '';
      if (mode === 'bat') {{
        const v = b.xwoba;
        if (v != null) {{ t = Math.max(0, Math.min(1, (v - 0.200) / 0.400));
          lab = v.toFixed(3).slice(1); sub = b.n ? String(b.n) : ''; }}
      }} else if (mode === 'loc') {{
        const v = q.loc_pct || 0;
        if (v) {{ t = Math.max(0, Math.min(1, v / 9)); lab = v.toFixed(1); }}
      }} else {{
        const lv = q.loc_pct || 0, bv = b.xwoba;
        const s = (bv == null) ? 0 : lv * Math.max(0, bv - 0.320);
        if (s > 0) {{ t = Math.max(0, Math.min(1, s / 1.6)); lab = s.toFixed(2);
          sub = b.hr ? b.hr + 'HR' : ''; }}
      }}
      const hot = mode === 'risk' ? 'var(--green)' : (mode === 'loc' ? 'var(--accent)' : 'var(--red)');
      let style = 'background:var(--surface2)';
      if (t != null) {{
        style = t >= 0.5
          ? `background:color-mix(in srgb,${{hot}} ${{Math.round(t*88)}}%,var(--surface2))`
          : `background:color-mix(in srgb,#2f6fa8 ${{Math.round((0.5-t)*2*50)}}%,var(--surface2))`;
      }}
      out += `<div class="zcell${{inz}}" style="${{style}}"><b>${{lab}}</b><i>${{sub}}</i></div>`;
    }}
    return out;
  }}

  function detailHTML(p) {{
    const log = p.log || [];
    const names = {{hand: 'vs ' + ((p.ctx && p.ctx.hand && p.ctx.hand.code === 'vl') ? 'LHP' : 'RHP'),
                   time: (p.ctx_night === 'day' ? 'day games' : 'night games'),
                   site: p.ctx_home ? 'at home' : 'on the road'}};
    const ctx = p.ctx ? Object.keys(names).filter(k => p.ctx[k]).map(k => {{
      const v = p.ctx[k];
      const cls = (!v.thin && Math.abs(v.edge) >= 0.060) ? (v.edge > 0 ? 'ctx-up' : 'ctx-down') : '';
      return `<span class="pill-ctx ${{cls}}">${{names[k]}} <b>${{f1(v.ops,3)}}</b>`
           + `<span class="dim"> ${{v.edge > 0 ? '+' : ''}}${{Math.round(v.edge*1000)}}</span></span>`;
    }}).join('') : '';

    // Matchup archetypes — what kind of arm, what kind of bat, and the fit
    const ap = p.arch_p, fams = p.fams || {{}};
    let fit = '';
    if (ap && Object.keys(fams).length) {{
      const order = ['fastball','breaking','offspeed'];
      fit = order.filter(k => fams[k] && ap.fam[k] >= 8).map(k => {{
        const share = ap.fam[k], xw = fams[k].xwoba;
        const good = xw >= 0.380, bad = xw <= 0.280;
        return `<tr><td>${{k}}</td><td>${{f1(share,0)}}%</td>
          <td class="${{good ? 'ctx-up' : (bad ? 'ctx-down' : '')}}">${{f1(xw,3)}}</td>
          <td class="dim">${{good ? 'he hurts it' : (bad ? 'it beats him' : 'neutral')}}</td></tr>`;
      }}).join('');
    }}

    const h2 = p.h2h;
    const wrows = [['L5',p.w5],['L15',p.w15]].filter(x => x[1]).map(([lab,w]) =>
      `<tr><td>${{lab}}</td><td>${{w.games}}</td><td>${{w.pa}}</td><td>${{w.hr}}</td>`
      + `<td>${{w.near_hr}}</td><td>${{f1(w.brl_pct,0)}}%</td><td>${{f1(w.hh_pct,0)}}%</td>`
      + `<td>${{f1(w.avg_ev,1)}}</td><td>${{f1(w.max_ev,1)}}</td></tr>`).join('');

    const logRows = log.length ? log.map(g =>
      `<tr><td>${{g.date}}</td><td>${{g.h}}-for-${{g.ab}}</td><td>${{g.hr}}</td><td>${{g.tb}}</td>`
      + `<td>${{g.bb}}</td><td>${{g.k}}</td><td>${{g.hard}}/${{g.bbe}}</td>`
      + `<td>${{f1(g.avg_ev,1)}}</td><td>${{f1(g.max_ev,1)}}</td><td>${{g.best_dist ?? '·'}}</td></tr>`).join('')
      : '<tr><td colspan="10" class="dim">No pitch-level games in the last 30 days.</td></tr>';

    return `<div class="dwrap">
      <div class="dhead">
        <span class="dname">${{esc(p.batter)}}</span><span class="hand">${{p.bats}}</span>
        ${{p.order ? `<span class="slot-badge slot-in">#${{p.order}}</span>` : ''}}
        <span class="dim">${{esc(p.game)}} · facing ${{esc(p.pitcher)}}</span>
        <span class="dprob">${{f1(p.prob,1)}}%<span class="dodds">${{esc(p.odds||'')}}</span></span>
      </div>
      ${{ctx ? `<div class="pill-row">${{ctx}}</div>` : ''}}

      ${{(p.bgrid || p.pgrid) ? `<div class="zrow">
        <div class="zbox"><h6>Where he does damage</h6><div class="zgrid">${{zgrid('bat', p.bgrid, p.pgrid)}}</div>
          <div class="zcap">xwOBA on contact, last 30 days. Small figure is batted balls in that cell.</div></div>
        <div class="zbox"><h6>Where ${{esc(p.pitcher)}} lives</h6><div class="zgrid">${{zgrid('loc', p.bgrid, p.pgrid)}}</div>
          <div class="zcap">Share of his pitches to ${{p.side}}HB landing in each cell.</div></div>
        <div class="zbox"><h6>Overlap · the danger</h6><div class="zgrid">${{zgrid('risk', p.bgrid, p.pgrid)}}</div>
          <div class="zcap">Location share multiplied by the damage he does there — bright cells are pitches thrown into his power.</div></div>
      </div>` : ''}}

      <div class="charts">
        ${{chart(log,'tb','Total bases',1.5)}}
        ${{chart(log,'hard','Hard-hit balls (95+)',0.5)}}
        ${{chart(log,'max_ev','Max exit velo',104, v => v ? v.toFixed(0) : '–', 88)}}
      </div>

      <div class="dgrid">
        <div>
          <h5>Matchup type</h5>
          <div class="dctx"><b>The arm:</b> ${{ap ? esc(ap.label) : 'not enough recent data'}}
            ${{ap && ap.lead ? `<span class="dim">— leads with ${{ap.lead}} at ${{f1(ap.lead_usage,0)}}% to ${{p.side}}HB</span>` : ''}}</div>
          <div class="dctx"><b>The bat:</b> ${{esc(p.arch_b || '')}}</div>
          ${{ap && ap.pa ? `<div class="dctx"><b>vs ${{p.side}}HB this window:</b> ${{ap.pa}} PA ·
            ${{f1(ap.woba,3)}} wOBA · ${{f1(ap.slg,3)}} SLG · ${{ap.hr}} HR · ${{f1(ap.k,0)}}% K · ${{f1(ap.brl,1)}}% barrel</div>` : ''}}
          ${{fit ? `<table class="dtbl" style="margin-top:6px"><thead><tr><th>Pitch family</th><th>He throws</th>
            <th>Hitter xwOBA</th><th></th></tr></thead><tbody>${{fit}}</tbody></table>` : ''}}
          ${{h2 ? `<div class="dctx" style="margin-top:6px"><b>Head to head:</b> ${{h2.h}}-for-${{h2.ab}},
            ${{h2.hr}} HR, ${{h2.bb}} BB, ${{h2.k}} K in ${{h2.pa}} PA <span class="dim">(${{f1(h2.ops,3)}} OPS)</span></div>` : ''}}
        </div>
        <div>
          <h5>Last 5 games</h5>
          <table class="dtbl"><thead><tr><th>Date</th><th>AB</th><th>HR</th><th>TB</th><th>BB</th><th>K</th>
            <th>Hard</th><th>EV</th><th>Max</th><th>Best</th></tr></thead><tbody>${{logRows}}</tbody></table>
          <h5 style="margin-top:8px">Rolling windows</h5>
          <table class="dtbl"><thead><tr><th>Win</th><th>G</th><th>PA</th><th>HR</th><th>Near</th>
            <th>Brl</th><th>HH</th><th>EV</th><th>Max</th></tr></thead>
            <tbody>${{wrows || '<tr><td colspan="9" class="dim">·</td></tr>'}}</tbody></table>
          ${{(p.edges||[]).length ? `<div class="dctx"><b>Edges:</b> ${{p.edges.map(esc).join(', ')}}</div>` : ''}}
          ${{(p.weak||[]).length ? `<div class="dctx"><b>Weak spots:</b> ${{p.weak.map(esc).join(', ')}}</div>` : ''}}
          ${{(p.sig||[]).length ? `<div class="dctx"><b>Signals firing:</b> ${{p.sig.map(esc).join(' · ')}}</div>` : ''}}
        </div>
      </div></div>`;
  }}

  tbody.addEventListener('click', ev => {{
    const row = ev.target.closest('tr.brow');
    if (!row) return;
    const det = row.nextElementSibling;
    if (!det || !det.classList.contains('drow')) return;
    const open = !det.hidden;
    if (open) {{ det.hidden = true; row.classList.remove('open'); return; }}
    if (!det.dataset.built) {{
      det.firstElementChild.innerHTML = detailHTML(JSON.parse(row.dataset.detail));
      det.dataset.built = '1';
    }}
    det.hidden = false;
    row.classList.add('open');
  }});

  paint();
}})();
</script>
"""

with open(OUT, "w") as f:
    f.write(page)

print(f"Written: {OUT} ({os.path.getsize(OUT)//1024}KB)")
