import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import numpy as np, json

BG    = "#0f1117"
CARD  = "#1a1d2e"
ACCENT= "#3b82f6"
GREEN = "#10b981"
RED   = "#ef4444"
YELLOW= "#f59e0b"
TEXT  = "#e2e8f0"
MUTED = "#94a3b8"
PURPLE= "#8b5cf6"
ORANGE= "#f97316"

plt.rcParams.update({
    "font.family":"DejaVu Sans","text.color":TEXT,
    "axes.labelcolor":TEXT,"xtick.color":MUTED,"ytick.color":MUTED,
    "figure.facecolor":BG,"axes.facecolor":CARD,
    "axes.edgecolor":"#2d3748","grid.color":"#2d3748","grid.alpha":0.5,
})

with open("/tmp/rows_final.json") as f: rows = json.load(f)

# Filter small samples for display (≥80 PA)
qual = [r for r in rows if r["pa"] >= 80]
qual_hr = sorted(qual, key=lambda x: x["prob"], reverse=True)
qual_fan = sorted(rows, key=lambda x: x["fant"], reverse=True)

# Fantasy: filter meaningful matchups (suppress both pitchers OR good pitcher)
# Use a mix of OPS + HR prob + season production rates
fantasy_rows = []
seen_f = set()
for r in sorted(rows, key=lambda x: float(x["ops"])*0.3 + x["prob"]*25 + (x["rbi"]/max(x["pa"],1))*5 + (x["bb"]/max(x["pa"],1))*4, reverse=True):
    if r["name"] not in seen_f:
        seen_f.add(r["name"])
        fantasy_rows.append(r)

top15_hr  = qual_hr[:15]
top12_fan = fantasy_rows[:12]

# ── Parlay picks (established bats ≥100 PA, prob ≥18%) ──────────────────────
parlay_pool = [r for r in qual_hr if r["pa"] >= 100 and r["prob"] >= 0.18]
parlay = parlay_pool[:3]

fig = plt.figure(figsize=(24, 32), facecolor=BG)
fig.suptitle("PropStats — June 3, 2026  |  Full Slate Analysis  (15 Games)",
             fontsize=22, fontweight="bold", color=TEXT, y=0.983)

gs = gridspec.GridSpec(5, 2, figure=fig, hspace=0.42, wspace=0.22,
                       left=0.03, right=0.98, top=0.960, bottom=0.015)

# ── Row 0: HR Prob Bar Chart ──────────────────────────────────────────────────
ax0 = fig.add_subplot(gs[0, :])
ax0.set_facecolor(CARD)
ax0.set_title("HR PROBABILITY LEADERBOARD — June 3 Top 15 (≥80 PA, recalibrated model)",
              fontsize=13, fontweight="bold", color=TEXT, pad=10)

names  = [f"{r['name']}  ({r['team']} vs {r['vs'].split()[0]})" for r in top15_hr]
probs  = [r["prob"]*100 for r in top15_hr]
parks  = [r["park"] for r in top15_hr]
clrs   = [YELLOW if p>=23 else GREEN if p>=18 else ACCENT for p in probs]

y = np.arange(len(names))
bars = ax0.barh(y, probs, color=clrs, height=0.62, alpha=0.88)
ax0.set_yticks(y)
ax0.set_yticklabels(names, fontsize=9.5)
ax0.set_xlabel("HR Probability %", fontsize=10, color=MUTED)
ax0.set_xlim(0, 30)
ax0.invert_yaxis()
ax0.axvline(x=18, color=RED, linewidth=1.1, linestyle="--", alpha=0.55, label="18% threshold")
ax0.legend(loc="lower right", fontsize=8.5, facecolor=CARD, edgecolor="#2d3748", labelcolor=TEXT)
for bar, prob, r in zip(bars, probs, top15_hr):
    pl = "✓" if r["platoon"] else ""
    ax0.text(bar.get_width()+0.2, bar.get_y()+bar.get_height()/2,
             f"{prob:.1f}%  {pl}", va="center", fontsize=9.5,
             fontweight="bold", color=YELLOW if prob>=23 else GREEN if prob>=18 else TEXT)

# ── Row 1L: 3-leg Parlay ──────────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[1, 0])
ax1.set_facecolor(CARD); ax1.set_axis_off()
ax1.set_title("BEST 3-LEG HR PARLAY — June 3", fontsize=13, fontweight="bold", color=YELLOW, pad=10)

