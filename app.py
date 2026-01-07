"""
🏀 NBA Props Research Tool - PropFinder Edition
Three-tier navigation with premium PropFinder-style modular cards
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import statistics

# Page Configuration
st.set_page_config(
    page_title="PropStats Pro",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Premium CSS - PropFinder Style
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');

    * { font-family: 'Inter', sans-serif; }

    /* Background */
    .stApp { background-color: #0E1117; }

    #MainMenu, footer, header { visibility: hidden; }

    /* Main Header */
    .main-header {
        background: linear-gradient(135deg, #1A1C24 0%, #0E1117 100%);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-bottom: 2px solid #00FFA3;
        padding: 1.2rem 0;
        margin-bottom: 2rem;
        position: sticky;
        top: 0;
        z-index: 999;
        box-shadow: 0 4px 20px rgba(0, 255, 163, 0.1);
    }

    /* Glassmorphism Cards */
    .glass-card {
        background: rgba(26, 28, 36, 0.7);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        transition: all 0.3s ease;
    }

    .glass-card:hover {
        border-color: rgba(0, 255, 163, 0.3);
        box-shadow: 0 8px 32px rgba(0, 255, 163, 0.1);
    }

    /* Premium Card Container */
    .premium-card {
        background: #1A1C24;
        border: 1px solid #333;
        border-radius: 16px;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.6);
    }

    /* PropScore Badge with Neon Glow */
    .propscore-high {
        background: linear-gradient(135deg, #00FFA3, #00CC82);
        color: #000;
        box-shadow: 0 0 25px rgba(0, 255, 163, 0.6), 0 0 50px rgba(0, 255, 163, 0.3);
    }

    .propscore-medium {
        background: linear-gradient(135deg, #FFC107, #FF9800);
        color: #000;
        box-shadow: 0 0 25px rgba(255, 193, 7, 0.6), 0 0 50px rgba(255, 193, 7, 0.3);
    }

    .propscore-low {
        background: linear-gradient(135deg, #EF4444, #DC2626);
        color: white;
        box-shadow: 0 0 25px rgba(239, 68, 68, 0.6), 0 0 50px rgba(239, 68, 68, 0.3);
    }

    /* Heat Map Colors */
    .heat-high {
        background: linear-gradient(135deg, #00FFA3, #00CC82);
        color: #000;
        box-shadow: 0 0 15px rgba(0, 255, 163, 0.3);
    }

    .heat-medium {
        background: linear-gradient(135deg, #FFC107, #FF9800);
        color: #000;
        box-shadow: 0 0 15px rgba(255, 193, 7, 0.3);
    }

    .heat-low {
        background: linear-gradient(135deg, #EF4444, #DC2626);
        color: white;
        box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);
    }

    /* Stat Tabs */
    .stat-tab {
        display: inline-block;
        padding: 0.6rem 1.5rem;
        margin: 0.25rem;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        cursor: pointer;
        transition: all 0.2s;
        background: rgba(55, 65, 81, 0.5);
        color: #9CA3AF;
        border: 1px solid transparent;
    }

    .stat-tab-active {
        background: linear-gradient(135deg, #00FFA3, #00CC82);
        color: #000;
        border: 1px solid #00FFA3;
        box-shadow: 0 0 15px rgba(0, 255, 163, 0.4);
    }

    /* Buttons */
    .stButton button {
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.1), rgba(0, 255, 163, 0.05));
        color: #00FFA3;
        border: 2px solid #00FFA3;
        border-radius: 12px;
        font-weight: 700;
        padding: 0.8rem 1.5rem;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-size: 0.95rem;
    }

    .stButton button:hover {
        background: #00FFA3;
        color: #000;
        box-shadow: 0 0 20px rgba(0, 255, 163, 0.6);
        transform: translateY(-2px);
    }

    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #00FFA3;
        text-shadow: 0 0 10px rgba(0, 255, 163, 0.5);
        font-weight: 900;
    }

    /* Inputs */
    input, select {
        background-color: #1A1C24 !important;
        color: white !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
    }

    input:focus, select:focus {
        border-color: #00FFA3 !important;
        box-shadow: 0 0 10px rgba(0, 255, 163, 0.3) !important;
    }

    .block-container {
        padding-top: 1rem;
        max-width: 1400px;
    }

    /* Matchup Difficulty Badge */
    .difficulty-badge {
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# Team Data
TEAM_COLORS = {
    'ATL': '#E03A3E', 'BOS': '#007A33', 'BKN': '#000000', 'CHA': '#1D1160',
    'CHI': '#CE1141', 'CLE': '#860038', 'DAL': '#00538C', 'DEN': '#0E2240',
    'DET': '#C8102E', 'GSW': '#1D428A', 'HOU': '#CE1141', 'IND': '#002D62',
    'LAC': '#C8102E', 'LAL': '#552583', 'MEM': '#5D76A9', 'MIA': '#98002E',
    'MIL': '#00471B', 'MIN': '#0C2340', 'NOP': '#0C2340', 'NYK': '#006BB6',
    'OKC': '#007AC1', 'ORL': '#0077C0', 'PHI': '#006BB6', 'PHX': '#1D1160',
    'POR': '#E03A3E', 'SAC': '#5A2D81', 'SAS': '#C4CED4', 'TOR': '#CE1141',
    'UTA': '#002B5C', 'WAS': '#002B5C'
}

TEAM_NAMES = {
    'ATL': 'Hawks', 'BOS': 'Celtics', 'BKN': 'Nets', 'CHA': 'Hornets',
    'CHI': 'Bulls', 'CLE': 'Cavaliers', 'DAL': 'Mavericks', 'DEN': 'Nuggets',
    'DET': 'Pistons', 'GSW': 'Warriors', 'HOU': 'Rockets', 'IND': 'Pacers',
    'LAC': 'Clippers', 'LAL': 'Lakers', 'MEM': 'Grizzlies', 'MIA': 'Heat',
    'MIL': 'Bucks', 'MIN': 'Timberwolves', 'NOP': 'Pelicans', 'NYK': 'Knicks',
    'OKC': 'Thunder', 'ORL': 'Magic', 'PHI': '76ers', 'PHX': 'Suns',
    'POR': 'Trail Blazers', 'SAC': 'Kings', 'SAS': 'Spurs', 'TOR': 'Raptors',
    'UTA': 'Jazz', 'WAS': 'Wizards'
}

TEAM_STATS = {
    'LAL': {'ppg': 116.2, 'pace': 99.8, 'def_rank': 15, 'off_rank': 8, 'pg_def_rank': 18},
    'GSW': {'ppg': 118.5, 'pace': 101.2, 'def_rank': 12, 'off_rank': 3, 'pg_def_rank': 22},
    'BOS': {'ppg': 120.1, 'pace': 98.5, 'def_rank': 2, 'off_rank': 1, 'pg_def_rank': 5},
    'MIA': {'ppg': 110.8, 'pace': 96.2, 'def_rank': 5, 'off_rank': 18, 'pg_def_rank': 8},
    'DAL': {'ppg': 117.9, 'pace': 100.1, 'def_rank': 14, 'off_rank': 5, 'pg_def_rank': 20},
    'PHX': {'ppg': 115.4, 'pace': 99.5, 'def_rank': 18, 'off_rank': 7, 'pg_def_rank': 28},
    'MIL': {'ppg': 119.2, 'pace': 100.8, 'def_rank': 10, 'off_rank': 2, 'pg_def_rank': 12},
    'PHI': {'ppg': 114.3, 'pace': 97.8, 'def_rank': 8, 'off_rank': 12, 'pg_def_rank': 9},
    'DEN': {'ppg': 116.8, 'pace': 98.9, 'def_rank': 16, 'off_rank': 6, 'pg_def_rank': 15},
    'MIN': {'ppg': 113.5, 'pace': 99.2, 'def_rank': 7, 'off_rank': 14, 'pg_def_rank': 11},
    'OKC': {'ppg': 118.9, 'pace': 101.5, 'def_rank': 1, 'off_rank': 4, 'pg_def_rank': 3},
    'MEM': {'ppg': 112.1, 'pace': 100.3, 'def_rank': 11, 'off_rank': 16, 'pg_def_rank': 14},
    'NYK': {'ppg': 111.7, 'pace': 96.8, 'def_rank': 3, 'off_rank': 19, 'pg_def_rank': 6},
    'ATL': {'ppg': 117.5, 'pace': 101.8, 'def_rank': 22, 'off_rank': 9, 'pg_def_rank': 25},
    'CLE': {'ppg': 115.9, 'pace': 98.1, 'def_rank': 6, 'off_rank': 10, 'pg_def_rank': 7},
    'BKN': {'ppg': 109.4, 'pace': 99.7, 'def_rank': 25, 'off_rank': 23, 'pg_def_rank': 30}
}

TEAM_ROSTERS = {
    'LAL': [
        {'id': '2544', 'name': 'LeBron James', 'pos': 'F', 'number': '23',
         'stats': {'points': 25.5, 'rebounds': 7.2, 'assists': 8.1}},
        {'id': '203076', 'name': 'Anthony Davis', 'pos': 'C', 'number': '3',
         'stats': {'points': 27.8, 'rebounds': 11.3, 'assists': 3.5}},
    ],
    'GSW': [
        {'id': '201939', 'name': 'Stephen Curry', 'pos': 'G', 'number': '30',
         'stats': {'points': 26.4, 'rebounds': 4.5, 'assists': 5.2, 'threes': 4.8}},
        {'id': '203110', 'name': 'Klay Thompson', 'pos': 'G', 'number': '11',
         'stats': {'points': 19.5, 'rebounds': 3.5, 'assists': 2.3, 'threes': 3.2}},
    ],
    'BOS': [
        {'id': '1628369', 'name': 'Jayson Tatum', 'pos': 'F', 'number': '0',
         'stats': {'points': 28.2, 'rebounds': 8.6, 'assists': 4.9}},
        {'id': '1628464', 'name': 'Jaylen Brown', 'pos': 'G-F', 'number': '7',
         'stats': {'points': 24.7, 'rebounds': 6.1, 'assists': 3.5}},
    ],
    'DAL': [
        {'id': '1629029', 'name': 'Luka Doncic', 'pos': 'G', 'number': '77',
         'stats': {'points': 32.4, 'rebounds': 8.0, 'assists': 9.8}},
        {'id': '1626157', 'name': 'Kyrie Irving', 'pos': 'G', 'number': '2',
         'stats': {'points': 25.2, 'rebounds': 4.9, 'assists': 5.3}},
    ],
    'MIL': [
        {'id': '203507', 'name': 'Giannis Antetokounmpo', 'pos': 'F', 'number': '34',
         'stats': {'points': 31.1, 'rebounds': 11.2, 'assists': 6.1}},
        {'id': '203081', 'name': 'Damian Lillard', 'pos': 'G', 'number': '0',
         'stats': {'points': 25.7, 'rebounds': 4.3, 'assists': 7.6}},
    ],
    'PHI': [
        {'id': '203954', 'name': 'Joel Embiid', 'pos': 'C', 'number': '21',
         'stats': {'points': 29.5, 'rebounds': 10.8, 'assists': 5.2}},
        {'id': '1630178', 'name': 'Tyrese Maxey', 'pos': 'G', 'number': '0',
         'stats': {'points': 27.4, 'rebounds': 3.8, 'assists': 6.9}},
    ],
    'DEN': [
        {'id': '203999', 'name': 'Nikola Jokic', 'pos': 'C', 'number': '15',
         'stats': {'points': 27.9, 'rebounds': 12.3, 'assists': 9.2}},
        {'id': '1628378', 'name': 'Jamal Murray', 'pos': 'G', 'number': '27',
         'stats': {'points': 21.2, 'rebounds': 4.1, 'assists': 6.5}},
    ],
    'PHX': [
        {'id': '201142', 'name': 'Kevin Durant', 'pos': 'F', 'number': '35',
         'stats': {'points': 28.3, 'rebounds': 6.8, 'assists': 5.0}},
        {'id': '1626164', 'name': 'Devin Booker', 'pos': 'G', 'number': '1',
         'stats': {'points': 26.8, 'rebounds': 4.6, 'assists': 6.9}},
    ],
    'OKC': [
        {'id': '1628983', 'name': 'Shai Gilgeous-Alexander', 'pos': 'G', 'number': '2',
         'stats': {'points': 30.8, 'rebounds': 5.5, 'assists': 6.2}},
        {'id': '1630602', 'name': 'Chet Holmgren', 'pos': 'C', 'number': '7',
         'stats': {'points': 16.9, 'rebounds': 7.8, 'assists': 2.5}},
    ],
    'MIN': [
        {'id': '1630162', 'name': 'Anthony Edwards', 'pos': 'G', 'number': '5',
         'stats': {'points': 27.6, 'rebounds': 5.4, 'assists': 5.1}},
        {'id': '203497', 'name': 'Rudy Gobert', 'pos': 'C', 'number': '27',
         'stats': {'points': 13.8, 'rebounds': 12.9, 'assists': 1.2}},
    ],
    'MIA': [
        {'id': '1628389', 'name': 'Bam Adebayo', 'pos': 'C', 'number': '13',
         'stats': {'points': 19.4, 'rebounds': 10.2, 'assists': 4.1}},
        {'id': '1630527', 'name': 'Tyler Herro', 'pos': 'G', 'number': '14',
         'stats': {'points': 23.8, 'rebounds': 5.3, 'assists': 5.0}},
    ],
    'NYK': [
        {'id': '1629649', 'name': 'Jalen Brunson', 'pos': 'G', 'number': '11',
         'stats': {'points': 28.1, 'rebounds': 3.8, 'assists': 6.7}},
        {'id': '1629628', 'name': 'Julius Randle', 'pos': 'F', 'number': '30',
         'stats': {'points': 24.3, 'rebounds': 9.2, 'assists': 5.0}},
    ],
    'CLE': [
        {'id': '1628378', 'name': 'Donovan Mitchell', 'pos': 'G', 'number': '45',
         'stats': {'points': 27.8, 'rebounds': 5.3, 'assists': 6.2}},
        {'id': '1629029', 'name': 'Evan Mobley', 'pos': 'F-C', 'number': '4',
         'stats': {'points': 16.2, 'rebounds': 9.4, 'assists': 3.1}},
    ],
    'ATL': [
        {'id': '1629027', 'name': 'Trae Young', 'pos': 'G', 'number': '11',
         'stats': {'points': 26.4, 'rebounds': 2.8, 'assists': 10.8}},
    ],
    'MEM': [
        {'id': '1629630', 'name': 'Ja Morant', 'pos': 'G', 'number': '12',
         'stats': {'points': 25.9, 'rebounds': 5.8, 'assists': 8.1}},
    ],
    'BKN': [
        {'id': '1629028', 'name': 'Mikal Bridges', 'pos': 'F', 'number': '1',
         'stats': {'points': 21.8, 'rebounds': 4.5, 'assists': 3.7}},
    ]
}

# Helper Functions
def generate_todays_games():
    """Generate mock games for today's slate"""
    matchups = [
        ('LAL', 'GSW', '10:00 PM ET'),
        ('BOS', 'MIA', '7:30 PM ET'),
        ('DAL', 'PHX', '9:00 PM ET'),
        ('MIL', 'PHI', '7:00 PM ET'),
        ('DEN', 'MIN', '8:00 PM ET'),
        ('OKC', 'MEM', '8:00 PM ET'),
        ('NYK', 'ATL', '7:30 PM ET'),
        ('CLE', 'BKN', '7:30 PM ET'),
    ]

    games = []
    for away, home, time in matchups:
        games.append({
            'away_team': away,
            'home_team': home,
            'time': time,
            'away_players': TEAM_ROSTERS.get(away, []),
            'home_players': TEAM_ROSTERS.get(home, []),
            'away_stats': TEAM_STATS.get(away, {}),
            'home_stats': TEAM_STATS.get(home, {})
        })

    return games

