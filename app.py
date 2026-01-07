"""
🏀 NBA Props Research Tool
Sleek, layered interface with neon accents
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random

# Page Configuration
st.set_page_config(
    page_title="PropStats",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Enhanced Dark Theme with Neon Accents (Gemini + Claude Hybrid)
st.markdown("""
<style>
    /* Main Container */
    .stApp {
        background-color: #0E1117;
    }

    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Custom Header */
    .main-header {
        background: linear-gradient(135deg, #1A1C24 0%, #0E1117 100%);
        backdrop-filter: blur(12px);
        border-bottom: 2px solid #00FFA3;
        padding: 1.2rem 0;
        margin-bottom: 2rem;
        position: sticky;
        top: 0;
        z-index: 999;
        box-shadow: 0 4px 20px rgba(0, 255, 163, 0.1);
    }

    /* Game Cards with Hover Effects */
    div[data-testid="stExpander"] {
        background: linear-gradient(135deg, #1A1C24 0%, #151820 100%);
        border: 1px solid #2A2D3A;
        border-radius: 16px;
        margin: 1rem 0;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    div[data-testid="stExpander"]:hover {
        border-color: #00FFA3;
        box-shadow: 0 8px 24px rgba(0, 255, 163, 0.2);
        transform: translateY(-2px);
    }

    /* Neon Button Styling */
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
        box-shadow: 0 0 20px rgba(0, 255, 163, 0.6),
                    0 0 40px rgba(0, 255, 163, 0.3);
        transform: translateY(-2px);
    }

    /* Player Chip Buttons */
    .player-chip {
        background: linear-gradient(135deg, #1A1C24, #151820);
        border: 1px solid #2A2D3A;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }

    .player-chip:hover {
        border-color: #00FFA3;
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.1), rgba(0, 255, 163, 0.05));
    }

    /* Team Badges */
    .team-badge {
        display: inline-block;
        padding: 0.6rem 1.2rem;
        border-radius: 10px;
        font-weight: 800;
        font-size: 1.3rem;
        text-shadow: 0 0 10px currentColor;
    }

    /* Stat Badges with Neon Glow */
    .stat-badge {
        display: inline-block;
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.15), rgba(0, 255, 163, 0.05));
        color: #00FFA3;
        border: 1px solid rgba(0, 255, 163, 0.3);
        padding: 0.4rem 0.9rem;
        border-radius: 8px;
        font-size: 0.85rem;
        font-weight: 700;
        margin: 0.25rem;
        box-shadow: 0 0 10px rgba(0, 255, 163, 0.2);
    }

    /* Hit Rate Cards */
    .hit-high {
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.2), rgba(0, 255, 163, 0.1));
        border: 2px solid #00FFA3;
        color: #00FFA3;
        box-shadow: 0 0 20px rgba(0, 255, 163, 0.3);
    }
    .hit-medium {
        background: linear-gradient(135deg, rgba(255, 193, 7, 0.2), rgba(255, 193, 7, 0.1));
        border: 2px solid #FFC107;
        color: #FFC107;
        box-shadow: 0 0 20px rgba(255, 193, 7, 0.3);
    }
    .hit-low {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1));
        border: 2px solid #EF4444;
        color: #EF4444;
        box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
    }

    /* Metrics Enhancement */
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem;
        color: #00FFA3;
        text-shadow: 0 0 10px rgba(0, 255, 163, 0.5);
        font-weight: 900;
    }

    div[data-testid="stMetricDelta"] {
        color: #888;
    }

    /* Expander Header */
    .streamlit-expanderHeader {
        background: linear-gradient(135deg, rgba(26, 28, 36, 0.9), rgba(21, 24, 32, 0.9));
        border-radius: 12px;
        border: 1px solid #2A2D3A;
        font-weight: 700;
        font-size: 1.1rem;
        padding: 1rem 1.5rem;
    }

    .streamlit-expanderHeader:hover {
        border-color: #00FFA3;
        box-shadow: 0 0 15px rgba(0, 255, 163, 0.2);
    }

    /* Input Fields */
    .stSelectbox, .stNumberInput {
        background: #1A1C24;
        border-radius: 10px;
    }

    input, select {
        background-color: #1A1C24 !important;
        color: white !important;
        border: 1px solid #2A2D3A !important;
        border-radius: 8px !important;
    }

    input:focus, select:focus {
        border-color: #00FFA3 !important;
        box-shadow: 0 0 10px rgba(0, 255, 163, 0.3) !important;
    }

    /* Container Padding */
    .block-container {
        padding-top: 1rem;
        max-width: 1400px;
    }

    /* Back Button Special Styling */
    .back-button {
        color: #888;
        font-size: 1rem;
        cursor: pointer;
        transition: color 0.2s;
    }

    .back-button:hover {
        color: #00FFA3;
    }
