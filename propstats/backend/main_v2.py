"""
PropStats API v2.0 - Enhanced NBA Props Research
Uses nba_api for reliable real-time data
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import time
import json

# NBA API imports
from nba_api.stats.static import players, teams
from nba_api.stats.endpoints import (
    playergamelog,
    commonplayerinfo,
    playercareerstats,
    leaguegamefinder
)

app = FastAPI(title="PropStats API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DATABASE_PATH", "nba_props.db")

# Team info for logos and colors
TEAM_INFO = {
    "ATL": {"id": 1610612737, "name": "Hawks", "city": "Atlanta", "color": "#E03A3E"},
    "BOS": {"id": 1610612738, "name": "Celtics", "city": "Boston", "color": "#007A33"},
    "BKN": {"id": 1610612751, "name": "Nets", "city": "Brooklyn", "color": "#000000"},
    "CHA": {"id": 1610612766, "name": "Hornets", "city": "Charlotte", "color": "#1D1160"},
    "CHI": {"id": 1610612741, "name": "Bulls", "city": "Chicago", "color": "#CE1141"},
    "CLE": {"id": 1610612739, "name": "Cavaliers", "city": "Cleveland", "color": "#6F263D"},
    "DAL": {"id": 1610612742, "name": "Mavericks", "city": "Dallas", "color": "#00538C"},
    "DEN": {"id": 1610612743, "name": "Nuggets", "city": "Denver", "color": "#0E2240"},
    "DET": {"id": 1610612765, "name": "Pistons", "city": "Detroit", "color": "#C8102E"},
    "GSW": {"id": 1610612744, "name": "Warriors", "city": "Golden State", "color": "#1D428A"},
    "HOU": {"id": 1610612745, "name": "Rockets", "city": "Houston", "color": "#CE1141"},
    "IND": {"id": 1610612754, "name": "Pacers", "city": "Indiana", "color": "#002D62"},
    "LAC": {"id": 1610612746, "name": "Clippers", "city": "LA", "color": "#C8102E"},
    "LAL": {"id": 1610612747, "name": "Lakers", "city": "Los Angeles", "color": "#552583"},
    "MEM": {"id": 1610612763, "name": "Grizzlies", "city": "Memphis", "color": "#5D76A9"},
    "MIA": {"id": 1610612748, "name": "Heat", "city": "Miami", "color": "#98002E"},
    "MIL": {"id": 1610612749, "name": "Bucks", "city": "Milwaukee", "color": "#00471B"},
    "MIN": {"id": 1610612750, "name": "Timberwolves", "city": "Minnesota", "color": "#0C2340"},
    "NOP": {"id": 1610612740, "name": "Pelicans", "city": "New Orleans", "color": "#0C2340"},
    "NYK": {"id": 1610612752, "name": "Knicks", "city": "New York", "color": "#006BB6"},
    "OKC": {"id": 1610612760, "name": "Thunder", "city": "Oklahoma City", "color": "#007AC1"},
    "ORL": {"id": 1610612753, "name": "Magic", "city": "Orlando", "color": "#0077C0"},
    "PHI": {"id": 1610612755, "name": "76ers", "city": "Philadelphia", "color": "#006BB6"},
    "PHX": {"id": 1610612756, "name": "Suns", "city": "Phoenix", "color": "#1D1160"},
    "POR": {"id": 1610612757, "name": "Trail Blazers", "city": "Portland", "color": "#E03A3E"},
    "SAC": {"id": 1610612758, "name": "Kings", "city": "Sacramento", "color": "#5A2D81"},
    "SAS": {"id": 1610612759, "name": "Spurs", "city": "San Antonio", "color": "#C4CED4"},
    "TOR": {"id": 1610612761, "name": "Raptors", "city": "Toronto", "color": "#CE1141"},
    "UTA": {"id": 1610612762, "name": "Jazz", "city": "Utah", "color": "#002B5C"},
    "WAS": {"id": 1610612764, "name": "Wizards", "city": "Washington", "color": "#002B5C"},
}

def init_db():
    """Create tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            team_id TEXT,
            team_abbreviation TEXT,
            team_name TEXT,
            position TEXT,
            height TEXT,
            weight TEXT,
            jersey_number TEXT,
            is_active INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            game_id TEXT NOT NULL,
            game_date DATE NOT NULL,
            season TEXT NOT NULL,
            team_abbreviation TEXT,
            opponent_abbreviation TEXT,
            is_home INTEGER,
            game_result TEXT,
            minutes_played REAL,
            points INTEGER DEFAULT 0,
            rebounds INTEGER DEFAULT 0,
            offensive_rebounds INTEGER DEFAULT 0,
            defensive_rebounds INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            steals INTEGER DEFAULT 0,
            blocks INTEGER DEFAULT 0,
            fg3m INTEGER DEFAULT 0,
            fg3a INTEGER DEFAULT 0,
            fgm INTEGER DEFAULT 0,
            fga INTEGER DEFAULT 0,
            ftm INTEGER DEFAULT 0,
            fta INTEGER DEFAULT 0,
            turnovers INTEGER DEFAULT 0,
            personal_fouls INTEGER DEFAULT 0,
            plus_minus INTEGER DEFAULT 0,
            UNIQUE(player_id, game_id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_player ON game_logs(player_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON game_logs(game_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_season ON game_logs(season)")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usage_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            player_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            action TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

def get_player_headshot_url(player_id: str) -> str:
    """Get NBA.com headshot URL for a player"""
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

def get_team_logo_url(team_abbr: str) -> str:
    """Get NBA.com team logo URL"""
    team_info = TEAM_INFO.get(team_abbr)
    if team_info:
        return f"https://cdn.nba.com/logos/nba/{team_info['id']}/primary/L/logo.svg"
    return ""

def sync_all_players():
    """Sync all active NBA players to database"""
    try:
        all_players = players.get_active_players()
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        count = 0
        for player in all_players:
            cursor.execute("""
                INSERT OR REPLACE INTO players 
                (player_id, full_name, first_name, last_name, is_active, updated_at)
                VALUES (?, ?, ?, ?, 1, datetime('now'))
            """, (
                str(player['id']),
                player['full_name'],
                player['first_name'],
                player['last_name']
            ))
            count += 1
        
        conn.commit()
        conn.close()
        print(f"✅ Synced {count} active players")
        return count
    except Exception as e:
        print(f"❌ Error syncing players: {e}")
        return 0

def fetch_player_details(player_id: str):
    """Fetch detailed player info from NBA API"""
    try:
        time.sleep(0.6)  # Rate limiting
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        data = info.get_dict()
        
        if data['resultSets'] and data['resultSets'][0]['rowSet']:
            row = data['resultSets'][0]['rowSet'][0]
            headers = data['resultSets'][0]['headers']
            
            player_data = dict(zip(headers, row))
            
            # Update database
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE players SET
                    team_id = ?,
                    team_abbreviation = ?,
                    team_name = ?,
                    position = ?,
                    height = ?,
                    weight = ?,
                    jersey_number = ?,
                    updated_at = datetime('now')
                WHERE player_id = ?
            """, (
                str(player_data.get('TEAM_ID', '')),
                player_data.get('TEAM_ABBREVIATION', ''),
                player_data.get('TEAM_NAME', ''),
                player_data.get('POSITION', ''),
                player_data.get('HEIGHT', ''),
                player_data.get('WEIGHT', ''),
                player_data.get('JERSEY', ''),
                player_id
            ))
            conn.commit()
            conn.close()
            
            return player_data
    except Exception as e:
        print(f"Error fetching player details: {e}")
    return None

def fetch_player_game_logs(player_id: str, season: str = "2024-25"):
    """Fetch game logs for a player using nba_api"""
    try:
        time.sleep(0.6)  # Rate limiting
        
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        )
        
        data = gamelog.get_dict()
        
        if not data['resultSets'] or not data['resultSets'][0]['rowSet']:
            return 0
        
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        games_stored = 0
        for row in rows:
            game = dict(zip(headers, row))
            
            matchup = game.get('MATCHUP', '')
            is_home = 1 if 'vs.' in matchup else 0
            parts = matchup.split()
            opponent = parts[-1] if parts else ''
            team = parts[0] if parts else ''
            
            # Parse minutes
            minutes_str = str(game.get('MIN', '0'))
            minutes = 0.0
            if minutes_str and minutes_str != 'None':
                if ':' in minutes_str:
                    m_parts = minutes_str.split(':')
                    minutes = float(m_parts[0]) + float(m_parts[1]) / 60.0
                else:
                    try:
                        minutes = float(minutes_str)
                    except:
                        minutes = 0.0
            
            cursor.execute("""
                INSERT OR REPLACE INTO game_logs 
                (player_id, game_id, game_date, season, team_abbreviation, 
                 opponent_abbreviation, is_home, game_result, minutes_played,
                 points, rebounds, offensive_rebounds, defensive_rebounds,
                 assists, steals, blocks, fg3m, fg3a, fgm, fga, ftm, fta,
                 turnovers, personal_fouls, plus_minus)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(player_id),
                game.get('Game_ID', ''),
                game.get('GAME_DATE', ''),
                season,
                team,
                opponent,
                is_home,
                game.get('WL', ''),
                minutes,
                game.get('PTS', 0) or 0,
                game.get('REB', 0) or 0,
                game.get('OREB', 0) or 0,
                game.get('DREB', 0) or 0,
                game.get('AST', 0) or 0,
                game.get('STL', 0) or 0,
                game.get('BLK', 0) or 0,
                game.get('FG3M', 0) or 0,
                game.get('FG3A', 0) or 0,
                game.get('FGM', 0) or 0,
                game.get('FGA', 0) or 0,
                game.get('FTM', 0) or 0,
                game.get('FTA', 0) or 0,
                game.get('TOV', 0) or 0,
                game.get('PF', 0) or 0,
                game.get('PLUS_MINUS', 0) or 0
            ))
            games_stored += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ Stored {games_stored} games for player {player_id}")
        return games_stored
        
    except Exception as e:
        print(f"❌ Error fetching game logs for {player_id}: {e}")
        return 0

def track_usage(ip: str, player_id: str, action: str):
    """Track user actions"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO usage_tracking (ip_address, player_id, action)
        VALUES (?, ?, ?)
    """, (ip, player_id, action))
    conn.commit()
    conn.close()