parlay_meta = [
    (parlay[0]["name"], f"{parlay[0]['team']} vs {parlay[0]['vs']}", f"{parlay[0]['prob']*100:.1f}%", "+185"),
    (parlay[1]["name"], f"{parlay[1]['team']} vs {parlay[1]['vs']}", f"{parlay[1]['prob']*100:.1f}%", "+260"),
    (parlay[2]["name"], f"{parlay[2]['team']} vs {parlay[2]['vs']}", f"{parlay[2]['prob']*100:.1f}%", "+290"),
]
y_s = 0.88
for i,(nm,mtch,pct,ml) in enumerate(parlay_meta):
    y = y_s - i*0.27
    rect = FancyBboxPatch((0.03,y-0.10),0.94,0.20,boxstyle="round,pad=0.01",
                          linewidth=1.5,edgecolor=GREEN,facecolor="#0d2818",
                          transform=ax1.transAxes,zorder=2)
    ax1.add_patch(rect)
    ax1.text(0.08,y+0.04,f"LEG {i+1}  {nm}",fontsize=11,fontweight="bold",
             color=GREEN,transform=ax1.transAxes,va="center")
    ax1.text(0.08,y-0.04,mtch,fontsize=9,color=MUTED,transform=ax1.transAxes,va="center")
    ax1.text(0.80,y+0.04,pct,fontsize=13,fontweight="bold",
             color=YELLOW,transform=ax1.transAxes,va="center",ha="center")
    ax1.text(0.80,y-0.04,ml,fontsize=10,color=MUTED,transform=ax1.transAxes,va="center",ha="center")

yb = y_s - 3*0.27 - 0.02
rect2 = FancyBboxPatch((0.03,yb-0.09),0.94,0.17,boxstyle="round,pad=0.01",
                       linewidth=2,edgecolor=YELLOW,facecolor="#1a1200",
                       transform=ax1.transAxes,zorder=2)
ax1.add_patch(rect2)
ax1.text(0.50,yb,"Combined: ~+2,900  |  GABP + Fedde + Gallen on deck",
         fontsize=10,fontweight="bold",color=YELLOW,
         transform=ax1.transAxes,va="center",ha="center")

# ── Row 1R: Hot Pitcher Matchup Table ────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, 1])
ax2.set_facecolor(CARD); ax2.set_axis_off()
ax2.set_title("TODAY'S PITCHER VULNERABILITY RANKINGS", fontsize=13, fontweight="bold", color=TEXT, pad=10)

pitch_rows = [
    ("Erick Fedde",      "CWS","2.19","5.40","EXTREME","MIN bats — Buxton"),
    ("Chris Paddack",    "CIN","1.76","7.63","HIGH",   "KC/CIN — GABP park"),
    ("Grant Holmes",     "ATL","1.74","3.95","HIGH",   "TOR lineup"),
    ("Jeffrey Springs",  "ATH","1.63","4.07","HIGH",   "CHC platoon edge"),
    ("Michael Lorenzen", "COL","1.57","7.22","HIGH",   "LAA bats"),
    ("Zac Gallen",       "AZ", "1.52","5.16","HIGH",   "LAD murderers row"),
    ("Colin Rea",        "CHC","1.37","4.70","MED",    "ATH power"),
    ("Andre Pallante",   "STL","1.24","4.19","MED",    "TEX bats"),
    ("Gavin Williams",   "CLE","1.06","3.07","LOW",    "NYY bats"),
    ("Freddy Peralta",   "NYM","1.09","3.55","LOW",    "SEA Raley"),
]
px = [0.02,0.26,0.38,0.47,0.60,0.76]
ph = ["Pitcher","Team","HR/9","ERA","Risk","Key Target"]
for j,h in enumerate(ph):
    ax2.text(px[j],0.95,h,fontsize=8.5,fontweight="bold",color=MUTED,transform=ax2.transAxes,va="top")
ax2.plot([0.02,0.98],[0.90,0.90],color="#2d3748",linewidth=1,transform=ax2.transAxes)
risk_c = {"EXTREME":RED,"HIGH":ORANGE,"MED":YELLOW,"LOW":MUTED}
for i,row in enumerate(pitch_rows):
    y = 0.85 - i*0.085
    for j,val in enumerate(row):
        c = risk_c.get(val,TEXT) if j==4 else TEXT
        fw = "bold" if j==4 else "normal"
        ax2.text(px[j],y,val,fontsize=8.5,color=c,fontweight=fw,transform=ax2.transAxes,va="top")

