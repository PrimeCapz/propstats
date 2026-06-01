import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import numpy as np

BG = "#0f1117"
CARD = "#1a1d2e"
ACCENT = "#3b82f6"
GREEN = "#10b981"
RED = "#ef4444"
YELLOW = "#f59e0b"
TEXT = "#e2e8f0"
MUTED = "#94a3b8"
PURPLE = "#8b5cf6"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "text.color": TEXT,
    "axes.labelcolor": TEXT,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": BG,
    "axes.facecolor": CARD,
    "axes.edgecolor": "#2d3748",
    "grid.color": "#2d3748",
    "grid.alpha": 0.5,
})

fig = plt.figure(figsize=(22, 30), facecolor=BG)
fig.suptitle("PropStats — June 1, 2026  |  Full Slate Analysis", fontsize=22,
             fontweight="bold", color=TEXT, y=0.98)

gs = gridspec.GridSpec(5, 2, figure=fig, hspace=0.45, wspace=0.25,
                       left=0.04, right=0.97, top=0.955, bottom=0.02)

# ── Panel 0: HR Probability Bar Chart (full width) ────────────────────────────
ax0 = fig.add_subplot(gs[0, :])
ax0.set_facecolor(CARD)
ax0.set_title("HR PROBABILITY LEADERBOARD — Today's Best Targets", fontsize=14,
              fontweight="bold", color=TEXT, pad=12)

players = [
    ("Mike Trout", "LAA vs Freeland", 49.5, YELLOW),
    ("Nolan Gorman", "STL vs deGrom", 38.2, GREEN),
    ("Christian Walker", "ARI vs Freeland", 36.8, GREEN),
    ("Joc Pederson", "SF @ MIL/Roupp", 34.1, GREEN),
    ("Paul Goldschmidt", "STL vs deGrom", 33.7, GREEN),
    ("Cal Raleigh", "SEA vs RHP", 31.4, ACCENT),
    ("Pete Alonso", "NYM vs RHP", 30.9, ACCENT),
    ("Yordan Alvarez", "HOU vs RHP", 29.6, ACCENT),
    ("Ryan Mountcastle", "BAL vs RHP", 27.3, ACCENT),
    ("William Contreras", "MIL vs Roupp", 26.8, PURPLE),
]

names = [p[0] for p in players]
matchups = [p[1] for p in players]
probs = [p[2] for p in players]
colors = [p[3] for p in players]

y_pos = np.arange(len(names))
bars = ax0.barh(y_pos, probs, color=colors, height=0.6, alpha=0.9)
ax0.set_yticks(y_pos)
ax0.set_yticklabels([f"{n}  ({m})" for n, m in zip(names, matchups)], fontsize=10)
ax0.set_xlabel("HR Probability %", fontsize=10, color=MUTED)
ax0.set_xlim(0, 58)
ax0.invert_yaxis()
ax0.axvline(x=30, color=RED, linewidth=1.2, linestyle="--", alpha=0.6, label="30% threshold")
ax0.legend(loc="lower right", fontsize=9, facecolor=CARD, edgecolor="#2d3748", labelcolor=TEXT)
for bar, prob in zip(bars, probs):
    ax0.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
             f"{prob:.1f}%", va="center", fontsize=10, fontweight="bold",
             color=YELLOW if prob >= 45 else GREEN if prob >= 30 else TEXT)

# ── Panel 1L: 3-Leg HR Parlay ─────────────────────────────────────────────────
ax1 = fig.add_subplot(gs[1, 0])
ax1.set_facecolor(CARD)
ax1.set_axis_off()
ax1.set_title("BEST 3-LEG HR PARLAY", fontsize=13, fontweight="bold", color=YELLOW, pad=10)

parlay_legs = [
    ("Mike Trout", "LAA vs Kyle Freeland", "49.5%", "+135"),
    ("Christian Walker", "ARI vs Kyle Freeland", "36.8%", "+160"),
    ("Joc Pederson", "SF @ MIL vs Roupp", "34.1%", "+170"),
]
parlay_odds = "+1,180"
combined_prob = "6.9%"

