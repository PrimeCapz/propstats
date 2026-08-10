"""
weather_engine.py — Game-time wind + temp forecasts for HR board scoring.

Uses Open-Meteo (free, no API key) for hourly wind forecasts.
Wind component toward CF drives HR bonus/penalty in build_hr_attack_board().

CF bearing = compass direction FROM home plate TO center field.
Positive component = tailwind (wind blowing out to CF, HR boost).
Negative component = headwind (wind blowing into HP, HR suppress).
"""

import math
import time
import requests
from datetime import datetime, timezone

_REQUEST_TIMEOUT = 12
_weather_cache: dict = {}   # (lat_r3, lon_r3) → raw Open-Meteo response

# Stadium coordinates and CF bearing for all 30 MLB parks.
# cf_bearing = compass degrees FROM home plate TOWARD center field (0=N, 90=E, 180=S, 270=W).
# dome=True → wind_bonus always 0.
# retractable=True → treated as open unless strong precip (not modeled).
STADIUM_DATA = {
    # AL East
    "Yankee Stadium":             {"lat": 40.8296, "lon": -73.9262, "cf_bearing": 305, "dome": False, "retractable": False},
    "Fenway Park":                {"lat": 42.3467, "lon": -71.0972, "cf_bearing":  65, "dome": False, "retractable": False},
    "Oriole Park at Camden Yards":{"lat": 39.2839, "lon": -76.6218, "cf_bearing":  55, "dome": False, "retractable": False},
    "Camden Yards":               {"lat": 39.2839, "lon": -76.6218, "cf_bearing":  55, "dome": False, "retractable": False},
    "Citizens Bank Park":         {"lat": 39.9061, "lon": -75.1665, "cf_bearing":  50, "dome": False, "retractable": False},
    "Rogers Centre":              {"lat": 43.6414, "lon": -79.3894, "cf_bearing": 185, "dome": True,  "retractable": False},
    "Tropicana Field":            {"lat": 27.7683, "lon": -82.6534, "cf_bearing":  90, "dome": True,  "retractable": False},
    # AL Central
    "Progressive Field":          {"lat": 41.4962, "lon": -81.6852, "cf_bearing": 265, "dome": False, "retractable": False},
    "Comerica Park":              {"lat": 42.3390, "lon": -83.0485, "cf_bearing":  55, "dome": False, "retractable": False},
    "Target Field":               {"lat": 44.9817, "lon": -93.2785, "cf_bearing": 310, "dome": False, "retractable": False},
    "Guaranteed Rate Field":      {"lat": 41.8300, "lon": -87.6338, "cf_bearing": 170, "dome": False, "retractable": False},
    "Kauffman Stadium":           {"lat": 39.0516, "lon": -94.4803, "cf_bearing":  85, "dome": False, "retractable": False},
    # AL West
    "Minute Maid Park":           {"lat": 29.7573, "lon": -95.3557, "cf_bearing":  50, "dome": False, "retractable": True},
    "Globe Life Field":           {"lat": 32.7473, "lon": -97.0819, "cf_bearing":  25, "dome": True,  "retractable": False},
    "Angel Stadium":              {"lat": 33.8003, "lon": -117.8827,"cf_bearing": 100, "dome": False, "retractable": False},
    "T-Mobile Park":              {"lat": 47.5914, "lon": -122.3326,"cf_bearing":  25, "dome": False, "retractable": True},
    # A's playing at Sutter Health Park (Sacramento) — see Temp/relocated below
    # NL East
    "Truist Park":                {"lat": 33.8905, "lon": -84.4677, "cf_bearing":  65, "dome": False, "retractable": False},
    "Nationals Park":             {"lat": 38.8730, "lon": -77.0074, "cf_bearing":  35, "dome": False, "retractable": False},
    "Citi Field":                 {"lat": 40.7571, "lon": -73.8458, "cf_bearing": 290, "dome": False, "retractable": False},
    "loanDepot park":             {"lat": 25.7781, "lon": -80.2197, "cf_bearing": 355, "dome": False, "retractable": True},
    "loanDepot Park":             {"lat": 25.7781, "lon": -80.2197, "cf_bearing": 355, "dome": False, "retractable": True},
    # NL Central
    "Great American Ball Park":   {"lat": 39.0972, "lon": -84.5068, "cf_bearing": 100, "dome": False, "retractable": False},
    "Wrigley Field":              {"lat": 41.9484, "lon": -87.6553, "cf_bearing": 195, "dome": False, "retractable": False},
    "Busch Stadium":              {"lat": 38.6226, "lon": -90.1928, "cf_bearing": 100, "dome": False, "retractable": False},
    "American Family Field":      {"lat": 43.0281, "lon": -87.9712, "cf_bearing":  75, "dome": False, "retractable": True},
    "PNC Park":                   {"lat": 40.4469, "lon": -80.0058, "cf_bearing": 330, "dome": False, "retractable": False},
    # NL West
    "Coors Field":                {"lat": 39.7559, "lon": -104.9942,"cf_bearing":  60, "dome": False, "retractable": False},
    "Chase Field":                {"lat": 33.4453, "lon": -112.0667,"cf_bearing": 355, "dome": False, "retractable": True},
    "Dodger Stadium":             {"lat": 34.0739, "lon": -118.2400,"cf_bearing":  80, "dome": False, "retractable": False},
    "Petco Park":                 {"lat": 32.7076, "lon": -117.1570,"cf_bearing": 260, "dome": False, "retractable": False},
    "Oracle Park":                {"lat": 37.7786, "lon": -122.3893,"cf_bearing": 310, "dome": False, "retractable": False},
    # Temp/relocated
    "Sutter Health Park":         {"lat": 38.5789, "lon": -121.5067,"cf_bearing":  85, "dome": False, "retractable": False},
}