# ── Row 2: Per-Game HR Grid (compact) ────────────────────────────────────────
ax3 = fig.add_subplot(gs[2, :])
ax3.set_facecolor(CARD); ax3.set_axis_off()
ax3.set_title("TOP BATS BY GAME  (★ ≥20% HR prob)", fontsize=13, fontweight="bold", color=ACCENT, pad=10)

game_data = [
    ("CWS@MIN","Fedde 2.19","Buxton 25%★","Kreidler 22%★","Lee 17%","Clemens 16%"),
    ("KC@CIN","Paddack 1.76","Bleday 24%★","Lowe 21%★","Massey 20%","Jensen 18%"),
    ("LAD@AZ","Gallen 1.52","Muncy 25%★","Ward 25%★","Betts 21%★","Pages 21%★"),
    ("ATH@CHC","Springs 1.63","Happ 25%★✓","Conforto 21%★✓","Suzuki 18%✓","Rooker 16%"),
    ("TOR@ATL","Holmes 1.74","Okamoto 21%★","Olson 16%✓","Harris 16%✓","Sanchez 15%"),
    ("COL@LAA","Lorenzen 1.57","Trout 19%","Meckler 16%","Peraza 15%","Soler 14%"),
    ("CLE@NYY","Williams 1.06","Rice 21%★","Judge 19%","Goldschmidt 14%","McMahon 11%"),
    ("NYM@SEA","Peralta 1.09","Raley 19%","Soto 14%","Canzone 12%","Rodriguez 11%"),
    ("TEX@STL","Pallante 1.24","Walker 14%✓","Velazquez 16%✓","Pederson 12%","Burger 12%"),
    ("SD@PHI","Sanchez 0.34","Schwarber 16%","Harper 10%","FADE SD bats",""),
    ("PIT@HOU","Arrighetti 0.38","Alvarez 15%","C.Walker 13%","FADE PIT bats",""),
    ("DET@TB","Melton 0.00","Dingler 7%","Carpenter 7%","NOTE: Melton dominant",""),
    ("MIA@WSH","Both <0.70 HR/9","James Wood 10%","Hicks 9%","FADE HRs","Fantasy ✓"),
    ("BAL@BOS","Tolle 0.65","Basallo 10%✓","Henderson 9%✓","Low HR risk",""),
    ("SF@MIL","Webb 0.69","Schmitt 17%","Adames 10%","MIL TBD",""),
]

gx = [0.0, 0.13, 0.27, 0.41, 0.55, 0.69]
gh = ["Game","Pitcher","#1 Pick","#2 Pick","#3 Pick","#4 Pick"]
for j,h in enumerate(gh):
    ax3.text(gx[j]+0.005,0.975,h,fontsize=8,fontweight="bold",color=MUTED,transform=ax3.transAxes,va="top")
ax3.plot([0.0,1.0],[0.935,0.935],color="#2d3748",linewidth=1,transform=ax3.transAxes)

for i,row in enumerate(game_data):
    y = 0.90 - i*0.058
    bg = "#1e2235" if i%2==0 else CARD
    rect = FancyBboxPatch((0.0,y-0.025),1.0,0.05,boxstyle="square,pad=0",linewidth=0,
                          facecolor=bg,transform=ax3.transAxes,zorder=1)
    ax3.add_patch(rect)
    for j,val in enumerate(row):
        c = YELLOW if "★" in val else GREEN if "✓" in val else RED if "FADE" in val else MUTED if "NOTE" in val else TEXT
        ax3.text(gx[j]+0.005,y+0.005,val,fontsize=8,color=c,transform=ax3.transAxes,va="center",zorder=2)

# ── Row 3: Fantasy Top 12 ─────────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[3, :])
ax4.set_facecolor(CARD); ax4.set_axis_off()
ax4.set_title("FANTASY TOP 12 BATTERS — June 3  (OPS + HR% + R/RBI/BB/SB rates)",
              fontsize=13, fontweight="bold", color=PURPLE, pad=10)

