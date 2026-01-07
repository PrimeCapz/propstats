"""
🏀 PropStats - Clean, Modern NBA Props Research
Inspired by PrizePicks, Underdog, and professional betting platforms
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import statistics

# Import live NBA data module
try:
    from nba_data import get_enriched_games, get_player_game_log, init_nba_data, enrich_game_with_rosters
    NBA_DATA_AVAILABLE = True
except ImportError:
    NBA_DATA_AVAILABLE = False
    print("NBA data module not available, using mock data")

# Page Configuration
st.set_page_config(
    page_title="PropStats",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CLEAN, MODERN CSS - Betting Platform Style
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* Layered Background with Court-Inspired Depth */
    .stApp {
        background: #f1f3f5;
        background-image:
            radial-gradient(circle at 20% 50%, rgba(59, 130, 246, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, rgba(16, 185, 129, 0.08) 0%, transparent 50%),
            radial-gradient(circle at 50% 20%, rgba(139, 92, 246, 0.05) 0%, transparent 50%),
            repeating-linear-gradient(0deg, transparent, transparent 100px, rgba(59, 130, 246, 0.02) 100px, rgba(59, 130, 246, 0.02) 200px),
            linear-gradient(180deg, rgba(255, 255, 255, 0.5) 0%, rgba(241, 243, 245, 0) 100%);
        background-attachment: fixed;
        position: relative;
    }

    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background-image:
            radial-gradient(circle at 50% 50%, transparent 40%, rgba(59, 130, 246, 0.03) 100%);
        pointer-events: none;
        z-index: 0;
    }

    #MainMenu, footer, header { visibility: hidden; }

    /* Layered Professional Header with Glassmorphism */
    .main-header {
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.95) 0%, rgba(250, 251, 252, 0.95) 100%);
        backdrop-filter: blur(20px) saturate(180%);
        -webkit-backdrop-filter: blur(20px) saturate(180%);
        border-bottom: 1px solid rgba(229, 231, 235, 0.8);
        padding: 1.25rem 0;
        position: sticky;
        top: 0;
        z-index: 999;
        box-shadow:
            0 1px 3px rgba(0, 0, 0, 0.05),
            0 4px 20px rgba(59, 130, 246, 0.08),
            0 10px 40px rgba(0, 0, 0, 0.04),
            inset 0 -1px 0 rgba(255, 255, 255, 0.9),
            inset 0 1px 0 rgba(255, 255, 255, 0.5);
    }

    /* Layered Prop Card - Enhanced with Glassmorphism */
    .prop-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(255, 255, 255, 0.95) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(229, 231, 235, 0.8);
        border-radius: 16px;
        padding: 0;
        margin: 0.75rem 0;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow:
            0 2px 4px rgba(0, 0, 0, 0.04),
            0 8px 16px rgba(0, 0, 0, 0.05),
            0 16px 32px rgba(0, 0, 0, 0.03),
            inset 0 1px 0 rgba(255, 255, 255, 0.8);
        position: relative;
        overflow: hidden;
    }

    .prop-card::before {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        background: radial-gradient(circle at top right, rgba(59, 130, 246, 0.03) 0%, transparent 60%);
        opacity: 0;
        transition: opacity 0.4s;
        pointer-events: none;
    }

    .prop-card::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899);
        border-radius: 0 0 16px 16px;
        opacity: 0;
        transition: opacity 0.4s;
    }

    .prop-card:hover {
        border-color: rgba(59, 130, 246, 0.3);
        box-shadow:
            0 4px 12px rgba(59, 130, 246, 0.1),
            0 12px 32px rgba(59, 130, 246, 0.08),
            0 20px 48px rgba(0, 0, 0, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 1);
        transform: translateY(-4px) scale(1.005);
    }

    .prop-card:hover::before {
        opacity: 1;
    }

    .prop-card:hover::after {
        opacity: 1;
    }

    .prop-card-header {
        background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);
        padding: 1.5rem 1.75rem;
        border-bottom: 1px solid #f3f4f6;
        position: relative;
    }

    .prop-card-body {
        padding: 1.75rem;
    }

    /* Game Card - Premium 3D Depth with Glassmorphism */
    .game-card {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(255, 255, 255, 0.95) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(229, 231, 235, 0.8);
        border-radius: 20px;
        padding: 0;
        margin: 1rem 0;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow:
            0 2px 4px rgba(0, 0, 0, 0.04),
            0 8px 16px rgba(0, 0, 0, 0.06),
            0 16px 32px rgba(0, 0, 0, 0.04),
            inset 0 1px 0 rgba(255, 255, 255, 0.8),
            inset 0 -1px 0 rgba(0, 0, 0, 0.02);
        position: relative;
        overflow: hidden;
    }

    .game-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 5px;
        height: 100%;
        background: linear-gradient(180deg, #3b82f6, #8b5cf6, #ec4899);
        opacity: 0;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .game-card::after {
        content: '';
        position: absolute;
        top: 0;
        right: 0;
        bottom: 0;
        left: 0;
        background: radial-gradient(circle at top right, rgba(59, 130, 246, 0.05) 0%, transparent 60%);
        opacity: 0;
        transition: opacity 0.4s;
        pointer-events: none;
    }

    .game-card:hover {
        transform: translateY(-6px) scale(1.01);
        box-shadow:
            0 4px 12px rgba(59, 130, 246, 0.15),
            0 12px 40px rgba(59, 130, 246, 0.12),
            0 20px 60px rgba(0, 0, 0, 0.1),
            inset 0 1px 0 rgba(255, 255, 255, 1),
            inset 0 -1px 0 rgba(59, 130, 246, 0.1);
        border-color: rgba(59, 130, 246, 0.4);
    }

    .game-card:hover::before {
        opacity: 1;
        width: 6px;
    }

    .game-card:hover::after {
        opacity: 1;
    }

    .game-card-header {
        background: linear-gradient(135deg, #f9fafb 0%, #ffffff 100%);
        border-bottom: 1px solid #f3f4f6;
        padding: 1.25rem 1.75rem;
    }

    .game-card-body {
        padding: 1.5rem 1.75rem;
    }

    /* Player Card - Premium Sports Platform Style */
    .player-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 20px;
        overflow: hidden;
        margin: 1rem 0;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.08),
            0 12px 40px rgba(0, 0, 0, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.5);
        position: relative;
    }

    .player-card-header {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 50%, #1d4ed8 100%);
        padding: 2.5rem 2rem;
        color: white;
        position: relative;
        overflow: hidden;
    }

    .player-card-header::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background:
            radial-gradient(circle at top right, rgba(255, 255, 255, 0.15) 0%, transparent 60%),
            radial-gradient(circle at bottom left, rgba(139, 92, 246, 0.2) 0%, transparent 50%);
        pointer-events: none;
    }

    .player-card-header::after {
        content: '';
        position: absolute;
        bottom: -2px;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6, #ec4899, #3b82f6);
        background-size: 200% 100%;
        animation: shimmer 3s linear infinite;
    }

    @keyframes shimmer {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }

    /* Stat Pill */
    .stat-pill {
        display: inline-block;
        background: #f3f4f6;
        border-radius: 20px;
        padding: 0.5rem 1rem;
        margin: 0.25rem;
        font-size: 0.875rem;
        font-weight: 600;
        color: #374151;
        transition: all 0.2s;
    }

    .stat-pill:hover {
        background: #3b82f6;
        color: white;
        transform: scale(1.05);
    }

    .stat-pill-active {
        background: #3b82f6;
        color: white;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
    }

    /* PropScore Badge - Premium Circular Design */
    .propscore-badge {
        display: inline-flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 2rem;
        border-radius: 20px;
        min-width: 140px;
        position: relative;
        overflow: hidden;
    }

    .propscore-badge::before {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 70%);
        animation: pulse-glow 3s ease-in-out infinite;
    }

    @keyframes pulse-glow {
        0%, 100% { opacity: 0.5; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.1); }
    }

    .propscore-high {
        background: linear-gradient(135deg, #10b981 0%, #059669 50%, #047857 100%);
        color: white;
        box-shadow:
            0 4px 12px rgba(16, 185, 129, 0.4),
            0 8px 24px rgba(16, 185, 129, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }

    .propscore-medium {
        background: linear-gradient(135deg, #f59e0b 0%, #d97706 50%, #b45309 100%);
        color: white;
        box-shadow:
            0 4px 12px rgba(245, 158, 11, 0.4),
            0 8px 24px rgba(245, 158, 11, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }

    .propscore-low {
        background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%);
        color: white;
        box-shadow:
            0 4px 12px rgba(239, 68, 68, 0.4),
            0 8px 24px rgba(239, 68, 68, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
    }

    /* Circular Progress Indicator */
    .circular-progress {
        position: relative;
        width: 160px;
        height: 160px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1rem auto;
    }

    .circular-progress-ring {
        transform: rotate(-90deg);
        width: 160px;
        height: 160px;
    }

    .circular-progress-ring circle {
        fill: none;
        stroke-width: 12;
        stroke-linecap: round;
        transition: stroke-dashoffset 1s ease;
    }

    .progress-bg {
        stroke: rgba(0, 0, 0, 0.1);
    }

    .progress-fill-high {
        stroke: url(#gradient-green);
        filter: drop-shadow(0 0 8px rgba(16, 185, 129, 0.5));
    }

    .progress-fill-medium {
        stroke: url(#gradient-orange);
        filter: drop-shadow(0 0 8px rgba(245, 158, 11, 0.5));
    }

    .progress-fill-low {
        stroke: url(#gradient-red);
        filter: drop-shadow(0 0 8px rgba(239, 68, 68, 0.5));
    }

    /* Layered Hit Rate Cards */
    .hit-rate-card {
        background: white;
        border: 2px solid #f3f4f6;
        border-radius: 12px;
        padding: 1.25rem 1.5rem;
        margin: 0.75rem 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        position: relative;
        overflow: hidden;
    }

    .hit-rate-card::before {
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 5px;
        transition: width 0.3s;
    }

    .hit-rate-card:hover {
        transform: translateX(4px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
    }

    .hit-rate-high {
        background: linear-gradient(135deg, #f0fdf4 0%, #ffffff 50%, #fafafa 100%);
        border-left: 5px solid #10b981;
    }

    .hit-rate-high::before {
        background: linear-gradient(180deg, #10b981, #059669);
    }

    .hit-rate-high:hover::before {
        width: 100%;
        opacity: 0.05;
    }

    .hit-rate-medium {
        background: linear-gradient(135deg, #fffbeb 0%, #ffffff 50%, #fafafa 100%);
        border-left: 5px solid #f59e0b;
    }

    .hit-rate-medium::before {
        background: linear-gradient(180deg, #f59e0b, #d97706);
    }

    .hit-rate-medium:hover::before {
        width: 100%;
        opacity: 0.05;
    }

    .hit-rate-low {
        background: linear-gradient(135deg, #fef2f2 0%, #ffffff 50%, #fafafa 100%);
        border-left: 5px solid #ef4444;
    }

    .hit-rate-low::before {
        background: linear-gradient(180deg, #ef4444, #dc2626);
    }

    .hit-rate-low:hover::before {
        width: 100%;
        opacity: 0.05;
    }

    /* Buttons - Clean & Modern */
    .stButton button {
        background: #3b82f6;
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        padding: 0.75rem 1.5rem;
        transition: all 0.2s;
        font-size: 0.95rem;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2);
    }

    .stButton button:hover {
        background: #2563eb;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        transform: translateY(-1px);
    }

    .stButton button:active {
        transform: translateY(0);
    }

    /* Secondary Button Style */
    .stButton button[kind="secondary"] {
        background: white;
        color: #3b82f6;
        border: 2px solid #3b82f6;
    }

    .stButton button[kind="secondary"]:hover {
        background: #eff6ff;
    }

    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #3b82f6;
        font-weight: 700;
    }

    div[data-testid="stMetricLabel"] {
        color: #6b7280;
        font-weight: 500;
        text-transform: uppercase;
        font-size: 0.75rem;
        letter-spacing: 0.5px;
    }

    /* Inputs */
    input, select {
        background-color: white !important;
        border: 2px solid #e5e7eb !important;
        border-radius: 10px !important;
        padding: 0.75rem !important;
        color: #111827 !important;
        font-weight: 500 !important;
    }

    input:focus, select:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }

    /* Team Colors as Accents */
    .team-badge {
        display: inline-block;
        padding: 0.375rem 0.75rem;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.875rem;
        letter-spacing: 0.5px;
    }

    /* Matchup Difficulty Badge */
    .difficulty-easy {
        background: #dcfce7;
        color: #166534;
        border: 1px solid #bbf7d0;
    }

    .difficulty-medium {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #fde68a;
    }

    .difficulty-hard {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #fecaca;
    }

    /* Data Table Style */
    .data-row {
        display: grid;
        grid-template-columns: 1fr 2fr 1fr;
        gap: 1rem;
        padding: 0.75rem;
        border-bottom: 1px solid #f3f4f6;
        align-items: center;
    }

    .data-row:last-child {
        border-bottom: none;
    }

    /* Progress Bar */
    .progress-bar {
        width: 100%;
        height: 8px;
        background: #f3f4f6;
        border-radius: 4px;
        overflow: hidden;
    }

    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #3b82f6, #2563eb);
        border-radius: 4px;
        transition: width 0.3s ease;
    }

    /* Recommendation Card */
    .recommendation-card {
        border: 3px solid;
        border-radius: 16px;
        padding: 2rem;
        margin: 2rem 0;
        text-align: center;
        background: white;
    }

    .rec-strong-over {
        border-color: #10b981;
        background: linear-gradient(135deg, #f0fdf4 0%, white 100%);
    }

    .rec-lean-over {
        border-color: #84cc16;
        background: linear-gradient(135deg, #f7fee7 0%, white 100%);
    }

    .rec-toss-up {
        border-color: #6b7280;
        background: linear-gradient(135deg, #f9fafb 0%, white 100%);
    }

    .rec-lean-under {
        border-color: #f97316;
        background: linear-gradient(135deg, #fff7ed 0%, white 100%);
    }

    .rec-strong-under {
        border-color: #ef4444;
        background: linear-gradient(135deg, #fef2f2 0%, white 100%);
    }

    .block-container {
        padding-top: 1rem;
        max-width: 1600px;
    }

    /* Quick Stats Badge */
    .quick-stat {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        margin: 0.25rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    }

    .quick-stat-label {
        font-size: 0.75rem;
        color: #6b7280;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    .quick-stat-value {
        font-size: 1.125rem;
        color: #111827;
        font-weight: 700;
    }

    /* Stat Comparison */
    .stat-comparison {
        display: grid;
        grid-template-columns: 1fr auto 1fr;
        gap: 1rem;
        align-items: center;
        padding: 0.75rem;
        background: #f9fafb;
        border-radius: 8px;
        margin: 0.5rem 0;
    }

    .stat-vs {
        color: #9ca3af;
        font-weight: 700;
        font-size: 0.875rem;
    }

    /* Tag System */
    .tag {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        margin: 0.25rem;
    }

    .tag-live {
        background: #dcfce7;
        color: #166534;
    }

    .tag-upcoming {
        background: #dbeafe;
        color: #1e40af;
    }

    /* Section Headers */
    .section-header {
        font-size: 0.875rem;
        font-weight: 700;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #f3f4f6;
    }

    /* Team Logo Styling */
    .team-logo {
        width: 60px;
        height: 60px;
        object-fit: contain;
        filter: drop-shadow(0 2px 8px rgba(0, 0, 0, 0.15));
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .team-logo:hover {
        transform: scale(1.1) rotate(5deg);
        filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.25));
    }

    .team-logo-large {
        width: 100px;
        height: 100px;
        object-fit: contain;
        filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.2));
    }

    .team-logo-watermark {
        position: absolute;
        width: 200px;
        height: 200px;
        opacity: 0.08;
        right: -20px;
        top: 50%;
        transform: translateY(-50%) rotate(-15deg);
        pointer-events: none;
        z-index: 0;
    }

    /* VS Indicator - Modern Battle Style */
    .vs-indicator {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 50px;
        height: 50px;
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
        border-radius: 50%;
        color: white;
        font-weight: 900;
        font-size: 0.875rem;
        box-shadow:
            0 4px 12px rgba(99, 102, 241, 0.4),
            0 8px 24px rgba(139, 92, 246, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
        position: relative;
        z-index: 2;
    }

    .vs-indicator::before {
        content: '';
        position: absolute;
        top: -3px;
        left: -3px;
        right: -3px;
        bottom: -3px;
        background: linear-gradient(135deg, #6366f1, #8b5cf6, #ec4899);
        border-radius: 50%;
        z-index: -1;
        animation: rotate-border 3s linear infinite;
    }

    @keyframes rotate-border {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    /* Enhanced Player Headshot */
    .player-headshot {
        width: 120px;
        height: 120px;
        border-radius: 50%;
        border: 4px solid rgba(255, 255, 255, 0.3);
        background: rgba(255, 255, 255, 0.1);
        object-fit: cover;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.2),
            0 8px 24px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.2);
        transition: all 0.3s ease;
    }

    .player-headshot:hover {
        transform: scale(1.05);
        border-color: rgba(255, 255, 255, 0.5);
        box-shadow:
            0 6px 16px rgba(0, 0, 0, 0.25),
            0 12px 32px rgba(0, 0, 0, 0.2);
    }

    /* Live Pulse Animation */
    .live-pulse {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #10b981;
        border-radius: 50%;
        margin-right: 0.5rem;
        animation: pulse 2s ease-in-out infinite;
    }

    @keyframes pulse {
        0%, 100% {
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
        }
        50% {
            box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
        }
    }

    /* Enhanced Stat Cards with Glassmorphism */
    .stat-card-premium {
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.9) 100%);
        backdrop-filter: blur(10px) saturate(180%);
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow:
            0 4px 12px rgba(0, 0, 0, 0.08),
            0 12px 32px rgba(0, 0, 0, 0.06),
            inset 0 1px 0 rgba(255, 255, 255, 0.8);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .stat-card-premium:hover {
        transform: translateY(-2px);
        box-shadow:
            0 6px 16px rgba(0, 0, 0, 0.1),
            0 16px 40px rgba(0, 0, 0, 0.08);
    }

    /* Subtle Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .fade-in {
        animation: fadeIn 0.5s ease;
    }

    @keyframes slideIn {
        from { opacity: 0; transform: translateX(-20px); }
        to { opacity: 1; transform: translateX(0); }
    }

    .slide-in {
        animation: slideIn 0.4s ease;
    }

    /* Gradient Overlays for Charts */
    .chart-container {
        background: white;
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow:
            0 2px 8px rgba(0, 0, 0, 0.04),
            0 8px 24px rgba(0, 0, 0, 0.04);
        border: 1px solid #f3f4f6;
    }
</style>
""", unsafe_allow_html=True)

