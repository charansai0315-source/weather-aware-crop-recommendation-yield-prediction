"""HTTP API for crop ranking and historical yield estimation."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from app.train import ARTIFACTS, train_crop_model, train_yield_model

app = FastAPI(title="Fieldwise ML", version="1.0.0")

CLASSIFIER_PATH = ARTIFACTS / "crop_classifier.joblib"
PROFILES_PATH = ARTIFACTS / "crop_profiles.joblib"
YIELD_PATH = ARTIFACTS / "yield_regressor.joblib"
COVERAGE_PATH = ARTIFACTS / "yield_coverage.json"
METRICS_PATH = ARTIFACTS / "training_metrics.json"


class RecommendationInput(BaseModel):
    location: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    season: str
    soilType: str
    nitrogen: float = Field(ge=0, le=500)
    phosphorus: float = Field(ge=0, le=500)
    potassium: float = Field(ge=0, le=500)
    ph: float = Field(ge=0, le=14)
    areaAcres: float = Field(gt=0, le=100000)
    soilMoisture: float | None = Field(default=None, ge=0, le=100)
    temperatureC: float | None = None
    humidityPct: float | None = Field(default=None, ge=0, le=100)
    rainfallMm: float | None = Field(default=None, ge=0)


def load_models() -> tuple[Any, dict, Any, pd.DataFrame, dict]:
    if not (CLASSIFIER_PATH.exists() and PROFILES_PATH.exists() and YIELD_PATH.exists()):
        crop_metrics = train_crop_model()
        yield_metrics = train_yield_model()
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        METRICS_PATH.write_text(json.dumps({"cropModel": crop_metrics, "yieldModel": yield_metrics}, indent=2))
    classifier = joblib.load(CLASSIFIER_PATH)
    profiles = joblib.load(PROFILES_PATH)
    yield_model = joblib.load(YIELD_PATH)
    coverage = pd.read_json(COVERAGE_PATH) if COVERAGE_PATH.exists() else pd.DataFrame()
    metrics = json.loads(METRICS_PATH.read_text()) if METRICS_PATH.exists() else {}
    return classifier, profiles, yield_model, coverage, metrics


classifier, crop_profiles, yield_model, yield_coverage, metrics = load_models()


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "cropModelLoaded": classifier is not None, "yieldModelLoaded": yield_model is not None}


ALIASES = {
    "chickpea": ["gram", "chickpea", "bengal gram"],
    "kidneybeans": ["rajmash", "rajmash kholar", "kidney bean"],
    "pigeonpeas": ["arhar/tur", "arhar", "tur", "pigeon pea"],
    "mothbeans": ["moth", "moth bean"],
    "mungbean": ["moong(green gram)", "green gram", "mung bean"],
    "blackgram": ["urd", "black gram", "urad"],
    "lentil": ["masoor", "lentil"],
    "maize": ["maize", "corn"],
    "rice": ["rice"],
    "cotton": ["cotton(lint)", "cotton", "kapas"],
    "jute": ["jute"],
    "coffee": ["coffee"],
    "grapes": ["grapes"],
    "mango": ["mango"],
    "banana": ["banana"],
    "watermelon": ["watermelon"],
    "muskmelon": ["muskmelon"],
    "orange": ["orange"],
    "papaya": ["papaya"],
    "coconut": ["coconut"],
    "pomegranate": ["pome granet", "pomegranate"],
    "apple": ["apple"],
}

STATE_ALIASES = {
    "andhra pradesh": "Andhra Pradesh", "telangana": "Telangana", "tamil nadu": "Tamil Nadu",
    "karnataka": "Karnataka", "maharashtra": "Maharashtra", "uttar pradesh": "Uttar Pradesh",
    "madhya pradesh": "Madhya Pradesh", "gujarat": "Gujarat", "rajasthan": "Rajasthan",
    "punjab": "Punjab", "haryana": "Haryana", "west bengal": "West Bengal", "odisha": "Orissa",
    "orissa": "Orissa", "bihar": "Bihar", "kerala": "Kerala", "assam": "Assam",
    "chhattisgarh": "Chhattisgarh", "jharkhand": "Jharkhand", "uttarakhand": "Uttaranchal",
    "himachal pradesh": "Himachal Pradesh", "jammu and kashmir": "Jammu and Kashmir",
}


def season_for_yield(season: str) -> str:
    aliases = {"zaid": "Summer", "summer": "Summer", "kharif": "Kharif", "rabi": "Rabi"}
    return aliases.get(season.strip().lower(), season.strip().title())


def yield_name(crop: str) -> str | None:
    aliases = ALIASES.get(crop.strip().lower(), [crop.strip()])
    known = set(yield_coverage["crop"].astype(str).str.casefold()) if not yield_coverage.empty else set()
    for alias in aliases:
        if alias.casefold() in known:
            return alias
    return None


def explain(crop: str, values: dict[str, float]) -> list[str]:
    key = crop.casefold()
    center = crop_profiles["centers"].get(key)
    ranges = crop_profiles["ranges"].get(key)
    if not center or not ranges:
        return ["This crop ranked highest from the nutrient, pH, temperature and humidity inputs in the training dataset."]
    distances = []
    for feature, value in values.items():
        scale = max(float(crop_profiles["scale"].get(feature, 1.0)), 1e-6)
        distance = abs(value - float(center[feature])) / scale
        lower, upper = ranges[feature]
        in_range = float(lower) <= value <= float(upper)
        label = {"N": "Nitrogen", "P": "Phosphorus", "K": "Potassium", "temperature": "Temperature", "humidity": "Humidity", "ph": "pH"}[feature]
        distances.append((distance, f"{label} is within the middle range seen for this crop in the training data." if in_range else f"{label} differs from the typical training range; confirm with local agronomy advice."))
    distances.sort(key=lambda row: row[0])
    return [message for _, message in distances[:2]]


@app.post("/recommend")
def recommend(payload: RecommendationInput,
              x_ml_service_token: str | None = Header(default=None, alias="X-ML-Service-Token")) -> dict:
    expected_token = os.getenv("ML_SERVICE_TOKEN", "").strip()
    if expected_token and not secrets.compare_digest(x_ml_service_token or "", expected_token):
        raise HTTPException(status_code=401, detail="Unauthorized model service request.")

    weather_features = {
        "temperature": payload.temperatureC,
        "humidity": payload.humidityPct,
    }
    warnings: list[str] = []
    feature_values = {
        "N": payload.nitrogen,
        "P": payload.phosphorus,
        "K": payload.potassium,
        "temperature": weather_features["temperature"] if weather_features["temperature"] is not None else crop_profiles["medians"]["temperature"],
        "humidity": weather_features["humidity"] if weather_features["humidity"] is not None else crop_profiles["medians"]["humidity"],
        "ph": payload.ph,
    }
    if payload.temperatureC is None or payload.humidityPct is None:
        warnings.append("Some live weather readings were missing; the model filled them with training-set medians.")

    x = pd.DataFrame([feature_values], columns=["N", "P", "K", "temperature", "humidity", "ph"])
    scores = classifier.predict_proba(x)[0]
    ranked = sorted(zip(classifier.classes_, scores), key=lambda item: item[1], reverse=True)[:3]
    state_name = STATE_ALIASES.get(payload.state.strip().casefold(), payload.state.strip())
    season_name = season_for_yield(payload.season)
    area_ha = payload.areaAcres * 0.40468564224
    recommendations = []

    for crop, score in ranked:
        crop_label = str(crop).replace("_", " ").title()
        historical_crop = yield_name(str(crop))
        yield_total = None
        yield_per_hectare = None
        yield_details = None
        note = "The crop ranking is a machine-learning result, not a guaranteed field outcome."
        if historical_crop:
            row = yield_coverage[
                (yield_coverage["state"].astype(str).str.casefold() == state_name.casefold())
                & (yield_coverage["crop"].astype(str).str.casefold() == historical_crop.casefold())
                & (yield_coverage["season"].astype(str).str.casefold() == season_name.casefold())
            ] if not yield_coverage.empty else pd.DataFrame()
            if not row.empty:
                estimate = max(float(yield_model.predict(pd.DataFrame([{
                    "state": state_name, "crop": historical_crop, "season": season_name,
                    "year": int(metrics.get("yieldModel", {}).get("lastYear", 2015)),
                }]))[0]), 0.0)
                yield_per_hectare = round(estimate, 2)
                yield_total = round(estimate * area_ha, 2)
                yield_details = {
                    "state": state_name,
                    "season": season_name,
                    "sourceRecords": int(row.iloc[0]["rows"]),
                    "latestYear": int(row.iloc[0]["latestYear"]),
                }
                note = f"Historical {state_name} {season_name} records exist for this crop; this is a broad benchmark, not a farm-specific forecast."
            else:
                note = "The historical dataset has no matching state, crop and season records, so no yield estimate is shown."
        else:
            note = "No compatible historical production category was found, so no yield estimate is shown."
        recommendations.append({
            "name": crop_label,
            "suitability": int(round(float(score) * 100)),
            "estimatedYieldTonnes": yield_total,
            "yieldTonnesPerHectare": yield_per_hectare,
            "yieldCoverage": yield_details,
            "reasons": explain(str(crop), feature_values),
            "note": note,
        })

    if payload.soilType:
        warnings.append("Soil texture and season are captured for context, but the crop classifier dataset does not include those fields.")
    warnings.append("The model vote-share score is a relative ranking, not a calibrated probability or planting guarantee.")
    warnings.append("Crop training records contain broad nutrient and climate profiles; they are not locally validated for your specific field.")
    if payload.rainfallMm is not None:
        warnings.append("The next-7-day rainfall total is shown in the weather panel but is not compared with crop-cycle rainfall in the training data.")
    yield_info = metrics.get("yieldModel", {})
    yield_mae = yield_info.get("temporalHoldoutMaeTonnesPerHectare")
    if yield_mae is not None and float(yield_mae) > 10:
        warnings.append(f"Yield validation error was high ({float(yield_mae):.1f} tonnes/ha on 2013–2015 holdout data); treat historical yield figures as highly uncertain.")
    yield_quality = (
        f" Temporal holdout MAE was {float(yield_mae):.1f} tonnes/ha on 2013–2015 records."
        if yield_mae is not None else ""
    )
    return {
        "method": "Python ML · Random Forest",
        "yieldNote": f"Yield estimates are historical district benchmarks from {yield_info.get('firstYear', '—')}–{yield_info.get('lastYear', '—')} records. They are not current-season predictions; no estimate is shown without matching state/crop/season records.{yield_quality} The validation error means these numbers should not guide planting or financial decisions.",
        "modelMetrics": metrics.get("cropModel", {}),
        "yieldMetrics": yield_info,
        "recommendations": recommendations,
        "warnings": warnings,
    }
