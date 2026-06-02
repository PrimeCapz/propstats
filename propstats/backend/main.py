"""
PropStats API v3.0 - NBA Props + Baseball Analysis
"""

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime, timedelta
import time

# NBA API imports
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog, commonplayerinfo

# Baseball engine
from baseball_engine import (
    get_today_games,
    get_full_game_analysis,
    get_pitcher_season_stats,
    get_pitcher_splits,
    get_pitcher_recent_starts,
    get_pitch_arsenal,
    get_batter_season_stats,
    get_batter_splits,
    get_batter_vs_pitcher,
    get_game_lineups,
    get_weather_for_venue,
    get_ballpark_factors,
    search_mlb_players,
)
from odds_engine import (
    get_all_game_odds,
    get_batter_last_n,
    get_pitcher_last_n,
    analyze_pitcher_k_prop,
    analyze_batter_hit_prop,
    analyze_batter_hr_prop,
    analyze_total,
    build_prop_sheet,
    get_game_odds_by_espn_id,
    get_espn_game_map,
    get_meatball_matchups,
    get_blast_alerts,
    get_bat_speed_surges,
    build_hr_matchup_table,
    calc_hr_probability,
    calc_batter_power,
    calc_pitcher_vulnerability,
    calc_context_score,
    get_value_hr_picks,
    get_handedness_edge,
)
from baseball_engine import (
    get_batter_savant,
    get_pitcher_savant,
    get_today_savant_leaderboards,
)

app = FastAPI(title="PropStats API", version="3.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.getenv("DATABASE_PATH", "propstats.db")
CURRENT_SEASON = "2025-26"  # Current NBA season (Oct 2025 - June 2026)
REFRESH_HOURS = 6  # Refresh data if older than this

TEAM_INFO = {
    "ATL": {"name": "Hawks", "color": "#E03A3E"},
    "BOS": {"name": "Celtics", "color": "#007A33"},
    "BKN": {"name": "Nets", "color": "#000000"},
    "CHA": {"name": "Hornets", "color": "#1D1160"},
    "CHI": {"name": "Bulls", "color": "#CE1141"},
    "CLE": {"name": "Cavaliers", "color": "#860038"},
    "DAL": {"name": "Mavericks", "color": "#00538C"},
    "DEN": {"name": "Nuggets", "color": "#0E2240"},
    "DET": {"name": "Pistons", "color": "#C8102E"},
    "GSW": {"name": "Warriors", "color": "#1D428A"},
    "HOU": {"name": "Rockets", "color": "#CE1141"},
    "IND": {"name": "Pacers", "color": "#002D62"},
    "LAC": {"name": "Clippers", "color": "#C8102E"},
    "LAL": {"name": "Lakers", "color": "#552583"},
    "MEM": {"name": "Grizzlies", "color": "#5D76A9"},
    "MIA": {"name": "Heat", "color": "#98002E"},
    "MIL": {"name": "Bucks", "color": "#00471B"},
    "MIN": {"name": "Timberwolves", "color": "#0C2340"},
    "NOP": {"name": "Pelicans", "color": "#0C2340"},
    "NYK": {"name": "Knicks", "color": "#006BB6"},
    "OKC": {"name": "Thunder", "color": "#007AC1"},
    "ORL": {"name": "Magic", "color": "#0077C0"},
    "PHI": {"name": "76ers", "color": "#006BB6"},
    "PHX": {"name": "Suns", "color": "#1D1160"},
    "POR": {"name": "Trail Blazers", "color": "#E03A3E"},
    "SAC": {"name": "Kings", "color": "#5A2D81"},
    "SAS": {"name": "Spurs", "color": "#C4CED4"},
    "TOR": {"name": "Raptors", "color": "#CE1141"},
    "UTA": {"name": "Jazz", "color": "#002B5C"},
    "WAS": {"name": "Wizards", "color": "#002B5C"},
}

def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS players (
            player_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            team TEXT,
            position TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS game_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id TEXT NOT NULL,
            game_id TEXT,
            game_date TEXT,
            opponent TEXT,
            is_home INTEGER,
            result TEXT,
            minutes REAL,
            points INTEGER,
            rebounds INTEGER,
            assists INTEGER,
            steals INTEGER,
            blocks INTEGER,
            fg3m INTEGER,
            turnovers INTEGER,
            season TEXT,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(player_id, game_id)
        )
    """)
    
    c.execute("CREATE INDEX IF NOT EXISTS idx_player_season ON game_logs(player_id, season)")
    conn.commit()
    conn.close()

init_db()

def get_headshot(player_id: str) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

def fetch_player_games(player_id: str) -> int:
    """Fetch current season games from NBA API"""
    try:
        time.sleep(0.6)  # Rate limit
        
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=CURRENT_SEASON,
            season_type_all_star='Regular Season'
        )
        
        data = gamelog.get_dict()
        
        if not data.get('resultSets') or not data['resultSets'][0].get('rowSet'):
            print(f"No games found for player {player_id} in {CURRENT_SEASON}")
            return 0
        
        headers = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Clear old data for this player/season and re-fetch
        c.execute("DELETE FROM game_logs WHERE player_id = ? AND season = ?", (player_id, CURRENT_SEASON))
        
        count = 0
        for row in rows:
            game = dict(zip(headers, row))
            
            matchup = game.get('MATCHUP', '')
            is_home = 1 if 'vs.' in matchup else 0
            opponent = matchup.split()[-1] if matchup else ''
            
            # Parse minutes
            mins = 0
            min_str = str(game.get('MIN', '0'))
            if min_str and min_str != 'None':
                if ':' in min_str:
                    parts = min_str.split(':')
                    mins = int(parts[0]) + int(parts[1]) / 60
                else:
                    try:
                        mins = float(min_str)
                    except:
                        mins = 0
            
            c.execute("""
                INSERT OR REPLACE INTO game_logs 
                (player_id, game_id, game_date, opponent, is_home, result, minutes,
                 points, rebounds, assists, steals, blocks, fg3m, turnovers, season, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                player_id,
                game.get('Game_ID', ''),
                game.get('GAME_DATE', ''),
                opponent,
                is_home,
                game.get('WL', ''),
                round(mins, 1),
                game.get('PTS', 0) or 0,
                game.get('REB', 0) or 0,
                game.get('AST', 0) or 0,
                game.get('STL', 0) or 0,
                game.get('BLK', 0) or 0,
                game.get('FG3M', 0) or 0,
                game.get('TOV', 0) or 0,
                CURRENT_SEASON
            ))
            count += 1
        
        conn.commit()
        conn.close()
        print(f"✅ Fetched {count} games for player {player_id} ({CURRENT_SEASON})")
        return count
        
    except Exception as e:
        print(f"❌ Error fetching games: {e}")
        return 0

