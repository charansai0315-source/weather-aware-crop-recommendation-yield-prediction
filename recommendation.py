from math import isfinite


ACRES_TO_HECTARES = 0.404686

# Broad educational profiles for the first prototype. Replace these with
# locally validated agronomic data before using the app for farm decisions.
CROPS = [
    {
        "name": "Rice",
        "seasons": ["Kharif", "Rabi"],
        "soils": ["clay", "alluvial", "loamy"],
        "ph": [5.5, 7.5],
        "n": [60, 150], "p": [25, 70], "k": [20, 80],
        "temperature": [22, 35], "weekly_rain": [15, 100],
        "yield_t_ha": 4.1,
        "note": "Check water availability and field drainage before planting.",
    },
    {
        "name": "Maize",
        "seasons": ["Kharif", "Rabi", "Zaid"],
        "soils": ["loamy", "alluvial", "black", "red"],
        "ph": [5.5, 7.5],
        "n": [60, 160], "p": [20, 80], "k": [20, 80],
        "temperature": [18, 32], "weekly_rain": [5, 50],
        "yield_t_ha": 3.5,
        "note": "Avoid waterlogging; confirm that rainfall or irrigation is adequate.",
    },
    {
        "name": "Cotton",
        "seasons": ["Kharif"],
        "soils": ["black", "loamy"],
        "ph": [5.5, 8.0],
        "n": [30, 120], "p": [15, 60], "k": [30, 120],
        "temperature": [21, 35], "weekly_rain": [5, 40],
        "yield_t_ha": 1.8,
        "note": "Black soils can hold water; monitor drainage after heavy rain.",
    },
    {
        "name": "Chickpea",
        "seasons": ["Rabi"],
        "soils": ["black", "sandy", "loamy", "red"],
        "ph": [5.5, 8.0],
        "n": [10, 60], "p": [15, 60], "k": [15, 80],
        "temperature": [15, 30], "weekly_rain": [0, 25],
        "yield_t_ha": 1.2,
        "note": "Excess moisture near flowering can raise disease risk.",
    },
    {
        "name": "Groundnut",
        "seasons": ["Kharif", "Rabi"],
        "soils": ["sandy", "loamy", "red"],
        "ph": [5.5, 7.5],
        "n": [10, 60], "p": [20, 80], "k": [20, 100],
        "temperature": [20, 32], "weekly_rain": [5, 40],
        "yield_t_ha": 1.7,
        "note": "Loose, well-drained soil is useful for peg and pod development.",
    },
    {
        "name": "Sorghum (Jowar)",
        "seasons": ["Kharif", "Rabi"],
        "soils": ["black", "red", "loamy"],
        "ph": [5.0, 8.5],
        "n": [20, 100], "p": [10, 50], "k": [20, 80],
        "temperature": [22, 36], "weekly_rain": [0, 30],
        "yield_t_ha": 1.3,
        "note": "A comparatively drought-tolerant cereal; verify local variety timing.",
    },
    {
        "name": "Soybean",
        "seasons": ["Kharif"],
        "soils": ["black", "loamy"],
        "ph": [5.5, 7.5],
        "n": [20, 100], "p": [20, 80], "k": [20, 100],
        "temperature": [20, 32], "weekly_rain": [10, 45],
        "yield_t_ha": 1.6,
        "note": "Use a locally recommended variety and avoid standing water.",
    },
    {
        "name": "Wheat",
        "seasons": ["Rabi"],
        "soils": ["loamy", "clay", "alluvial"],
        "ph": [6.0, 7.5],
        "n": [40, 140], "p": [20, 70], "k": [20, 80],
        "temperature": [10, 25], "weekly_rain": [0, 25],
        "yield_t_ha": 3.4,
        "note": "The next-week forecast is not a substitute for the full-season outlook.",
    },
]


class RecommendationInputError(Exception):
    pass


def _number(value, label, low, high):
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RecommendationInputError(f"Enter a valid number for {label}.") from exc
    if not isfinite(result) or result < low or result > high:
        raise RecommendationInputError(f"{label} must be between {low} and {high}.")
    return result


def _range_score(value, bounds, slack):
    low, high = bounds
    if low <= value <= high:
        return 100.0
    distance = low - value if value < low else value - high
    return max(0.0, 100.0 * (1 - distance / slack))


