"""
weather.py
----------
Fetches real-time weather data from OpenWeatherMap and generates
farming advisories based on temperature + humidity.

Set your API key in the environment variable OPENWEATHER_API_KEY,
or pass it directly when calling get_weather_advisory().

If no key is available the module returns demo (mock) data so the
app still runs in offline / demo mode.
"""

import os
import requests
from datetime import datetime

# ── Constants ─────────────────────────────────────────────────────────────────
_API_BASE    = "https://api.openweathermap.org/data/2.5/weather"
_DEFAULT_LOC = "Delhi,IN"
_TIMEOUT     = 8  # seconds


# ── Advisory rules ────────────────────────────────────────────────────────────
def _build_advisory(temp: float, humidity: float, description: str) -> list[str]:
    """
    Generate farming advisories from weather metrics.

    Rule table
    ----------
    Temp > 35 °C          → Heat stress warning, increase irrigation
    Temp < 15 °C          → Cold stress, avoid transplanting
    Humidity > 80 %       → High fungal risk, reduce canopy wetness
    Humidity < 40 %       → Drought risk, ensure consistent watering
    Rain / drizzle        → Hold off on fertiliser application
    Default               → Conditions suitable for normal farming
    """
    advisories = []

    if temp > 35:
        advisories.append("🌡️ Heat stress risk — increase irrigation frequency.")
    elif temp < 15:
        advisories.append("🥶 Cold stress — delay transplanting seedlings.")
    else:
        advisories.append("🌤️ Temperature is optimal for rice growth.")

    if humidity > 80:
        advisories.append("💧 High humidity — elevated fungal disease risk. Ensure good field drainage.")
    elif humidity < 40:
        advisories.append("🏜️ Low humidity / drought risk — maintain consistent irrigation schedule.")
    else:
        advisories.append("💦 Humidity is within acceptable range for paddy cultivation.")

    lower_desc = description.lower()
    if any(w in lower_desc for w in ["rain", "drizzle", "shower", "thunderstorm"]):
        advisories.append("🌧️ Rain expected — postpone fertiliser and pesticide application.")
    elif "clear" in lower_desc or "sunny" in lower_desc:
        advisories.append("☀️ Clear sky — good conditions for spraying if needed.")

    return advisories


# ── Mock data (offline / demo) ────────────────────────────────────────────────
def _mock_weather(location: str) -> dict:
    return {
        "location":    location,
        "temperature": 31.0,
        "feels_like":  33.5,
        "humidity":    72,
        "description": "partly cloudy",
        "wind_speed":  3.6,
        "timestamp":   datetime.now().strftime("%d %b %Y, %H:%M"),
        "advisories":  _build_advisory(31.0, 72, "partly cloudy"),
        "source":      "demo",
    }


# ── Public API ────────────────────────────────────────────────────────────────
def get_weather_advisory(location: str = _DEFAULT_LOC, api_key: str | None = None) -> dict:
    """
    Fetch weather data and return advisory dict.

    Parameters
    ----------
    location : city name (e.g. "Delhi,IN", "Kolkata,IN")
    api_key  : OpenWeatherMap API key (falls back to env var)

    Returns
    -------
    dict with temperature, humidity, description, advisories, source
    """
    key = api_key or os.getenv("OPENWEATHER_API_KEY", "")

    if not key:
        # No key available — return demo data
        data = _mock_weather(location)
        data["advisories"].insert(
            0,
            "ℹ️ Demo weather data (add OPENWEATHER_API_KEY for live data).",
        )
        return data

    try:
        resp = requests.get(
            _API_BASE,
            params={"q": location, "appid": key, "units": "metric"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()

        temp        = raw["main"]["temp"]
        feels_like  = raw["main"]["feels_like"]
        humidity    = raw["main"]["humidity"]
        description = raw["weather"][0]["description"]
        wind_speed  = raw["wind"]["speed"]
        city_name   = raw.get("name", location)

        return {
            "location":    city_name,
            "temperature": round(temp, 1),
            "feels_like":  round(feels_like, 1),
            "humidity":    humidity,
            "description": description.capitalize(),
            "wind_speed":  wind_speed,
            "timestamp":   datetime.now().strftime("%d %b %Y, %H:%M"),
            "advisories":  _build_advisory(temp, humidity, description),
            "source":      "live",
        }

    except requests.exceptions.RequestException as exc:
        # Network error — fall back to mock
        data = _mock_weather(location)
        data["advisories"].insert(0, f"⚠️ Weather API error ({exc}) — showing demo data.")
        return data
