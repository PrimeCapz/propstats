"""
🏀 NBA Props Research Tool - Mission Control Edition
Futuristic interactive interface with advanced glassmorphism and HUD elements
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import statistics

# Page Configuration
st.set_page_config(
    page_title="PropStats Mission Control",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# FUTURISTIC CSS - Mission Control Style
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Inter:wght@300;400;600;700;900&display=swap');

    * {
        font-family: 'Inter', sans-serif;
        margin: 0;
        padding: 0;
    }

    /* Dark Mode 2.0 - Near Black Background */
    .stApp {
        background: #050505;
        background-image:
            radial-gradient(at 20% 30%, rgba(0, 255, 163, 0.03) 0px, transparent 50%),
            radial-gradient(at 80% 70%, rgba(138, 43, 226, 0.03) 0px, transparent 50%),
            radial-gradient(at 50% 50%, rgba(0, 119, 255, 0.02) 0px, transparent 50%);
        background-attachment: fixed;
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* Animated Holographic Header */
    .main-header {
        background: linear-gradient(135deg, rgba(10, 10, 15, 0.95) 0%, rgba(5, 5, 5, 0.98) 100%);
        backdrop-filter: blur(40px) saturate(180%);
        -webkit-backdrop-filter: blur(40px) saturate(180%);
        border-bottom: 1px solid transparent;
        border-image: linear-gradient(90deg,
            transparent 0%,
            rgba(0, 255, 163, 0.5) 20%,
            rgba(138, 43, 226, 0.5) 50%,
            rgba(0, 119, 255, 0.5) 80%,
            transparent 100%) 1;
        padding: 1.5rem 0;
        margin-bottom: 3rem;
        position: sticky;
        top: 0;
        z-index: 999;
        box-shadow:
            0 4px 30px rgba(0, 255, 163, 0.15),
            0 8px 60px rgba(138, 43, 226, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        animation: headerGlow 4s ease-in-out infinite;
    }

    @keyframes headerGlow {
        0%, 100% { box-shadow: 0 4px 30px rgba(0, 255, 163, 0.15), 0 8px 60px rgba(138, 43, 226, 0.1); }
        50% { box-shadow: 0 4px 40px rgba(0, 255, 163, 0.25), 0 8px 80px rgba(138, 43, 226, 0.2); }
    }

    /* Kinetic Typography */
    .kinetic-title {
        font-family: 'Orbitron', sans-serif;
        font-weight: 900;
        background: linear-gradient(135deg, #00FFA3 0%, #00D4FF 50%, #8A2BE2 100%);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        animation: gradientShift 6s ease infinite, textPulse 2s ease-in-out infinite;
        filter: drop-shadow(0 0 20px rgba(0, 255, 163, 0.4));
    }

    @keyframes gradientShift {
        0%, 100% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
    }

    @keyframes textPulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }

    /* Liquid Glass Cards with Shimmer */
    .liquid-glass {
        background: linear-gradient(135deg,
            rgba(26, 28, 36, 0.4) 0%,
            rgba(15, 15, 20, 0.6) 100%);
        backdrop-filter: blur(40px) saturate(150%);
        -webkit-backdrop-filter: blur(40px) saturate(150%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 2rem;
        box-shadow:
            0 8px 32px rgba(0, 0, 0, 0.6),
            inset 0 1px 0 rgba(255, 255, 255, 0.1),
            0 0 40px rgba(0, 255, 163, 0.05);
        position: relative;
        overflow: hidden;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .liquid-glass::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: linear-gradient(
            45deg,
            transparent 0%,
            rgba(0, 255, 163, 0.1) 25%,
            transparent 50%
        );
        animation: shimmer 6s linear infinite;
        pointer-events: none;
    }

    @keyframes shimmer {
        0% { transform: translate(-100%, -100%) rotate(45deg); }
        100% { transform: translate(100%, 100%) rotate(45deg); }
    }

    .liquid-glass:hover {
        transform: translateY(-8px) scale(1.02);
        border-color: rgba(0, 255, 163, 0.4);
        box-shadow:
            0 16px 64px rgba(0, 255, 163, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.2),
            0 0 80px rgba(0, 255, 163, 0.15);
    }

    /* HUD-Style Elements */
    .hud-frame {
        background: rgba(5, 5, 5, 0.8);
        border: 2px solid;
        border-image: linear-gradient(135deg,
            rgba(0, 255, 163, 0.6) 0%,
            rgba(0, 119, 255, 0.6) 50%,
            rgba(138, 43, 226, 0.6) 100%) 1;
        border-radius: 16px;
        padding: 1.5rem;
        position: relative;
        overflow: hidden;
        box-shadow:
            0 0 30px rgba(0, 255, 163, 0.2),
            inset 0 0 30px rgba(0, 255, 163, 0.05);
    }

    .hud-frame::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(0, 255, 163, 0.3), transparent);
        animation: scan 3s linear infinite;
    }

    @keyframes scan {
        0% { left: -100%; }
        100% { left: 100%; }
    }

    /* Holographic Stats Badge */
    .holo-badge {
        position: relative;
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.2), rgba(0, 119, 255, 0.2));
        border: 1px solid rgba(0, 255, 163, 0.4);
        border-radius: 12px;
        padding: 1rem 1.5rem;
        backdrop-filter: blur(20px);
        box-shadow:
            0 0 20px rgba(0, 255, 163, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
        animation: holoPulse 3s ease-in-out infinite;
    }

    @keyframes holoPulse {
        0%, 100% {
            box-shadow: 0 0 20px rgba(0, 255, 163, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.2);
        }
        50% {
            box-shadow: 0 0 40px rgba(0, 255, 163, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.3);
        }
    }

    /* PropScore HUD with Advanced Glow */
    .propscore-hud-high {
        background: radial-gradient(circle at center,
            rgba(0, 255, 163, 0.3) 0%,
            rgba(0, 200, 130, 0.1) 100%);
        border: 2px solid #00FFA3;
        color: #00FFA3;
        box-shadow:
            0 0 40px rgba(0, 255, 163, 0.8),
            0 0 80px rgba(0, 255, 163, 0.4),
            inset 0 0 40px rgba(0, 255, 163, 0.2);
        animation: propscoreGlow 2s ease-in-out infinite;
    }

    .propscore-hud-medium {
        background: radial-gradient(circle at center,
            rgba(255, 193, 7, 0.3) 0%,
            rgba(255, 152, 0, 0.1) 100%);
        border: 2px solid #FFC107;
        color: #FFC107;
        box-shadow:
            0 0 40px rgba(255, 193, 7, 0.8),
            0 0 80px rgba(255, 193, 7, 0.4),
            inset 0 0 40px rgba(255, 193, 7, 0.2);
        animation: propscoreGlow 2s ease-in-out infinite;
    }

    .propscore-hud-low {
        background: radial-gradient(circle at center,
            rgba(239, 68, 68, 0.3) 0%,
            rgba(220, 38, 38, 0.1) 100%);
        border: 2px solid #EF4444;
        color: #EF4444;
        box-shadow:
            0 0 40px rgba(239, 68, 68, 0.8),
            0 0 80px rgba(239, 68, 68, 0.4),
            inset 0 0 40px rgba(239, 68, 68, 0.2);
        animation: propscoreGlow 2s ease-in-out infinite;
    }

    @keyframes propscoreGlow {
        0%, 100% { filter: brightness(1); }
        50% { filter: brightness(1.3); }
    }

    /* Heat Map with Neon Effects */
    .heat-hud-high {
        background: linear-gradient(135deg, rgba(0, 255, 163, 0.25), rgba(0, 200, 130, 0.35));
        border: 1px solid #00FFA3;
        color: #00FFA3;
        box-shadow:
            0 0 25px rgba(0, 255, 163, 0.5),
            inset 0 0 25px rgba(0, 255, 163, 0.1);
        font-weight: 900;
        text-shadow: 0 0 10px rgba(0, 255, 163, 0.8);
    }

    .heat-hud-medium {
        background: linear-gradient(135deg, rgba(255, 193, 7, 0.25), rgba(255, 152, 0, 0.35));
        border: 1px solid #FFC107;
        color: #FFC107;
        box-shadow:
            0 0 25px rgba(255, 193, 7, 0.5),
            inset 0 0 25px rgba(255, 193, 7, 0.1);
        font-weight: 900;
        text-shadow: 0 0 10px rgba(255, 193, 7, 0.8);
    }

    .heat-hud-low {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.25), rgba(220, 38, 38, 0.35));
        border: 1px solid #EF4444;
        color: #EF4444;
        box-shadow:
            0 0 25px rgba(239, 68, 68, 0.5),
            inset 0 0 25px rgba(239, 68, 68, 0.1);
        font-weight: 900;
        text-shadow: 0 0 10px rgba(239, 68, 68, 0.8);
    }

    /* Ripple Effect Buttons */
    .stButton button {
        background: linear-gradient(135deg,
            rgba(0, 255, 163, 0.15) 0%,
            rgba(0, 119, 255, 0.15) 100%);
        color: #00FFA3;
        border: 2px solid rgba(0, 255, 163, 0.5);
        border-radius: 16px;
        font-weight: 700;
        padding: 1rem 2rem;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-size: 0.95rem;
        position: relative;
        overflow: hidden;
        box-shadow:
            0 4px 20px rgba(0, 255, 163, 0.2),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
    }

    .stButton button::before {
        content: '';
        position: absolute;
        top: 50%;
        left: 50%;
        width: 0;
        height: 0;
        border-radius: 50%;
        background: rgba(0, 255, 163, 0.4);
        transform: translate(-50%, -50%);
        transition: width 0.6s, height 0.6s;
    }

    .stButton button:hover::before {
        width: 300px;
        height: 300px;
    }

    .stButton button:hover {
        background: linear-gradient(135deg,
            rgba(0, 255, 163, 0.3) 0%,
            rgba(0, 119, 255, 0.3) 100%);
        border-color: #00FFA3;
        transform: translateY(-4px);
        box-shadow:
            0 8px 40px rgba(0, 255, 163, 0.4),
            0 0 60px rgba(0, 255, 163, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
    }

    .stButton button:active {
        transform: translateY(-2px);
    }

    /* Animated Tab Selection */
    .stat-tab {
        display: inline-block;
        padding: 0.8rem 2rem;
        margin: 0.5rem;
        border-radius: 12px;
        font-weight: 700;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        cursor: pointer;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        background: rgba(30, 30, 40, 0.5);
        color: #666;
        border: 1px solid rgba(255, 255, 255, 0.1);
        position: relative;
        overflow: hidden;
    }

    .stat-tab::before {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 0;
        height: 2px;
        background: #00FFA3;
        transition: width 0.3s;
    }

    .stat-tab:hover::before {
        width: 100%;
    }

    /* Parallax Depth Layers */
    .depth-layer-1 {
        transform: translateZ(0);
        transition: transform 0.3s ease-out;
    }

    .depth-layer-2 {
        transform: translateZ(20px);
        transition: transform 0.3s ease-out;
    }

    /* Metrics with Glow */
    div[data-testid="stMetricValue"] {
        font-size: 2.5rem;
        color: #00FFA3;
        text-shadow:
            0 0 20px rgba(0, 255, 163, 0.8),
            0 0 40px rgba(0, 255, 163, 0.4);
        font-weight: 900;
        font-family: 'Orbitron', sans-serif;
        animation: metricGlow 2s ease-in-out infinite;
    }

    @keyframes metricGlow {
        0%, 100% { text-shadow: 0 0 20px rgba(0, 255, 163, 0.8), 0 0 40px rgba(0, 255, 163, 0.4); }
        50% { text-shadow: 0 0 30px rgba(0, 255, 163, 1), 0 0 60px rgba(0, 255, 163, 0.6); }
    }

    /* Inputs with Neon Focus */
    input, select {
        background-color: rgba(10, 10, 15, 0.8) !important;
        color: #00FFA3 !important;
        border: 1px solid rgba(0, 255, 163, 0.3) !important;
        border-radius: 12px !important;
        font-family: 'Orbitron', sans-serif !important;
        transition: all 0.3s ease !important;
    }

    input:focus, select:focus {
        border-color: #00FFA3 !important;
        box-shadow:
            0 0 20px rgba(0, 255, 163, 0.5) !important,
            inset 0 0 20px rgba(0, 255, 163, 0.1) !important;
        background-color: rgba(0, 255, 163, 0.05) !important;
    }

    /* Loading Animation */
    @keyframes dataStream {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }

    .data-stream {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg,
            transparent 0%,
            #00FFA3 50%,
            transparent 100%);
        animation: dataStream 2s linear infinite;
    }

    .block-container {
        padding-top: 2rem;
        max-width: 1600px;
    }

    /* Holographic Player Card */
    .holo-player-card {
        background: linear-gradient(135deg,
            rgba(10, 10, 20, 0.9) 0%,
            rgba(5, 5, 10, 0.95) 100%);
        border: 1px solid;
        border-image: linear-gradient(135deg,
            rgba(0, 255, 163, 0.5) 0%,
            rgba(138, 43, 226, 0.5) 100%) 1;
        border-radius: 24px;
        overflow: hidden;
        box-shadow:
            0 16px 64px rgba(0, 255, 163, 0.2),
            0 8px 32px rgba(138, 43, 226, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.1);
        position: relative;
    }

    .holo-player-card::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: conic-gradient(
            from 0deg,
            transparent 0deg,
            rgba(0, 255, 163, 0.1) 90deg,
            transparent 180deg,
            rgba(138, 43, 226, 0.1) 270deg,
            transparent 360deg
        );
        animation: holoRotate 8s linear infinite;
        pointer-events: none;
    }

    @keyframes holoRotate {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* Scanline Effect */
    .scanlines {
        position: relative;
    }

    .scanlines::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: repeating-linear-gradient(
            0deg,
            rgba(0, 255, 163, 0.03) 0px,
            transparent 1px,
            transparent 2px,
            rgba(0, 255, 163, 0.03) 3px
        );
        pointer-events: none;
        animation: scanlineMove 8s linear infinite;
    }

    @keyframes scanlineMove {
        0% { transform: translateY(0); }
        100% { transform: translateY(100%); }
    }
</style>
""", unsafe_allow_html=True)

