"""
NBA Live Data Fetcher
Pulls real-time NBA data from NBA.com via nba_api
"""

from datetime import datetime, timedelta
import pandas as pd
from nba_api.stats.endpoints import (
    scoreboardv2,
    leaguegamefinder,
    teamgamelog,
    playergamelog,
    commonteamroster,
    leaguedashteamstats,
    leaguedashplayerstats,
    playerdashboardbygeneralsplits,
    leaguedashptdefend
)
from nba_api.stats.static import teams, players
import streamlit as st
from functools import lru_cache
import time

# Team abbreviation mapping (NBA API uses different abbrevs)
TEAM_ABB_MAP = {
    'ATL': 'ATL', 'BOS': 'BOS', 'BKN': 'BKN', 'CHA': 'CHA',
    'CHI': 'CHI', 'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN',
    'DET': 'DET', 'GSW': 'GS', 'HOU': 'HOU', 'IND': 'IND',
    'LAC': 'LAC', 'LAL': 'LAL', 'MEM': 'MEM', 'MIA': 'MIA',
    'MIL': 'MIL', 'MIN': 'MIN', 'NOP': 'NO', 'NYK': 'NY',
    'OKC': 'OKC', 'ORL': 'ORL', 'PHI': 'PHI', 'PHX': 'PHX',
    'POR': 'POR', 'SAC': 'SAC', 'SAS': 'SA', 'TOR': 'TOR',
    'UTA': 'UTA', 'WAS': 'WAS'
}

# Reverse mapping
ABB_TEAM_MAP = {v: k for k, v in TEAM_ABB_MAP.items()}

# Cache duration in seconds (15 minutes for most data)
CACHE_DURATION = 900

@st.cache_data(ttl=CACHE_DURATION)
def get_todays_games():
    """Fetch today's NBA games with actual schedules"""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        scoreboard = scoreboardv2.ScoreboardV2(game_date=today)
        games_data = scoreboard.get_data_frames()[0]

        if games_data.empty:
            return []

        games = []
        processed_game_ids = set()

        for _, row in games_data.iterrows():
            game_id = row['GAME_ID']

            # Skip if we've already processed this game
            if game_id in processed_game_ids:
                continue
            processed_game_ids.add(game_id)

            # Determine home/away
            away_team_id = row['VISITOR_TEAM_ID'] if 'VISITOR_TEAM_ID' in row else row['HOME_TEAM_ID']
            home_team_id = row['HOME_TEAM_ID']

            away_abbrev = get_team_abbreviation(away_team_id)
            home_abbrev = get_team_abbreviation(home_team_id)

            # Parse game time
            game_time = row.get('GAME_STATUS_TEXT', 'TBD')

            games.append({
                'game_id': game_id,
                'away_team': away_abbrev,
                'home_team': home_abbrev,
                'time': game_time,
                'away_team_id': away_team_id,
                'home_team_id': home_team_id
            })

        return games

    except Exception as e:
        print(f"Error fetching today's games: {e}")
        return []

@st.cache_data(ttl=CACHE_DURATION)
def get_team_abbreviation(team_id):
    """Get team abbreviation from team ID"""
    all_teams = teams.get_teams()
    for team in all_teams:
        if team['id'] == team_id:
            abbrev = team['abbreviation']
            return ABB_TEAM_MAP.get(abbrev, abbrev)
    return 'UNK'

@st.cache_data(ttl=3600)  # Cache team stats for 1 hour
def get_team_stats():
    """Fetch current season team statistics"""
    try:
        # Get basic team stats (PPG)
        team_stats_basic = leaguedashteamstats.LeagueDashTeamStats(
            season='2024-25',
            per_mode_detailed='PerGame'
        )
        df_basic = team_stats_basic.get_data_frames()[0]

        # Get advanced stats (PACE, OFF_RATING, DEF_RATING)
        team_stats_advanced = leaguedashteamstats.LeagueDashTeamStats(
            season='2024-25',
            measure_type_detailed_defense='Advanced'
        )
        df_advanced = team_stats_advanced.get_data_frames()[0]

        # Merge dataframes on TEAM_ID
        df = pd.merge(df_basic, df_advanced, on='TEAM_ID', suffixes=('', '_adv'))

        # Calculate ranks
        df['OFF_RANK'] = df['OFF_RATING'].rank(ascending=False).astype(int)
        df['DEF_RANK'] = df['DEF_RATING'].rank(ascending=True).astype(int)

        stats_dict = {}
        for _, row in df.iterrows():
            team_abbrev = get_team_abbreviation(row['TEAM_ID'])
            stats_dict[team_abbrev] = {
                'ppg': round(row['PTS'], 1),
                'pace': round(row['PACE'], 1),
                'off_rank': int(row['OFF_RANK']),
                'def_rank': int(row['DEF_RANK']),
                'pg_def_rank': int(row['DEF_RANK'])  # Simplified for now
            }

        return stats_dict

    except Exception as e:
        print(f"Error fetching team stats: {e}")
        return {}