def generate_player_game_log(base_stat, num_games=20):
    """Generate realistic game log with gaussian distribution"""
    games = []
    dates = [(datetime.now() - timedelta(days=i*3)).strftime("%b %d") for i in range(num_games)]
    dates.reverse()

    for date in dates:
        value = max(0, int(random.gauss(base_stat, base_stat * 0.3)))
        games.append({
            'date': date,
            'value': value,
            'opponent': random.choice(list(TEAM_NAMES.keys()))
        })

    return games

def calculate_propscore(hit_rate, season_avg, line, consistency, difficulty):
    """
    Calculate PropScore (0-100) - Confidence rating for the prop
    Higher score = stronger OVER | Lower score = stronger UNDER
    """
    # Base score from hit rate (0-40 points)
    hit_score = (hit_rate / 100) * 40

    # Margin score: distance from line (0-30 points)
    margin = season_avg - line
    margin_pct = (margin / line * 100) if line > 0 else 0
    margin_score = min(30, max(-30, margin_pct * 3))
    margin_score = (margin_score + 30)  # Normalize to 0-60

    # Consistency bonus (0-20 points)
    consistency_score = consistency / 5

    # Difficulty adjustment (-10 to +10)
    difficulty_scores = {'easy': 10, 'medium': 0, 'hard': -10}
    difficulty_score = difficulty_scores.get(difficulty, 0)

    # Calculate final score
    propscore = hit_score + margin_score + consistency_score + difficulty_score
    propscore = max(0, min(100, propscore))

    return int(propscore)