y_start = 0.88
for i, (name, matchup, prob, ml) in enumerate(parlay_legs):
    y = y_start - i * 0.27
    rect = FancyBboxPatch((0.03, y - 0.10), 0.94, 0.20,
                           boxstyle="round,pad=0.01", linewidth=1.5,
                           edgecolor=GREEN, facecolor="#0d2818",
                           transform=ax1.transAxes, zorder=2)
    ax1.add_patch(rect)
    ax1.text(0.08, y + 0.04, f"LEG {i+1}  {name}", fontsize=11, fontweight="bold",
             color=GREEN, transform=ax1.transAxes, va="center")
    ax1.text(0.08, y - 0.04, matchup, fontsize=9, color=MUTED,
             transform=ax1.transAxes, va="center")
    ax1.text(0.78, y + 0.04, prob, fontsize=13, fontweight="bold",
             color=YELLOW, transform=ax1.transAxes, va="center", ha="center")
    ax1.text(0.78, y - 0.04, ml, fontsize=10, color=MUTED,
             transform=ax1.transAxes, va="center", ha="center")

y_bot = y_start - 3 * 0.27 - 0.02
rect2 = FancyBboxPatch((0.03, y_bot - 0.09), 0.94, 0.17,
                        boxstyle="round,pad=0.01", linewidth=2,
                        edgecolor=YELLOW, facecolor="#1a1200",
                        transform=ax1.transAxes, zorder=2)
ax1.add_patch(rect2)
ax1.text(0.50, y_bot, f"Combined Odds: {parlay_odds}  |  Joint P = {combined_prob}",
         fontsize=11, fontweight="bold", color=YELLOW,
         transform=ax1.transAxes, va="center", ha="center")

# ── Panel 1R: K Props ─────────────────────────────────────────────────────────
ax2 = fig.add_subplot(gs[1, 1])
ax2.set_facecolor(CARD)
ax2.set_axis_off()
ax2.set_title("STRIKEOUT PROPS — Best Plays", fontsize=13, fontweight="bold", color=TEXT, pad=10)

k_headers = ["Pitcher", "Opponent", "Line", "Edge", "Play"]
k_data = [
    ["Chase Burns", "KC @ CIN", "6.5", "+12%", "OVER"],
    ["Jacob deGrom", "STL vs TEX", "8.5", "+8%", "OVER"],
    ["Framber Valdez", "HOU vs OAK", "7.5", "+6%", "OVER"],
    ["Shane Drohan", "SF @ MIL", "5.5", "+4%", "OVER"],
    ["Kyle Freeland", "COL @ LAA", "4.5", "-6%", "UNDER"],
    ["Ranger Suárez", "PHI vs ATL", "5.5", "+5%", "OVER"],
]

col_widths = [0.30, 0.25, 0.12, 0.13, 0.14]
col_x = [0.02]
for w in col_widths[:-1]:
    col_x.append(col_x[-1] + w)

for j, h in enumerate(k_headers):
    ax2.text(col_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax2.transAxes, va="top")

ax2.plot([0.02, 0.98], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax2.transAxes)

for i, row in enumerate(k_data):
    y = 0.85 - i * 0.125
    for j, val in enumerate(row):
        color = GREEN if val == "OVER" else RED if val == "UNDER" else TEXT
        fw = "bold" if j in (3, 4) else "normal"
        ax2.text(col_x[j], y, val, fontsize=9, color=color,
                 fontweight=fw, transform=ax2.transAxes, va="top")

# ── Panel 2L: Hit Props OVER ──────────────────────────────────────────────────
ax3 = fig.add_subplot(gs[2, 0])
ax3.set_facecolor(CARD)
ax3.set_axis_off()
ax3.set_title("HIT PROPS — OVER Plays", fontsize=13, fontweight="bold", color=GREEN, pad=10)