def get_usage_count(ip: str, hours: int = 24):
    """Get usage count for IP in last N hours"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT player_id) FROM usage_tracking
        WHERE ip_address = ?
        AND timestamp > datetime('now', '-' || ? || ' hours')
        AND action = 'analysis'
    """, (ip, hours))
    count = cursor.fetchone()[0]
    conn.close()
    return count

# =====================
# API ENDPOINTS
# =====================

@app.get("/")
def root():
    return {
        "status": "live",
        "message": "PropStats API v2.0 🏀",
        "version": "2.0.0",
        "features": [
            "Real-time NBA stats via nba_api",
            "Player headshots",
            "Team logos",
            "Multi-season support",
            "Enhanced stat categories"
        ]
    }

@app.get("/health")
def health():
    """Health check endpoint"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM players WHERE is_active = 1")
    players_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_logs")
    games_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM game_logs")
    players_with_data = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "status": "healthy",
        "players": players_count,
        "players_with_data": players_with_data,
        "games": games_count,
        "version": "2.0.0"
    }

@app.get("/players/search")
def search_players(q: str = Query(..., min_length=2)):
    """Search for players by name"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, full_name, team_abbreviation, position, jersey_number
        FROM players
        WHERE full_name LIKE ? AND is_active = 1
        ORDER BY full_name
        LIMIT 15
    """, (f"%{q}%",))
    
    player_list = []
    for row in cursor.fetchall():
        player_id = row[0]
        team_abbr = row[2] or "FA"
        team_info = TEAM_INFO.get(team_abbr, {})
        
        player_list.append({
            "id": player_id,
            "name": row[1],
            "team": team_abbr,
            "team_name": team_info.get("name", "Free Agent"),
            "team_color": team_info.get("color", "#666666"),
            "position": row[3] or "N/A",
            "jersey": row[4] or "",
            "headshot": get_player_headshot_url(player_id),
            "team_logo": get_team_logo_url(team_abbr) if team_abbr != "FA" else ""
        })
    
    conn.close()
    return {"players": player_list, "count": len(player_list)}

@app.get("/players/{player_id}")
def get_player_info(player_id: str):
    """Get detailed player information"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT player_id, full_name, team_abbreviation, team_name, position,
               height, weight, jersey_number
        FROM players WHERE player_id = ?
    """, (player_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        # Try to find in static data and sync
        all_players = players.get_active_players()
        player_match = next((p for p in all_players if str(p['id']) == player_id), None)
        
        if player_match:
            # Sync this player
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO players (player_id, full_name, first_name, last_name, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (player_id, player_match['full_name'], player_match['first_name'], player_match['last_name']))
            conn.commit()
            conn.close()
            
            # Fetch additional details
            fetch_player_details(player_id)
            
            return get_player_info(player_id)
        
        raise HTTPException(status_code=404, detail="Player not found")
    
    team_abbr = row[2] or "FA"
    team_info = TEAM_INFO.get(team_abbr, {})
    
    return {
        "id": row[0],
        "name": row[1],
        "team": team_abbr,
        "team_name": row[3] or team_info.get("name", "Free Agent"),
        "team_color": team_info.get("color", "#666666"),
        "position": row[4] or "N/A",
        "height": row[5] or "",
        "weight": row[6] or "",
        "jersey": row[7] or "",
        "headshot": get_player_headshot_url(player_id),
        "team_logo": get_team_logo_url(team_abbr)
    }

@app.get("/players/{player_id}/analysis")
def get_player_analysis(
    request: Request,
    player_id: str,
    stat: str = Query(..., regex="^(points|rebounds|assists|threes|steals|blocks|pra|pr|pa|ra|turnovers|double_double)$"),
    line: float = Query(..., ge=0),
    season: str = Query(default="2024-25")
):
    """Get player analysis with hit rates for a specific stat and line"""
    
    # Map stat names to database columns / calculations
    stat_map = {
        "points": "points",
        "rebounds": "rebounds",
        "assists": "assists",
        "threes": "fg3m",
        "steals": "steals",
        "blocks": "blocks",
        "turnovers": "turnovers",
        "pra": "(points + rebounds + assists)",
        "pr": "(points + rebounds)",
        "pa": "(points + assists)",
        "ra": "(rebounds + assists)",
        "double_double": None  # Special handling
    }
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if we have recent data for this player
    cursor.execute("""
        SELECT COUNT(*), MAX(game_date) FROM game_logs 
        WHERE player_id = ? AND season = ?
    """, (player_id, season))
    result = cursor.fetchone()
    game_count = result[0]
    last_game = result[1]
    
    # Fetch fresh data if needed (no data or data is old)
    needs_refresh = False
    if game_count == 0:
        needs_refresh = True
    elif last_game:
        last_date = datetime.strptime(last_game, "%b %d, %Y") if ", " in last_game else datetime.strptime(last_game, "%Y-%m-%d")
        if (datetime.now() - last_date).days > 1:
            needs_refresh = True
    
    if needs_refresh:
        print(f"📊 Fetching fresh data for player {player_id}...")
        fetch_player_game_logs(player_id, season)
        # Also try previous season for more data
        prev_season = f"{int(season[:4])-1}-{int(season[:4])%100:02d}"
        fetch_player_game_logs(player_id, prev_season)
    
    # Get player info
    cursor.execute("""
        SELECT full_name, team_abbreviation, position, jersey_number
        FROM players WHERE player_id = ?
    """, (player_id,))
    player_info = cursor.fetchone()
    
    if not player_info:
        # Try to sync player
        all_players = players.get_active_players()
        player_match = next((p for p in all_players if str(p['id']) == player_id), None)
        if player_match:
            cursor.execute("""
                INSERT OR REPLACE INTO players (player_id, full_name, is_active)
                VALUES (?, ?, 1)
            """, (player_id, player_match['full_name']))
            conn.commit()
            player_info = (player_match['full_name'], 'FA', 'N/A', '')
        else:
            conn.close()
            raise HTTPException(status_code=404, detail="Player not found")
    
    # Build query based on stat type
    if stat == "double_double":
        # Count games with 2+ categories >= 10
        select_expr = """
            (CASE WHEN points >= 10 THEN 1 ELSE 0 END +
             CASE WHEN rebounds >= 10 THEN 1 ELSE 0 END +
             CASE WHEN assists >= 10 THEN 1 ELSE 0 END +
             CASE WHEN steals >= 10 THEN 1 ELSE 0 END +
             CASE WHEN blocks >= 10 THEN 1 ELSE 0 END)
        """
        line = 2  # Need at least 2 categories at 10+
    else:
        select_expr = stat_map[stat]
    
    # Get all games for this player (current + previous season for more data)
    cursor.execute(f"""
        SELECT 
            game_date,
            opponent_abbreviation,
            {select_expr} as stat_value,
            is_home,
            game_result,
            minutes_played,
            points,
            rebounds,
            assists,
            fg3m,
            steals,
            blocks,
            turnovers,
            season
        FROM game_logs
        WHERE player_id = ?
        ORDER BY game_date DESC
        LIMIT 50
    """, (player_id,))
    
    games = []
    all_values = []
    current_season_values = []
    
    for row in cursor.fetchall():
        value = row[2] if row[2] is not None else 0
        all_values.append(value)
        
        game_season = row[13]
        if game_season == season:
            current_season_values.append(value)
        
        games.append({
            "date": row[0],
            "opponent": row[1],
            "value": value,
            "hit": value > line,
            "is_home": row[3] == 1,
            "result": row[4],
            "minutes": round(row[5], 1) if row[5] else 0,
            "pts": row[6] or 0,
            "reb": row[7] or 0,
            "ast": row[8] or 0,
            "fg3m": row[9] or 0,
            "stl": row[10] or 0,
            "blk": row[11] or 0,
            "tov": row[12] or 0,
            "season": game_season
        })
    
    conn.close()
    
    # Calculate hit rates
    def calc_hit_rate(games_list):
        if not games_list:
            return {"hits": 0, "total": 0, "pct": 0}
        hits = sum(1 for g in games_list if g["hit"])
        return {
            "hits": hits,
            "total": len(games_list),
            "pct": round((hits / len(games_list)) * 100, 1)
        }
    
    # Calculate home/away splits
    home_games = [g for g in games if g["is_home"]]
    away_games = [g for g in games if not g["is_home"]]
    
    # Current season games only
    current_season_games = [g for g in games if g["season"] == season]
    
    # Calculate averages
    season_avg = round(sum(current_season_values) / len(current_season_values), 1) if current_season_values else 0.0
    l5_avg = round(sum(all_values[:5]) / min(5, len(all_values)), 1) if all_values else 0.0
    l10_avg = round(sum(all_values[:10]) / min(10, len(all_values)), 1) if all_values else 0.0
    
    # Calculate variance/consistency score
    if len(all_values) >= 5:
        import statistics
        std_dev = statistics.stdev(all_values[:10]) if len(all_values) >= 10 else statistics.stdev(all_values)
        consistency = max(0, 100 - (std_dev / max(1, l10_avg) * 100))
    else:
        consistency = 50
    
    # Track usage
    client_ip = request.client.host if request.client else "unknown"
    track_usage(client_ip, player_id, "analysis")
    
    team_abbr = player_info[1] or "FA"
    team_info = TEAM_INFO.get(team_abbr, {})
    
    return {
        "player": {
            "id": player_id,
            "name": player_info[0],
            "team": team_abbr,
            "team_name": team_info.get("name", "Free Agent"),
            "team_color": team_info.get("color", "#666666"),
            "position": player_info[2] or "N/A",
            "jersey": player_info[3] or "",
            "headshot": get_player_headshot_url(player_id),
            "team_logo": get_team_logo_url(team_abbr)
        },
        "stat": stat,
        "line": line,
        "season": season,
        "averages": {
            "season": season_avg,
            "l5": l5_avg,
            "l10": l10_avg,
            "career": round(sum(all_values) / len(all_values), 1) if all_values else 0
        },
        "games": games[:30],  # Return last 30 games
        "hit_rates": {
            "season": calc_hit_rate(current_season_games),
            "l5": calc_hit_rate(games[:5]),
            "l10": calc_hit_rate(games[:10]),
            "l20": calc_hit_rate(games[:20]),
            "home": calc_hit_rate(home_games[:15]),
            "away": calc_hit_rate(away_games[:15])
        },
        "metrics": {
            "consistency": round(consistency, 1),
            "trend": "up" if l5_avg > l10_avg else "down" if l5_avg < l10_avg else "stable",
            "games_played": len(current_season_games)
        },
        "recommendation": get_recommendation(
            calc_hit_rate(games[:10])["pct"], 
            season_avg, 
            line,
            consistency
        )
    }

def get_recommendation(hit_rate: float, avg: float, line: float, consistency: float):
    """Generate recommendation based on hit rate, average, and consistency"""
    diff = avg - line
    diff_pct = (diff / line * 100) if line > 0 else 0
    
    # Calculate confidence based on hit rate, margin, and consistency
    score = (hit_rate * 0.5) + (min(diff_pct, 30) * 0.3) + (consistency * 0.2)
    
    if hit_rate >= 70 and diff > 0:
        return {
            "verdict": "STRONG OVER",
            "confidence": "high",
            "score": min(95, round(score)),
            "color": "#10b981"
        }
    elif hit_rate >= 60 and diff > 0:
        return {
            "verdict": "LEAN OVER",
            "confidence": "medium",
            "score": min(80, round(score)),
            "color": "#84cc16"
        }
    elif hit_rate <= 30 and diff < 0:
        return {
            "verdict": "STRONG UNDER",
            "confidence": "high",
            "score": min(95, round(100 - score)),
            "color": "#ef4444"
        }
    elif hit_rate <= 40 and diff < 0:
        return {
            "verdict": "LEAN UNDER",
            "confidence": "medium",
            "score": min(80, round(100 - score)),
            "color": "#f97316"
        }
    else:
        return {
            "verdict": "TOSS UP",
            "confidence": "low",
            "score": 50,
            "color": "#6b7280"
        }

@app.get("/teams")
def get_all_teams():
    """Get all NBA teams with logos and colors"""
    team_list = []
    for abbr, info in TEAM_INFO.items():
        team_list.append({
            "abbreviation": abbr,
            "id": info["id"],
            "name": info["name"],
            "city": info["city"],
            "full_name": f"{info['city']} {info['name']}",
            "color": info["color"],
            "logo": get_team_logo_url(abbr)
        })
    return {"teams": sorted(team_list, key=lambda x: x["city"])}

@app.get("/usage/check")
def check_usage(ip: str):
    """Check if user has exceeded free tier limits"""
    count = get_usage_count(ip, hours=24)
    FREE_LIMIT = int(os.getenv("FREE_TIER_LIMIT", "50"))
    
    return {
        "used": count,
        "limit": FREE_LIMIT,
        "remaining": max(0, FREE_LIMIT - count),
        "exceeded": count >= FREE_LIMIT,
        "reset_hours": 24
    }

# =====================
# ADMIN ENDPOINTS
# =====================

@app.post("/admin/sync-players")
def sync_players_endpoint(secret: str = Query(...)):
    """Sync all NBA players"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    count = sync_all_players()
    return {"success": count > 0, "players_synced": count}

@app.post("/admin/sync-player/{player_id}")
def sync_single_player(player_id: str, secret: str = Query(...)):
    """Sync specific player's game log"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    # Fetch player details
    fetch_player_details(player_id)
    
    # Fetch game logs for current and previous season
    games_current = fetch_player_game_logs(player_id, "2024-25")
    games_prev = fetch_player_game_logs(player_id, "2023-24")
    
    return {
        "success": games_current > 0 or games_prev > 0,
        "player_id": player_id,
        "games_synced": {
            "2024-25": games_current,
            "2023-24": games_prev
        }
    }

@app.get("/admin/stats")
def admin_stats(secret: str = Query(...)):
    """Get database stats"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM players WHERE is_active = 1")
    total_players = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM game_logs")
    total_games = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT player_id) FROM game_logs")
    players_with_data = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(DISTINCT ip_address) FROM usage_tracking 
        WHERE timestamp > datetime('now', '-24 hours')
    """)
    daily_users = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM usage_tracking 
        WHERE timestamp > datetime('now', '-24 hours')
    """)
    daily_requests = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        "total_players": total_players,
        "players_with_data": players_with_data,
        "total_games": total_games,
        "daily_users": daily_users,
        "daily_requests": daily_requests
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
