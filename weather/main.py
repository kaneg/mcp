from __future__ import annotations

import os
from typing import Literal, Optional

import requests
from mcp.server.fastmcp import FastMCP

# Server name for MCP registry/clients
mcp = FastMCP("Weather Server", log_level="ERROR")

WTTR_BASE = os.environ.get("WTTR_BASE", "https://wttr.in")
DEFAULT_TIMEOUT = float(os.environ.get("WTTR_TIMEOUT", "10"))


def _fetch_wttr(city: str, unit: Literal["metric", "imperial"]) -> dict:
    """Fetch weather data from wttr.in as JSON.

    Args:
        city: City name or query (e.g., "London", "San Francisco").
        unit: "metric" or "imperial"; affects temp units we return.

    Returns:
        Parsed JSON dict from wttr.in (?format=j1).

    Raises:
        requests.RequestException if HTTP fails or invalid status.
        ValueError if JSON malformed.
    """
    # wttr.in JSON endpoint
    url = f"{WTTR_BASE}/{requests.utils.quote(city)}"
    params = {"format": "j1"}
    resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT, headers={"User-Agent": "mcp-weather-server/0.1"})
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, dict):
        raise ValueError("Unexpected response format from wttr.in")
    # Add our chosen unit to the dict for later formatting
    data["_unit"] = unit
    return data


def _format_current_summary(data: dict) -> str:
    """Create a concise textual summary from wttr.in JSON."""
    unit = data.get("_unit", "metric")

    # wttr.in structure: current_condition is a list with one dict
    current = None
    try:
        current_list = data.get("current_condition") or []
        current = current_list[0] if current_list else None
    except Exception:
        current = None

    if not current:
        return "No current weather data available."

    # Extract fields safely. wttr.in uses arrays for many string fields
    def _get(field: str, default: str = "") -> str:
        val = current.get(field, default)
        if isinstance(val, list) and val and isinstance(val[0], dict) and "value" in val[0]:
            return val[0]["value"]
        if isinstance(val, list) and val and isinstance(val[0], str):
            return val[0]
        if isinstance(val, (str, int, float)):
            return str(val)
        return default

    # Temperatures are provided as FeelsLikeC/FeelsLikeF, temp_C/temp_F
    temp = _get("temp_C" if unit == "metric" else "temp_F", "")
    feels = _get("FeelsLikeC" if unit == "metric" else "FeelsLikeF", "")
    desc = _get("weatherDesc", "")
    wind_kmph = _get("windspeedKmph", "")
    wind_mph = _get("windspeedMiles", "")
    humidity = _get("humidity", "")

    temp_unit = "°C" if unit == "metric" else "°F"
    wind = f"{wind_kmph} km/h" if unit == "metric" else f"{wind_mph} mph"

    parts = []
    if temp:
        parts.append(f"Temp: {temp}{temp_unit}")
    if feels:
        parts.append(f"Feels like: {feels}{temp_unit}")
    if desc:
        parts.append(f"Conditions: {desc}")
    if wind.strip():
        parts.append(f"Wind: {wind}")
    if humidity:
        parts.append(f"Humidity: {humidity}%")

    if not parts:
        return "No current weather data available."

    return "; ".join(parts)


@mcp.tool(description="Get current weather for a city using wttr.in")
def weather(
    city: str,
    unit: Literal["metric", "imperial"] = "metric",
) -> str:
    """Query current weather by city name using wttr.in.

    Args:
        city: City name or query (e.g., "London", "San Francisco").
        unit: "metric" (C, km/h) or "imperial" (F, mph).

    Returns:
        A concise human-readable weather summary.
    """
    city = (city or "").strip()
    if not city:
        return "Please provide a non-empty city name."

    if unit not in ("metric", "imperial"):
        return 'Invalid unit. Use "metric" or "imperial".'

    try:
        data = _fetch_wttr(city, unit)
        return _format_current_summary(data)
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", None)
        if status == 404:
            return f"City not found: {city}"
        return f"HTTP error from wttr.in: {e}"
    except requests.Timeout:
        return "Request to wttr.in timed out. Please try again later."
    except requests.RequestException as e:
        return f"Network error contacting wttr.in: {e}"
    except ValueError as e:
        return f"Unexpected response from wttr.in: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


def main() -> None:
    """Entry point to run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