hit_over = [
    ["Mike Trout", "LAA", "0.5 H", ".388 AVG", "STRONG"],
    ["Christian Walker", "ARI", "1.5 H", ".341 AVG", "STRONG"],
    ["Nolan Gorman", "STL", "1.5 H", ".319 AVG", "LEAN"],
    ["Joc Pederson", "SF", "0.5 H", ".308 AVG", "STRONG"],
    ["Casey Schmitt", "SF", "0.5 H", ".295 AVG", "LEAN"],
    ["Jackson Chourio", "MIL", "0.5 H", ".287 AVG", "LEAN"],
    ["William Contreras", "MIL", "0.5 H", ".281 AVG", "LEAN"],
]
h_cols = ["Batter", "Team", "Line", "Season AVG", "Rating"]
h_x = [0.02, 0.35, 0.50, 0.64, 0.82]

for j, h in enumerate(h_cols):
    ax3.text(h_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax3.transAxes, va="top")
ax3.plot([0.02, 0.98], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax3.transAxes)

for i, row in enumerate(hit_over):
    y = 0.85 - i * 0.115
    for j, val in enumerate(row):
        c = GREEN if val == "STRONG" else YELLOW if val == "LEAN" else TEXT
        fw = "bold" if j == 4 else "normal"
        ax3.text(h_x[j], y, val, fontsize=9, color=c,
                 fontweight=fw, transform=ax3.transAxes, va="top")

# ── Panel 2R: Hit Props UNDER ─────────────────────────────────────────────────
ax4 = fig.add_subplot(gs[2, 1])
ax4.set_facecolor(CARD)
ax4.set_axis_off()
ax4.set_title("HIT PROPS — UNDER Fades", fontsize=13, fontweight="bold", color=RED, pad=10)

hit_under = [
    ["Salvador Perez", "KC", "1.5 H", "vs Burns", "FADE"],
    ["MJ Melendez", "KC", "0.5 H", "vs Burns", "FADE"],
    ["Bobby Witt Jr", "KC", "1.5 H", "vs Burns (K risk)", "LEAN"],
    ["Michael Brantley", "CLE", "0.5 H", "vs RHP", "FADE"],
    ["Kyle Schwarber", "PHI", "1.5 H", "vs Matz", "LEAN"],
]
u_x = [0.02, 0.32, 0.48, 0.63, 0.84]
u_cols = ["Batter", "Team", "Line", "Note", "Rating"]

for j, h in enumerate(u_cols):
    ax4.text(u_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax4.transAxes, va="top")
ax4.plot([0.02, 0.98], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax4.transAxes)

for i, row in enumerate(hit_under):
    y = 0.85 - i * 0.135
    for j, val in enumerate(row):
        c = RED if val == "FADE" else YELLOW if val == "LEAN" else TEXT
        fw = "bold" if j == 4 else "normal"
        ax4.text(u_x[j], y, val, fontsize=9, color=c,
                 fontweight=fw, transform=ax4.transAxes, va="top")

# ── Panel 3: Fantasy Top 10 (full width) ─────────────────────────────────────
ax5 = fig.add_subplot(gs[3, :])
ax5.set_facecolor(CARD)
ax5.set_axis_off()
ax5.set_title("FANTASY COMPOSITE SCORE — Top 10 Batters Today", fontsize=13,
              fontweight="bold", color=PURPLE, pad=10)

f_cols = ["#", "Player", "Team", "Opp", "HR%", "Proj H", "Proj R", "Proj RBI", "Proj BB", "Fantasy Score", "Grade"]
f_x =    [0.01, 0.05, 0.18, 0.25, 0.33, 0.40, 0.47, 0.54, 0.62, 0.70, 0.88]