def get_matchup_difficulty(opponent_team, player_pos):
    """Calculate matchup difficulty based on opponent defensive ranking"""
    opp_stats = TEAM_STATS.get(opponent_team, {})

    # Use position-specific defensive ranking if available
    if 'G' in player_pos:
        def_rank = opp_stats.get('pg_def_rank', 15)
    else:
        def_rank = opp_stats.get('def_rank', 15)

    if def_rank >= 25:
        return 'easy', f"vs {player_pos}: {def_rank}th", 'heat-high'
    elif def_rank >= 15:
        return 'medium', f"vs {player_pos}: {def_rank}th", 'heat-medium'
    else:
        return 'hard', f"vs {player_pos}: {def_rank}th", 'heat-low'

def create_enhanced_bar_chart(games, line, stat_name):
    """Create premium bar chart with neon green/red and yellow line"""
    fig = go.Figure()

    # Neon Green for OVER, Muted Red for UNDER
    colors = ['#00FFA3' if g['value'] > line else '#DC2626' for g in games[:10]]

    fig.add_trace(go.Bar(
        x=[g['date'] for g in games[:10]],
        y=[g['value'] for g in games[:10]],
        marker=dict(
            color=colors,
            line=dict(color='#0E1117', width=3)
        ),
        text=[g['value'] for g in games[:10]],
        textposition='outside',
        textfont=dict(color='white', size=12, family='Inter', weight='bold'),
        hovertemplate='<b>%{x}</b><br>%{y}<br><extra></extra>'
    ))

    # Bright Neon Yellow dashed line for target
    fig.add_hline(
        y=line,
        line_dash="dash",
        line_color="#FFD700",  # Bright Neon Yellow
        line_width=3,
        annotation_text=f"LINE: {line}",
        annotation_position="right",
        annotation_font=dict(color="#FFD700", size=13, family='Inter', weight='bold')
    )

    fig.update_layout(
        plot_bgcolor='#1A1C24',
        paper_bgcolor='#1A1C24',
        font=dict(color='white', family='Inter'),
        height=280,
        margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(showgrid=False, showline=False, zeroline=False, color='#666'),
        yaxis=dict(showgrid=True, gridcolor='rgba(42, 45, 58, 0.3)', showline=False,
                   zeroline=False, title="", color='#666'),
        hovermode='x unified'
    )

    return fig

