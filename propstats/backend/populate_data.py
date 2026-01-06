"""
PropStats Data Populator
Run this to populate your database with NBA player data
"""

import requests
import time
import sqlite3
from datetime import datetime

DB_PATH = "nba_props.db"

NBA_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.nba.com/',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Origin': 'https://www.nba.com',
    'Host': 'stats.nba.com',
    'Connection': 'keep-alive',
}

def init_database():
    """Create database tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            team_abbreviation TEXT,
            position TEXT,
            is_active INTEGER DEFAULT 1
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
            points INTEGER,
            total_rebounds INTEGER,
            assists INTEGER,
            steals INTEGER,
            blocks INTEGER,
            fg3m INTEGER,
            turnovers INTEGER DEFAULT 0,
            UNIQUE(player_id, game_id)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_player ON game_logs(player_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_date ON game_logs(game_date)")
    
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
    print("✅ Database initialized")

def fetch_all_players():
    """Fetch all NBA players"""
    url = "https://stats.nba.com/stats/commonallplayers"
    params = {
        'LeagueID': '00',
        'Season': '2024-25',
        'IsOnlyCurrentSeason': '1'
    }
    
    print("🔄 Fetching all NBA players...")
    
    try:
        response = requests.get(url, headers=NBA_HEADERS, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        players = []
        for player in data['resultSets'][0]['rowSet']:
            players.append({
                'id': str(player[0]),
                'name': player[2],
                'team': player[8] if len(player) > 8 else '',
                'position': ''
            })
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for player in players:
            cursor.execute("""
                INSERT OR REPLACE INTO players (player_id, full_name, team_abbreviation, position, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (player['id'], player['name'], player['team'], player['position']))
        
        conn.commit()
        conn.close()
        
        print(f"✅ Stored {len(players)} players")
        return players
        
    except Exception as e:
        print(f"❌ Error fetching players: {e}")
        return []