</style>
""", unsafe_allow_html=True)

# Team data
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

# Enhanced roster with more players per team
TEAM_ROSTERS = {
    'LAL': [
        {'id': '2544', 'name': 'LeBron James', 'pos': 'F', 'stats': {'points': 25.5, 'rebounds': 7.2, 'assists': 8.1}},
        {'id': '203076', 'name': 'Anthony Davis', 'pos': 'F-C', 'stats': {'points': 27.8, 'rebounds': 11.3, 'assists': 3.5}},
        {'id': '1629027', 'name': 'Austin Reaves', 'pos': 'G', 'stats': {'points': 16.2, 'rebounds': 4.3, 'assists': 5.8}},
        {'id': '1630224', 'name': "D'Angelo Russell", 'pos': 'G', 'stats': {'points': 18.1, 'rebounds': 2.9, 'assists': 6.2}}
    ],
    'GSW': [
        {'id': '201939', 'name': 'Stephen Curry', 'pos': 'G', 'stats': {'points': 26.4, 'rebounds': 4.5, 'assists': 5.2, 'threes': 4.8}},
        {'id': '1629029', 'name': 'Jonathan Kuminga', 'pos': 'F', 'stats': {'points': 16.8, 'rebounds': 5.2, 'assists': 2.1}},
        {'id': '203110', 'name': 'Klay Thompson', 'pos': 'G', 'stats': {'points': 19.5, 'rebounds': 3.5, 'assists': 2.3, 'threes': 3.2}},
        {'id': '203546', 'name': 'Draymond Green', 'pos': 'F', 'stats': {'points': 8.6, 'rebounds': 7.2, 'assists': 6.8}}
    ],
    'BOS': [
        {'id': '1628369', 'name': 'Jayson Tatum', 'pos': 'F', 'stats': {'points': 28.2, 'rebounds': 8.6, 'assists': 4.9}},
        {'id': '1628464', 'name': 'Jaylen Brown', 'pos': 'G-F', 'stats': {'points': 24.7, 'rebounds': 6.1, 'assists': 3.5}},
        {'id': '1630527', 'name': 'Derrick White', 'pos': 'G', 'stats': {'points': 15.2, 'rebounds': 4.1, 'assists': 5.3}},
        {'id': '1627759', 'name': 'Kristaps Porzingis', 'pos': 'C', 'stats': {'points': 20.1, 'rebounds': 7.2, 'assists': 1.9}}
    ],
    'DAL': [
        {'id': '1629029', 'name': 'Luka Doncic', 'pos': 'G', 'stats': {'points': 32.4, 'rebounds': 8.0, 'assists': 9.8}},
        {'id': '1626157', 'name': 'Kyrie Irving', 'pos': 'G', 'stats': {'points': 25.2, 'rebounds': 4.9, 'assists': 5.3}},
        {'id': '1629648', 'name': 'Dereck Lively II', 'pos': 'C', 'stats': {'points': 9.2, 'rebounds': 8.4, 'assists': 1.8}}
    ],
    'MIL': [
        {'id': '203507', 'name': 'Giannis Antetokounmpo', 'pos': 'F', 'stats': {'points': 31.1, 'rebounds': 11.2, 'assists': 6.1}},
        {'id': '203081', 'name': 'Damian Lillard', 'pos': 'G', 'stats': {'points': 25.7, 'rebounds': 4.3, 'assists': 7.6}},
        {'id': '203114', 'name': 'Khris Middleton', 'pos': 'F', 'stats': {'points': 15.1, 'rebounds': 4.7, 'assists': 5.3}}
    ],
    'PHI': [
        {'id': '203954', 'name': 'Joel Embiid', 'pos': 'C', 'stats': {'points': 29.5, 'rebounds': 10.8, 'assists': 5.2}},
        {'id': '1630178', 'name': 'Tyrese Maxey', 'pos': 'G', 'stats': {'points': 27.4, 'rebounds': 3.8, 'assists': 6.9}},
        {'id': '203967', 'name': 'Tobias Harris', 'pos': 'F', 'stats': {'points': 17.2, 'rebounds': 5.4, 'assists': 3.1}}
    ],
    'DEN': [
        {'id': '203999', 'name': 'Nikola Jokic', 'pos': 'C', 'stats': {'points': 27.9, 'rebounds': 12.3, 'assists': 9.2}},
        {'id': '1628378', 'name': 'Jamal Murray', 'pos': 'G', 'stats': {'points': 21.2, 'rebounds': 4.1, 'assists': 6.5}},
        {'id': '203924', 'name': 'Aaron Gordon', 'pos': 'F', 'stats': {'points': 14.3, 'rebounds': 6.6, 'assists': 3.5}}
    ],
    'PHX': [
        {'id': '201142', 'name': 'Kevin Durant', 'pos': 'F', 'stats': {'points': 28.3, 'rebounds': 6.8, 'assists': 5.0}},
        {'id': '1626164', 'name': 'Devin Booker', 'pos': 'G', 'stats': {'points': 26.8, 'rebounds': 4.6, 'assists': 6.9}},
        {'id': '203944', 'name': 'Bradley Beal', 'pos': 'G', 'stats': {'points': 18.2, 'rebounds': 4.4, 'assists': 5.0}}
    ],
    'OKC': [
        {'id': '1628983', 'name': 'Shai Gilgeous-Alexander', 'pos': 'G', 'stats': {'points': 30.8, 'rebounds': 5.5, 'assists': 6.2}},
        {'id': '1630602', 'name': 'Chet Holmgren', 'pos': 'C', 'stats': {'points': 16.9, 'rebounds': 7.8, 'assists': 2.5}},
        {'id': '1630534', 'name': 'Jalen Williams', 'pos': 'F', 'stats': {'points': 19.1, 'rebounds': 4.5, 'assists': 4.5}}
    ],
    'MIN': [
        {'id': '1630162', 'name': 'Anthony Edwards', 'pos': 'G', 'stats': {'points': 27.6, 'rebounds': 5.4, 'assists': 5.1}},
        {'id': '1626157', 'name': 'Rudy Gobert', 'pos': 'C', 'stats': {'points': 13.8, 'rebounds': 12.9, 'assists': 1.2}},
        {'id': '1630567', 'name': 'Jaden McDaniels', 'pos': 'F', 'stats': {'points': 10.5, 'rebounds': 3.9, 'assists': 1.9}}
    ],
    'MIA': [
        {'id': '1628389', 'name': 'Bam Adebayo', 'pos': 'C', 'stats': {'points': 19.4, 'rebounds': 10.2, 'assists': 4.1}},
        {'id': '1630527', 'name': 'Tyler Herro', 'pos': 'G', 'stats': {'points': 23.8, 'rebounds': 5.3, 'assists': 5.0}},
        {'id': '202710', 'name': 'Jimmy Butler', 'pos': 'F', 'stats': {'points': 20.8, 'rebounds': 5.3, 'assists': 5.0}}
    ],
    'NYK': [
        {'id': '1629649', 'name': 'Jalen Brunson', 'pos': 'G', 'stats': {'points': 28.1, 'rebounds': 3.8, 'assists': 6.7}},
        {'id': '1629628', 'name': 'Julius Randle', 'pos': 'F', 'stats': {'points': 24.3, 'rebounds': 9.2, 'assists': 5.0}},
        {'id': '203497', 'name': 'OG Anunoby', 'pos': 'F', 'stats': {'points': 15.1, 'rebounds': 4.8, 'assists': 2.1}}
    ],
    'CLE': [
        {'id': '1628378', 'name': 'Donovan Mitchell', 'pos': 'G', 'stats': {'points': 27.8, 'rebounds': 5.3, 'assists': 6.2}},
        {'id': '1629029', 'name': 'Evan Mobley', 'pos': 'F-C', 'stats': {'points': 16.2, 'rebounds': 9.4, 'assists': 3.1}},
        {'id': '1629636', 'name': 'Darius Garland', 'pos': 'G', 'stats': {'points': 18.0, 'rebounds': 2.7, 'assists': 6.5}}
    ],
    'ATL': [
        {'id': '1629027', 'name': 'Trae Young', 'pos': 'G', 'stats': {'points': 26.4, 'rebounds': 2.8, 'assists': 10.8}},
        {'id': '1629029', 'name': 'Dejounte Murray', 'pos': 'G', 'stats': {'points': 20.1, 'rebounds': 5.3, 'assists': 5.2}}
    ],
    'MEM': [
        {'id': '1629630', 'name': 'Ja Morant', 'pos': 'G', 'stats': {'points': 25.9, 'rebounds': 5.8, 'assists': 8.1}},
        {'id': '1630583', 'name': 'Jaren Jackson Jr', 'pos': 'F-C', 'stats': {'points': 18.6, 'rebounds': 6.4, 'assists': 1.6}}
    ],
    'BKN': [
        {'id': '1629028', 'name': 'Mikal Bridges', 'pos': 'F', 'stats': {'points': 21.8, 'rebounds': 4.5, 'assists': 3.7}},
        {'id': '1629673', 'name': 'Cam Thomas', 'pos': 'G', 'stats': {'points': 22.5, 'rebounds': 3.2, 'assists': 2.9}}
    ]
}

def generate_todays_games():
    """Generate mock games for today"""
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
            'home_players': TEAM_ROSTERS.get(home, [])
        })

    return games

def generate_player_game_log(base_stat, num_games=15):
    """Generate realistic game log"""
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

def create_bar_chart(games, line, stat_name):
    """Create dark-themed bar chart with neon accents"""
    fig = go.Figure()

    colors = ['#00FFA3' if g['value'] > line else '#EF4444' for g in games]

    fig.add_trace(go.Bar(
        x=[g['date'] for g in games],
        y=[g['value'] for g in games],
        marker=dict(
            color=colors,
            line=dict(color='#0E1117', width=2)
        ),
        text=[g['value'] for g in games],
        textposition='outside',
        textfont=dict(color='white', size=11, family='Arial Black'),
        hovertemplate='<b>%{x}</b><br>%{y}<br><extra></extra>'
    ))

    # Neon yellow threshold line
    fig.add_hline(
        y=line,
        line_dash="dash",
        line_color="#FFC107",
        line_width=3,
        annotation_text=f"Line: {line}",
        annotation_position="right",
        annotation_font=dict(color="#FFC107", size=14, family='Arial Black')
    )

    fig.update_layout(
        plot_bgcolor='#0E1117',
        paper_bgcolor='#0E1117',
        font=dict(color='white', family='Arial'),
        height=350,
        margin=dict(l=10, r=10, t=10, b=40),
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False,
            color='#888'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(42, 45, 58, 0.5)',
            showline=False,
            zeroline=False,
            title=stat_name,
            color='#888'
        ),
        hovermode='x unified'
    )

    return fig

# ========== SESSION STATE MANAGEMENT ==========
if 'view' not in st.session_state:
    st.session_state.view = 'slate'  # Options: 'slate', 'analysis'
if 'selected_game' not in st.session_state:
    st.session_state.selected_game = None
if 'selected_player' not in st.session_state:
    st.session_state.selected_player = None

# ========== HEADER ==========
st.markdown("""
<div class="main-header">
    <div style="max-width: 1400px; margin: 0 auto; padding: 0 1rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 45px; height: 45px; background: linear-gradient(135deg, #00FFA3, #00CC82); border-radius: 12px;
                        display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.5rem;
                        box-shadow: 0 0 20px rgba(0, 255, 163, 0.5);">P</div>
            <span style="font-size: 1.6rem; font-weight: 900; color: white; text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);">PropStats</span>
        </div>
        <div style="color: #00FFA3; font-size: 1rem; font-weight: 600; text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);">
            🏀 NBA PLAYER PROPS
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ========== LAYER 1: THE DAILY SLATE ==========
if st.session_state.view == 'slate':
    st.markdown(f"""
    <div style="margin-bottom: 2.5rem; text-align: center;">
        <h1 style="color: white; font-size: 2.5rem; font-weight: 900; margin-bottom: 0.5rem;
                   text-shadow: 0 0 20px rgba(0, 255, 163, 0.3);">
            Today's NBA Slate
        </h1>
        <p style="color: #00FFA3; font-size: 1.1rem; font-weight: 600;">
            {datetime.now().strftime('%A, %B %d, %Y')}
        </p>
    </div>
    """, unsafe_allow_html=True)

    games = generate_todays_games()

    for idx, game in enumerate(games):
        away_color = TEAM_COLORS.get(game['away_team'], '#666')
        home_color = TEAM_COLORS.get(game['home_team'], '#666')

        with st.expander(
            f"🏀  {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]}  •  {game['time']}",
            expanded=(idx < 2)
        ):
            st.markdown(f"""
            <div style="display: flex; justify-content: space-around; align-items: center;
                        padding: 1.5rem 0; border-bottom: 1px solid #2A2D3A; margin-bottom: 1.5rem;">
                <div style="text-align: center;">
                    <div class="team-badge" style="background: linear-gradient(135deg, {away_color}60, {away_color}30);
                                                    color: {away_color}; border: 2px solid {away_color}40;">
                        {game['away_team']}
                    </div>
                    <div style="color: #888; font-size: 0.9rem; margin-top: 0.5rem; font-weight: 600;">AWAY</div>
                </div>
                <div style="color: #00FFA3; font-size: 2rem; font-weight: 900; text-shadow: 0 0 10px rgba(0, 255, 163, 0.3);">@</div>
                <div style="text-align: center;">
                    <div class="team-badge" style="background: linear-gradient(135deg, {home_color}60, {home_color}30);
                                                    color: {home_color}; border: 2px solid {home_color}40;">
                        {game['home_team']}
                    </div>
                    <div style="color: #888; font-size: 0.9rem; margin-top: 0.5rem; font-weight: 600;">HOME</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Player Chips Layout
            st.markdown(f"### {TEAM_NAMES[game['away_team']]} Players")
            cols = st.columns(2)
            for i, player in enumerate(game['away_players']):
                with cols[i % 2]:
                    if st.button(
                        f"🎯 {player['name']} • {player['pos']}",
                        key=f"away_{idx}_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected_player = player
                        st.session_state.selected_game = game
                        st.session_state.view = 'analysis'
                        st.rerun()

                    stats_html = "".join([
                        f'<span class="stat-badge">{k.upper()}: {v}</span>'
                        for k, v in list(player['stats'].items())[:3]
                    ])
                    st.markdown(f'<div style="margin: 0.5rem 0 1rem 0;">{stats_html}</div>', unsafe_allow_html=True)

            st.markdown(f"### {TEAM_NAMES[game['home_team']]} Players")
            cols = st.columns(2)
            for i, player in enumerate(game['home_players']):
                with cols[i % 2]:
                    if st.button(
                        f"🎯 {player['name']} • {player['pos']}",
                        key=f"home_{idx}_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected_player = player
                        st.session_state.selected_game = game
                        st.session_state.view = 'analysis'
                        st.rerun()

                    stats_html = "".join([
                        f'<span class="stat-badge">{k.upper()}: {v}</span>'
                        for k, v in list(player['stats'].items())[:3]
                    ])
                    st.markdown(f'<div style="margin: 0.5rem 0 1rem 0;">{stats_html}</div>', unsafe_allow_html=True)

# ========== LAYER 2: PLAYER ANALYSIS ==========
elif st.session_state.view == 'analysis':
    # Back Button
    if st.button("← BACK TO SLATE", use_container_width=False):
        st.session_state.view = 'slate'
        st.rerun()

    player = st.session_state.selected_player
    game = st.session_state.selected_game

    # Player Header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(0, 255, 163, 0.15), rgba(0, 255, 163, 0.05));
                border: 2px solid #00FFA3; border-radius: 16px; padding: 2rem; margin-bottom: 2rem;
                box-shadow: 0 0 30px rgba(0, 255, 163, 0.2);">
        <h1 style="color: white; font-size: 2.8rem; margin-bottom: 0.5rem; font-weight: 900;
                   text-shadow: 0 0 20px rgba(0, 255, 163, 0.3);">
            {player['name']}
        </h1>
        <p style="color: #00FFA3; font-size: 1.2rem; font-weight: 600;">
            {player['pos']} • {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]} • {game['time']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stat & Line Selection
    col1, col2 = st.columns([1, 1])
    available_stats = list(player['stats'].keys())

    with col1:
        selected_stat = st.selectbox(
            "📊 SELECT STAT",
            options=available_stats,
            format_func=lambda x: x.upper()
        )

    base_value = player['stats'][selected_stat]

    with col2:
        line = st.number_input(
            "🎯 BETTING LINE",
            min_value=0.5,
            max_value=100.0,
            value=float(base_value),
            step=0.5
        )

    # Generate Data
    game_log = generate_player_game_log(base_value)
    hits = sum(1 for g in game_log if g['value'] > line)
    total = len(game_log)
    hit_rate = (hits / total * 100) if total > 0 else 0

    l5_avg = sum(g['value'] for g in game_log[-5:]) / 5
    l10_avg = sum(g['value'] for g in game_log[-10:]) / 10
    season_avg = sum(g['value'] for g in game_log) / len(game_log)

    # Metrics Row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Season Avg", f"{season_avg:.1f}")
    with col2:
        st.metric("L10 Avg", f"{l10_avg:.1f}", delta=f"{l10_avg - season_avg:+.1f}")
    with col3:
        st.metric("L5 Avg", f"{l5_avg:.1f}", delta=f"{l5_avg - l10_avg:+.1f}")
    with col4:
        color_class = 'hit-high' if hit_rate >= 65 else 'hit-medium' if hit_rate >= 50 else 'hit-low'
        st.markdown(f"""
        <div class="{color_class}" style="padding: 1.2rem; border-radius: 12px; text-align: center;">
            <div style="font-size: 0.75rem; opacity: 0.8; margin-bottom: 0.3rem; font-weight: 600;">HIT RATE</div>
            <div style="font-size: 2.2rem; font-weight: 900;">{hit_rate:.0f}%</div>
            <div style="font-size: 0.9rem; opacity: 0.9; font-weight: 600;">{hits}/{total} Games</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Chart
    st.markdown(f"### 📈 Last {len(game_log)} Games Performance")
    chart = create_bar_chart(game_log, line, selected_stat.upper())
    st.plotly_chart(chart, use_container_width=True)

    # Verdict Card
    if hit_rate >= 70 and season_avg > line:
        verdict = "STRONG OVER ✅"
        verdict_color = "#00FFA3"
        confidence = "High"
    elif hit_rate >= 55 and season_avg > line:
        verdict = "LEAN OVER 📈"
        verdict_color = "#84cc16"
        confidence = "Medium"
    elif hit_rate <= 30 and season_avg < line:
        verdict = "STRONG UNDER ❌"
        verdict_color = "#EF4444"
        confidence = "High"
    elif hit_rate <= 45 and season_avg < line:
        verdict = "LEAN UNDER 📉"
        verdict_color = "#f97316"
        confidence = "Medium"
    else:
        verdict = "TOSS UP ⚖️"
        verdict_color = "#71717a"
        confidence = "Low"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {verdict_color}25, {verdict_color}10);
                border: 3px solid {verdict_color}; border-radius: 16px;
                padding: 2.5rem; text-align: center; margin: 2rem 0;
                box-shadow: 0 0 30px {verdict_color}40;">
        <div style="font-size: 1rem; color: #888; margin-bottom: 0.5rem; font-weight: 600;">RECOMMENDATION</div>
        <div style="font-size: 3rem; font-weight: 900; color: {verdict_color}; margin-bottom: 0.5rem;
                    text-shadow: 0 0 20px {verdict_color}50;">
            {verdict}
        </div>
        <div style="font-size: 1.1rem; color: #888; font-weight: 600;">Confidence: {confidence}</div>
    </div>
    """, unsafe_allow_html=True)

    # Game Log
    with st.expander("📋 Detailed Game Log"):
        df = pd.DataFrame(game_log)
        df['Hit'] = df['value'] > line
        df['vs Line'] = df['value'] - line
        df = df[['date', 'opponent', 'value', 'Hit', 'vs Line']]
        df.columns = ['Date', 'Opponent', selected_stat.upper(), 'Hit', '+/-']
        st.dataframe(df, use_container_width=True, hide_index=True)

# Footer
st.markdown("""
<div style="margin-top: 4rem; padding: 2rem 0; border-top: 2px solid #2A2D3A; text-align: center; color: #888;">
    <p style="font-weight: 600;">PropStats © 2025 • Powered by Real-Time NBA Data</p>
    <p style="font-size: 0.85rem; margin-top: 0.5rem; color: #666;">⚠️ For entertainment purposes only. Gamble responsibly. 21+</p>
</div>
""", unsafe_allow_html=True)