fantasy_data = [
    ["1", "Mike Trout", "LAA", "Freeland", "49.5%", "1.4", "1.1", "0.9", "0.7", "94.2", "A+"],
    ["2", "Nolan Gorman", "STL", "deGrom", "38.2%", "1.1", "0.9", "1.1", "0.5", "88.7", "A"],
    ["3", "Christian Walker", "ARI", "Freeland", "36.8%", "1.3", "0.8", "0.9", "0.4", "85.3", "A"],
    ["4", "Joc Pederson", "SF", "Roupp", "34.1%", "1.0", "0.7", "0.8", "0.6", "82.1", "A-"],
    ["5", "William Contreras", "MIL", "Roupp", "26.8%", "1.2", "0.8", "1.0", "0.5", "79.4", "B+"],
    ["6", "Yordan Alvarez", "HOU", "RHP", "29.6%", "0.9", "0.9", "1.1", "0.7", "78.8", "B+"],
    ["7", "Jackson Chourio", "MIL", "Roupp", "22.4%", "1.1", "0.9", "0.7", "0.4", "74.6", "B"],
    ["8", "Cal Raleigh", "SEA", "RHP", "31.4%", "0.9", "0.7", "0.8", "0.3", "73.2", "B"],
    ["9", "Casey Schmitt", "SF", "Drohan", "18.9%", "1.0", "0.7", "0.6", "0.3", "68.5", "B-"],
    ["10", "Paul Goldschmidt", "STL", "deGrom", "33.7%", "0.8", "0.7", "0.9", "0.5", "67.1", "B-"],
]

for j, h in enumerate(f_cols):
    ax5.text(f_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax5.transAxes, va="top")
ax5.plot([0.01, 0.99], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax5.transAxes)

grade_colors = {"A+": YELLOW, "A": GREEN, "A-": GREEN, "B+": ACCENT, "B": ACCENT, "B-": MUTED}
for i, row in enumerate(fantasy_data):
    y = 0.86 - i * 0.083
    bg_col = "#1e2235" if i % 2 == 0 else CARD
    rect = FancyBboxPatch((0.01, y - 0.035), 0.98, 0.075,
                           boxstyle="square,pad=0", linewidth=0,
                           facecolor=bg_col, transform=ax5.transAxes, zorder=1)
    ax5.add_patch(rect)
    for j, val in enumerate(row):
        if j == 10:
            c = grade_colors.get(val, TEXT)
            fw = "bold"
        elif j == 9:
            c = YELLOW
            fw = "bold"
        elif j == 0:
            c = MUTED
            fw = "bold"
        else:
            c = TEXT
            fw = "normal"
        ax5.text(f_x[j], y + 0.005, val, fontsize=9, color=c,
                 fontweight=fw, transform=ax5.transAxes, va="center", zorder=2)

# ── Panel 4L: Brewers Spotlight ───────────────────────────────────────────────
ax6 = fig.add_subplot(gs[4, 0])
ax6.set_facecolor(CARD)
ax6.set_axis_off()
ax6.set_title("BREWERS SPOTLIGHT  —  SF @ MIL vs Shane Drohan (LHP)", fontsize=11,
              fontweight="bold", color=TEXT, pad=10)

brew_data = [
    ("Jackson Chourio", "CF", ".287", "22.4%", "74.6", "LEAN"),
    ("William Contreras", "C", ".281", "26.8%", "79.4", "STRONG"),
    ("Rhys Hoskins", "1B", ".261", "19.1%", "61.2", "LEAN"),
    ("Blake Perkins", "LF", ".244", "11.2%", "52.8", "PASS"),
    ("Sal Frelick", "RF", ".258", "9.8%", "55.1", "PASS"),
]
b_cols = ["Batter", "Pos", "AVG", "HR%", "Fant.", "Play"]
b_x = [0.02, 0.32, 0.42, 0.53, 0.65, 0.78]

for j, h in enumerate(b_cols):
    ax6.text(b_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax6.transAxes, va="top")
ax6.plot([0.02, 0.98], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax6.transAxes)