def _find_stadium(venue_name: str) -> dict | None:
    """Match venue_name string to STADIUM_DATA with fuzzy fallback."""
    if venue_name in STADIUM_DATA:
        return STADIUM_DATA[venue_name]
    v = venue_name.lower()
    for k, d in STADIUM_DATA.items():
        if k.lower() in v or v in k.lower():
            return d
    for k, d in STADIUM_DATA.items():
        for word in k.lower().split():
            if len(word) >= 5 and word in v:
                return d
    return None


def _fetch_open_meteo(lat: float, lon: float) -> dict | None:
    """Fetch hourly wind + temp from Open-Meteo. Results cached by lat/lon."""
    key = (round(lat, 3), round(lon, 3))
    if key in _weather_cache:
        return _weather_cache[key]
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=wind_speed_10m,wind_direction_10m,temperature_2m"
        "&wind_speed_unit=mph&temperature_unit=fahrenheit"
        "&timezone=UTC&forecast_days=2"
    )
    try:
        r = requests.get(url, timeout=_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        _weather_cache[key] = data
        return data
    except Exception:
        return None


def _find_hour_index(times: list, game_time_utc: str) -> int:
    """Find hourly slot index closest to game_time_utc ('2026-08-10T23:10:00Z')."""
    if not game_time_utc or not times:
        return min(19, len(times) - 1) if times else 0  # default 7pm UTC slot
    try:
        raw = game_time_utc[:16].rstrip("Z")
        dt_game = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    except Exception:
        return 0
    best_idx, best_diff = 0, float("inf")
    for i, t_str in enumerate(times):
        try:
            t = datetime.strptime(t_str[:16], "%Y-%m-%dT%H:%M")
            diff = abs((t - dt_game).total_seconds())
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        except Exception:
            continue
    return best_idx


def compute_wind_component(wind_from_deg: float, cf_bearing: float, wind_speed_mph: float) -> float:
    """
    Component of wind speed toward CF outfield.
    Positive = tailwind (wind going OUT, HR boost).
    Negative = headwind (wind coming IN, HR suppress).
    """
    wind_to_deg = (wind_from_deg + 180) % 360
    angle_diff = abs(wind_to_deg - cf_bearing)
    if angle_diff > 180:
        angle_diff = 360 - angle_diff
    return round(wind_speed_mph * math.cos(math.radians(angle_diff)), 1)


def wind_bonus_from_component(component: float) -> float:
    """HR score bonus/penalty (points on 0-100 scale) based on wind toward CF."""
    if component >= 15:     return 12.0
    elif component >= 10:   return  7.0
    elif component >= 6:    return  4.0
    elif component >= 3:    return  2.0
    elif component >= -3:   return  0.0
    elif component >= -6:   return -3.0
    elif component >= -10:  return -6.0
    else:                   return -10.0


def _cardinal(deg: float) -> str:
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE",
            "S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[round(deg / 22.5) % 16]


_NULL = {
    "wind_mph": 0, "wind_from_deg": 0, "wind_from_label": "—",
    "wind_component_cf": 0, "wind_bonus": 0, "temp_f": 72,
    "dome": False, "retractable": False, "tag": "", "matched": False,
}


def get_weather_for_game(venue_name: str, game_time_utc: str) -> dict:
    """
    Returns wind + temp dict for a game.

    game_time_utc: ISO string from MLB API e.g. "2026-08-10T23:10:00Z" (UTC).

    Returned keys: wind_mph, wind_from_deg, wind_from_label, wind_component_cf,
                   wind_bonus, temp_f, dome, retractable, tag, matched,
                   cf_bearing (when matched)
    """
    stadium = _find_stadium(venue_name)

    if stadium is None:
        return {**_NULL, "error": f"Venue not found: {venue_name}"}

    if stadium.get("dome"):
        return {**_NULL, "dome": True, "tag": "DOME", "matched": True}

    lat, lon = stadium["lat"], stadium["lon"]
    cf_bearing = stadium["cf_bearing"]
    retractable = stadium.get("retractable", False)

    raw = _fetch_open_meteo(lat, lon)
    if not raw:
        return {**_NULL, "matched": True, "error": "Weather API unavailable"}

    hourly = raw.get("hourly", {})
    times  = hourly.get("time", [])
    speeds = hourly.get("wind_speed_10m", [])
    dirs   = hourly.get("wind_direction_10m", [])
    temps  = hourly.get("temperature_2m", [])

    idx       = _find_hour_index(times, game_time_utc)
    wind_mph  = float(speeds[idx]) if idx < len(speeds) else 0.0
    wind_deg  = float(dirs[idx])   if idx < len(dirs)   else 0.0
    temp_f    = float(temps[idx])  if idx < len(temps)  else 72.0

    component  = compute_wind_component(wind_deg, cf_bearing, wind_mph)
    bonus      = wind_bonus_from_component(component)
    from_label = _cardinal(wind_deg)

    tag = ""
    if component >= 6:
        tag = f"WIND BOOST ({wind_mph:.0f}mph out→CF)"
    elif component <= -6:
        tag = f"WIND SUPPRESS ({wind_mph:.0f}mph in←HP)"
    elif abs(component) >= 3:
        tag = f"WIND ({wind_mph:.0f}mph {from_label})"

    return {
        "wind_mph":          round(wind_mph, 1),
        "wind_from_deg":     round(wind_deg, 0),
        "wind_from_label":   from_label,
        "wind_component_cf": component,
        "wind_bonus":        bonus,
        "temp_f":            round(temp_f, 1),
        "dome":              False,
        "retractable":       retractable,
        "tag":               tag,
        "matched":           True,
        "cf_bearing":        cf_bearing,
    }


def get_weather_for_all_games(games: list) -> dict:
    """
    Fetch weather for all games, deduplicating by venue.
    Returns {venue_name: weather_dict}.
    """
    venue_weather: dict = {}
    for g in games:
        venue     = g.get("venue_name", "Unknown")
        game_time = g.get("game_time", "")
        if venue not in venue_weather:
            venue_weather[venue] = get_weather_for_game(venue, game_time)
            time.sleep(0.05)
    return venue_weather