# Team Data (same as before)
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
    """Calculate PropScore (0-100)"""
    hit_score = (hit_rate / 100) * 40
    margin = season_avg - line
    margin_pct = (margin / line * 100) if line > 0 else 0
    margin_score = min(30, max(-30, margin_pct * 3))
    margin_score = (margin_score + 30)
    consistency_score = consistency / 5
    difficulty_scores = {'easy': 10, 'medium': 0, 'hard': -10}
    difficulty_score = difficulty_scores.get(difficulty, 0)
    propscore = hit_score + margin_score + consistency_score + difficulty_score
    propscore = max(0, min(100, propscore))
    return int(propscore)

def get_matchup_difficulty(opponent_team, player_pos):
    """Calculate matchup difficulty"""
    opp_stats = TEAM_STATS.get(opponent_team, {})
    if 'G' in player_pos:
        def_rank = opp_stats.get('pg_def_rank', 15)
    else:
        def_rank = opp_stats.get('def_rank', 15)

    if def_rank >= 25:
        return 'easy', f"vs {player_pos}: {def_rank}th", 'heat-hud-high'
    elif def_rank >= 15:
        return 'medium', f"vs {player_pos}: {def_rank}th", 'heat-hud-medium'
    else:
        return 'hard', f"vs {player_pos}: {def_rank}th", 'heat-hud-low'

