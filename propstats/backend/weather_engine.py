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
    # Houston renamed Minute Maid Park to Daikin Park; the API reports the new
    # name, so without this alias every Astros home game silently got no weather.
    "Daikin Park":                {"lat": 29.7573, "lon": -95.3557, "cf_bearing":  50, "dome": False, "retractable": True},
    "Globe Life Field":           {"lat": 32.7473, "lon": -97.0819, "cf_bearing":  25, "dome": True,  "retractable": False},
    "Angel Stadium":              {"lat": 33.8003, "lon": -117.8827,"cf_bearing": 100, "dome": False, "retractable": False},
    "T-Mobile Park":              {"lat": 47.5914, "lon": -122.3326,"cf_bearing":  25, "dome": False, "retractable": True},
    "Las Vegas Ballpark":         {"lat": 36.1718, "lon": -115.2318,"cf_bearing":  50, "dome": False, "retractable": False},
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
        "&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,"
        "surface_pressure,relative_humidity_2m"
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



# ---------------------------------------------------------------------------
# Air density and ball carry
# ---------------------------------------------------------------------------
# Batted-ball carry is governed by air density, which depends on temperature,
# barometric pressure and humidity — not temperature alone. The model below is
# standard psychrometrics, and it reproduces the known anchor: Coors Field at
# ~840 hPa comes out at 80% of sea-level density, implying a 1.41x home-run
# multiplier against a published Coors factor of ~1.28-1.35 (the gap is the
# humidor, which the physics does not know about).
#
# MEASURED BUT NOT USED IN PROBABILITIES. Backtested over 102 outdoor games
# across eight Sep-2026 slates, the carry index did not predict home runs:
#     absolute carry vs game HR        r = +0.087
#     park-relative carry vs game HR   r = -0.118
#     thickest 25% / middle / thinnest  3.10 / 2.12 / 2.76 HR per game
# The quartile pattern is non-monotone, i.e. noise. That sample is also far too
# small to settle the question — at 2.58 HR/game with sd 1.39, resolving a 5%
# effect needs roughly 770 games — so the index is computed and logged on every
# game to accumulate a sample, and deliberately left out of the HR probability
# until the data earns its way in. Do not wire it into scoring on the strength
# of the physics alone.
_R_DRY, _R_VAPOR = 287.058, 461.495
RHO_STD = 1.2211          # kg/m3 at 59F, 1013.25 hPa, 50% RH
CARRY_EXPONENT = 1.56     # calibrated so the Coors density ratio reproduces its park factor


def _saturation_vapor_pressure_hpa(temp_c: float) -> float:
    """Tetens approximation."""
    return 6.1078 * 10 ** (7.5 * temp_c / (237.3 + temp_c))


def air_density(temp_f: float, pressure_hpa: float, humidity_pct: float) -> float:
    """Density of moist air in kg/m3."""
    temp_c = (temp_f - 32.0) * 5.0 / 9.0
    temp_k = temp_c + 273.15
    p_vapor = _saturation_vapor_pressure_hpa(temp_c) * (humidity_pct / 100.0) * 100.0
    p_dry = pressure_hpa * 100.0 - p_vapor
    return p_dry / (_R_DRY * temp_k) + p_vapor / (_R_VAPOR * temp_k)


def carry_index(temp_f: float, pressure_hpa: float, humidity_pct: float) -> float:
    """Ball-carry multiplier relative to standard sea-level air.

    Above 1.0 means thinner air than standard and more carry.
    """
    rho = air_density(temp_f, pressure_hpa, humidity_pct)
    if rho <= 0:
        return 1.0
    return (RHO_STD / rho) ** CARRY_EXPONENT


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
    press  = hourly.get("surface_pressure", [])
    humid  = hourly.get("relative_humidity_2m", [])

    idx       = _find_hour_index(times, game_time_utc)
    wind_mph  = float(speeds[idx]) if idx < len(speeds) else 0.0
    wind_deg  = float(dirs[idx])   if idx < len(dirs)   else 0.0
    temp_f    = float(temps[idx])  if idx < len(temps)  else 72.0
    pressure  = float(press[idx])  if idx < len(press) and press[idx] is not None else 1013.25
    humidity  = float(humid[idx])  if idx < len(humid) and humid[idx] is not None else 50.0

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
        "pressure_hpa":      round(pressure, 1),
        "humidity_pct":      round(humidity, 0),
        "air_density":       round(air_density(temp_f, pressure, humidity), 4),
        # Diagnostic only — see the note on carry_index. Not used in scoring.
        "carry_index":       round(carry_index(temp_f, pressure, humidity), 3),
        "dome":              False,
        "retractable":       retractable,
        "tag":               tag,
        "matched":           True,
        "cf_bearing":        cf_bearing,
    }


def prefetch_weather(venues: list) -> int:
    """Warm the weather cache for many venues in a single Open-Meteo request.

    Open-Meteo accepts comma-separated coordinate lists and returns one block
    per location, so a 15-game slate costs one call instead of fifteen. Firing
    them individually reliably trips the free tier's rate limit, and a 429 is
    silent — the venue just falls back to the 72F default and every downstream
    wind and carry number for that park is fabricated.

    Returns the number of venues cached. Falls back to per-venue fetching by
    simply doing nothing, since get_weather_for_game still works on its own.
    """
    coords, seen = [], set()
    for v in venues:
        st = _find_stadium(v)
        if not st:
            continue
        key = (round(st["lat"], 3), round(st["lon"], 3))
        if key in seen or key in _weather_cache:
            continue
        seen.add(key)
        coords.append(key)
    if not coords:
        return 0

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={','.join(str(c[0]) for c in coords)}"
        f"&longitude={','.join(str(c[1]) for c in coords)}"
        "&hourly=wind_speed_10m,wind_direction_10m,temperature_2m,"
        "surface_pressure,relative_humidity_2m"
        "&wind_speed_unit=mph&temperature_unit=fahrenheit"
        "&timezone=UTC&forecast_days=2"
    )
    try:
        r = requests.get(url, timeout=_REQUEST_TIMEOUT * 3)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return 0

    blocks = data if isinstance(data, list) else [data]
    if len(blocks) != len(coords):
        return 0
    for key, blk in zip(coords, blocks):
        _weather_cache[key] = blk
    return len(coords)


def get_weather_for_all_games(games: list) -> dict:
    """
    Fetch weather for all games, deduplicating by venue.
    Returns {venue_name: weather_dict}.
    """
    prefetch_weather([g.get("venue_name", "") for g in games])

    venue_weather: dict = {}
    for g in games:
        venue     = g.get("venue_name", "Unknown")
        game_time = g.get("game_time", "")
        if venue not in venue_weather:
            venue_weather[venue] = get_weather_for_game(venue, game_time)
    return venue_weather
