"""
Weather API using OpenWeatherMap One Call API 3.0.

Endpoint selection by trip distance from today:
  <= 2 days  : hourly forecast  (/onecall, hourly array, 48 h max)
  <= 8 days  : daily forecast   (/onecall, daily array, 8 days max)
  >  8 days  : day summary      (/onecall/day_summary, per-day call, up to ~1.5 yrs)
"""
import logging
import os
import requests
from datetime import date, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
GEOCODING_URL  = "http://api.openweathermap.org/geo/1.0/direct"
ONECALL_URL    = "https://api.openweathermap.org/data/3.0/onecall"
DAY_SUMMARY_URL = "https://api.openweathermap.org/data/3.0/onecall/day_summary"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_coords(city: str) -> tuple[float, float]:
    logger.info("Geocoding city: %s", city)
    resp = requests.get(
        GEOCODING_URL,
        params={"q": city, "limit": 1, "appid": OPENWEATHER_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        logger.warning("City not found in geocoding response: %s", city)
        raise ValueError(f"City not found: {city}")
    lat, lon = data[0]["lat"], data[0]["lon"]
    logger.info("Resolved %s -> lat=%.4f, lon=%.4f", city, lat, lon)
    return lat, lon


def _uv_risk(uvi: float) -> str:
    if uvi >= 11: return "Extreme"
    if uvi >= 8:  return "Very High"
    if uvi >= 6:  return "High"
    if uvi >= 3:  return "Moderate"
    return "Low"


def _risk_level(avg_temp_high: float, avg_rain_chance: float, avg_temp_low: float, max_uvi: float) -> str:
    if max_uvi >= 11 or avg_temp_high >= 40:
        return "HIGH"
    if max_uvi >= 6 or avg_rain_chance >= 60 or avg_temp_low <= 0:
        return "MEDIUM"
    return "LOW"


def _date_range(start_date: str, end_date: str) -> list[date]:
    try:
        d_start = date.fromisoformat(start_date)
        d_end   = date.fromisoformat(end_date)
    except ValueError:
        d_start = d_end = date.today()
    days = []
    cur = d_start
    while cur <= d_end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


# ---------------------------------------------------------------------------
# Strategy 1: hourly  (trip starts within 2 days)
# ---------------------------------------------------------------------------

def _fetch_hourly(lat: float, lon: float, d_start: date, d_end: date) -> list[dict]:
    logger.info("Fetching hourly forecast for lat=%.4f lon=%.4f, %s to %s", lat, lon, d_start, d_end)
    resp = requests.get(
        ONECALL_URL,
        params={"lat": lat, "lon": lon, "exclude": "current,minutely,daily,alerts",
                "units": "metric", "appid": OPENWEATHER_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    hourly = resp.json().get("hourly", [])
    logger.debug("Hourly response: %d data points received", len(hourly))

    # Group hours by date
    by_date: dict[date, list[dict]] = {}
    for h in hourly:
        hdate = datetime.fromtimestamp(h["dt"], tz=timezone.utc).date()
        if d_start <= hdate <= d_end:
            by_date.setdefault(hdate, []).append(h)

    daily_forecast = []
    for day_date in sorted(by_date):
        hours = by_date[day_date]
        temps   = [h["temp"] for h in hours]
        pops    = [h.get("pop", 0) * 100 for h in hours]
        humids  = [h["humidity"] for h in hours]
        uvis    = [h.get("uvi", 0) for h in hours]
        # pick most-frequent condition
        conditions = [h["weather"][0]["description"].title() for h in hours if h.get("weather")]
        condition  = max(set(conditions), key=conditions.count) if conditions else "Unknown"

        daily_forecast.append({
            "date": str(day_date),
            "forecast_type": "hourly",
            "condition": condition,
            "temp_high_c": round(max(temps), 1),
            "temp_low_c": round(min(temps), 1),
            "humidity_pct": round(sum(humids) / len(humids)),
            "rain_chance_pct": round(max(pops)),
            "uv_index": round(max(uvis), 1),
            "hourly_breakdown": [
                {
                    "time": datetime.fromtimestamp(h["dt"], tz=timezone.utc).strftime("%H:%M UTC"),
                    "temp_c": round(h["temp"], 1),
                    "feels_like_c": round(h.get("feels_like", h["temp"]), 1),
                    "humidity_pct": h["humidity"],
                    "rain_chance_pct": round(h.get("pop", 0) * 100),
                    "rain_mm": h.get("rain", {}).get("1h", 0),
                    "snow_mm": h.get("snow", {}).get("1h", 0),
                    "wind_speed_ms": round(h.get("wind_speed", 0), 1),
                    "condition": h["weather"][0]["description"].title() if h.get("weather") else "Unknown",
                }
                for h in hours
            ],
        })
    return daily_forecast


# ---------------------------------------------------------------------------
# Strategy 2: daily forecast  (trip within 8 days)
# ---------------------------------------------------------------------------

def _fetch_daily(lat: float, lon: float, d_start: date, d_end: date) -> tuple[list[dict], dict]:
    logger.info("Fetching daily forecast for lat=%.4f lon=%.4f, %s to %s", lat, lon, d_start, d_end)
    resp = requests.get(
        ONECALL_URL,
        params={"lat": lat, "lon": lon, "exclude": "current,minutely,hourly,alerts",
                "units": "metric", "appid": OPENWEATHER_API_KEY},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    logger.debug("Daily response: %d day(s) received", len(data.get("daily", [])))

    daily_forecast = []
    for day in data.get("daily", []):
        day_date = datetime.fromtimestamp(day["dt"], tz=timezone.utc).date()
        if d_start <= day_date <= d_end:
            daily_forecast.append({
                "date": str(day_date),
                "forecast_type": "daily",
                "condition": day["weather"][0]["description"].title() if day.get("weather") else "Unknown",
                "summary": day.get("summary", ""),
                "temp_high_c": round(day["temp"]["max"], 1),
                "temp_low_c": round(day["temp"]["min"], 1),
                "temp_morn_c": round(day["temp"]["morn"], 1),
                "temp_eve_c": round(day["temp"]["eve"], 1),
                "feels_like_day_c": round(day["feels_like"]["day"], 1),
                "humidity_pct": day["humidity"],
                "rain_chance_pct": round(day.get("pop", 0) * 100),
                "rain_mm": day.get("rain", 0) or 0,
                "snow_mm": day.get("snow", 0) or 0,
                "wind_speed_ms": round(day.get("wind_speed", 0), 1),
                "wind_deg": day.get("wind_deg", 0),
                "uv_index": round(day.get("uvi", 0), 1),
                "clouds_pct": day.get("clouds", 0),
                "sunrise": datetime.fromtimestamp(day["sunrise"], tz=timezone.utc).strftime("%H:%M UTC") if day.get("sunrise") else None,
                "sunset": datetime.fromtimestamp(day["sunset"], tz=timezone.utc).strftime("%H:%M UTC") if day.get("sunset") else None,
            })
    return daily_forecast, data.get("current", {})


# ---------------------------------------------------------------------------
# Strategy 3: day summary  (trip > 8 days away, up to ~1.5 years)
# ---------------------------------------------------------------------------

def _fetch_day_summary(lat: float, lon: float, days: list[date]) -> list[dict]:
    logger.info("Fetching long-term day summaries for lat=%.4f lon=%.4f, %d day(s)", lat, lon, len(days))
    daily_forecast = []
    for d in days:
        try:
            logger.debug("Fetching day summary for %s", d)
            resp = requests.get(
                DAY_SUMMARY_URL,
                params={"lat": lat, "lon": lon, "date": str(d),
                        "units": "metric", "appid": OPENWEATHER_API_KEY},
                timeout=10,
            )
            resp.raise_for_status()
            s = resp.json()
            daily_forecast.append({
                "date": str(d),
                "forecast_type": "long_term_summary",
                "temp_high_c": round(s.get("temperature", {}).get("max", 0), 1),
                "temp_low_c": round(s.get("temperature", {}).get("min", 0), 1),
                "temp_morn_c": round(s.get("temperature", {}).get("morning", 0), 1),
                "temp_eve_c": round(s.get("temperature", {}).get("evening", 0), 1),
                "humidity_pct": s.get("humidity", {}).get("afternoon", 0),
                "rain_mm": round(s.get("precipitation", {}).get("total", 0), 1),
                "wind_speed_ms": round(s.get("wind", {}).get("max", {}).get("speed", 0), 1),
                "wind_deg": s.get("wind", {}).get("max", {}).get("direction", 0),
                "clouds_pct": s.get("cloud_cover", {}).get("afternoon", 0),
                "pressure_hpa": s.get("pressure", {}).get("afternoon", 0),
            })
        except Exception as exc:
            logger.warning("Day summary failed for %s: %s", d, exc)
    return daily_forecast


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_weather(city: str, start_date: str, end_date: str) -> dict[str, Any]:
    """Get weather forecast using the best-fit OpenWeatherMap One Call 3.0 endpoint."""
    logger.info("get_weather called: city=%s, start=%s, end=%s", city, start_date, end_date)

    if not OPENWEATHER_API_KEY:
        logger.error("OPENWEATHER_API_KEY is not set")
        return {"status": "error", "message": "OPENWEATHER_API_KEY not configured"}

    try:
        lat, lon = _get_coords(city)
    except Exception as e:
        logger.error("Geocoding failed for city=%s: %s", city, e)
        return {"status": "error", "message": f"Geocoding failed: {e}"}

    days      = _date_range(start_date, end_date)
    today     = date.today()
    days_ahead = (days[0] - today).days   # how far the trip start is from today
    logger.info("Trip starts in %d day(s), covering %d day(s) total", days_ahead, len(days))

    if days_ahead < 0:
        logger.warning("Trip start date %s is in the past (%d days ago)", days[0], -days_ahead)
        return {
            "status": "error",
            "message": f"Trip start date {days[0]} is in the past. Please provide a future date.",
        }

    # Choose strategy
    try:
        if days_ahead <= 2:
            forecast_type  = "hourly (48-hour detail)"
            logger.info("Strategy: hourly forecast")
            d_start, d_end = days[0], days[-1]
            daily_forecast = _fetch_hourly(lat, lon, d_start, d_end)
            current        = {}
        elif days_ahead <= 8:
            forecast_type  = "daily (8-day forecast)"
            logger.info("Strategy: daily forecast")
            d_start, d_end = days[0], days[-1]
            daily_forecast, current = _fetch_daily(lat, lon, d_start, d_end)
        else:
            forecast_type  = "long-term day summary (up to 1.5 years)"
            logger.info("Strategy: long-term day summary")
            daily_forecast = _fetch_day_summary(lat, lon, days)
            current        = {}
    except Exception as e:
        logger.error("Weather fetch failed: %s", e, exc_info=True)
        return {"status": "error", "message": f"Weather fetch failed: {e}"}

    logger.info("Weather fetch complete: %d day(s) of forecast returned", len(daily_forecast))

    # Aggregate stats across all forecast days
    temp_highs    = [d["temp_high_c"] for d in daily_forecast if "temp_high_c" in d]
    temp_lows     = [d["temp_low_c"]  for d in daily_forecast if "temp_low_c"  in d]
    humidities    = [d["humidity_pct"] for d in daily_forecast if "humidity_pct" in d]
    rain_chances  = [d["rain_chance_pct"] for d in daily_forecast if "rain_chance_pct" in d]
    uvi_values    = [d["uv_index"] for d in daily_forecast if "uv_index" in d]

    avg_temp_high  = round(sum(temp_highs)   / len(temp_highs),   1) if temp_highs   else round(current.get("temp", 0), 1)
    avg_temp_low   = round(sum(temp_lows)    / len(temp_lows),    1) if temp_lows    else round(current.get("temp", 0), 1)
    avg_humidity   = round(sum(humidities)   / len(humidities))       if humidities   else current.get("humidity", 0)
    avg_rain_chance= round(sum(rain_chances) / len(rain_chances))     if rain_chances else 0
    max_uvi        = round(max(uvi_values),  1)                       if uvi_values   else round(current.get("uvi", 0), 1)

    # Current conditions (only available for onecall strategies)
    current_block = {}
    if current:
        current_block = {
            "condition": current.get("weather", [{}])[0].get("description", "Unknown").title(),
            "temp_c": round(current.get("temp", 0), 1),
            "feels_like_c": round(current.get("feels_like", 0), 1),
            "humidity_pct": current.get("humidity", 0),
            "wind_speed_ms": round(current.get("wind_speed", 0), 1),
            "uv_index": round(current.get("uvi", 0), 1),
            "visibility_m": current.get("visibility", 0),
            "clouds_pct": current.get("clouds", 0),
        }

    return {
        "status": "success",
        "city": city,
        "coordinates": {"lat": lat, "lon": lon},
        "period": f"{start_date} to {end_date}",
        "forecast_type": forecast_type,
        **({"current": current_block} if current_block else {}),
        "avg_temp_high_c": avg_temp_high,
        "avg_temp_low_c": avg_temp_low,
        "avg_humidity_pct": avg_humidity,
        "rain_chance_pct": avg_rain_chance,
        "uv_index": max_uvi,
        "uv_risk": _uv_risk(max_uvi),
        "risk_level": _risk_level(avg_temp_high, avg_rain_chance, avg_temp_low, max_uvi),
        "daily_forecast": daily_forecast,
    }