def create_enhanced_bar_chart(games, line, stat_name):
    """Create futuristic bar chart with neon effects"""
    fig = go.Figure()

    colors = ['#00FFA3' if g['value'] > line else '#EF4444' for g in games[:10]]

    fig.add_trace(go.Bar(
        x=[g['date'] for g in games[:10]],
        y=[g['value'] for g in games[:10]],
        marker=dict(
            color=colors,
            line=dict(color='#050505', width=4),
            opacity=0.9
        ),
        text=[g['value'] for g in games[:10]],
        textposition='outside',
        textfont=dict(color='#00FFA3', size=13, family='Orbitron', weight='bold'),
        hovertemplate='<b>%{x}</b><br>%{y}<br><extra></extra>'
    ))

    fig.add_hline(
        y=line,
        line_dash="dash",
        line_color="#00D4FF",
        line_width=4,
        annotation_text=f"◆ TARGET: {line} ◆",
        annotation_position="right",
        annotation_font=dict(color="#00D4FF", size=14, family='Orbitron', weight='bold')
    )

    fig.update_layout(
        plot_bgcolor='rgba(5, 5, 5, 0.8)',
        paper_bgcolor='rgba(5, 5, 5, 0.5)',
        font=dict(color='#00FFA3', family='Orbitron'),
        height=300,
        margin=dict(l=10, r=10, t=10, b=40),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor='rgba(0, 255, 163, 0.3)',
            zeroline=False,
            color='#00FFA3',
            tickfont=dict(size=11, family='Orbitron')
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(0, 255, 163, 0.1)',
            showline=True,
            linecolor='rgba(0, 255, 163, 0.3)',
            zeroline=False,
            title="",
            color='#00FFA3',
            tickfont=dict(size=11, family='Orbitron')
        ),
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