# Team Data with Enhanced Branding
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

# Team Logo URLs - Using ESPN's CDN (reliable and high quality)
TEAM_LOGOS = {
    'ATL': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/atl.png',
    'BOS': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/bos.png',
    'BKN': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/bkn.png',
    'CHA': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/cha.png',
    'CHI': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/chi.png',
    'CLE': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/cle.png',
    'DAL': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/dal.png',
    'DEN': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/den.png',
    'DET': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/det.png',
    'GSW': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/gs.png',
    'HOU': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/hou.png',
    'IND': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/ind.png',
    'LAC': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/lac.png',
    'LAL': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/lal.png',
    'MEM': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/mem.png',
    'MIA': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/mia.png',
    'MIL': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/mil.png',
    'MIN': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/min.png',
    'NOP': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/no.png',
    'NYK': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/ny.png',
    'OKC': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/okc.png',
    'ORL': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/orl.png',
    'PHI': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/phi.png',
    'PHX': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/phx.png',
    'POR': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/por.png',
    'SAC': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/sac.png',
    'SAS': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/sa.png',
    'TOR': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/tor.png',
    'UTA': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/utah.png',
    'WAS': 'https://a.espncdn.com/combiner/i?img=/i/teamlogos/nba/500/wsh.png'
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
    """Fetch today's games - uses live NBA data when available"""

    # Try to use live NBA data first
    if NBA_DATA_AVAILABLE:
        try:
            games = get_enriched_games()
            if games:  # If we got live data, use it
                return games
        except Exception as e:
            print(f"Error fetching live NBA data: {e}")
            # Fall through to mock data

    # Fallback to mock data
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

def generate_player_game_log(player_id, stat_type, base_stat, num_games=20):
    """Fetch player game log - uses live NBA data when available"""

    # Try to use live NBA data first
    if NBA_DATA_AVAILABLE and player_id:
        try:
            real_games = get_player_game_log(player_id, num_games)
            if real_games:
                # Convert to format expected by app
                formatted_games = []
                for game in real_games:
                    value = game.get(stat_type, 0)
                    formatted_games.append({
                        'date': game['date'],
                        'value': value,
                        'opponent': game['opponent']
                    })
                return formatted_games
        except Exception as e:
            print(f"Error fetching player game log: {e}")
            # Fall through to mock data

    # Fallback to mock data
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
        return 'easy', f"#{def_rank} vs {player_pos}", 'difficulty-easy'
    elif def_rank >= 15:
        return 'medium', f"#{def_rank} vs {player_pos}", 'difficulty-medium'
    else:
        return 'hard', f"#{def_rank} vs {player_pos}", 'difficulty-hard'

def create_clean_chart(games, line, stat_name):
    """Create stunning, professional chart with enhanced visuals"""
    fig = go.Figure()

    # Enhanced colors with gradient effect
    colors = []
    for g in games[:10]:
        if g['value'] > line:
            # Green gradient for hits
            colors.append('rgba(16, 185, 129, 0.9)')
        else:
            # Gray for misses
            colors.append('rgba(148, 163, 184, 0.6)')

    fig.add_trace(go.Bar(
        x=[g['date'] for g in games[:10]],
        y=[g['value'] for g in games[:10]],
        marker=dict(
            color=colors,
            line=dict(color='white', width=3),
            cornerradius=6
        ),
        text=[g['value'] for g in games[:10]],
        textposition='outside',
        textfont=dict(color='#111827', size=13, family='Inter', weight='bold'),
        hovertemplate='<b>%{x}</b><br><b style="font-size:16px;">%{y}</b><br><extra></extra>',
        hoverlabel=dict(
            bgcolor='white',
            bordercolor='#e5e7eb',
            font=dict(color='#111827', family='Inter', size=14)
        )
    ))

    # Enhanced line annotation
    fig.add_hline(
        y=line,
        line_dash="dash",
        line_color="#ef4444",
        line_width=4,
        annotation_text=f"🎯 Line: {line}",
        annotation_position="right",
        annotation_font=dict(
            color="#ef4444",
            size=13,
            family='Inter',
            weight='bold'
        ),
        annotation_bgcolor='rgba(255, 255, 255, 0.9)',
        annotation_bordercolor='#ef4444',
        annotation_borderwidth=2,
        annotation_borderpad=8
    )

    fig.update_layout(
        plot_bgcolor='rgba(249, 250, 251, 0.5)',
        paper_bgcolor='transparent',
        font=dict(color='#6b7280', family='Inter'),
        height=300,
        margin=dict(l=20, r=20, t=30, b=40),
        xaxis=dict(
            showgrid=False,
            showline=True,
            linecolor='#e5e7eb',
            linewidth=2,
            zeroline=False,
            color='#374151',
            tickfont=dict(size=11, weight='bold')
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='rgba(229, 231, 235, 0.5)',
            gridwidth=1,
            showline=True,
            linecolor='#e5e7eb',
            linewidth=2,
            zeroline=False,
            title="",
            color='#374151',
            tickfont=dict(size=11, weight='bold')
        ),
        hovermode='x unified',
        hoverlabel=dict(
            bgcolor='white',
            bordercolor='#e5e7eb'
        )
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

# ========== CLEAN HEADER ==========
current_date = datetime.now().strftime('%b %d, %Y')
st.markdown(f"""
<div class="main-header">
    <div style="max-width: 1600px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: space-between; align-items: center;">
        <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="width: 45px; height: 45px; background: linear-gradient(135deg, #3b82f6, #2563eb); border-radius: 12px;
                        display: flex; align-items: center; justify-content: center; font-weight: 900; font-size: 1.5rem; color: white;
                        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);">P</div>
            <div>
                <div style="font-size: 1.75rem; font-weight: 900; color: #111827; letter-spacing: -0.5px;">PropStats</div>
                <div style="font-size: 0.8rem; color: #6b7280; font-weight: 600; letter-spacing: 0.5px;">NBA PROPS RESEARCH</div>
            </div>
        </div>
        <div style="display: flex; gap: 1rem; align-items: center;">
            <span class="tag tag-live"><span class="live-pulse"></span>LIVE</span>
            <div style="text-align: right;">
                <div style="font-size: 0.7rem; color: #9ca3af; font-weight: 600; text-transform: uppercase;">Today</div>
                <div style="color: #111827; font-size: 0.9rem; font-weight: 700;">{current_date}</div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ========== LAYER 1: TODAY'S SLATE ==========
if st.session_state.view == 'slate':
    st.markdown("""
    <div style="margin: 2.5rem 0 2rem 0;">
        <div style="display: flex; justify-content: space-between; align-items: end; margin-bottom: 1rem;">
            <div>
                <h1 style="color: #111827; font-size: 2.5rem; font-weight: 900; margin-bottom: 0.5rem; letter-spacing: -1px;">Today's Games</h1>
                <p style="color: #6b7280; font-size: 1.05rem;">Select a matchup to view detailed player props</p>
            </div>
            <div class="quick-stat" style="margin: 0;">
                <div>
                    <div class="quick-stat-label">Total Games</div>
                    <div class="quick-stat-value">8</div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    games = generate_todays_games()

    cols = st.columns(2, gap="large")
    for idx, game in enumerate(games):
        away_color = TEAM_COLORS.get(game['away_team'], '#666')
        home_color = TEAM_COLORS.get(game['home_team'], '#666')
        away_logo = TEAM_LOGOS.get(game['away_team'], '')
        home_logo = TEAM_LOGOS.get(game['home_team'], '')

        with cols[idx % 2]:
            # Safe stat access with defaults
            away_ppg = game.get('away_stats', {}).get('ppg', 'N/A')
            away_pace = game.get('away_stats', {}).get('pace', 'N/A')
            home_ppg = game.get('home_stats', {}).get('ppg', 'N/A')
            home_pace = game.get('home_stats', {}).get('pace', 'N/A')

            st.markdown(f"""
            <div class="game-card fade-in" style="animation-delay: {idx * 0.05}s;">
                <div class="game-card-header">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span class="tag tag-upcoming">{game['time']}</span>
                        <div style="display: flex; gap: 0.5rem;">
                            <div style="text-align: center;">
                                <div style="font-size: 0.65rem; color: #9ca3af; font-weight: 600;">PLAYERS</div>
                                <div style="font-size: 1.125rem; font-weight: 800; color: #3b82f6;">{len(game.get('away_players', [])) + len(game.get('home_players', []))}</div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="game-card-body">
                    <div style="display: flex; align-items: center; justify-content: space-between; gap: 1.5rem; position: relative;">
                        <!-- Away Team -->
                        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.75rem;">
                            <img src="{away_logo}" class="team-logo" alt="{game['away_team']}" onerror="this.style.display='none'">
                            <div style="text-align: center;">
                                <div style="font-weight: 800; font-size: 1.125rem; color: #111827; letter-spacing: -0.5px;">{game['away_team']}</div>
                                <div style="font-size: 0.7rem; color: #6b7280; font-weight: 600;">{TEAM_NAMES.get(game['away_team'], game['away_team'])}</div>
                            </div>
                            <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
                                <div style="text-align: center;">
                                    <div style="font-size: 0.65rem; color: #6b7280; font-weight: 600;">PPG</div>
                                    <div style="font-size: 0.95rem; font-weight: 700; color: #111827;">{away_ppg}</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.65rem; color: #6b7280; font-weight: 600;">PACE</div>
                                    <div style="font-size: 0.95rem; font-weight: 700; color: #111827;">{away_pace}</div>
                                </div>
                            </div>
                        </div>

                        <!-- VS Indicator -->
                        <div class="vs-indicator">VS</div>

                        <!-- Home Team -->
                        <div style="flex: 1; display: flex; flex-direction: column; align-items: center; gap: 0.75rem;">
                            <img src="{home_logo}" class="team-logo" alt="{game['home_team']}" onerror="this.style.display='none'">
                            <div style="text-align: center;">
                                <div style="font-weight: 800; font-size: 1.125rem; color: #111827; letter-spacing: -0.5px;">{game['home_team']}</div>
                                <div style="font-size: 0.7rem; color: #6b7280; font-weight: 600;">{TEAM_NAMES.get(game['home_team'], game['home_team'])}</div>
                            </div>
                            <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
                                <div style="text-align: center;">
                                    <div style="font-size: 0.65rem; color: #6b7280; font-weight: 600;">PPG</div>
                                    <div style="font-size: 0.95rem; font-weight: 700; color: #111827;">{home_ppg}</div>
                                </div>
                                <div style="text-align: center;">
                                    <div style="font-size: 0.65rem; color: #6b7280; font-weight: 600;">PACE</div>
                                    <div style="font-size: 0.95rem; font-weight: 700; color: #111827;">{home_pace}</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"View Props →", key=f"game_{idx}", use_container_width=True):
                st.session_state.selected_game = game
                st.session_state.view = 'matchup'
                st.rerun()

# ========== LAYER 2: MATCHUP BOARD ==========
elif st.session_state.view == 'matchup':
    game = st.session_state.selected_game

    # Enrich with rosters if using live data and rosters not loaded
    if NBA_DATA_AVAILABLE and not game.get('away_players'):
        with st.spinner('Loading rosters...'):
            try:
                game = enrich_game_with_rosters(game)
                st.session_state.selected_game = game  # Update session state
            except Exception as e:
                print(f"Error enriching game with rosters: {e}")
                st.warning("Unable to load live rosters. Showing limited data.")

    if st.button("← Back to Games", type="secondary"):
        st.session_state.view = 'slate'
        st.rerun()

    st.markdown(f"""
    <div style="margin: 2rem 0 1.5rem 0;">
        <div style="display: flex; align-items: center; gap: 1rem; margin-bottom: 1rem;">
            <h1 style="color: #111827; font-size: 2rem; font-weight: 800; margin: 0;">
                {TEAM_NAMES[game['away_team']]} @ {TEAM_NAMES[game['home_team']]}
            </h1>
            <span class="tag tag-upcoming">{game['time']}</span>
        </div>
        <p style="color: #6b7280; font-size: 1rem;">Select a player to view detailed prop analysis</p>
    </div>
    """, unsafe_allow_html=True)

    # Team Stats Comparison
    col1, col2 = st.columns(2, gap="large")

    # Safe stat access
    away_stats = game.get('away_stats', {})
    home_stats = game.get('home_stats', {})

    away_ppg = away_stats.get('ppg', 110)
    away_pace = away_stats.get('pace', 100)
    away_off_rank = away_stats.get('off_rank', 15)
    away_def_rank = away_stats.get('def_rank', 15)

    with col1:
        away_logo = TEAM_LOGOS.get(game['away_team'], '')
        st.markdown(f"""
        <div class="prop-card slide-in">
            <div class="prop-card-header" style="position: relative; overflow: hidden;">
                <img src="{away_logo}" class="team-logo-watermark" alt="{game['away_team']}" onerror="this.style.display='none'">
                <div style="display: flex; align-items: center; gap: 1rem; position: relative; z-index: 1;">
                    <img src="{away_logo}" style="width: 48px; height: 48px; object-fit: contain;" alt="{game['away_team']}" onerror="this.style.display='none'">
                    <div>
                        <h3 style="font-size: 1.25rem; font-weight: 800; color: #111827; margin: 0; letter-spacing: -0.5px;">
                            {game['away_team']}
                        </h3>
                        <div style="font-size: 0.875rem; color: #6b7280; font-weight: 600;">{TEAM_NAMES.get(game['away_team'], game['away_team'])}</div>
                    </div>
                </div>
            </div>
            <div class="prop-card-body">
                <div style="display: grid; gap: 0.75rem;">
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">PPG</span>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {away_ppg/1.3}%"></div>
                        </div>
                        <span style="font-weight: 800; color: #111827;">{away_ppg}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Pace</span>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {away_pace}%"></div>
                        </div>
                        <span style="font-weight: 800; color: #111827;">{away_pace}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Off Rank</span>
                        <span></span>
                        <span style="font-weight: 800; color: #10b981;">#{away_off_rank}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Def Rank</span>
                        <span></span>
                        <span style="font-weight: 800; color: #ef4444;">#{away_def_rank}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    home_ppg = home_stats.get('ppg', 110)
    home_pace = home_stats.get('pace', 100)
    home_off_rank = home_stats.get('off_rank', 15)
    home_def_rank = home_stats.get('def_rank', 15)

    with col2:
        home_logo = TEAM_LOGOS.get(game['home_team'], '')
        st.markdown(f"""
        <div class="prop-card slide-in" style="animation-delay: 0.1s;">
            <div class="prop-card-header" style="position: relative; overflow: hidden;">
                <img src="{home_logo}" class="team-logo-watermark" alt="{game['home_team']}" onerror="this.style.display='none'">
                <div style="display: flex; align-items: center; gap: 1rem; position: relative; z-index: 1;">
                    <img src="{home_logo}" style="width: 48px; height: 48px; object-fit: contain;" alt="{game['home_team']}" onerror="this.style.display='none'">
                    <div>
                        <h3 style="font-size: 1.25rem; font-weight: 800; color: #111827; margin: 0; letter-spacing: -0.5px;">
                            {game['home_team']}
                        </h3>
                        <div style="font-size: 0.875rem; color: #6b7280; font-weight: 600;">{TEAM_NAMES.get(game['home_team'], game['home_team'])}</div>
                    </div>
                </div>
            </div>
            <div class="prop-card-body">
                <div style="display: grid; gap: 0.75rem;">
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">PPG</span>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {home_ppg/1.3}%"></div>
                        </div>
                        <span style="font-weight: 800; color: #111827;">{home_ppg}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Pace</span>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: {home_pace}%"></div>
                        </div>
                        <span style="font-weight: 800; color: #111827;">{home_pace}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Off Rank</span>
                        <span></span>
                        <span style="font-weight: 800; color: #10b981;">#{home_off_rank}</span>
                    </div>
                    <div class="data-row">
                        <span style="color: #6b7280; font-weight: 600;">Def Rank</span>
                        <span></span>
                        <span style="font-weight: 800; color: #ef4444;">#{home_def_rank}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Player Selection
    if game.get('away_players'):
        st.markdown(f"<div class='section-header'>{TEAM_NAMES.get(game['away_team'], game['away_team'])} Players</div>", unsafe_allow_html=True)
        cols = st.columns(3, gap="medium")
        for i, player in enumerate(game['away_players']):
            with cols[i % 3]:
                player_name = player.get('name', 'Unknown Player')
                player_pos = player.get('pos', '?')
                player_num = player.get('number', '0')
                if st.button(f"{player_name}\n{player_pos} • #{player_num}", key=f"away_{i}", use_container_width=True):
                    st.session_state.selected_player = player
                    st.session_state.view = 'player'
                    st.rerun()
    else:
        st.info(f"Loading {TEAM_NAMES.get(game['away_team'], game['away_team'])} roster...")

    if game.get('home_players'):
        st.markdown(f"<div class='section-header'>{TEAM_NAMES.get(game['home_team'], game['home_team'])} Players</div>", unsafe_allow_html=True)
        cols = st.columns(3, gap="medium")
        for i, player in enumerate(game['home_players']):
            with cols[i % 3]:
                player_name = player.get('name', 'Unknown Player')
                player_pos = player.get('pos', '?')
                player_num = player.get('number', '0')
                if st.button(f"{player_name}\n{player_pos} • #{player_num}", key=f"home_{i}", use_container_width=True):
                    st.session_state.selected_player = player
                    st.session_state.view = 'player'
                    st.rerun()
    else:
        st.info(f"Loading {TEAM_NAMES.get(game['home_team'], game['home_team'])} roster...")

# ========== LAYER 3: PLAYER DEEP DIVE ==========
elif st.session_state.view == 'player':
    if st.button("← Back to Matchup", type="secondary"):
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
    team_logo = TEAM_LOGOS.get(player_team, '')
    opponent_logo = TEAM_LOGOS.get(opponent_team, '')
    headshot_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player['id']}.png"

    # Player Card Header with Enhanced Design
    st.markdown(f"""
    <div class="player-card fade-in">
        <div class="player-card-header">
            <!-- Team Logo Watermark -->
            <img src="{team_logo}" style="position: absolute; width: 300px; height: 300px; opacity: 0.1; right: -50px; top: 50%; transform: translateY(-50%) rotate(-15deg); pointer-events: none; z-index: 0;" alt="{player_team}" onerror="this.style.display='none'">

            <div style="display: flex; justify-content: space-between; align-items: start; position: relative; z-index: 1;">
                <div style="display: flex; gap: 2rem; align-items: center;">
                    <!-- Enhanced Player Headshot -->
                    <img src="{headshot_url}" class="player-headshot" alt="{player['name']}" onerror="this.style.display='none'">

                    <div>
                        <h1 style="font-size: 2.25rem; font-weight: 900; margin: 0 0 0.75rem 0; color: white; letter-spacing: -1px; text-shadow: 0 2px 8px rgba(0,0,0,0.2);">
                            {player['name']}
                        </h1>
                        <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
                            <span class="team-badge" style="background: rgba(255,255,255,0.25); color: white; padding: 0.5rem 1rem; backdrop-filter: blur(10px);">
                                {player_team} • {player['pos']} • #{player.get('number', '0')}
                            </span>
                            <span class="team-badge" style="background: rgba(255,255,255,0.15); color: white; padding: 0.5rem 1rem; backdrop-filter: blur(10px);">
                                vs {opponent_team}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Matchup Logos -->
                <div style="display: flex; align-items: center; gap: 0.75rem; opacity: 0.9;">
                    <img src="{team_logo}" style="width: 40px; height: 40px; object-fit: contain; filter: brightness(0) invert(1) drop-shadow(0 2px 4px rgba(0,0,0,0.2));" alt="{player_team}" onerror="this.style.display='none'">
                    <span style="color: rgba(255,255,255,0.6); font-weight: 700; font-size: 0.875rem;">@</span>
                    <img src="{opponent_logo}" style="width: 40px; height: 40px; object-fit: contain; filter: brightness(0) invert(1) drop-shadow(0 2px 4px rgba(0,0,0,0.2));" alt="{opponent_team}" onerror="this.style.display='none'">
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Stat Selection
    available_stats = list(player['stats'].keys())
    st.markdown("<div class='section-header'>Select Stat Category</div>", unsafe_allow_html=True)

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

    # Line Input
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        line = st.number_input("Betting Line", min_value=0.5, max_value=100.0,
                               value=float(base_value), step=0.5, key="line_input")

    # Generate Data
    player_id = player.get('id', None)
    game_log = generate_player_game_log(player_id, selected_stat, base_value)

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
    propscore_class = 'propscore-high' if propscore >= 65 else 'propscore-medium' if propscore >= 40 else 'propscore-low'
    propscore_label = 'HIGH CONFIDENCE' if propscore >= 65 else 'MEDIUM' if propscore >= 40 else 'LOW CONFIDENCE'

    # Main Content
    col_left, col_right = st.columns([1, 2], gap="large")

    with col_left:
        # Circular PropScore Indicator
        circumference = 2 * 3.14159 * 70  # radius = 70
        progress_offset = circumference - (propscore / 100) * circumference
        progress_class = 'progress-fill-high' if propscore >= 65 else 'progress-fill-medium' if propscore >= 40 else 'progress-fill-low'

        st.markdown(f"""
        <!-- SVG Gradients Definition -->
        <svg width="0" height="0" style="position: absolute;">
            <defs>
                <linearGradient id="gradient-green" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#10b981;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#059669;stop-opacity:1" />
                </linearGradient>
                <linearGradient id="gradient-orange" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#f59e0b;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#d97706;stop-opacity:1" />
                </linearGradient>
                <linearGradient id="gradient-red" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:#ef4444;stop-opacity:1" />
                    <stop offset="100%" style="stop-color:#dc2626;stop-opacity:1" />
                </linearGradient>
            </defs>
        </svg>

        <div class="propscore-badge {propscore_class}" style="width: 100%; margin-bottom: 1.5rem; padding: 2rem 1rem;">
            <div style="font-size: 0.75rem; font-weight: 700; opacity: 0.9; margin-bottom: 1rem; letter-spacing: 1px;">PROPSCORE</div>

            <!-- Circular Progress -->
            <div class="circular-progress">
                <svg class="circular-progress-ring">
                    <circle class="progress-bg" cx="80" cy="80" r="70" />
                    <circle class="{progress_class}" cx="80" cy="80" r="70"
                            stroke-dasharray="{circumference}"
                            stroke-dashoffset="{progress_offset}" />
                </svg>
                <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
                    <div style="font-size: 3.5rem; font-weight: 900; line-height: 1; color: white; text-shadow: 0 2px 8px rgba(0,0,0,0.2);">{propscore}</div>
                    <div style="font-size: 0.75rem; font-weight: 600; opacity: 0.8; margin-top: 0.25rem;">/ 100</div>
                </div>
            </div>

            <div style="font-size: 0.8rem; font-weight: 700; opacity: 0.9; margin-top: 1rem; letter-spacing: 0.5px;">{propscore_label}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div class='section-header'>Hit Rates</div>", unsafe_allow_html=True)

        # Hit Rate Cards
        def get_hit_class(rate):
            if rate >= 65:
                return 'hit-rate-high'
            elif rate >= 50:
                return 'hit-rate-medium'
            else:
                return 'hit-rate-low'

        for label, rate, hits, total in [
            ('Last 5 Games', l5_rate, l5_hits, 5),
            ('Last 10 Games', l10_rate, l10_hits, 10),
            ('Last 20 Games', l20_rate, l20_hits, 20)
        ]:
            hit_class = get_hit_class(rate)
            st.markdown(f"""
            <div class="hit-rate-card {hit_class}">
                <div>
                    <div style="font-size: 0.875rem; font-weight: 600; color: #6b7280; margin-bottom: 0.25rem;">{label}</div>
                    <div style="font-size: 0.75rem; color: #9ca3af;">{hits}/{total} games</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 2rem; font-weight: 800; color: #111827;">{rate:.0f}%</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Matchup Difficulty
        st.markdown(f"""
        <div class="team-badge {difficulty_class}" style="width: 100%; margin-top: 1rem; text-align: center; padding: 0.75rem;">
            <div style="font-size: 0.75rem; font-weight: 600; margin-bottom: 0.25rem;">MATCHUP DIFFICULTY</div>
            <div style="font-size: 1rem; font-weight: 700;">{difficulty_text.upper()}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_right:
        st.markdown("<div class='section-header'>Performance Timeline</div>", unsafe_allow_html=True)

        st.markdown("<div class='chart-container'>", unsafe_allow_html=True)
        chart = create_clean_chart(game_log, line, selected_stat.upper())
        st.plotly_chart(chart, use_container_width=True, config={'displayModeBar': False})
        st.markdown("</div>", unsafe_allow_html=True)

        # Stats Grid
        col1, col2, col3 = st.columns(3)

        metrics = [
            ("Season Avg", season_avg, f"{season_avg - line:+.1f} vs Line"),
            ("L10 Avg", l10_avg, f"{l10_avg - season_avg:+.1f}"),
            ("Consistency", consistency, "HIGH" if consistency >= 70 else "MED" if consistency >= 50 else "LOW")
        ]

        for col, (label, value, delta) in zip([col1, col2, col3], metrics):
            with col:
                st.metric(label=label, value=f"{value:.1f}", delta=delta)

    # Recommendation
    if propscore >= 70:
        verdict, verdict_class, icon = "STRONG OVER", "rec-strong-over", "🔥"
    elif propscore >= 55:
        verdict, verdict_class, icon = "LEAN OVER", "rec-lean-over", "📈"
    elif propscore <= 30:
        verdict, verdict_class, icon = "STRONG UNDER", "rec-strong-under", "❌"
    elif propscore <= 45:
        verdict, verdict_class, icon = "LEAN UNDER", "rec-lean-under", "📉"
    else:
        verdict, verdict_class, icon = "TOSS UP", "rec-toss-up", "⚖️"

    st.markdown(f"""
    <div class="recommendation-card {verdict_class}">
        <div style="font-size: 0.875rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.5rem;">
            Recommendation
        </div>
        <div style="font-size: 2.5rem; font-weight: 900; color: #111827; margin: 0.5rem 0;">
            {icon} {verdict}
        </div>
        <div style="font-size: 0.95rem; color: #6b7280; font-weight: 600;">
            Confidence: {propscore}/100 • Based on L10 hit rate, trends, and matchup
        </div>
    </div>
    """, unsafe_allow_html=True)

# Footer
st.markdown("""
<div style="margin-top: 4rem; padding: 2rem 0; border-top: 1px solid #e5e7eb; text-align: center;">
    <div style="font-weight: 700; color: #111827; margin-bottom: 0.5rem;">PropStats</div>
    <p style="color: #9ca3af; font-size: 0.875rem;">© 2025 • NBA Props Research Platform</p>
    <p style="font-size: 0.75rem; margin-top: 0.5rem; color: #d1d5db;">⚠️ For entertainment purposes only. 21+ Gamble responsibly.</p>
</div>
""", unsafe_allow_html=True)
