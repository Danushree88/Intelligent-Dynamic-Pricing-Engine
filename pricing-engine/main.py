from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pickle
import numpy as np
import pandas as pd
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Pricing Engine")

BASE_PRICE = float(os.getenv("BASE_PRICE", 120))
SURGE_CAP = float(os.getenv("SURGE_CAP_MULTIPLIER", 2.5))
DEMAND_SERVICE_URL = os.getenv("DEMAND_SERVICE_URL", "http://demand-service:8002")
DRIVER_SERVICE_URL = os.getenv("DRIVER_SERVICE_URL", "http://driver-service:8003")
COMPETITOR_SERVICE_URL = os.getenv("COMPETITOR_SERVICE_URL", "http://competitor-service:8005")

# Load model and feature list at startup
with open("model.pkl", "rb") as f:
    model = pickle.load(f)

with open("features.pkl", "rb") as f:
    FEATURES = pickle.load(f)

# --- Mappings (same as trainer) ---
ZONE_MAP     = {"A": 0, "B": 1, "C": 2, "D": 3}   # A=Urban, B=Suburban, C=Rural, D=Rural2
VEHICLE_MAP  = {"Economy": 0, "Premium": 1}
LOYALTY_MAP  = {"Regular": 0, "Silver": 1, "Gold": 2}
TIME_MAP     = {"Morning": 9, "Afternoon": 14, "Evening": 18, "Night": 23}


class PriceRequest(BaseModel):
    zone: str                       # "A", "B", "C", "D"
    hour: int                       # 0–23 (actual hour OR use time_of_day)
    is_raining: int                 # 0 or 1
    vehicle_type: str = "Economy"   # "Economy" or "Premium"
    loyalty_status: str = "Regular" # "Regular", "Silver", "Gold"
    ride_duration: int = 30         # estimated minutes
    num_past_rides: int = 0         # customer history
    avg_rating: float = 4.0         # driver rating


class PriceResponse(BaseModel):
    price: float
    explanation: dict
    competitor_price: float | None = None


def fetch_demand(zone: str) -> float:
    try:
        r = requests.get(f"{DEMAND_SERVICE_URL}/demand/{zone}", timeout=2)
        return r.json().get("demand_score", 1.0)
    except Exception:
        return 1.0


def fetch_drivers(zone: str) -> int:
    try:
        r = requests.get(f"{DRIVER_SERVICE_URL}/drivers/{zone}", timeout=2)
        return r.json().get("driver_count", 20)
    except Exception:
        return 20


def fetch_competitor_price(zone: str) -> float | None:
    try:
        r = requests.get(f"{COMPETITOR_SERVICE_URL}/compete/{zone}", timeout=2)
        return r.json().get("competitor_price")
    except Exception:
        return None


def explain_price(
    base: float, demand_score: float, driver_count: int,
    is_raining: int, hour: int, vehicle_type: str,
    loyalty: str, ride_duration: int, final_price: float
) -> dict:
    demand_contribution  = round((demand_score - 1.0) * base * 0.3, 2)
    rain_contribution    = round(is_raining * base * 0.15, 2)
    driver_contribution  = round(max(0, (20 - driver_count) / 20) * base * 0.15, 2)
    peak_contribution    = round(base * 0.1, 2) if hour in range(8, 11) or hour in range(17, 20) else 0.0
    vehicle_contribution = round(base * 0.1, 2) if vehicle_type == "Premium" else 0.0
    loyalty_discount     = round(-base * 0.05, 2) if loyalty == "Gold" else (round(-base * 0.02, 2) if loyalty == "Silver" else 0.0)
    duration_contribution = round(ride_duration * 1.5, 2)

    return {
        "base_price":        f"₹{base}",
        "demand_effect":     f"+₹{demand_contribution}",
        "rain_effect":       f"+₹{rain_contribution}",
        "low_driver_effect": f"+₹{driver_contribution}",
        "peak_hour_effect":  f"+₹{peak_contribution}",
        "vehicle_effect":    f"+₹{vehicle_contribution}",
        "loyalty_discount":  f"₹{loyalty_discount}",
        "duration_effect":   f"+₹{duration_contribution}",
        "final_price":       f"₹{round(final_price, 2)}"
    }


@app.post("/price", response_model=PriceResponse)
def get_price(req: PriceRequest):
    # Validate inputs
    if req.zone not in ZONE_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid zone. Use: {list(ZONE_MAP.keys())}")
    if not (0 <= req.hour <= 23):
        raise HTTPException(status_code=400, detail="hour must be 0–23")
    if req.is_raining not in (0, 1):
        raise HTTPException(status_code=400, detail="is_raining must be 0 or 1")
    if req.vehicle_type not in VEHICLE_MAP:
        raise HTTPException(status_code=400, detail="vehicle_type must be Economy or Premium")
    if req.loyalty_status not in LOYALTY_MAP:
        raise HTTPException(status_code=400, detail="loyalty_status must be Regular, Silver, or Gold")

    # Fetch live data from microservices
    demand_score    = fetch_demand(req.zone)
    driver_count    = fetch_drivers(req.zone)
    competitor_price = fetch_competitor_price(req.zone)

    # Build feature vector in exact same order as training
    feature_values = {
        "hour":          req.hour,
        "demand_score":  demand_score,
        "driver_count":  driver_count,
        "zone":          ZONE_MAP[req.zone],
        "vehicle_type":  VEHICLE_MAP[req.vehicle_type],
        "loyalty":       LOYALTY_MAP[req.loyalty_status],
        "ride_duration": req.ride_duration,
        "num_past_rides": req.num_past_rides,
        "avg_rating":    req.avg_rating,
        "is_raining":    req.is_raining,
    }

    X = pd.DataFrame([feature_values])[FEATURES]

    # XGBoost predicts final price directly (not multiplier anymore)
    predicted_price = float(model.predict(X)[0])

    # Apply surge cap
    max_price = BASE_PRICE * SURGE_CAP
    predicted_price = min(predicted_price, max_price)
    predicted_price = max(predicted_price, BASE_PRICE)  # never below base

    # Competitor adjustment: undercut if they're cheaper
    if competitor_price and competitor_price < predicted_price:
        predicted_price = max(predicted_price * 0.95, BASE_PRICE)

    explanation = explain_price(
        BASE_PRICE, demand_score, driver_count,
        req.is_raining, req.hour, req.vehicle_type,
        req.loyalty_status, req.ride_duration, predicted_price
    )

    return PriceResponse(
        price=round(predicted_price, 2),
        explanation=explanation,
        competitor_price=competitor_price
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "pricing-engine"}