# ========== HOLOGRAPHIC HEADER ==========
st.markdown("""
<div class="main-header scanlines">
    <div class="data-stream"></div>
    <div style="max-width: 1600px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="width: 55px; height: 55px; background: linear-gradient(135deg, #00FFA3 0%, #00D4FF 50%, #8A2BE2 100%);
                        border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.8rem;
                        font-family: 'Orbitron', sans-serif; box-shadow: 0 0 40px rgba(0, 255, 163, 0.8), 0 0 80px rgba(138, 43, 226, 0.4);
                        animation: iconPulse 2s ease-in-out infinite;">P</div>
            <div>
                <span class="kinetic-title" style="font-size: 2rem;">PROPSTATS MISSION CONTROL</span>
                <div style="color: rgba(0, 255, 163, 0.7); font-size: 0.75rem; font-weight: 600; letter-spacing: 3px; margin-top: 0.25rem;">
                    TACTICAL BETTING INTELLIGENCE
                </div>
            </div>
        </div>
        <div class="holo-badge">
            <div style="color: #00FFA3; font-size: 0.7rem; font-weight: 700; letter-spacing: 2px;">LIVE</div>
            <div style="color: white; font-size: 1.1rem; font-weight: 900; font-family: 'Orbitron';">SYSTEM ACTIVE</div>
        </div>
    </div>
</div>

<style>
@keyframes iconPulse {
    0%, 100% { transform: scale(1) rotate(0deg); }
    50% { transform: scale(1.1) rotate(180deg); }
}
</style>
""", unsafe_allow_html=True)