# ========== SESSION STATE ==========
if 'view' not in st.session_state:
    st.session_state.view = 'slate'
if 'selected_game' not in st.session_state:
    st.session_state.selected_game = None
if 'selected_player' not in st.session_state:
    st.session_state.selected_player = None
if 'selected_stat' not in st.session_state:
    st.session_state.selected_stat = 'points'

# ========== HEADER ==========
st.markdown("""
<div class="main-header">
    <div style="max-width: 1400px; margin: 0 auto; padding: 0 1rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 45px; height: 45px; background: linear-gradient(135deg, #00FFA3, #00CC82); border-radius: 12px;
                        display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.5rem;
                        box-shadow: 0 0 20px rgba(0, 255, 163, 0.5);">P</div>
            <span style="font-size: 1.6rem; font-weight: 900; color: white; text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);">PropStats Pro</span>
        </div>
        <div style="color: #00FFA3; font-size: 1rem; font-weight: 600;">
            🏀 PREMIUM PLAYER PROPS
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ========== LAYER 1: THE SLATE ==========
if st.session_state.view == 'slate':
    st.markdown(f"""
    <div style="margin-bottom: 2.5rem; text-align: center;">
        <h1 style="color: white; font-size: 2.5rem; font-weight: 900; margin-bottom: 0.5rem;">
            Today's NBA Slate
        </h1>
        <p style="color: #00FFA3; font-size: 1.1rem; font-weight: 600;">
            {datetime.now().strftime('%A, %B %d, %Y')}
        </p>
    </div>
    """, unsafe_allow_html=True)

    games = generate_todays_games()

    # 2-column grid of matchups
    cols = st.columns(2)
    for idx, game in enumerate(games):
        away_color = TEAM_COLORS.get(game['away_team'], '#666')
        home_color = TEAM_COLORS.get(game['home_team'], '#666')

        with cols[idx % 2]:
            st.markdown(f"""
            <div class="glass-card" style="margin: 1rem 0; text-align: center;">
                <div style="display: flex; justify-content: space-around; align-items: center; padding: 1rem 0;">
                    <div>
                        <div style="color: {away_color}; font-size: 2rem; font-weight: 900;">{game['away_team']}</div>
                        <div style="color: #888; font-size: 0.8rem; margin-top: 0.5rem;">{TEAM_NAMES[game['away_team']]}</div>
                    </div>
                    <div style="color: #00FFA3; font-size: 1.5rem; font-weight: 900;">@</div>
                    <div>
                        <div style="color: {home_color}; font-size: 2rem; font-weight: 900;">{game['home_team']}</div>
                        <div style="color: #888; font-size: 0.8rem; margin-top: 0.5rem;">{TEAM_NAMES[game['home_team']]}</div>
                    </div>
                </div>
                <div style="color: #00FFA3; font-size: 0.9rem; font-weight: 600; margin-top: 0.5rem;">
                    {game['time']}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"View Matchup →", key=f"game_{idx}", use_container_width=True):
                st.session_state.selected_game = game
                st.session_state.view = 'matchup'
                st.rerun()

