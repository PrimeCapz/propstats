"""
🏀 NBA Props Research Tool
Clean, game-first interface for analyzing player props
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

# Dark Theme Styling (matching React app)
st.markdown("""
<style>
    /* Main container */
    .stApp {
        background-color: #09090b;
    }

    /* Hide default Streamlit elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Custom header */
    .main-header {
        background: rgba(24, 24, 27, 0.8);
        backdrop-filter: blur(12px);
        border-bottom: 1px solid #27272a;
        padding: 1rem 0;
        margin-bottom: 2rem;
        position: sticky;
        top: 0;
        z-index: 999;
    }

    /* Game cards */
    .game-card {
        background: linear-gradient(135deg, rgba(39, 39, 42, 0.4), rgba(24, 24, 27, 0.6));
        border: 1px solid #3f3f46;
        border-radius: 16px;
        padding: 1.5rem;
        margin: 1rem 0;
        cursor: pointer;
        transition: all 0.3s ease;
    }

    .game-card:hover {
        border-color: #52525b;
        transform: translateY(-2px);
        box-shadow: 0 8px 16px rgba(0,0,0,0.3);
    }

    /* Team colors */
    .team-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 12px;
        font-weight: 700;
        font-size: 1.2rem;
    }

    /* Player cards */
    .player-card {
        background: rgba(39, 39, 42, 0.5);
        border: 1px solid #3f3f46;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        transition: all 0.2s ease;
    }

    .player-card:hover {
        background: rgba(52, 52, 56, 0.6);
        border-color: #10b981;
    }

    /* Stat badges */
    .stat-badge {
        display: inline-block;
        background: rgba(16, 185, 129, 0.1);
        color: #10b981;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-size: 0.85rem;
        font-weight: 600;
        margin: 0.25rem;
    }

    /* Hit rate colors */
    .hit-high {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.1));
        color: #10b981;
    }
    .hit-medium {
        background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), rgba(202, 138, 4, 0.1));
        color: #eab308;
    }
    .hit-low {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.1));
        color: #ef4444;
    }

    /* Buttons */
    .stButton button {
        background: rgba(39, 39, 42, 0.8);
        color: white;
        border: 1px solid #52525b;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.2s ease;
    }

    .stButton button:hover {
        background: rgba(52, 52, 56, 0.9);
        border-color: #10b981;
        transform: translateY(-1px);
    }

    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #10b981;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(39, 39, 42, 0.6);
        border-radius: 12px;
        border: 1px solid #3f3f46;
    }

    /* Remove extra padding */
    .block-container {
        padding-top: 1rem;
        max-width: 1400px;
    }