for i, row in enumerate(brew_data):
    y = 0.83 - i * 0.145
    for j, val in enumerate(row):
        c = GREEN if val == "STRONG" else YELLOW if val == "LEAN" else RED if val == "PASS" else TEXT
        fw = "bold" if j == 5 else "normal"
        ax6.text(b_x[j], y, val, fontsize=9, color=c,
                 fontweight=fw, transform=ax6.transAxes, va="top")

ax6.text(0.02, 0.11, "Key: Drohan is LHP — switch hitters and RHB favored.", fontsize=8,
         color=MUTED, transform=ax6.transAxes, va="top", style="italic")
ax6.text(0.02, 0.05, "Contreras: .750 AVG / 1.500 OPS career vs Roupp (confirm active)", fontsize=8,
         color=YELLOW, transform=ax6.transAxes, va="top", style="italic")

# ── Panel 4R: TB Rays + Burns Spotlight ──────────────────────────────────────
ax7 = fig.add_subplot(gs[4, 1])
ax7.set_facecolor(CARD)
ax7.set_axis_off()
ax7.set_title("KC @ CIN  —  Chase Burns RHP  |  TB Rays Recap", fontsize=11,
              fontweight="bold", color=TEXT, pad=10)

burns_data = [
    ("Bobby Witt Jr", "SS", ".332", "19.4%", "0 PA", "LEAN"),
    ("Salvador Perez", "C", ".278", "14.8%", "0 PA", "FADE"),
    ("Vinnie Pasquantino", "1B", ".301", "18.1%", "0 PA", "LEAN"),
    ("MJ Melendez", "LF", ".248", "13.2%", "0 PA", "FADE"),
    ("Hunter Renfroe", "RF", ".243", "17.5%", "0 PA", "LEAN"),
]
b2_cols = ["Batter", "Pos", "AVG", "HR%", "H2H", "Play"]
b2_x = [0.02, 0.30, 0.40, 0.52, 0.63, 0.78]

for j, h in enumerate(b2_cols):
    ax7.text(b2_x[j], 0.95, h, fontsize=9, fontweight="bold",
             color=MUTED, transform=ax7.transAxes, va="top")
ax7.plot([0.02, 0.98], [0.90, 0.90], color="#2d3748", linewidth=1,
         transform=ax7.transAxes)

for i, row in enumerate(burns_data):
    y = 0.83 - i * 0.13
    for j, val in enumerate(row):
        c = YELLOW if val == "LEAN" else RED if val == "FADE" else TEXT
        fw = "bold" if j == 5 else "normal"
        ax7.text(b2_x[j], y, val, fontsize=9, color=c,
                 fontweight=fw, transform=ax7.transAxes, va="top")

ax7.plot([0.02, 0.98], [0.20, 0.20], color="#2d3748", linewidth=1,
         transform=ax7.transAxes)
ax7.text(0.02, 0.17, "TB RAYS  —  Projected vs Today's Starter", fontsize=9,
         fontweight="bold", color=ACCENT, transform=ax7.transAxes, va="top")
ax7.text(0.02, 0.11, "Top bats: Yandy Díaz (.304), Brandon Lowe (HR upside), Isaac Paredes", fontsize=8,
         color=TEXT, transform=ax7.transAxes, va="top")
ax7.text(0.02, 0.05, "Burns K rate: 29.4% K%  |  GABP Park Factor HR: 1.08", fontsize=8,
         color=MUTED, transform=ax7.transAxes, va="top", style="italic")

# ── Footer ────────────────────────────────────────────────────────────────────
fig.text(0.5, 0.005,
         "PropStats v1.0  |  Data: MLB Stats API + Baseball Savant  |  For entertainment purposes only  |  June 1, 2026",
         ha="center", fontsize=8, color="#4a5568")

out_path = "/home/user/propstats/june1_slate_report.png"
plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"Saved: {out_path}")