def _score_crop(crop, data, weather):
    season_score = 100.0 if data["season"] in crop["seasons"] else 0.0
    soil_score = 100.0 if data["soilType"] in crop["soils"] else 25.0
    ph_score = _range_score(data["ph"], crop["ph"], 1.5)
    nutrient_score = sum(
        _range_score(data[key], crop[key], max(20, crop[key][1] - crop[key][0]))
        for key in ("n", "p", "k")
    ) / 3

    current_temp = weather.get("current", {}).get("temperatureC")
    rain_week = weather.get("next7Days", {}).get("precipitationMm")
    temp_score = _range_score(current_temp, crop["temperature"], 10) if current_temp is not None else 50
    rain_score = _range_score(rain_week, crop["weekly_rain"], 25) if rain_week is not None else 50

    # Weather is deliberately a smaller, short-term signal. It is not seasonal climate data.
    score = (
        season_score * 0.20
        + soil_score * 0.15
        + ph_score * 0.25
        + nutrient_score * 0.25
        + temp_score * 0.10
        + rain_score * 0.05
    )
    return round(score)


def recommend_crops(payload):
    try:
        season = str(payload.get("season", "")).strip()
        soil_type = str(payload.get("soilType", "")).strip().lower()
        area = _number(payload.get("areaAcres"), "land area", 0.01, 100000)
        nutrients = {
            "n": _number(payload.get("nitrogen"), "nitrogen", 0, 500),
            "p": _number(payload.get("phosphorus"), "phosphorus", 0, 500),
            "k": _number(payload.get("potassium"), "potassium", 0, 500),
            "ph": _number(payload.get("ph"), "soil pH", 0, 14),
        }
    except AttributeError as exc:
        raise RecommendationInputError("Farm details are missing.") from exc

    if season not in {"Kharif", "Rabi", "Zaid"}:
        raise RecommendationInputError("Choose Kharif, Rabi, or Zaid season.")
    if soil_type not in {"black", "red", "alluvial", "sandy", "clay", "loamy"}:
        raise RecommendationInputError("Choose a supported soil texture.")

    moisture = payload.get("soilMoisture")
    if moisture not in (None, ""):
        nutrients["soilMoisture"] = _number(moisture, "soil moisture", 0, 100)

    weather = payload.get("weather") if isinstance(payload.get("weather"), dict) else {}
    ranked = []
    for crop in CROPS:
        score = _score_crop(crop, {**nutrients, "season": season, "soilType": soil_type}, weather)
        hectares = area * ACRES_TO_HECTARES
        estimate = crop["yield_t_ha"] * hectares * (0.65 + 0.35 * score / 100)
        ranked.append(
            {
                "name": crop["name"],
                "suitability": score,
                "estimatedYieldTonnes": round(estimate, 2),
                "baselineYieldTonnesPerHectare": crop["yield_t_ha"],
                "reasons": _reasons(crop, nutrients, season, soil_type, weather),
                "note": crop["note"],
            }
        )

    ranked.sort(key=lambda item: item["suitability"], reverse=True)
    warnings = _weather_advice(weather)
    if "soilMoisture" in nutrients:
        if nutrients["soilMoisture"] < 25:
            warnings.append("The entered soil-moisture reading is low; check the crop stage and irrigation needs.")
        elif nutrients["soilMoisture"] > 80:
            warnings.append("The entered soil-moisture reading is high; check drainage and confirm the sensor or report units.")

    return {
        "recommendations": ranked[:3],
        "warnings": warnings,
        "method": "Explainable crop-profile match (prototype)",
        "yieldNote": "Yield figures are rough planning estimates from broad crop baselines, adjusted by the match score. They are not a trained or locally validated yield model.",
    }


def _reasons(crop, nutrients, season, soil_type, weather):
    reasons = []
    reasons.append("Season fits" if season in crop["seasons"] else "Season differs from this crop profile")
    reasons.append("Soil texture fits" if soil_type in crop["soils"] else "Soil texture is a weaker match")
    if crop["ph"][0] <= nutrients["ph"] <= crop["ph"][1]:
        reasons.append("Soil pH is within the profile range")
    else:
        reasons.append("Soil pH is outside the profile range")

    matches = sum(crop[key][0] <= nutrients[key] <= crop[key][1] for key in ("n", "p", "k"))
    reasons.append(f"{matches} of 3 NPK readings fit broad profile ranges")

    temp = weather.get("current", {}).get("temperatureC")
    if temp is not None:
        reasons.append("Current temperature is suitable" if crop["temperature"][0] <= temp <= crop["temperature"][1] else "Current temperature is outside the broad range")
    return reasons


def _weather_advice(weather):
    notes = []
    current = weather.get("current", {})
    upcoming = weather.get("next7Days", {})
    temp = current.get("temperatureC")
    rain = upcoming.get("precipitationMm")
    if temp is not None and temp >= 35:
        notes.append("High daytime heat is forecast or observed; check local heat and irrigation advisories.")
    if rain is not None and rain < 2:
        notes.append("Very little rain is forecast for the next 7 days; review irrigation plans.")
    elif rain is not None and rain >= 70:
        notes.append("Heavy rain is forecast in the next 7 days; check field drainage and local alerts.")
    notes.append("The weather snapshot covers the next 7 days only. Use seasonal forecasts and local agricultural guidance for planting decisions.")
    return notes