</style>
""", unsafe_allow_html=True)

# Team data with colors (matching React app)
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

# Star players for each team
TEAM_ROSTERS = {
    'LAL': [
        {'id': '2544', 'name': 'LeBron James', 'pos': 'F', 'stats': {'points': 25.5, 'rebounds': 7.2, 'assists': 8.1}},
        {'id': '203076', 'name': 'Anthony Davis', 'pos': 'F-C', 'stats': {'points': 27.8, 'rebounds': 11.3, 'assists': 3.5}}
    ],
    'GSW': [
        {'id': '201939', 'name': 'Stephen Curry', 'pos': 'G', 'stats': {'points': 26.4, 'rebounds': 4.5, 'assists': 5.2, 'threes': 4.8}},
        {'id': '1629029', 'name': 'Jonathan Kuminga', 'pos': 'F', 'stats': {'points': 16.8, 'rebounds': 5.2, 'assists': 2.1}}
    ],
    'BOS': [
        {'id': '1628369', 'name': 'Jayson Tatum', 'pos': 'F', 'stats': {'points': 28.2, 'rebounds': 8.6, 'assists': 4.9}},
        {'id': '1628464', 'name': 'Jaylen Brown', 'pos': 'G-F', 'stats': {'points': 24.7, 'rebounds': 6.1, 'assists': 3.5}}
    ],
    'DAL': [
        {'id': '1629029', 'name': 'Luka Doncic', 'pos': 'G', 'stats': {'points': 32.4, 'rebounds': 8.0, 'assists': 9.8}},
        {'id': '1626157', 'name': 'Kyrie Irving', 'pos': 'G', 'stats': {'points': 25.2, 'rebounds': 4.9, 'assists': 5.3}}
    ],
    'MIL': [
        {'id': '203507', 'name': 'Giannis Antetokounmpo', 'pos': 'F', 'stats': {'points': 31.1, 'rebounds': 11.2, 'assists': 6.1}},
        {'id': '203081', 'name': 'Damian Lillard', 'pos': 'G', 'stats': {'points': 25.7, 'rebounds': 4.3, 'assists': 7.6}}
    ],
    'PHI': [
        {'id': '203954', 'name': 'Joel Embiid', 'pos': 'C', 'stats': {'points': 29.5, 'rebounds': 10.8, 'assists': 5.2}},
        {'id': '1630178', 'name': 'Tyrese Maxey', 'pos': 'G', 'stats': {'points': 27.4, 'rebounds': 3.8, 'assists': 6.9}}
    ],
    'DEN': [
        {'id': '203999', 'name': 'Nikola Jokic', 'pos': 'C', 'stats': {'points': 27.9, 'rebounds': 12.3, 'assists': 9.2}},
        {'id': '1628378', 'name': 'Jamal Murray', 'pos': 'G', 'stats': {'points': 21.2, 'rebounds': 4.1, 'assists': 6.5}}
    ],
    'PHX': [
        {'id': '201142', 'name': 'Kevin Durant', 'pos': 'F', 'stats': {'points': 28.3, 'rebounds': 6.8, 'assists': 5.0}},
        {'id': '1626164', 'name': 'Devin Booker', 'pos': 'G', 'stats': {'points': 26.8, 'rebounds': 4.6, 'assists': 6.9}}
    ],
    'OKC': [
        {'id': '1628983', 'name': 'Shai Gilgeous-Alexander', 'pos': 'G', 'stats': {'points': 30.8, 'rebounds': 5.5, 'assists': 6.2}},
        {'id': '1630602', 'name': 'Chet Holmgren', 'pos': 'C', 'stats': {'points': 16.9, 'rebounds': 7.8, 'assists': 2.5}}
    ],
    'MIN': [
        {'id': '1630162', 'name': 'Anthony Edwards', 'pos': 'G', 'stats': {'points': 27.6, 'rebounds': 5.4, 'assists': 5.1}},
        {'id': '1626157', 'name': 'Rudy Gobert', 'pos': 'C', 'stats': {'points': 13.8, 'rebounds': 12.9, 'assists': 1.2}}
    ],
    'MIA': [
        {'id': '1628389', 'name': 'Bam Adebayo', 'pos': 'C', 'stats': {'points': 19.4, 'rebounds': 10.2, 'assists': 4.1}},
        {'id': '1630527', 'name': 'Tyler Herro', 'pos': 'G', 'stats': {'points': 23.8, 'rebounds': 5.3, 'assists': 5.0}}
    ],
    'NYK': [
        {'id': '1629649', 'name': 'Jalen Brunson', 'pos': 'G', 'stats': {'points': 28.1, 'rebounds': 3.8, 'assists': 6.7}},
        {'id': '1629628', 'name': 'Julius Randle', 'pos': 'F', 'stats': {'points': 24.3, 'rebounds': 9.2, 'assists': 5.0}}
    ],
    'CLE': [
        {'id': '1628378', 'name': 'Donovan Mitchell', 'pos': 'G', 'stats': {'points': 27.8, 'rebounds': 5.3, 'assists': 6.2}},
        {'id': '1629029', 'name': 'Evan Mobley', 'pos': 'F-C', 'stats': {'points': 16.2, 'rebounds': 9.4, 'assists': 3.1}}
    ],
    'ATL': [
        {'id': '1629027', 'name': 'Trae Young', 'pos': 'G', 'stats': {'points': 26.4, 'rebounds': 2.8, 'assists': 10.8}},
        {'id': '1629028', 'name': 'Dejounte Murray', 'pos': 'G', 'stats': {'points': 20.1, 'rebounds': 5.3, 'assists': 5.2}}
    ],
    'MEM': [
        {'id': '1629630', 'name': 'Ja Morant', 'pos': 'G', 'stats': {'points': 25.9, 'rebounds': 5.8, 'assists': 8.1}},
        {'id': '1630583', 'name': 'Jaren Jackson Jr', 'pos': 'F-C', 'stats': {'points': 18.6, 'rebounds': 6.4, 'assists': 1.6}}
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
    """Generate realistic game log for a player"""
    games = []
    dates = [(datetime.now() - timedelta(days=i*3)).strftime("%b %d") for i in range(num_games)]
    dates.reverse()

    for i, date in enumerate(dates):
        value = max(0, int(random.gauss(base_stat, base_stat * 0.3)))
        games.append({
            'date': date,
            'value': value,
            'opponent': random.choice(list(TEAM_NAMES.keys()))
        })

    return games

def create_bar_chart(games, line, stat_name):
    """Create sleek bar chart matching React app style"""
    fig = go.Figure()

    # Determine hit/miss for colors
    colors = ['#10b981' if g['value'] > line else '#ef4444' for g in games]

    fig.add_trace(go.Bar(
        x=[g['date'] for g in games],
        y=[g['value'] for g in games],
        marker=dict(
            color=colors,
            line=dict(color='#18181b', width=1)
        ),
        text=[g['value'] for g in games],
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>%{y}<br><extra></extra>'
    ))

    # Add line threshold
    fig.add_hline(
        y=line,
        line_dash="dash",
        line_color="#eab308",
        line_width=2,
        annotation_text=f"Line: {line}",
        annotation_position="right"
    )

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', family='Arial'),
        height=300,
        margin=dict(l=10, r=10, t=10, b=40),
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(63, 63, 70, 0.3)',
            showline=False,
            zeroline=False,
            title=stat_name
        ),
        hovermode='x unified'
    )

    return fig

# ========== MAIN APP ==========

# Initialize session state
if 'selected_game' not in st.session_state:
    st.session_state.selected_game = None
if 'selected_player' not in st.session_state:
    st.session_state.selected_player = None

# Header
st.markdown("""
<div class="main-header">
    <div style="max-width: 1400px; margin: 0 auto; padding: 0 1rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #10b981, #059669); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.5rem;">P</div>
            <span style="font-size: 1.5rem; font-weight: 700; color: white;">PropStats</span>
        </div>
        <div style="color: #71717a; font-size: 0.9rem;">🏀 NBA Player Props Research</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Back button if player is selected