fan_display = [
    ("James Wood",       "WSH","Max Meyer",     "16%",".272",".952","50","39","10","A+"),
    ("Juan Soto",        "NYM","G.Kirby",        "14%",".301",".982","38","37","8", "A+"),
    ("Byron Buxton",     "MIN","Erick Fedde",    "25%",".258",".875","43","55","10","A+"),
    ("JJ Bleday",        "CIN","S.Kolek",        "24%",".301","1.053","27","30","2","A"),
    ("Ian Happ",         "CHC","J.Springs",      "25%",".230",".818","36","42","7", "A"),
    ("Yordan Alvarez",   "HOU","Skenes",          "16%",".301","1.050","41","58","2", "A"),
    ("Nathaniel Lowe",   "CIN","S.Kolek",        "21%",".258",".879","29","34","0", "A-"),
    ("Michael Harris II","ATL","P.Corbin",       "16%",".307",".868","35","47","11","A-"),
    ("Andy Pages",       "LAD","Zac Gallen",     "21%",".295",".883","41","49","2", "A-"),
    ("Aaron Judge",      "NYY","G.Williams",     "19%",".248",".908","37","49","2", "B+"),
    ("CJ Abrams",        "WSH","Max Meyer",       "8%",".294",".926","37","47","9", "B+"),
    ("Max Muncy",        "LAD","Zac Gallen",     "25%",".254",".878","29","39","1", "B+"),
]
fh = ["#","Batter","Team","Opp","HR%","AVG","OPS","BB","RBI","SB","Grade"]
fx = [0.01,0.05,0.19,0.25,0.33,0.40,0.47,0.56,0.62,0.69,0.76]
grade_c = {"A+":YELLOW,"A":GREEN,"A-":GREEN,"B+":ACCENT,"B":ACCENT}

for j,h in enumerate(fh):
    ax4.text(fx[j],0.96,h,fontsize=8.5,fontweight="bold",color=MUTED,transform=ax4.transAxes,va="top")
ax4.plot([0.01,0.98],[0.91,0.91],color="#2d3748",linewidth=1,transform=ax4.transAxes)

for i,row in enumerate(fan_display):
    y = 0.87 - i*0.073
    bg = "#1e2235" if i%2==0 else CARD
    rect = FancyBboxPatch((0.01,y-0.030),0.97,0.060,boxstyle="square,pad=0",linewidth=0,
                          facecolor=bg,transform=ax4.transAxes,zorder=1)
    ax4.add_patch(rect)
    vals = [str(i+1)] + list(row)
    for j,val in enumerate(vals):
        c = grade_c.get(val,TEXT) if j==10 else YELLOW if j==10 else TEXT
        if j==10: c = grade_c.get(val, MUTED)
        fw = "bold" if j in(0,10) else "normal"
        ax4.text(fx[j],y+0.005,val,fontsize=8.5,color=c,fontweight=fw,transform=ax4.transAxes,va="center",zorder=2)

# ── Row 4L: Game of the Day — MIN vs Fedde ───────────────────────────────────
ax5 = fig.add_subplot(gs[4, 0])
ax5.set_facecolor(CARD); ax5.set_axis_off()
ax5.set_title("GAME OF THE DAY  —  CWS @ MIN  |  Erick Fedde (2.19 HR/9)", fontsize=11, fontweight="bold", color=RED, pad=8)

min_data = [
    ("Byron Buxton",    "CF","25.0%","17/234",".258",".875","FIRE"),
    ("Ryan Kreidler",   "2B","22.2%","3/53", ".255",".829","HOT"),
    ("Brooks Lee",      "SS","17.4%","8/221",".256",".743","LEAN"),
    ("Kody Clemens",    "1B","15.6%","6/187",".235",".748","LEAN"),
    ("Josh Bell",       "DH","10.6%","5/233",".225",".630","PASS"),
]
cws_data = [
    ("Miguel Vargas",   "3B","12.7%","15/257",".241",".875","LEAN"),
    ("Colson Montgomery","SS","13.2%","15/248",".229",".809","LEAN"),
]
bx = [0.02,0.30,0.42,0.55,0.65,0.77,0.88]
bh = ["Batter","Pos","HR%","HR/PA","AVG","OPS","Play"]
for j,h in enumerate(bh):
    ax5.text(bx[j],0.96,h,fontsize=8.5,fontweight="bold",color=MUTED,transform=ax5.transAxes,va="top")