# ========== LAYER 2: THE MATCHUP BOARD (Tale of the Tape) ==========
elif st.session_state.view == 'matchup':
    game = st.session_state.selected_game

    if st.button("← BACK TO SLATE"):
        st.session_state.view = 'slate'
        st.rerun()

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 2rem;">
        <h1 style="color: white; font-size: 2.5rem; font-weight: 900;">Tale of the Tape</h1>
        <p style="color: #00FFA3; font-size: 1.2rem; font-weight: 600;">
            {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]} • {game['time']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Glassmorphism Team Comparison
    col1, col2, col3 = st.columns([5, 2, 5])

    with col1:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <h2 style="color: {TEAM_COLORS[game['away_team']]}; font-size: 2rem; margin-bottom: 1rem;">
                {game['away_team']} {TEAM_NAMES[game['away_team']]}
            </h2>
            <div style="color: white; font-size: 1.2rem; margin: 0.5rem 0;">
                <strong>{game['away_stats']['ppg']}</strong> PPG
            </div>
            <div style="color: #888; font-size: 1rem; margin: 0.5rem 0;">
                Pace: {game['away_stats']['pace']}
            </div>
            <div style="color: #00FFA3; font-size: 1rem; margin: 0.5rem 0; font-weight: 700;">
                Off Rank: #{game['away_stats']['off_rank']}
            </div>
            <div style="color: #EF4444; font-size: 1rem; margin: 0.5rem 0; font-weight: 700;">
                Def Rank: #{game['away_stats']['def_rank']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 2rem 0;">
            <div style="color: #00FFA3; font-size: 3rem; font-weight: 900;">VS</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="glass-card" style="text-align: center;">
            <h2 style="color: {TEAM_COLORS[game['home_team']]}; font-size: 2rem; margin-bottom: 1rem;">
                {game['home_team']} {TEAM_NAMES[game['home_team']]}
            </h2>
            <div style="color: white; font-size: 1.2rem; margin: 0.5rem 0;">
                <strong>{game['home_stats']['ppg']}</strong> PPG
            </div>
            <div style="color: #888; font-size: 1rem; margin: 0.5rem 0;">
                Pace: {game['home_stats']['pace']}
            </div>
            <div style="color: #00FFA3; font-size: 1rem; margin: 0.5rem 0; font-weight: 700;">
                Off Rank: #{game['home_stats']['off_rank']}
            </div>
            <div style="color: #EF4444; font-size: 1rem; margin: 0.5rem 0; font-weight: 700;">
                Def Rank: #{game['home_stats']['def_rank']}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Player Selection
    st.markdown(f"### {TEAM_NAMES[game['away_team']]} Players")
    cols = st.columns(2)
    for i, player in enumerate(game['away_players']):
        with cols[i % 2]:
            if st.button(f"🎯 {player['name']} • {player['pos']}", key=f"away_{i}", use_container_width=True):
                st.session_state.selected_player = player
                st.session_state.view = 'player'
                st.rerun()

    st.markdown(f"### {TEAM_NAMES[game['home_team']]} Players")
    cols = st.columns(2)
    for i, player in enumerate(game['home_players']):
        with cols[i % 2]:
            if st.button(f"🎯 {player['name']} • {player['pos']}", key=f"home_{i}", use_container_width=True):
                st.session_state.selected_player = player
                st.session_state.view = 'player'
                st.rerun()

# ========== LAYER 3: THE PLAYER DEEP DIVE (PropFinder Modular Card) ==========
elif st.session_state.view == 'player':
    if st.button("← BACK TO MATCHUP"):
        st.session_state.view = 'matchup'
        st.rerun()

    player = st.session_state.selected_player
    game = st.session_state.selected_game

    # Determine opponent and teams
    if player in game['away_players']:
        opponent_team = game['home_team']
        player_team = game['away_team']
    else:
        opponent_team = game['away_team']
        player_team = game['home_team']

    # Get matchup difficulty
    difficulty, difficulty_text, difficulty_class = get_matchup_difficulty(opponent_team, player['pos'])

    # Visual anchors
    team_color = TEAM_COLORS.get(player_team, '#666')
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player['id']}.png"

    # Get available stats and selection
    available_stats = list(player['stats'].keys())

    # TABBED STAT CATEGORIES
    st.markdown("<h3 style='color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 1rem;'>Select Stat Category</h3>", unsafe_allow_html=True)

    cols_tabs = st.columns(len(available_stats))
    for idx, stat in enumerate(available_stats):
        with cols_tabs[idx]:
            if st.button(
                stat.upper(),
                key=f"tab_{stat}",
                use_container_width=True,
                type="primary" if st.session_state.selected_stat == stat else "secondary"
            ):
                st.session_state.selected_stat = stat
                st.rerun()

    selected_stat = st.session_state.selected_stat
    base_value = player['stats'].get(selected_stat, 20)

    # Line input
    st.markdown("<br>", unsafe_allow_html=True)
    col_line1, col_line2 = st.columns([1, 3])
    with col_line1:
        line = st.number_input("🎯 BETTING LINE", min_value=0.5, max_value=100.0,
                               value=float(base_value), step=0.5, key="line_input")

    # Generate game log and calculate all metrics
    game_log = generate_player_game_log(base_value)

    l5_games = game_log[-5:]
    l10_games = game_log[-10:]
    l20_games = game_log[-20:]

    l5_avg = sum(g['value'] for g in l5_games) / 5
    l10_avg = sum(g['value'] for g in l10_games) / 10
    l20_avg = sum(g['value'] for g in l20_games) / 20
    season_avg = sum(g['value'] for g in game_log) / len(game_log)

    l5_hits = sum(1 for g in l5_games if g['value'] > line)
    l10_hits = sum(1 for g in l10_games if g['value'] > line)
    l20_hits = sum(1 for g in l20_games if g['value'] > line)

    l5_rate = (l5_hits / 5 * 100)
    l10_rate = (l10_hits / 10 * 100)
    l20_rate = (l20_hits / 20 * 100)

    # Consistency score
    consistency = max(0, 100 - (statistics.stdev([g['value'] for g in l10_games]) / max(1, l10_avg) * 100))

    # Calculate PropScore
    propscore = calculate_propscore(l10_rate, season_avg, line, consistency, difficulty)
    propscore_class = 'propscore-high' if propscore >= 65 else 'propscore-medium' if propscore >= 40 else 'propscore-low'
    propscore_label = 'HIGH CONFIDENCE' if propscore >= 65 else 'MEDIUM' if propscore >= 40 else 'LOW CONFIDENCE'

    # ========== PROPFINDER MODULAR CARD HEADER ==========
    st.markdown(f"""
    <div class="premium-card" style="margin: 2rem 0;">
        <div style="display: flex; justify-content: space-between; align-items: start; padding: 2rem; background: linear-gradient(135deg, #1A1C24, #151820); border-bottom: 1px solid #333;">
            <!-- Player Info with Headshot + Team Logo Overlay -->
            <div style="display: flex; gap: 1.5rem; align-items: center;">
                <div style="position: relative;">
                    <img src="{headshot_url}"
                         style="width: 96px; height: 96px; border-radius: 50%; border: 4px solid {team_color}; background: #333; object-fit: cover;"
                         onerror="this.style.display='none'">
                    <div style="position: absolute; bottom: -8px; right: -8px; width: 40px; height: 40px; background: {team_color};
                                border-radius: 50%; display: flex; align-items: center; justify-content: center;
                                border: 2px solid #0E1117; font-weight: 900; font-size: 0.9rem; color: white;">
                        {player_team}
                    </div>
                </div>
                <div>
                    <h1 style="color: white; font-size: 2.5rem; font-weight: 900; margin: 0; text-transform: uppercase; letter-spacing: -1px;">
                        {player['name']}
                    </h1>
                    <div style="display: flex; gap: 1rem; margin-top: 0.5rem; align-items: center;">
                        <span style="color: #888; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">
                            {player['pos']} • #{player.get('number', '0')}
                        </span>
                        <span style="background: rgba(138, 43, 226, 0.2); color: #BA55D3; padding: 0.25rem 0.75rem;
                                     border-radius: 6px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">
                            vs {opponent_team} • {game['time']}
                        </span>
                        <!-- Matchup Difficulty Badge -->
                        <span class="difficulty-badge {difficulty_class}" style="padding: 0.35rem 0.8rem;">
                            {difficulty_text}
                        </span>
                    </div>
                </div>
            </div>
            <!-- PropScore Badge with Neon Glow -->
            <div class="{propscore_class}" style="padding: 1.5rem 2rem; border-radius: 12px; text-align: center; min-width: 140px;">
                <div style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; opacity: 0.8;">
                    PROPSCORE
                </div>
                <div style="font-size: 3.5rem; font-weight: 900; line-height: 1; margin: 0.25rem 0;">
                    {propscore}
                </div>
                <div style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; opacity: 0.8;">
                    {propscore_label}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ========== MAIN CONTENT GRID ==========
    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("<h3 style='color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 1rem;'>Hit Rates</h3>", unsafe_allow_html=True)

        # Current line display
        st.markdown(f"""
        <div style="background: #1A1C24; border: 1px solid rgba(255, 215, 0, 0.3); border-radius: 12px; padding: 1.25rem; margin-bottom: 1.5rem;">
            <div style="color: #888; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px;">
                BETTING LINE
            </div>
            <div style="display: flex; align-items: baseline; gap: 0.5rem; margin-top: 0.5rem;">
                <span style="color: #FFD700; font-size: 2.5rem; font-weight: 900;">{line}</span>
                <span style="color: #666; font-size: 0.9rem; font-weight: 700;">{selected_stat.upper()}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # HEAT-MAPPED STAT GRID (L5, L10, L20)
        def get_heat_class(rate):
            if rate >= 65:
                return 'heat-high'  # Neon Green (65%+)
            elif rate >= 50:
                return 'heat-medium'  # Yellow (50-64%)
            else:
                return 'heat-low'  # Red (<50%)

        for label, rate, hits, total in [
            ('L5', l5_rate, l5_hits, 5),
            ('L10', l10_rate, l10_hits, 10),
            ('L20', l20_rate, l20_hits, 20)
        ]:
            heat_class = get_heat_class(rate)
            st.markdown(f"""
            <div class="{heat_class}" style="border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem; display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 900; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px;">{label}</span>
                <div style="text-align: right;">
                    <div style="font-size: 1.75rem; font-weight: 900; line-height: 1;">{rate:.0f}%</div>
                    <div style="font-size: 0.75rem; font-weight: 700; opacity: 0.8;">{hits}/{total}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("<h3 style='color: #888; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 1rem;'>Last 10 Games</h3>", unsafe_allow_html=True)

        # ADVANCED MICRO-CHART
        chart = create_enhanced_bar_chart(game_log, line, selected_stat.upper())
        st.plotly_chart(chart, use_container_width=True)

        # Averages grid
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"""
            <div style="background: #1A1C24; border-radius: 12px; padding: 1.25rem; text-align: center;">
                <div style="color: #888; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px;">
                    Season Avg
                </div>
                <div style="color: white; font-size: 2rem; font-weight: 900; margin-top: 0.5rem;">
                    {season_avg:.1f}
                </div>
                <div style="color: #00FFA3; font-size: 0.75rem; font-weight: 700; margin-top: 0.25rem;">
                    {season_avg - line:+.1f} vs Line
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="background: #1A1C24; border-radius: 12px; padding: 1.25rem; text-align: center;">
                <div style="color: #888; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px;">
                    L10 Avg
                </div>
                <div style="color: white; font-size: 2rem; font-weight: 900; margin-top: 0.5rem;">
                    {l10_avg:.1f}
                </div>
                <div style="color: #00FFA3; font-size: 0.75rem; font-weight: 700; margin-top: 0.25rem;">
                    {l10_avg - season_avg:+.1f}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div style="background: #1A1C24; border-radius: 12px; padding: 1.25rem; text-align: center;">
                <div style="color: #888; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px;">
                    Consistency
                </div>
                <div style="color: white; font-size: 2rem; font-weight: 900; margin-top: 0.5rem;">
                    {consistency:.0f}
                </div>
                <div style="color: #FFC107; font-size: 0.75rem; font-weight: 700; margin-top: 0.25rem;">
                    {'HIGH' if consistency >= 70 else 'MEDIUM' if consistency >= 50 else 'LOW'}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ========== AI RECOMMENDATION CARD ==========
    if propscore >= 70:
        verdict, verdict_color = "STRONG OVER ✅", "#00FFA3"
    elif propscore >= 55:
        verdict, verdict_color = "LEAN OVER 📈", "#84cc16"
    elif propscore <= 30:
        verdict, verdict_color = "STRONG UNDER ❌", "#EF4444"
    elif propscore <= 45:
        verdict, verdict_color = "LEAN UNDER 📉", "#f97316"
    else:
        verdict, verdict_color = "TOSS UP ⚖️", "#71717a"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {verdict_color}25, {verdict_color}10);
                border: 3px solid {verdict_color}; border-radius: 16px;
                padding: 2rem; margin: 2rem 0; box-shadow: 0 0 30px {verdict_color}40;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="color: {verdict_color}; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; opacity: 0.8;">
                    AI RECOMMENDATION
                </div>
                <div style="color: {verdict_color}; font-size: 2.5rem; font-weight: 900; margin-top: 0.5rem; text-shadow: 0 0 20px {verdict_color}50;">
                    {verdict}
                </div>
                <div style="color: #888; font-size: 0.9rem; font-weight: 700; margin-top: 0.5rem;">
                    Confidence: {propscore}% • PropScore: {propscore}/100
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========== FOOTER ==========
st.markdown("""
<div style="margin-top: 4rem; padding: 2rem 0; border-top: 2px solid #333; text-align: center; color: #888;">
    <p style="font-weight: 600;">PropStats Pro © 2025 • Premium NBA Props Analytics</p>
    <p style="font-size: 0.85rem; margin-top: 0.5rem; color: #666;">⚠️ For entertainment purposes only. Gamble responsibly. 21+</p>
</div>
""", unsafe_allow_html=True)