if st.session_state.selected_player:
    col1, col2, col3 = st.columns([1, 6, 1])
    with col1:
        if st.button("← Back to Games"):
            st.session_state.selected_player = None
            st.rerun()

# Main Content
if st.session_state.selected_player is None:
    # Show today's games
    st.markdown(f"""
    <div style="margin-bottom: 2rem;">
        <h1 style="color: white; font-size: 2rem; font-weight: 800; margin-bottom: 0.5rem;">Today's Games</h1>
        <p style="color: #71717a; font-size: 1rem;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
    </div>
    """, unsafe_allow_html=True)

    games = generate_todays_games()

    for idx, game in enumerate(games):
        away_color = TEAM_COLORS.get(game['away_team'], '#666')
        home_color = TEAM_COLORS.get(game['home_team'], '#666')

        with st.expander(
            f"🏀  {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]}  •  {game['time']}",
            expanded=(idx < 2)  # Expand first 2 games by default
        ):
            st.markdown(f"""
            <div style="display: flex; justify-content: space-around; align-items: center; padding: 1rem 0; border-bottom: 1px solid #3f3f46; margin-bottom: 1rem;">
                <div style="text-align: center;">
                    <div class="team-badge" style="background: linear-gradient(135deg, {away_color}40, {away_color}20); color: {away_color};">
                        {game['away_team']}
                    </div>
                    <div style="color: #a1a1aa; font-size: 0.9rem; margin-top: 0.5rem;">Away</div>
                </div>
                <div style="color: #71717a; font-size: 1.5rem; font-weight: 700;">@</div>
                <div style="text-align: center;">
                    <div class="team-badge" style="background: linear-gradient(135deg, {home_color}40, {home_color}20); color: {home_color};">
                        {game['home_team']}
                    </div>
                    <div style="color: #a1a1aa; font-size: 0.9rem; margin-top: 0.5rem;">Home</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Away team players
            st.markdown(f"**{TEAM_NAMES[game['away_team']]} Players**")
            cols = st.columns(2)
            for i, player in enumerate(game['away_players']):
                with cols[i % 2]:
                    if st.button(
                        f"{player['name']} • {player['pos']}",
                        key=f"away_{idx}_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected_player = player
                        st.session_state.selected_game = game
                        st.rerun()

                    # Show quick stats
                    stats_html = "".join([
                        f'<span class="stat-badge">{k.upper()}: {v}</span>'
                        for k, v in list(player['stats'].items())[:3]
                    ])
                    st.markdown(f'<div style="margin: 0.5rem 0;">{stats_html}</div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Home team players
            st.markdown(f"**{TEAM_NAMES[game['home_team']]} Players**")
            cols = st.columns(2)
            for i, player in enumerate(game['home_players']):
                with cols[i % 2]:
                    if st.button(
                        f"{player['name']} • {player['pos']}",
                        key=f"home_{idx}_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected_player = player
                        st.session_state.selected_game = game
                        st.rerun()

                    # Show quick stats
                    stats_html = "".join([
                        f'<span class="stat-badge">{k.upper()}: {v}</span>'
                        for k, v in list(player['stats'].items())[:3]
                    ])
                    st.markdown(f'<div style="margin: 0.5rem 0;">{stats_html}</div>', unsafe_allow_html=True)

else:
    # Player Analysis View
    player = st.session_state.selected_player
    game = st.session_state.selected_game

    # Player header
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(5, 150, 105, 0.05));
                border: 1px solid #3f3f46; border-radius: 16px; padding: 2rem; margin-bottom: 2rem;">
        <h1 style="color: white; font-size: 2.5rem; margin-bottom: 0.5rem;">{player['name']}</h1>
        <p style="color: #a1a1aa; font-size: 1.1rem;">
            {player['pos']} • {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]} • {game['time']}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stat selection
    available_stats = list(player['stats'].keys())

    col1, col2, col3 = st.columns([2, 2, 4])
    with col1:
        selected_stat = st.selectbox(
            "Select Stat",
            options=available_stats,
            format_func=lambda x: x.upper()
        )

    base_value = player['stats'][selected_stat]

    with col2:
        line = st.number_input(
            "Line",
            min_value=0.5,
            max_value=100.0,
            value=float(base_value),
            step=0.5
        )

    # Generate game log
    game_log = generate_player_game_log(base_value)

    # Calculate hit rate
    hits = sum(1 for g in game_log if g['value'] > line)
    total = len(game_log)
    hit_rate = (hits / total * 100) if total > 0 else 0

    # Calculate averages
    l5_avg = sum(g['value'] for g in game_log[-5:]) / 5
    l10_avg = sum(g['value'] for g in game_log[-10:]) / 10
    season_avg = sum(g['value'] for g in game_log) / len(game_log)

    # Metrics
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
        <div class="{color_class}" style="padding: 1rem; border-radius: 12px; text-align: center;">
            <div style="font-size: 0.75rem; opacity: 0.7; margin-bottom: 0.25rem;">Hit Rate</div>
            <div style="font-size: 2rem; font-weight: 800;">{hit_rate:.0f}%</div>
            <div style="font-size: 0.85rem; opacity: 0.9;">{hits}/{total} Games</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Chart
    st.markdown(f"### Last {len(game_log)} Games")
    chart = create_bar_chart(game_log, line, selected_stat.upper())
    st.plotly_chart(chart, use_container_width=True)

    # Recommendation
    if hit_rate >= 70 and season_avg > line:
        verdict = "STRONG OVER"
        verdict_color = "#10b981"
        confidence = "High"
    elif hit_rate >= 55 and season_avg > line:
        verdict = "LEAN OVER"
        verdict_color = "#84cc16"
        confidence = "Medium"
    elif hit_rate <= 30 and season_avg < line:
        verdict = "STRONG UNDER"
        verdict_color = "#ef4444"
        confidence = "High"
    elif hit_rate <= 45 and season_avg < line:
        verdict = "LEAN UNDER"
        verdict_color = "#f97316"
        confidence = "Medium"
    else:
        verdict = "TOSS UP"
        verdict_color = "#71717a"
        confidence = "Low"

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {verdict_color}20, {verdict_color}10);
                border: 2px solid {verdict_color}; border-radius: 16px;
                padding: 2rem; text-align: center; margin: 2rem 0;">
        <div style="font-size: 0.9rem; color: #a1a1aa; margin-bottom: 0.5rem;">Recommendation</div>
        <div style="font-size: 2.5rem; font-weight: 900; color: {verdict_color}; margin-bottom: 0.5rem;">{verdict}</div>
        <div style="font-size: 1rem; color: #a1a1aa;">Confidence: {confidence}</div>
    </div>
    """, unsafe_allow_html=True)

    # Game Log Table
    with st.expander("📋 Detailed Game Log"):
        df = pd.DataFrame(game_log)
        df['Hit'] = df['value'] > line
        df['vs Line'] = df['value'] - line
        df = df[['date', 'opponent', 'value', 'Hit', 'vs Line']]
        df.columns = ['Date', 'Opponent', selected_stat.upper(), 'Hit', '+/-']
        st.dataframe(df, use_container_width=True, hide_index=True)

# Footer
st.markdown("""
<div style="margin-top: 4rem; padding: 2rem 0; border-top: 1px solid #3f3f46; text-align: center; color: #71717a;">
    <p>PropStats © 2025 • Data updates every 6 hours • For entertainment purposes only</p>
    <p style="font-size: 0.85rem; margin-top: 0.5rem;">⚠️ Gamble responsibly. Must be 21+ where legal.</p>
</div>
""", unsafe_allow_html=True)
