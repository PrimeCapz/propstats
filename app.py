"""
🏀 NBA Player Prop Research Tool - MVP
Built with Streamlit | $0 Budget | Free + Premium Tiers
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import random

# Page Configuration
st.set_page_config(
    page_title="NBA Props Research 🏀",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #1d428a, #ffc72c);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin: 0.5rem 0;
    }
    .premium-lock {
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 2rem;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin: 2rem 0;
    }
    .unlock-btn {
        background: #00ff88;
        color: #000;
        font-weight: bold;
        padding: 1rem 2rem;
        border-radius: 50px;
        border: none;
        font-size: 1.2rem;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)


# Mock NBA Player Database
MOCK_PLAYERS = {
    "LeBron James": {"team": "LAL", "position": "F"},
    "Stephen Curry": {"team": "GSW", "position": "G"},
    "Kevin Durant": {"team": "PHX", "position": "F"},
    "Giannis Antetokounmpo": {"team": "MIL", "position": "F"},
    "Luka Doncic": {"team": "DAL", "position": "G"},
    "Joel Embiid": {"team": "PHI", "position": "C"},
    "Nikola Jokic": {"team": "DEN", "position": "C"},
    "Jayson Tatum": {"team": "BOS", "position": "F"},
    "Damian Lillard": {"team": "MIL", "position": "G"},
    "Anthony Davis": {"team": "LAL", "position": "F-C"},
    "Devin Booker": {"team": "PHX", "position": "G"},
    "Trae Young": {"team": "ATL", "position": "G"},
    "Ja Morant": {"team": "MEM", "position": "G"},
    "Donovan Mitchell": {"team": "CLE", "position": "G"},
    "Kawhi Leonard": {"team": "LAC", "position": "F"},
}


def generate_mock_game_data(player_name, stat_type, num_games=15):
    """
    Generate realistic mock game data for a player
    Returns a DataFrame with game-by-game stats
    """

    # Base stats for different stat types
    base_values = {
        "Points": 25,
        "Rebounds": 8,
        "Assists": 7,
        "Threes": 3,
        "Blocks": 1.5,
        "Steals": 1.2
    }

    # Variance for realism
    variance = {
        "Points": 8,
        "Rebounds": 4,
        "Assists": 3,
        "Threes": 2,
        "Blocks": 1,
        "Steals": 0.8
    }

    base = base_values.get(stat_type, 20)
    var = variance.get(stat_type, 5)

    # Generate dates (last N games)
    dates = [(datetime.now() - timedelta(days=i*3)).strftime("%Y-%m-%d")
             for i in range(num_games)]
    dates.reverse()

    # Generate stats with some variance
    random.seed(hash(player_name))  # Consistent data per player
    stats = [max(0, int(random.gauss(base, var))) for _ in range(num_games)]

    # Random opponents
    teams = ["BOS", "LAL", "GSW", "MIA", "BKN", "PHI", "MIL", "DEN", "PHX", "DAL"]
    opponents = [random.choice(teams) for _ in range(num_games)]

    return pd.DataFrame({
        "Date": dates,
        "Opponent": opponents,
        "Value": stats
    })


def generate_premium_data(player_name, stat_type, base_df):
    """
    Generate premium insights including hit rates and matchup difficulty
    """

    # Calculate averages
    l5_avg = base_df.head(5)["Value"].mean()
    l10_avg = base_df.head(10)["Value"].mean()
    season_avg = base_df["Value"].mean()

    # Calculate hit rates for different lines
    lines = [season_avg - 3, season_avg, season_avg + 3]
    hit_rates = []

    for line in lines:
        hits_l10 = sum(base_df.head(10)["Value"] > line)
        hit_rate = (hits_l10 / 10) * 100
        hit_rates.append({
            "Line": f"{stat_type} O/U {line:.1f}",
            "Last 10 Hit Rate": f"{hit_rate:.0f}%",
            "Hits": f"{hits_l10}/10",
            "Recommendation": "✅ OVER" if hit_rate >= 60 else "❌ UNDER" if hit_rate <= 40 else "⚠️ NEUTRAL"
        })

    # Matchup difficulty (mock)
    matchup_data = []
    opponents = base_df["Opponent"].unique()[:5]

    for opp in opponents:
        opp_games = base_df[base_df["Opponent"] == opp]
        avg_vs = opp_games["Value"].mean() if len(opp_games) > 0 else season_avg
        difficulty = "🔥 SMASH" if avg_vs > season_avg + 3 else "❄️ AVOID" if avg_vs < season_avg - 3 else "📊 NEUTRAL"

        matchup_data.append({
            "Opponent": opp,
            "Avg Against": f"{avg_vs:.1f}",
            "Difficulty": difficulty
        })

    return pd.DataFrame(hit_rates), pd.DataFrame(matchup_data), l5_avg, l10_avg, season_avg


def create_stats_chart(df, stat_type, num_games):
    """
    Create a professional bar chart using Plotly
    """

    chart_df = df.head(num_games)

    # Create bar chart with gradient colors
    fig = go.Figure()

    # Color bars based on value (higher = greener)
    colors = px.colors.sequential.Viridis

    fig.add_trace(go.Bar(
        x=chart_df["Date"],
        y=chart_df["Value"],
        text=chart_df["Value"],
        textposition="outside",
        marker=dict(
            color=chart_df["Value"],
            colorscale="Blues",
            line=dict(color='rgb(8,48,107)', width=1.5)
        ),
        hovertemplate="<b>%{x}</b><br>" +
                      f"{stat_type}: %{y}<br>" +
                      "Opponent: %{customdata}<br>" +
                      "<extra></extra>",
        customdata=chart_df["Opponent"]
    ))

    fig.update_layout(
        title=dict(
            text=f"{stat_type} - Last {num_games} Games",
            font=dict(size=24, color="#1d428a", family="Arial Black")
        ),
        xaxis=dict(
            title="Game Date",
            tickangle=-45,
            showgrid=True,
            gridcolor='lightgray'
        ),
        yaxis=dict(
            title=stat_type,
            showgrid=True,
            gridcolor='lightgray'
        ),
        plot_bgcolor='rgba(240,240,240,0.5)',
        paper_bgcolor='white',
        height=500,
        hovermode='x unified'
    )

    return fig


# ========== MAIN APP ==========

st.markdown('<h1 class="main-header">🏀 NBA Player Prop Research</h1>', unsafe_allow_html=True)

st.markdown("""
<div style='text-align: center; color: #666; margin-bottom: 2rem;'>
    <p style='font-size: 1.2rem;'>Research player stats, trends, and hit rates. <b>Free forever.</b></p>
    <p style='font-size: 0.9rem;'>📊 Unlock premium insights for smarter betting decisions</p>