# ========== LAYER 1: MISSION CONTROL SLATE ==========
if st.session_state.view == 'slate':
    st.markdown(f"""
    <div style="margin-bottom: 3rem; text-align: center;" class="scanlines">
        <h1 class="kinetic-title" style="font-size: 3rem; margin-bottom: 1rem;">
            TODAY'S TACTICAL SLATE
        </h1>
        <div class="holo-badge" style="display: inline-block;">
            <div style="color: #00D4FF; font-size: 1.2rem; font-weight: 900; font-family: 'Orbitron'; letter-spacing: 2px;">
                ◆ {datetime.now().strftime('%A, %B %d, %Y').upper()} ◆
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    games = generate_todays_games()

    # 2-column grid with liquid glass cards
    cols = st.columns(2, gap="large")
    for idx, game in enumerate(games):
        away_color = TEAM_COLORS.get(game['away_team'], '#666')
        home_color = TEAM_COLORS.get(game['home_team'], '#666')

        with cols[idx % 2]:
            st.markdown(f"""
            <div class="liquid-glass depth-layer-1" style="margin: 1.5rem 0; text-align: center;">
                <div style="display: flex; justify-content: space-around; align-items: center; padding: 1.5rem 0;">
                    <div style="flex: 1;">
                        <div style="color: {away_color}; font-size: 2.5rem; font-weight: 900; font-family: 'Orbitron';
                                    text-shadow: 0 0 20px {away_color}80;">{game['away_team']}</div>
                        <div style="color: rgba(255, 255, 255, 0.5); font-size: 0.85rem; margin-top: 0.75rem; letter-spacing: 1px;">
                            {TEAM_NAMES[game['away_team']]}
                        </div>
                    </div>
                    <div style="color: #00FFA3; font-size: 2rem; font-weight: 900; font-family: 'Orbitron';
                                text-shadow: 0 0 20px rgba(0, 255, 163, 0.8);">VS</div>
                    <div style="flex: 1;">
                        <div style="color: {home_color}; font-size: 2.5rem; font-weight: 900; font-family: 'Orbitron';
                                    text-shadow: 0 0 20px {home_color}80;">{game['home_team']}</div>
                        <div style="color: rgba(255, 255, 255, 0.5); font-size: 0.85rem; margin-top: 0.75rem; letter-spacing: 1px;">
                            {TEAM_NAMES[game['home_team']]}
                        </div>
                    </div>
                </div>
                <div class="hud-frame" style="margin: 1rem 0; padding: 0.75rem;">
                    <div style="color: #00D4FF; font-size: 0.95rem; font-weight: 700; font-family: 'Orbitron'; letter-spacing: 1.5px;">
                        ◆ {game['time']} ◆
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"◆ ENTER MATCHUP ◆", key=f"game_{idx}", use_container_width=True):
                st.session_state.selected_game = game
                st.session_state.view = 'matchup'
                st.rerun()