def needs_refresh(player_id: str) -> bool:
    """Check if player data needs refreshing"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        SELECT fetched_at FROM game_logs 
        WHERE player_id = ? AND season = ?
        ORDER BY fetched_at DESC LIMIT 1
    """, (player_id, CURRENT_SEASON))
    
    row = c.fetchone()
    conn.close()
    
    if not row:
        return True
    
    try:
        fetched = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        age_hours = (datetime.now() - fetched).total_seconds() / 3600
        return age_hours > REFRESH_HOURS
    except:
        return True

@app.get("/")
def root():
    return {"status": "ok", "season": CURRENT_SEASON, "version": "3.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "season": CURRENT_SEASON, "refresh_hours": REFRESH_HOURS}

@app.get("/players/search")
def search_players(q: str = Query(..., min_length=2)):
    """Search for players"""
    all_players = players.get_active_players()
    
    matches = [p for p in all_players if q.lower() in p['full_name'].lower()][:15]
    
    return {
        "players": [
            {
                "id": str(p['id']),
                "name": p['full_name'],
                "team": p.get('team_abbreviation', 'FA') or 'FA',
                "position": "",
                "headshot": get_headshot(p['id'])
            }
            for p in matches
        ]
    }

@app.get("/players/{player_id}/analysis")
def get_analysis(
    player_id: str,
    stat: str = Query(..., regex="^(points|rebounds|assists|threes|steals|blocks|pra)$"),
    line: float = Query(..., ge=0)
):
    """Get player analysis for a specific stat and line - 2025-26 season only"""
    
    # Check if we need fresh data
    if needs_refresh(player_id):
        print(f"🔄 Refreshing data for {player_id} ({CURRENT_SEASON})...")
        fetch_player_games(player_id)
    
    # Map stat to column
    stat_map = {
        "points": "points",
        "rebounds": "rebounds", 
        "assists": "assists",
        "threes": "fg3m",
        "steals": "steals",
        "blocks": "blocks",
        "pra": "(points + rebounds + assists)"
    }
    
    stat_col = stat_map.get(stat, "points")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get games for 2025-26 season ONLY
    c.execute(f"""
        SELECT 
            game_date,
            opponent,
            {stat_col} as value,
            is_home,
            result,
            minutes,
            points,
            rebounds,
            assists,
            fg3m,
            steals,
            blocks
        FROM game_logs
        WHERE player_id = ? AND season = ?
        ORDER BY game_date DESC
        LIMIT 30
    """, (player_id, CURRENT_SEASON))
    
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        return {
            "player_id": player_id,
            "stat": stat,
            "line": line,
            "season": CURRENT_SEASON,
            "games": [],
            "message": f"No games found for {CURRENT_SEASON} season. Data refreshes every {REFRESH_HOURS} hours."
        }
    
    games = []
    for row in rows:
        value = row[2] if row[2] is not None else 0
        games.append({
            "date": row[0],
            "opponent": row[1],
            "value": value,
            "is_home": bool(row[3]),
            "result": row[4],
            "minutes": row[5],
            "hit": value > line
        })
    
    # Calculate stats
    values = [g['value'] for g in games]
    avg = sum(values) / len(values) if values else 0
    
    def hit_rate(game_list):
        if not game_list:
            return {"hits": 0, "total": 0, "pct": 0}
        hits = sum(1 for g in game_list if g['hit'])
        return {"hits": hits, "total": len(game_list), "pct": round(hits / len(game_list) * 100)}
    
    return {
        "player_id": player_id,
        "stat": stat,
        "line": line,
        "season": CURRENT_SEASON,
        "games": games,
        "averages": {
            "season": round(avg, 1),
            "l5": round(sum(values[:5]) / min(5, len(values)), 1) if values else 0,
            "l10": round(sum(values[:10]) / min(10, len(values)), 1) if values else 0
        },
        "hit_rates": {
            "l5": hit_rate(games[:5]),
            "l10": hit_rate(games[:10]),
            "l20": hit_rate(games[:20]),
            "home": hit_rate([g for g in games if g['is_home']]),
            "away": hit_rate([g for g in games if not g['is_home']])
        }
    }

@app.post("/admin/sync-players")
def sync_players(secret: str = Query(...)):
    """Sync all active players (admin only)"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    all_players = players.get_active_players()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    count = 0
    for p in all_players:
        c.execute("""
            INSERT OR REPLACE INTO players (player_id, full_name, updated_at)
            VALUES (?, ?, datetime('now'))
        """, (str(p['id']), p['full_name']))
        count += 1
    
    conn.commit()
    conn.close()
    
    return {"synced": count, "season": CURRENT_SEASON}

@app.post("/admin/refresh-player/{player_id}")
def refresh_player(player_id: str, secret: str = Query(...)):
    """Force refresh a player's data"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    count = fetch_player_games(player_id)
    return {"player_id": player_id, "games_fetched": count, "season": CURRENT_SEASON}

@app.delete("/admin/clear-cache")
def clear_cache(secret: str = Query(...)):
    """Clear all cached game data to force refresh"""
    if secret != os.getenv("ADMIN_SECRET", "propstats2024"):
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM game_logs")
    conn.commit()
    conn.close()
    
    return {"status": "cache_cleared", "season": CURRENT_SEASON}

# ─────────────────────────────────────────────
#  BASEBALL ROUTES
# ─────────────────────────────────────────────

@app.get("/baseball/games")
def baseball_games(date: str = Query(None, description="YYYY-MM-DD, defaults to today")):
    """All MLB games for a date with probable pitchers."""
    games = get_today_games(date)
    return {"games": games, "count": len(games), "date": date or "today"}


@app.get("/baseball/game/{game_pk}/analysis")
def baseball_game_analysis(game_pk: int):
    """Full deep-dive analysis: pitchers, lineups, H2H matchups, weather, park factors."""
    result = get_full_game_analysis(game_pk)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@app.get("/baseball/game/{game_pk}/lineups")
def baseball_lineups(game_pk: int):
    """Confirmed/probable lineups for a game."""
    return get_game_lineups(game_pk)


@app.get("/baseball/pitcher/{pitcher_id}/profile")
def baseball_pitcher_profile(pitcher_id: int, season: int = Query(None)):
    """Pitcher profile: season stats, pitch arsenal, splits, recent starts."""
    stats = get_pitcher_season_stats(pitcher_id, season)
    if not stats:
        raise HTTPException(status_code=404, detail="Pitcher not found")
    arsenal = get_pitch_arsenal(pitcher_id, season)
    splits = get_pitcher_splits(pitcher_id, season)
    recent = get_pitcher_recent_starts(pitcher_id, season)
    return {
        "pitcher_id": pitcher_id,
        "profile": stats,
        "arsenal": arsenal,
        "splits": splits,
        "recent_starts": recent,
    }


@app.get("/baseball/batter/{batter_id}/profile")
def baseball_batter_profile(batter_id: int, season: int = Query(None)):
    """Batter profile: season stats + splits."""
    stats = get_batter_season_stats(batter_id, season)
    if not stats:
        raise HTTPException(status_code=404, detail="Batter not found")
    splits = get_batter_splits(batter_id, season)
    return {"batter_id": batter_id, "profile": stats, "splits": splits}


@app.get("/baseball/matchup")
def baseball_matchup(
    batter_id: int = Query(...),
    pitcher_id: int = Query(...),
    season: int = Query(None),
):
    """Head-to-head matchup: career + season H2H history."""
    batter = get_batter_season_stats(batter_id, season)
    pitcher = get_pitcher_season_stats(pitcher_id, season)
    h2h = get_batter_vs_pitcher(batter_id, pitcher_id, season)
    return {
        "batter": batter,
        "pitcher": pitcher,
        "h2h": h2h,
    }


@app.get("/baseball/players/search")
def baseball_search(
    q: str = Query(..., min_length=2),
    type: str = Query("all", regex="^(all|pitcher|batter)$"),
):
    """Search MLB players by name."""
    results = search_mlb_players(q, type)
    return {"players": results, "count": len(results)}


@app.get("/baseball/weather")
def baseball_weather(
    venue_id: int = Query(...),
    game_date: str = Query(..., description="YYYY-MM-DD"),
    game_time: str = Query(None, description="ISO datetime string"),
):
    """Weather forecast for a specific venue and date."""
    return get_weather_for_venue(venue_id, game_date, game_time)


@app.get("/baseball/park/{venue_name}")
def baseball_park_factors(venue_name: str):
    """Park factors for a venue."""
    return get_ballpark_factors(venue_name)


@app.get("/baseball/odds")
def baseball_odds(date: str = Query(None, description="YYYY-MM-DD, defaults to today")):
    """DraftKings lines (ML, run line, O/U) for all games via ESPN — no key required."""
    odds = get_all_game_odds(date)
    return {"odds": {f"{k[0]}@{k[1]}": v for k, v in odds.items()}, "date": date or "today"}


@app.get("/baseball/game/{game_pk}/odds")
def baseball_game_odds(game_pk: int, away: str = Query(...), home: str = Query(...),
                       date: str = Query(None)):
    """Odds for a single game by team abbreviations."""
    mapping = get_espn_game_map(date)
    espn_id = mapping.get((away.upper(), home.upper()))
    if not espn_id:
        raise HTTPException(status_code=404, detail="Game not found in ESPN odds")
    return get_game_odds_by_espn_id(espn_id)


@app.get("/baseball/game/{game_pk}/prop-sheet")
def baseball_prop_sheet(game_pk: int):
    """Full ranked prop sheet: K props, hit props, HR props, totals with lines & lean."""
    analysis = get_full_game_analysis(game_pk)
    if "error" in analysis:
        raise HTTPException(status_code=404, detail=analysis["error"])

    away_abbr = analysis.get("away_team", {}).get("abbr", "")
    home_abbr = analysis.get("home_team", {}).get("abbr", "")
    game_date = analysis.get("game_date", "")
    mapping = get_espn_game_map(game_date)
    espn_id = mapping.get((away_abbr, home_abbr))
    if espn_id:
        analysis["game_odds"] = get_game_odds_by_espn_id(espn_id)

    return build_prop_sheet(analysis)


@app.get("/baseball/batter/{batter_id}/last5")
def batter_last5(batter_id: int, season: int = Query(None)):
    """Last 5 games for a batter with AB, H, HR, RBI, BB, K, TB."""
    games = get_batter_last_n(batter_id, season, 5)
    return {"batter_id": batter_id, "games": games}


@app.get("/baseball/games/with-odds")
def games_with_odds(date: str = Query(None)):
    """Today's MLB schedule with live DraftKings lines embedded."""
    import time as _time
    games = get_today_games(date)
    odds_map = get_all_game_odds(date)

    for g in games:
        key = (g["away"]["team_abbr"].upper(), g["home"]["team_abbr"].upper())
        g["odds"] = odds_map.get(key, {})

    return {"games": games, "count": len(games), "date": date or "today"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# ── Advanced Statcast Routes ──────────────────────────────────────────────────

@app.get("/baseball/statcast/batter/{batter_id}")
def batter_statcast(batter_id: int, season: int = Query(None)):
    """Barrel%, xSLG, exit velo, bat speed, blast rate for a batter."""
    return {"batter_id": batter_id, "statcast": get_batter_savant(batter_id, season)}


@app.get("/baseball/statcast/pitcher/{pitcher_id}")
def pitcher_statcast(pitcher_id: int, season: int = Query(None)):
    """Hard contact / barrel% allowed for a pitcher."""
    return {"pitcher_id": pitcher_id, "statcast": get_pitcher_savant(pitcher_id, season)}


@app.get("/baseball/today/meatball-matchups")
def meatball_matchups(date: str = Query(None)):
    """Top xSLG matchups: power hitters vs hard-contact pitchers."""
    games = get_today_games(date)
    analyses = []
    for g in games:
        a = get_full_game_analysis(g["game_pk"])
        if "error" not in a:
            analyses.append(a)
    matchups = get_meatball_matchups(analyses)
    return {"matchups": matchups, "count": len(matchups)}


@app.get("/baseball/today/blast-alerts")
def blast_alerts_today(date: str = Query(None)):
    """Batters with high barrel/blast rates facing HR-prone pitchers."""
    games = get_today_games(date)
    analyses = []
    for g in games:
        a = get_full_game_analysis(g["game_pk"])
        if "error" not in a:
            analyses.append(a)
    alerts = get_blast_alerts(analyses)
    return {"alerts": alerts, "count": len(alerts)}


@app.get("/baseball/today/value-hr")
def value_hr_picks_today(
    date: str = Query(None),
    min_prob: float = Query(12.0, description="Min HR% to surface (default 12)"),
    max_prob: float = Query(21.0, description="Max HR% to surface (default 21)"),
):
    """
    Sleeper / value-tier HR bats: 12-21% probability range.
    These are the Bleday-type picks the top-10 leaderboard misses.
    Includes platoon edge flag and calibrated fair odds.
    """
    games = get_today_games(date)
    analyses = []
    for g in games:
        a = get_full_game_analysis(g["game_pk"])
        if "error" not in a:
            analyses.append(a)
    picks = get_value_hr_picks(analyses, min_prob / 100, max_prob / 100)
    return {"value_hr_picks": picks, "count": len(picks)}


@app.get("/baseball/today/bat-speed")
def bat_speed_today(date: str = Query(None)):
    """Fastest bats on today's slate."""
    games = get_today_games(date)
    analyses = []
    for g in games:
        a = get_full_game_analysis(g["game_pk"])
        if "error" not in a:
            analyses.append(a)
    surges = get_bat_speed_surges(analyses)
    return {"surges": surges, "count": len(surges)}


@app.get("/baseball/game/{game_pk}/hr-table")
def game_hr_table(game_pk: int):
    """Full HR matchup probability table for one game (like the screenshot grid)."""
    analysis = get_full_game_analysis(game_pk)
    if "error" in analysis:
        raise HTTPException(status_code=404, detail=analysis["error"])
    table = build_hr_matchup_table(analysis)
    return {
        "game_pk": game_pk,
        "away": analysis.get("away_team", {}),
        "home": analysis.get("home_team", {}),
        "venue": analysis.get("venue", {}),
        "weather": analysis.get("weather", {}),
        "park_factors": analysis.get("park_factors", {}),
        "table": table,
    }


@app.get("/baseball/today/hr-table")
def today_hr_table(date: str = Query(None)):
    """Full HR matchup table across all today's games."""
    import time as _t
    games = get_today_games(date)
    all_rows = []
    game_summaries = []
    for g in games:
        a = get_full_game_analysis(g["game_pk"])
        if "error" in a:
            continue
        rows = build_hr_matchup_table(a)
        game_summaries.append({
            "game_pk": g["game_pk"],
            "away": g["away"]["team_name"],
            "home": g["home"]["team_name"],
            "status": g["status"],
            "row_count": len(rows),
        })
        for r in rows:
            r["game_pk"] = g["game_pk"]
            r["away_team"] = g["away"]["team_name"]
            r["home_team"] = g["home"]["team_name"]
        all_rows.extend(rows)
        _t.sleep(0.2)
    all_rows.sort(key=lambda x: x["hr_prob_pct"], reverse=True)
    return {
        "rows": all_rows[:100],
        "games": game_summaries,
        "total": len(all_rows),
    }