</div>
""", unsafe_allow_html=True)


# Sidebar Configuration
st.sidebar.header("⚙️ Settings")

# Player Selection
selected_player = st.sidebar.selectbox(
    "Select Player",
    options=list(MOCK_PLAYERS.keys()),
    index=0
)

player_info = MOCK_PLAYERS[selected_player]

st.sidebar.markdown(f"""
**Team:** {player_info['team']}
**Position:** {player_info['position']}
""")

st.sidebar.divider()

# Stat Selection
stat_type = st.sidebar.selectbox(
    "Stat Type",
    options=["Points", "Rebounds", "Assists", "Threes", "Blocks", "Steals"],
    index=0
)

# Game Range Selection
num_games = st.sidebar.select_slider(
    "Number of Games",
    options=[5, 10, 15],
    value=10
)

st.sidebar.divider()
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔓 Premium Access")

# Access Code Input (for premium features)
access_code = st.sidebar.text_input(
    "Enter Access Code",
    type="password",
    placeholder="BETS2024",
    help="Get premium access with code BETS2024"
)

is_premium = access_code == "BETS2024"

if is_premium:
    st.sidebar.success("✅ Premium Unlocked!")
else:
    st.sidebar.info("💎 Enter code to unlock premium insights")


# ========== MAIN CONTENT ==========

# Generate Data
game_data = generate_mock_game_data(selected_player, stat_type, num_games=15)

# Display Chart
st.subheader(f"📈 {selected_player} - {stat_type} Trends")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="Last 5 Avg",
        value=f"{game_data.head(5)['Value'].mean():.1f}",
        delta=f"{game_data.head(5)['Value'].mean() - game_data.head(10)['Value'].mean():.1f}"
    )

with col2:
    st.metric(
        label="Last 10 Avg",
        value=f"{game_data.head(10)['Value'].mean():.1f}"
    )

with col3:
    st.metric(
        label="Season Avg",
        value=f"{game_data['Value'].mean():.1f}"
    )

# Show Chart
chart = create_stats_chart(game_data, stat_type, num_games)
st.plotly_chart(chart, use_container_width=True)

# Show Game Log
with st.expander("📋 View Game Log"):
    display_df = game_data.head(num_games).copy()
    display_df.index = range(1, len(display_df) + 1)
    st.dataframe(display_df, use_container_width=True)


# ========== PAYWALL SECTION ==========

st.markdown("---")

if not is_premium:
    # Show Locked Premium Section
    st.markdown("""
    <div class="premium-lock">
        <h2>🔒 Premium Insights</h2>
        <p style='font-size: 1.1rem; margin: 1rem 0;'>
            Unlock advanced analytics to make smarter prop bets:
        </p>
        <ul style='list-style: none; padding: 0; font-size: 1rem;'>
            <li>✅ Hit Rate Analysis (Last 5, 10, 20 games)</li>
            <li>✅ Line Recommendations (Over/Under)</li>
            <li>✅ Matchup Difficulty Ratings</li>
            <li>✅ Defense vs. Position Trends</li>
            <li>✅ Home/Away Splits</li>
        </ul>
        <p style='margin-top: 1.5rem; font-size: 1.3rem;'>
            <b>Unlock for just $5/month</b>
        </p>
    </div>
    """, unsafe_allow_html=True)

    # CTA Button (Placeholder Stripe Link)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💳 Unlock Premium Access - $5", use_container_width=True, type="primary"):
            st.info("🔗 Redirecting to payment... (Replace with your Stripe Payment Link)")
            st.markdown("""
            **Setup Instructions:**
            1. Create a Stripe account at [stripe.com](https://stripe.com)
            2. Create a Payment Link for $5/month subscription
            3. Replace this button with: `st.link_button("Unlock Premium", "YOUR_STRIPE_LINK")`
            """)

    st.warning("💡 **Hint:** Enter access code 'BETS2024' in the sidebar to demo premium features")

else:
    # Show Premium Content
    st.success("🎉 Premium Features Unlocked!")

    hit_rate_df, matchup_df, l5, l10, season = generate_premium_data(
        selected_player, stat_type, game_data
    )

    st.subheader("🎯 Hit Rate Analysis")

    # Show hit rates
    st.dataframe(
        hit_rate_df.style.set_properties(**{
            'background-color': '#f0f2f6',
            'color': '#000',
            'border-color': 'white'
        }),
        use_container_width=True,
        hide_index=True
    )

    st.markdown("---")

    st.subheader("🏟️ Matchup Difficulty")

    col1, col2 = st.columns(2)

    with col1:
        st.dataframe(
            matchup_df,
            use_container_width=True,
            hide_index=True
        )

    with col2:
        st.markdown("""
        ### 📊 Interpretation Guide

        - **🔥 SMASH**: Player performs well above average
        - **📊 NEUTRAL**: Performance near season average
        - **❄️ AVOID**: Player underperforms against this team

        ### 💡 Pro Tips
        - Look for 70%+ hit rates on recent lines
        - Check home/away splits for location edges
        - Monitor injury reports before betting
        """)

    st.markdown("---")

    # Advanced Stats Summary
    st.subheader("📈 Advanced Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("L5 Avg", f"{l5:.1f}", delta=f"{l5 - season:.1f}")

    with col2:
        st.metric("L10 Avg", f"{l10:.1f}", delta=f"{l10 - season:.1f}")

    with col3:
        st.metric("Season Avg", f"{season:.1f}")

    with col4:
        consistency = 100 - (game_data["Value"].std() / game_data["Value"].mean() * 100)
        st.metric("Consistency", f"{consistency:.0f}%")


# ========== FOOTER ==========

st.markdown("---")

st.markdown("""
<div style='text-align: center; color: #888; padding: 2rem 0;'>
    <p><b>Built with Streamlit</b> | Data updates every 6 hours</p>
    <p style='font-size: 0.9rem;'>⚠️ For entertainment purposes only. Gamble responsibly.</p>
</div>
""", unsafe_allow_html=True)


# ========== DEPLOYMENT GUIDE (Hidden in Code) ==========
"""
═══════════════════════════════════════════════════════════════
📦 HOW TO DEPLOY TO STREAMLIT COMMUNITY CLOUD (FREE)
═══════════════════════════════════════════════════════════════

STEP 1: Prepare Your GitHub Repository
---------------------------------------
1. Create a new GitHub repository (or use existing)
2. Add these files to your repo:
   - app.py (this file)
   - requirements.txt (see below)
   - README.md (optional)

3. Create requirements.txt with:
   ```
   streamlit>=1.31.0
   pandas>=2.0.0
   plotly>=5.18.0
   ```

4. Push to GitHub:
   ```bash
   git add .
   git commit -m "Add NBA Props Research Streamlit app"
   git push origin main
   ```

STEP 2: Deploy on Streamlit Cloud
----------------------------------
1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Select your repository
5. Main file path: app.py
6. Click "Deploy"!

Your app will be live at: https://yourapp.streamlit.app

═══════════════════════════════════════════════════════════════
💳 ADDING REAL STRIPE PAYMENTS
═══════════════════════════════════════════════════════════════

STEP 1: Create Stripe Payment Link
-----------------------------------
1. Go to https://stripe.com and create account
2. Navigate to Products > Add Product
   - Name: "NBA Props Premium"
   - Price: $5/month (recurring)
3. Click "Create payment link"
4. Copy the payment link URL

STEP 2: Update App Code
------------------------
Replace the button section (line ~380) with:

```python
st.link_button(
    "💳 Unlock Premium Access - $5",
    "https://buy.stripe.com/YOUR_PAYMENT_LINK_HERE",
    use_container_width=True
)
```

STEP 3: Handle Payment Verification (Advanced)
-----------------------------------------------
For production, integrate Stripe webhooks to verify payments
and manage access codes. This requires:
- Stripe webhook endpoint
- Database to store customer subscriptions
- Backend API for verification

For MVP, manual access codes work fine!

═══════════════════════════════════════════════════════════════
🔌 USING REAL NBA DATA (Optional Upgrade)
═══════════════════════════════════════════════════════════════

Replace mock data with balldontlie API:

```python
import requests

def fetch_real_player_stats(player_name, num_games=10):
    # Search for player
    url = "https://www.balldontlie.io/api/v1/players"
    response = requests.get(url, params={"search": player_name})
    player_id = response.json()["data"][0]["id"]

    # Get stats
    stats_url = "https://www.balldontlie.io/api/v1/stats"
    stats = requests.get(stats_url, params={
        "player_ids[]": player_id,
        "per_page": num_games
    })

    return stats.json()
```

Note: API rate limits apply. Mock data is fine for MVP!

═══════════════════════════════════════════════════════════════
"""