# ========== LAYER 2: TACTICAL MATCHUP BOARD ==========
elif st.session_state.view == 'matchup':
    game = st.session_state.selected_game

    if st.button("◄ RETURN TO SLATE"):
        st.session_state.view = 'slate'
        st.rerun()

    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 3rem;" class="scanlines">
        <h1 class="kinetic-title" style="font-size: 2.5rem;">TACTICAL MATCHUP ANALYSIS</h1>
        <div class="holo-badge" style="display: inline-block; margin-top: 1rem;">
            <div style="font-size: 1.1rem; font-weight: 900; font-family: 'Orbitron';">
                {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]} • {game['time']}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # HUD-style team comparison
    col1, col2, col3 = st.columns([5, 1, 5], gap="large")

    with col1:
        st.markdown(f"""
        <div class="hud-frame" style="text-align: center; min-height: 350px;">
            <h2 style="color: {TEAM_COLORS[game['away_team']]}; font-size: 2.2rem; margin-bottom: 1.5rem; font-family: 'Orbitron';
                       text-shadow: 0 0 20px {TEAM_COLORS[game['away_team']]}80;">
                {game['away_team']} {TEAM_NAMES[game['away_team']]}
            </h2>
            <div style="display: grid; gap: 1rem; margin-top: 2rem;">
                <div class="holo-badge">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px;">PPG</div>
                    <div style="color: white; font-size: 2rem; font-weight: 900; font-family: 'Orbitron';">{game['away_stats']['ppg']}</div>
                </div>
                <div class="holo-badge">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px;">PACE</div>
                    <div style="color: white; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">{game['away_stats']['pace']}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                    <div class="holo-badge" style="background: linear-gradient(135deg, rgba(0, 255, 163, 0.15), rgba(0, 200, 130, 0.15));">
                        <div style="color: #00FFA3; font-size: 0.7rem; letter-spacing: 1px;">OFF RANK</div>
                        <div style="color: #00FFA3; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">#{game['away_stats']['off_rank']}</div>
                    </div>
                    <div class="holo-badge" style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(220, 38, 38, 0.15));">
                        <div style="color: #EF4444; font-size: 0.7rem; letter-spacing: 1px;">DEF RANK</div>
                        <div style="color: #EF4444; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">#{game['away_stats']['def_rank']}</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div style="text-align: center; padding: 4rem 0; height: 100%; display: flex; align-items: center; justify-content: center;">
            <div style="color: #00FFA3; font-size: 4rem; font-weight: 900; font-family: 'Orbitron';
                        text-shadow: 0 0 40px rgba(0, 255, 163, 1);">
                VS
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="hud-frame" style="text-align: center; min-height: 350px;">
            <h2 style="color: {TEAM_COLORS[game['home_team']]}; font-size: 2.2rem; margin-bottom: 1.5rem; font-family: 'Orbitron';
                       text-shadow: 0 0 20px {TEAM_COLORS[game['home_team']]}80;">
                {game['home_team']} {TEAM_NAMES[game['home_team']]}
            </h2>
            <div style="display: grid; gap: 1rem; margin-top: 2rem;">
                <div class="holo-badge">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px;">PPG</div>
                    <div style="color: white; font-size: 2rem; font-weight: 900; font-family: 'Orbitron';">{game['home_stats']['ppg']}</div>
                </div>
                <div class="holo-badge">
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px;">PACE</div>
                    <div style="color: white; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">{game['home_stats']['pace']}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem;">
                    <div class="holo-badge" style="background: linear-gradient(135deg, rgba(0, 255, 163, 0.15), rgba(0, 200, 130, 0.15));">
                        <div style="color: #00FFA3; font-size: 0.7rem; letter-spacing: 1px;">OFF RANK</div>
                        <div style="color: #00FFA3; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">#{game['home_stats']['off_rank']}</div>
                    </div>
                    <div class="holo-badge" style="background: linear-gradient(135deg, rgba(239, 68, 68, 0.15), rgba(220, 38, 38, 0.15));">
                        <div style="color: #EF4444; font-size: 0.7rem; letter-spacing: 1px;">DEF RANK</div>
                        <div style="color: #EF4444; font-size: 1.5rem; font-weight: 900; font-family: 'Orbitron';">#{game['home_stats']['def_rank']}</div>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Player Selection with HUD style
    st.markdown(f"<h3 class='kinetic-title' style='font-size: 1.5rem; margin: 2rem 0 1rem 0;'>{TEAM_NAMES[game['away_team']]} ROSTER</h3>", unsafe_allow_html=True)
    cols = st.columns(2, gap="large")
    for i, player in enumerate(game['away_players']):
        with cols[i % 2]:
            if st.button(f"◆ {player['name']} • {player['pos']} ◆", key=f"away_{i}", use_container_width=True):
                st.session_state.selected_player = player
                st.session_state.view = 'player'
                st.rerun()

    st.markdown(f"<h3 class='kinetic-title' style='font-size: 1.5rem; margin: 2rem 0 1rem 0;'>{TEAM_NAMES[game['home_team']]} ROSTER</h3>", unsafe_allow_html=True)
    cols = st.columns(2, gap="large")
    for i, player in enumerate(game['home_players']):
        with cols[i % 2]:
            if st.button(f"◆ {player['name']} • {player['pos']} ◆", key=f"home_{i}", use_container_width=True):
                st.session_state.selected_player = player
                st.session_state.view = 'player'
                st.rerun()

# ========== LAYER 3: HOLOGRAPHIC PLAYER HUD ==========
elif st.session_state.view == 'player':
    if st.button("◄ RETURN TO MATCHUP"):
        st.session_state.view = 'matchup'
        st.rerun()

    player = st.session_state.selected_player
    game = st.session_state.selected_game

    # Determine teams
    if player in game['away_players']:
        opponent_team = game['home_team']
        player_team = game['away_team']
    else:
        opponent_team = game['away_team']
        player_team = game['home_team']

    difficulty, difficulty_text, difficulty_class = get_matchup_difficulty(opponent_team, player['pos'])
    team_color = TEAM_COLORS.get(player_team, '#666')
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player['id']}.png"

    # Stat tabs
    available_stats = list(player['stats'].keys())

    st.markdown("<h3 class='kinetic-title' style='font-size: 1.2rem; margin-bottom: 1rem; text-align: center;'>SELECT STAT CATEGORY</h3>", unsafe_allow_html=True)

    cols_tabs = st.columns(len(available_stats))
    for idx, stat in enumerate(available_stats):
        with cols_tabs[idx]:
            if st.button(
                f"◆ {stat.upper()} ◆",
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
        line = st.number_input("◆ TARGET LINE", min_value=0.5, max_value=100.0,
                               value=float(base_value), step=0.5, key="line_input")

    # Generate data
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

    consistency = max(0, 100 - (statistics.stdev([g['value'] for g in l10_games]) / max(1, l10_avg) * 100))

    propscore = calculate_propscore(l10_rate, season_avg, line, consistency, difficulty)
    propscore_class = 'propscore-hud-high' if propscore >= 65 else 'propscore-hud-medium' if propscore >= 40 else 'propscore-hud-low'
    propscore_label = 'HIGH CONFIDENCE' if propscore >= 65 else 'MEDIUM CONFIDENCE' if propscore >= 40 else 'LOW CONFIDENCE'

    # HOLOGRAPHIC PLAYER CARD
    st.markdown(f"""
    <div class="holo-player-card scanlines" style="margin: 2rem 0;">
        <div class="data-stream"></div>
        <div style="display: flex; justify-content: space-between; align-items: start; padding: 2.5rem;
                    background: linear-gradient(135deg, rgba(10, 10, 20, 0.95), rgba(5, 5, 10, 0.98));">
            <div style="display: flex; gap: 2rem; align-items: center;">
                <div style="position: relative;">
                    <img src="{headshot_url}"
                         style="width: 110px; height: 110px; border-radius: 50%; border: 4px solid {team_color};
                                background: #050505; object-fit: cover; box-shadow: 0 0 40px {team_color}80;"
                         onerror="this.style.display='none'">
                    <div style="position: absolute; bottom: -10px; right: -10px; width: 45px; height: 45px;
                                background: {team_color}; border-radius: 50%; display: flex; align-items: center;
                                justify-content: center; border: 3px solid #050505; font-weight: 900; font-size: 1rem;
                                font-family: 'Orbitron'; box-shadow: 0 0 20px {team_color}80;">
                        {player_team}
                    </div>
                </div>
                <div>
                    <h1 style="color: white; font-size: 3rem; font-weight: 900; margin: 0; text-transform: uppercase;
                               font-family: 'Orbitron'; letter-spacing: 2px; text-shadow: 0 0 20px rgba(255, 255, 255, 0.5);">
                        {player['name']}
                    </h1>
                    <div style="display: flex; gap: 1rem; margin-top: 1rem; align-items: center;">
                        <span class="holo-badge" style="padding: 0.5rem 1rem;">
                            {player['pos']} • #{player.get('number', '0')}
                        </span>
                        <span class="holo-badge" style="padding: 0.5rem 1rem; background: linear-gradient(135deg, rgba(138, 43, 226, 0.3), rgba(75, 0, 130, 0.3));">
                            VS {opponent_team} • {game['time']}
                        </span>
                        <span class="{difficulty_class}" style="padding: 0.5rem 1rem; border-radius: 8px;">
                            {difficulty_text}
                        </span>
                    </div>
                </div>
            </div>
            <div class="{propscore_class}" style="padding: 2rem 2.5rem; border-radius: 16px; text-align: center; min-width: 160px;">
                <div style="font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 3px; opacity: 0.9; font-family: 'Orbitron';">
                    PROPSCORE
                </div>
                <div style="font-size: 4.5rem; font-weight: 900; line-height: 1; margin: 0.5rem 0; font-family: 'Orbitron';">
                    {propscore}
                </div>
                <div style="font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; opacity: 0.9; font-family: 'Orbitron';">
                    {propscore_label}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # MAIN HUD GRID
    col_left, col_right = st.columns([1, 2], gap="large")

    with col_left:
        st.markdown("<h3 class='kinetic-title' style='font-size: 1.2rem; margin-bottom: 1.5rem;'>HIT RATE ANALYSIS</h3>", unsafe_allow_html=True)

        # Target line display
        st.markdown(f"""
        <div class="hud-frame" style="margin-bottom: 2rem; text-align: center;">
            <div style="color: rgba(0, 212, 255, 0.7); font-size: 0.75rem; font-weight: 700; letter-spacing: 3px; font-family: 'Orbitron';">
                TARGET LINE
            </div>
            <div style="display: flex; align-items: baseline; justify-content: center; gap: 1rem; margin-top: 1rem;">
                <span style="color: #00D4FF; font-size: 3.5rem; font-weight: 900; font-family: 'Orbitron'; text-shadow: 0 0 30px rgba(0, 212, 255, 1);">{line}</span>
                <span style="color: rgba(255, 255, 255, 0.5); font-size: 1rem; font-weight: 700; font-family: 'Orbitron';">{selected_stat.upper()}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Heat-mapped grid
        def get_heat_class(rate):
            if rate >= 65:
                return 'heat-hud-high'
            elif rate >= 50:
                return 'heat-hud-medium'
            else:
                return 'heat-hud-low'

        for label, rate, hits, total in [
            ('L5', l5_rate, l5_hits, 5),
            ('L10', l10_rate, l10_hits, 10),
            ('L20', l20_rate, l20_hits, 20)
        ]:
            heat_class = get_heat_class(rate)
            st.markdown(f"""
            <div class="{heat_class}" style="border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem;
                        display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 900; font-size: 1.1rem; letter-spacing: 2px; font-family: 'Orbitron';">{label}</span>
                <div style="text-align: right;">
                    <div style="font-size: 2.2rem; font-weight: 900; line-height: 1; font-family: 'Orbitron';">{rate:.0f}%</div>
                    <div style="font-size: 0.85rem; font-weight: 700; opacity: 0.9; margin-top: 0.25rem;">{hits}/{total}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown("<h3 class='kinetic-title' style='font-size: 1.2rem; margin-bottom: 1.5rem;'>PERFORMANCE TIMELINE</h3>", unsafe_allow_html=True)

        chart = create_enhanced_bar_chart(game_log, line, selected_stat.upper())
        st.plotly_chart(chart, use_container_width=True)

        # Stats grid
        col1, col2, col3 = st.columns(3, gap="medium")

        with col1:
            st.markdown(f"""
            <div class="hud-frame" style="text-align: center; padding: 1.5rem;">
                <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px; font-family: 'Orbitron';">
                    SEASON AVG
                </div>
                <div style="color: #00FFA3; font-size: 2.5rem; font-weight: 900; margin-top: 0.75rem; font-family: 'Orbitron'; text-shadow: 0 0 20px rgba(0, 255, 163, 0.8);">
                    {season_avg:.1f}
                </div>
                <div style="color: #00D4FF; font-size: 0.85rem; font-weight: 700; margin-top: 0.5rem;">
                    {season_avg - line:+.1f} vs Line
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="hud-frame" style="text-align: center; padding: 1.5rem;">
                <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px; font-family: 'Orbitron';">
                    L10 AVG
                </div>
                <div style="color: #00FFA3; font-size: 2.5rem; font-weight: 900; margin-top: 0.75rem; font-family: 'Orbitron'; text-shadow: 0 0 20px rgba(0, 255, 163, 0.8);">
                    {l10_avg:.1f}
                </div>
                <div style="color: #00D4FF; font-size: 0.85rem; font-weight: 700; margin-top: 0.5rem;">
                    {l10_avg - season_avg:+.1f}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="hud-frame" style="text-align: center; padding: 1.5rem;">
                <div style="color: rgba(255, 255, 255, 0.6); font-size: 0.75rem; letter-spacing: 2px; font-family: 'Orbitron';">
                    CONSISTENCY
                </div>
                <div style="color: #00FFA3; font-size: 2.5rem; font-weight: 900; margin-top: 0.75rem; font-family: 'Orbitron'; text-shadow: 0 0 20px rgba(0, 255, 163, 0.8);">
                    {consistency:.0f}
                </div>
                <div style="color: #FFC107; font-size: 0.85rem; font-weight: 700; margin-top: 0.5rem;">
                    {'HIGH' if consistency >= 70 else 'MEDIUM' if consistency >= 50 else 'LOW'}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # AI RECOMMENDATION
    if propscore >= 70:
        verdict, verdict_color = "STRONG OVER", "#00FFA3"
        icon = "▲▲▲"
    elif propscore >= 55:
        verdict, verdict_color = "LEAN OVER", "#84cc16"
        icon = "▲▲"
    elif propscore <= 30:
        verdict, verdict_color = "STRONG UNDER", "#EF4444"
        icon = "▼▼▼"
    elif propscore <= 45:
        verdict, verdict_color = "LEAN UNDER", "#f97316"
        icon = "▼▼"
    else:
        verdict, verdict_color = "TOSS UP", "#8A2BE2"
        icon = "◆"

    st.markdown(f"""
    <div class="hud-frame" style="margin: 3rem 0; padding: 3rem; text-align: center;
                border: 3px solid {verdict_color}; box-shadow: 0 0 60px {verdict_color}80, inset 0 0 60px {verdict_color}20;">
        <div style="color: {verdict_color}; font-size: 0.85rem; font-weight: 700; letter-spacing: 4px; opacity: 0.8; font-family: 'Orbitron';">
            TACTICAL RECOMMENDATION
        </div>
        <div style="color: {verdict_color}; font-size: 4rem; font-weight: 900; margin: 1rem 0; font-family: 'Orbitron';
                    text-shadow: 0 0 40px {verdict_color};">
            {icon} {verdict} {icon}
        </div>
        <div style="color: rgba(255, 255, 255, 0.7); font-size: 1.1rem; font-weight: 700; font-family: 'Orbitron';">
            Confidence: {propscore}% • PropScore: {propscore}/100
        </div>
    </div>
    """, unsafe_allow_html=True)

# ========== FOOTER ==========
st.markdown("""
<div style="margin-top: 6rem; padding: 3rem 0; border-top: 1px solid rgba(0, 255, 163, 0.2); text-align: center;">
    <div class="kinetic-title" style="font-size: 1.2rem; margin-bottom: 0.5rem;">
        PROPSTATS MISSION CONTROL
    </div>
    <p style="color: rgba(255, 255, 255, 0.4); font-size: 0.85rem; font-family: 'Orbitron';">
        © 2025 • TACTICAL BETTING INTELLIGENCE SYSTEM
    </p>
    <p style="font-size: 0.75rem; margin-top: 1rem; color: rgba(255, 255, 255, 0.3);">
        ⚠️ For entertainment purposes only. Gamble responsibly. 21+
    </p>
</div>
""", unsafe_allow_html=True)
