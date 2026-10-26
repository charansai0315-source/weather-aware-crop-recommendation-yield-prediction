import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherLookupError(Exception):
    pass


def _get_json(url, params):
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={"User-Agent": "FieldwiseCropAdvisor/1.0"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise WeatherLookupError(
            "Weather data could not be reached. Check your connection and try again."
        ) from exc


def get_weather(location, state=""):
    query = f"{location}, {state}, India" if state and state != "Other" else f"{location}, India"
    places = _get_json(
        GEOCODING_URL,
        {"name": query, "count": 1, "language": "en", "countryCode": "IN"},
    ).get("results", [])
    if not places:
        raise WeatherLookupError(
            "We could not find that place in India. Try a nearby city or district name."
        )

    place = places[0]
    forecast = _get_json(
        FORECAST_URL,
        {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
            "forecast_days": 7,
            "timezone": "auto",
        },
    )
    current = forecast.get("current", {})
    daily = forecast.get("daily", {})
    days = daily.get("time", [])
    rain = daily.get("precipitation_sum", [])
    max_temps = daily.get("temperature_2m_max", [])
    min_temps = daily.get("temperature_2m_min", [])
    daily_rows = [
        {
            "date": days[index],
            "rainMm": rain[index],
            "maxTempC": max_temps[index],
            "minTempC": min_temps[index],
        }
        for index in range(min(len(days), len(rain), len(max_temps), len(min_temps)))
    ]

    def rounded(value, digits=1):
        return round(value, digits) if isinstance(value, (int, float)) else None

    admin = place.get("admin1") or state
    return {
        "location": {
            "name": place.get("name", location),
            "admin1": admin,
            "country": place.get("country", "India"),
            "latitude": place["latitude"],
            "longitude": place["longitude"],
        },
        "updatedAt": current.get("time"),
        "current": {
            "temperatureC": rounded(current.get("temperature_2m")),
            "humidityPct": rounded(current.get("relative_humidity_2m"), 0),
            "precipitationMm": rounded(current.get("precipitation")),
            "windKmh": rounded(current.get("wind_speed_10m")),
        },
        "next7Days": {
            "precipitationMm": rounded(sum(value or 0 for value in rain)),
            "maxTempC": rounded(max((value for value in max_temps if value is not None), default=None)),
            "minTempC": rounded(min((value for value in min_temps if value is not None), default=None)),
        },
        "daily": daily_rows,
        "timezone": forecast.get("timezone", ""),
    }