def fetch_player_game_log(player_id: str, player_name: str):
    """Fetch game log for a player"""
    url = "https://stats.nba.com/stats/playergamelog"
    params = {
        'PlayerID': player_id,
        'Season': '2024-25',
        'SeasonType': 'Regular Season'
    }
    
    try:
        response = requests.get(url, headers=NBA_HEADERS, params=params, timeout=15)
        time.sleep(0.7)  # Rate limiting - important!
        
        response.raise_for_status()
        data = response.json()
        
        if not data['resultSets'] or not data['resultSets'][0]['rowSet']:
            return 0
        
        headers_list = data['resultSets'][0]['headers']
        games = data['resultSets'][0]['rowSet']
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        for game in games:
            matchup = game[headers_list.index('MATCHUP')]
            is_home = 1 if 'vs.' in matchup else 0
            opponent = matchup.split()[-1]
            
            minutes_str = str(game[headers_list.index('MIN')])
            minutes = 0.0
            if minutes_str and minutes_str != 'None' and ':' in minutes_str:
                parts = minutes_str.split(':')
                minutes = float(parts[0]) + float(parts[1]) / 60.0
            
            cursor.execute("""
                INSERT OR REPLACE INTO game_logs 
                (player_id, game_id, game_date, season, team_abbreviation, 
                 opponent_abbreviation, is_home, game_result, minutes_played,
                 points, total_rebounds, assists, steals, blocks, fg3m, turnovers)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                player_id,
                game[headers_list.index('GAME_ID')],
                game[headers_list.index('GAME_DATE')],
                '2024-25',
                matchup.split()[0],
                opponent,
                is_home,
                game[headers_list.index('WL')],
                minutes,
                game[headers_list.index('PTS')] or 0,
                game[headers_list.index('REB')] or 0,
                game[headers_list.index('AST')] or 0,
                game[headers_list.index('STL')] or 0,
                game[headers_list.index('BLK')] or 0,
                game[headers_list.index('FG3M')] or 0,
                game[headers_list.index('TOV')] if 'TOV' in headers_list else 0
            ))
        
        conn.commit()
        conn.close()
        
        return len(games)
        
    except Exception as e:
        print(f"❌ Error for {player_name}: {e}")
        return 0

# Top 100 NBA players by popularity/usage for props
TOP_PLAYERS = [
    "LeBron James", "Stephen Curry", "Kevin Durant", "Giannis Antetokounmpo",
    "Luka Doncic", "Nikola Jokic", "Joel Embiid", "Jayson Tatum",
    "Anthony Davis", "Damian Lillard", "Jimmy Butler", "Devin Booker",
    "Ja Morant", "Trae Young", "Donovan Mitchell", "Anthony Edwards",
    "Shai Gilgeous-Alexander", "Tyrese Haliburton", "De'Aaron Fox", "LaMelo Ball",
    "Paolo Banchero", "Chet Holmgren", "Victor Wembanyama", "Jalen Brunson",
    "Tyrese Maxey", "Cade Cunningham", "Scottie Barnes", "Franz Wagner",
    "Jaylen Brown", "Bam Adebayo", "Karl-Anthony Towns", "Zion Williamson",
    "Brandon Ingram", "CJ McCollum", "Dejounte Murray", "Darius Garland",
    "Alperen Sengun", "Lauri Markkanen", "Desmond Bane", "Jaren Jackson Jr.",
    "Mikal Bridges", "Jalen Williams", "Josh Giddey", "Evan Mobley",
    "Kawhi Leonard", "Paul George", "Russell Westbrook", "Chris Paul",
    "Kyrie Irving", "James Harden"
]

def quick_populate():
    """Quick populate - Top 50 players for fast testing"""
    print("🚀 Quick populate - Top 50 players")
    print("=" * 50)
    
    init_database()
    players = fetch_all_players()
    
    if not players:
        print("❌ Failed to fetch players. Check your internet connection.")
        return
    
    # Find top players in the list
    top_player_ids = []
    for player in players:
        if any(name.lower() in player['name'].lower() for name in TOP_PLAYERS[:50]):
            top_player_ids.append(player)
    
    # If we couldn't match names, just take first 50
    if len(top_player_ids) < 30:
        top_player_ids = players[:50]
    
    print(f"📊 Fetching game logs for {len(top_player_ids)} players...")
    print("⏱️  This will take about 1-2 minutes...")
    print()
    
    total_games = 0
    for i, player in enumerate(top_player_ids[:50]):
        print(f"[{i+1:2d}/50] {player['name'][:25]:<25}", end=" ")
        games = fetch_player_game_log(player['id'], player['name'])
        total_games += games
        if games > 0:
            print(f"✅ {games} games")
        else:
            print("⚠️  No games yet")
    
    print()
    print("=" * 50)
    print(f"✅ Quick populate complete!")
    print(f"📊 {len(players)} players in database")
    print(f"🏀 {total_games} game logs stored")
    print()
    print("Run 'python main.py' to start the API server!")

def full_populate():
    """Full populate - All active players (takes longer)"""
    print("🚀 Full populate - All active players")
    print("⚠️  This will take 10-15 minutes!")
    print("=" * 50)
    
    init_database()
    players = fetch_all_players()
    
    if not players:
        print("❌ Failed to fetch players")
        return
    
    print(f"📊 Fetching game logs for {len(players)} players...")
    
    total_games = 0
    for i, player in enumerate(players):
        print(f"[{i+1:3d}/{len(players)}] {player['name'][:25]:<25}", end=" ")
        games = fetch_player_game_log(player['id'], player['name'])
        total_games += games
        if games > 0:
            print(f"✅ {games} games")
        else:
            print("⏭️  skipped")
    
    print()
    print("=" * 50)
    print(f"✅ Full populate complete!")
    print(f"📊 {len(players)} players")
    print(f"🏀 {total_games} game logs")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--quick":
            quick_populate()
        elif sys.argv[1] == "--full":
            full_populate()
        else:
            print("Usage:")
            print("  python populate_data.py --quick  # Top 50 players (~2 min)")
            print("  python populate_data.py --full   # All players (~15 min)")
    else:
        print("🏀 PropStats Data Populator")
        print()
        print("Usage:")
        print("  python populate_data.py --quick  # Top 50 players (~2 min)")
        print("  python populate_data.py --full   # All players (~15 min)")
        print()
        print("Starting quick populate by default...")
        print()
        quick_populate()
