#!/usr/bin/env python3
"""
PropStats Setup Script - 2025-26 NBA Season
Run this after deploying to populate the database with NBA players
"""

import requests
import time
import os
import sys

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "propstats2024")
CURRENT_SEASON = "2025-26"

def sync_players():
    """Sync all NBA players to the database"""
    print("🏀 PropStats Setup")
    print("=" * 50)
    print(f"API URL: {API_URL}")
    print()
    
    print("📥 Syncing NBA players...")
    try:
        response = requests.post(
            f"{API_URL}/admin/sync-players",
            params={"secret": ADMIN_SECRET},
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Players synced successfully!")
            print(f"   Message: {data.get('message', 'Done')}")
        elif response.status_code == 403:
            print("❌ Unauthorized - check your ADMIN_SECRET")
            sys.exit(1)
        else:
            print(f"❌ Failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Could not connect to {API_URL}")
        print("   Make sure the backend is running!")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

def check_health():
    """Check if the API is healthy"""
    print()
    print("🔍 Checking API health...")
    try:
        response = requests.get(f"{API_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ API is healthy!")
            print(f"   Players: {data.get('players', 0)}")
            print(f"   Games: {data.get('games', 0)}")
            return True
        else:
            print(f"⚠️  API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

def sync_popular_players():
    """Pre-sync game logs for popular players"""
    popular_ids = [
        "2544",      # LeBron James
        "201566",    # LeBron (alt)
        "203507",    # Giannis
        "201142",    # Kevin Durant
        "203954",    # Joel Embiid
        "1629029",   # Luka Doncic
        "203999",    # Nikola Jokic
        "201935",    # James Harden
        "1628369",   # Jayson Tatum
        "203081",    # Damian Lillard
    ]
    
    print()
    print("📊 Pre-syncing popular players...")
    
    for player_id in popular_ids:
        try:
            response = requests.post(
                f"{API_URL}/admin/sync-player/{player_id}",
                params={"secret": ADMIN_SECRET},
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                games = data.get("games_synced", 0)
                if games > 0:
                    print(f"   ✓ Player {player_id}: {games} games synced")
            time.sleep(1)  # Rate limiting
        except Exception as e:
            print(f"   ⚠️  Player {player_id}: {e}")

def main():
    # Step 1: Check if API is running
    if not check_health():
        print()
        print("Please start the backend first:")
        print("  cd backend && python main.py")
        sys.exit(1)
    
    # Step 2: Sync all players
    sync_players()
    
    # Step 3: Pre-sync popular players (optional)
    print()
    response = input("Pre-sync popular players for faster initial loads? [y/N]: ")
    if response.lower() == 'y':
        sync_popular_players()
    
    # Done
    print()
    print("=" * 50)
    print("🎉 Setup complete!")
    print()
    print("Your PropStats API is ready at:", API_URL)
    print()
    print("Next steps:")
    print("1. Deploy frontend to Vercel/Netlify")
    print("2. Set VITE_API_URL to your backend URL")
    print("3. Start researching props! 🏀")
    print()

if __name__ == "__main__":
    main()