@st.cache_data(ttl=3600)
def get_team_roster(team_id):
    """Fetch current roster for a team"""
    try:
        roster = commonteamroster.CommonTeamRoster(team_id=team_id)
        df = roster.get_data_frames()[0]

        players_list = []
        for _, row in df.iterrows():
            players_list.append({
                'id': str(row['PLAYER_ID']),
                'name': row['PLAYER'],
                'pos': row['POSITION'],
                'number': row['NUM']
            })

        return players_list

    except Exception as e:
        print(f"Error fetching roster for team {team_id}: {e}")
        return []

@st.cache_data(ttl=3600)
def get_player_season_stats(player_id):
    """Fetch player's current season statistics"""
    try:
        player_stats = playerdashboardbygeneralsplits.PlayerDashboardByGeneralSplits(
            player_id=player_id,
            season='2024-25'
        )
        df = player_stats.get_data_frames()[0]

        if df.empty:
            return {}

        row = df.iloc[0]
        stats = {
            'points': round(row['PTS'], 1),
            'rebounds': round(row['REB'], 1),
            'assists': round(row['AST'], 1)
        }

        # Add threes if significant
        if row['FG3A'] > 2:
            stats['threes'] = round(row['FG3M'], 1)

        return stats

    except Exception as e:
        print(f"Error fetching stats for player {player_id}: {e}")
        return {
            'points': 0.0,
            'rebounds': 0.0,
            'assists': 0.0
        }

@st.cache_data(ttl=1800)  # Cache game logs for 30 minutes
def get_player_game_log(player_id, num_games=20):
    """Fetch player's recent game log"""
    try:
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season='2024-25'
        )
        df = gamelog.get_data_frames()[0]

        if df.empty:
            return []

        games = []
        for _, row in df.head(num_games).iterrows():
            game_date = datetime.strptime(row['GAME_DATE'], '%b %d, %Y')
            opp_abbrev = row['MATCHUP'].split()[-1]

            games.append({
                'date': game_date.strftime('%b %d'),
                'opponent': opp_abbrev,
                'points': int(row['PTS']),
                'rebounds': int(row['REB']),
                'assists': int(row['AST']),
                'threes': int(row['FG3M'])
            })

        return games

    except Exception as e:
        print(f"Error fetching game log for player {player_id}: {e}")
        return []

def get_enriched_games():
    """Get today's games with team stats (rosters fetched on-demand)"""
    games = get_todays_games()
    team_stats = get_team_stats()

    enriched = []
    for game in games:
        enriched.append({
            'away_team': game['away_team'],
            'home_team': game['home_team'],
            'time': game['time'],
            'away_team_id': game['away_team_id'],
            'home_team_id': game['home_team_id'],
            'away_players': [],  # Fetch on-demand when user clicks into game
            'home_players': [],  # Fetch on-demand when user clicks into game
            'away_stats': team_stats.get(game['away_team'], {}),
            'home_stats': team_stats.get(game['home_team'], {})
        })

    return enriched

def enrich_game_with_rosters(game):
    """Fetch rosters for a specific game (called when user clicks into game)"""
    if not game.get('away_players'):  # Only fetch if not already loaded
        away_roster = get_team_roster(game['away_team_id'])
        home_roster = get_team_roster(game['home_team_id'])

        # Enrich players with stats
        for player in away_roster[:3]:  # Top 3 players
            player['stats'] = get_player_season_stats(player['id'])

        for player in home_roster[:3]:
            player['stats'] = get_player_season_stats(player['id'])

        game['away_players'] = away_roster
        game['home_players'] = home_roster

    return game

# Initialize data on module load
def init_nba_data():
    """Initialize and warm up caches"""
    try:
        get_team_stats()
        get_todays_games()
        return True
    except Exception as e:
        print(f"Error initializing NBA data: {e}")
        return False
