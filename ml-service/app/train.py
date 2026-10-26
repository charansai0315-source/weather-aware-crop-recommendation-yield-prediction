"""Train crop ranking and historical yield models from the bundled public data."""

from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesRegressor, RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

CROP_FEATURES = ["N", "P", "K", "temperature", "humidity", "ph"]
YIELD_CATEGORICAL = ["state", "crop", "season"]
YIELD_NUMERIC = ["year"]


def train_crop_model() -> dict:
    path = RAW / "Crop_recommendation.csv"
    data = pd.read_csv(path)
    required = set(CROP_FEATURES + ["label"])
    if not required.issubset(data.columns):
        raise ValueError(f"Crop training data is missing columns: {sorted(required - set(data.columns))}")
    data = data[CROP_FEATURES + ["label"]].dropna().copy()
    data["label"] = data["label"].astype(str).str.strip().str.lower()
    x = data[CROP_FEATURES].astype(float)
    y = data["label"]
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.2, random_state=42, stratify=y
    )
    validation = RandomForestClassifier(
        n_estimators=220, min_samples_leaf=2, class_weight="balanced_subsample",
        random_state=42, n_jobs=-1,
    )
    validation.fit(x_train, y_train)
    predicted = validation.predict(x_test)
    metrics = {
        "rows": int(len(data)),
        "classes": int(y.nunique()),
        "holdoutAccuracy": round(float(accuracy_score(y_test, predicted)), 4),
        "holdoutMacroF1": round(float(f1_score(y_test, predicted, average="macro")), 4),
        "holdoutFraction": 0.2,
        "randomSeed": 42,
    }
    model = RandomForestClassifier(
        n_estimators=300, min_samples_leaf=2, class_weight="balanced_subsample",
        random_state=42, n_jobs=-1,
    )
    model.fit(x, y)
    joblib.dump(model, ARTIFACTS / "crop_classifier.joblib", compress=3)
    centers = data.groupby("label")[CROP_FEATURES].median().to_dict(orient="index")
    bounds = data.groupby("label")[CROP_FEATURES].quantile([0.1, 0.9]).unstack()
    ranges = {}
    for crop in y.unique():
        ranges[str(crop).strip().lower()] = {
            feature: [float(bounds.loc[crop, (feature, 0.1)]), float(bounds.loc[crop, (feature, 0.9)])]
            for feature in CROP_FEATURES
        }
    global_scale = data[CROP_FEATURES].std().replace(0, 1).to_dict()
    medians = {feature: float(data[feature].median()) for feature in CROP_FEATURES}
    joblib.dump({"centers": centers, "ranges": ranges, "scale": global_scale, "medians": medians}, ARTIFACTS / "crop_profiles.joblib", compress=3)
    return metrics


def train_yield_model() -> dict:
    path = RAW / "india_crop_production.csv"
    data = pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    required = {"State_Name", "Crop_Year", "Season", "Crop", "Area", "Production"}
    if not required.issubset(data.columns):
        raise ValueError(f"Yield training data is missing columns: {sorted(required - set(data.columns))}")
    data = data[list(required)].copy()
    data["Area"] = pd.to_numeric(data["Area"], errors="coerce")
    data["Production"] = pd.to_numeric(data["Production"], errors="coerce")
    data["Crop_Year"] = pd.to_numeric(data["Crop_Year"], errors="coerce")
    data = data.dropna(subset=["State_Name", "Season", "Crop", "Area", "Production", "Crop_Year"])
    data = data[(data["Area"] > 0) & (data["Production"] >= 0)]
    data["yield_t_ha"] = data["Production"] / data["Area"]
    data = data[np.isfinite(data["yield_t_ha"]) & (data["yield_t_ha"] > 0)]
    data["State_Name"] = data["State_Name"].astype(str).str.strip()
    data["Season"] = data["Season"].astype(str).str.strip()
    data["Crop"] = data["Crop"].astype(str).str.strip()
    # Aggregate noisy individual district rows to robust historical district-group medians.
    grouped = (
        data.groupby(["State_Name", "Crop", "Season", "Crop_Year"], as_index=False)
        .agg(yield_t_ha=("yield_t_ha", "median"), records=("yield_t_ha", "size"))
    )
    # Drop extreme ratios caused by reporting/unit errors, while retaining diverse crop types.
    limits = grouped.groupby("Crop")["yield_t_ha"].quantile(0.995)
    grouped = grouped[grouped.apply(lambda row: row["yield_t_ha"] <= limits.get(row["Crop"], np.inf), axis=1)]
    grouped = grouped.rename(columns={"State_Name": "state", "Crop": "crop", "Season": "season", "Crop_Year": "year"})
    grouped["year"] = grouped["year"].astype(float)
    last_year = int(grouped["year"].max())
    first_year = int(grouped["year"].min())
    historical_train = grouped[grouped["year"] <= last_year - 3]
    historical_test = grouped[grouped["year"] > last_year - 3]

    def pipeline() -> Pipeline:
        preprocess = ColumnTransformer([
            ("categorical", OneHotEncoder(handle_unknown="ignore", min_frequency=2), YIELD_CATEGORICAL),
            ("year", StandardScaler(), YIELD_NUMERIC),
        ])
        return Pipeline([
            ("features", preprocess),
            ("model", ExtraTreesRegressor(
                n_estimators=140, min_samples_leaf=2, max_features=0.9,
                random_state=42, n_jobs=-1,
            )),
        ])

    x_train = historical_train[YIELD_CATEGORICAL + YIELD_NUMERIC]
    y_train = historical_train["yield_t_ha"]
    validation = pipeline()
    validation.fit(x_train, y_train)
    validation_pred = np.maximum(validation.predict(historical_test[YIELD_CATEGORICAL + YIELD_NUMERIC]), 0)
    metrics = {
        "sourceRows": int(len(data)),
        "trainingGroups": int(len(grouped)),
        "stateCount": int(grouped["state"].nunique()),
        "cropCount": int(grouped["crop"].nunique()),
        "firstYear": first_year,
        "lastYear": last_year,
        "temporalHoldoutMaeTonnesPerHectare": round(float(mean_absolute_error(historical_test["yield_t_ha"], validation_pred)), 3),
        "temporalHoldoutYears": sorted(int(year) for year in historical_test["year"].unique()),
        "yieldUnit": "tonnes per hectare",
    }
    final_model = pipeline()
    final_model.fit(grouped[YIELD_CATEGORICAL + YIELD_NUMERIC], grouped["yield_t_ha"])
    joblib.dump(final_model, ARTIFACTS / "yield_regressor.joblib", compress=3)
    coverage = (
        grouped.groupby(["state", "crop", "season"])
        .agg(rows=("yield_t_ha", "size"), medianYield=("yield_t_ha", "median"), latestYear=("year", "max"))
        .reset_index()
    )
    coverage.to_json(ARTIFACTS / "yield_coverage.json", orient="records")
    return metrics


if __name__ == "__main__":
    summary = {"cropModel": train_crop_model(), "yieldModel": train_yield_model()}
    (ARTIFACTS / "training_metrics.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