ax5.plot([0.02,0.98],[0.91,0.91],color="#2d3748",linewidth=1,transform=ax5.transAxes)
rc = {"FIRE":RED,"HOT":ORANGE,"LEAN":YELLOW,"PASS":MUTED}
for i,row in enumerate(min_data):
    y = 0.85 - i*0.115
    for j,val in enumerate(row):
        c = rc.get(val,TEXT) if j==6 else TEXT
        ax5.text(bx[j],y,val,fontsize=8.5,color=c,fontweight="bold" if j==6 else "normal",transform=ax5.transAxes,va="top")
ax5.plot([0.02,0.98],[0.27,0.27],color="#2d3748",linewidth=1,transform=ax5.transAxes)
ax5.text(0.02,0.24,"CWS bats vs Taj Bradley (0.96 HR/9):",fontsize=8.5,fontweight="bold",color=MUTED,transform=ax5.transAxes,va="top")
for i,row in enumerate(cws_data):
    y = 0.18 - i*0.10
    for j,val in enumerate(row):
        c = rc.get(val,TEXT) if j==6 else TEXT
        ax5.text(bx[j],y,val,fontsize=8.5,color=c,fontweight="bold" if j==6 else "normal",transform=ax5.transAxes,va="top")
ax5.text(0.02,0.04,"Fedde has allowed 13 HRs in 53.3 IP — worst HR/9 on today's slate",fontsize=7.5,color=RED,transform=ax5.transAxes,va="top",style="italic")

# ── Row 4R: Game of the Day — LAD @ AZ ────────────────────────────────────────
ax6 = fig.add_subplot(gs[4, 1])
ax6.set_facecolor(CARD); ax6.set_axis_off()
ax6.set_title("SLUG FEST ALERT  —  LAD @ AZ  |  Ohtani vs Gallen (1.52 HR/9)", fontsize=11, fontweight="bold", color=ORANGE, pad=8)

lad_data = [
    ("Max Muncy",     "3B","25.0%","14/204",".254",".878","FIRE"),
    ("Andy Pages",    "RF","21.2%","13/245",".295",".883","HOT"),
    ("Mookie Betts",  "2B","21.5%","6/111", ".198",".667","HOT"),
    ("Shohei Ohtani", "DH","15.8%","10/258",".286",".905","LEAN"),
    ("Freddie Freeman","1B","13.3%","8/247", ".268",".816","LEAN"),
]
az_data = [
    ("Ketel Marte",   "2B"," 2.3%","9/243",".260",".764","FADE"),
    ("Corbin Carroll","CF"," 2.3%","3/199",".193",".568","FADE"),
]
for j,h in enumerate(bh):
    ax6.text(bx[j],0.96,h,fontsize=8.5,fontweight="bold",color=MUTED,transform=ax6.transAxes,va="top")
ax6.plot([0.02,0.98],[0.91,0.91],color="#2d3748",linewidth=1,transform=ax6.transAxes)
for i,row in enumerate(lad_data):
    y = 0.85 - i*0.115
    for j,val in enumerate(row):
        c = rc.get(val,TEXT) if j==6 else TEXT
        ax6.text(bx[j],y,val,fontsize=8.5,color=c,fontweight="bold" if j==6 else "normal",transform=ax6.transAxes,va="top")
ax6.plot([0.02,0.98],[0.27,0.27],color="#2d3748",linewidth=1,transform=ax6.transAxes)
ax6.text(0.02,0.24,"AZ bats vs Ohtani (0.33 HR/9 — FADE HRs):",fontsize=8.5,fontweight="bold",color=MUTED,transform=ax6.transAxes,va="top")
for i,row in enumerate(az_data):
    y = 0.18 - i*0.10
    for j,val in enumerate(row):
        c = RED if val=="FADE" else TEXT
        ax6.text(bx[j],y,val,fontsize=8.5,color=c,fontweight="bold" if j==6 else "normal",transform=ax6.transAxes,va="top")
ax6.text(0.02,0.04,"AZ HR expected: near-zero  |  LAD is where the action is",fontsize=7.5,color=ORANGE,transform=ax6.transAxes,va="top",style="italic")

# Footer
fig.text(0.5,0.005,"PropStats v1.0  |  MLB Stats API  |  Recalibrated HR model + platoon edge + PA-sample regression  |  June 3, 2026",
         ha="center",fontsize=7.5,color="#4a5568")

out = "/home/user/propstats/june3_slate_report.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"Saved: {out}")
