"""
Trains XGBoost on the real dynamic pricing dataset.
Place your CSV as: pricing-engine/rideshare_data.csv
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
import pickle
import os

# --- Mappings ---
TIME_MAP = {"Morning": 9, "Afternoon": 14, "Evening": 18, "Night": 23}
ZONE_MAP = {"Urban": 0, "Suburban": 1, "Rural": 2}
VEHICLE_MAP = {"Economy": 0, "Premium": 1}
LOYALTY_MAP = {"Regular": 0, "Silver": 1, "Gold": 2}

BASE_PRICE = 120.0


def load_and_prepare(csv_path):
    df = pd.read_csv(csv_path)
    df = df.dropna()

    df["hour"] = df["Time_of_Booking"].map(TIME_MAP)
    df["zone"] = df["Location_Category"].map(ZONE_MAP)
    df["vehicle_type"] = df["Vehicle_Type"].map(VEHICLE_MAP)
    df["loyalty"] = df["Customer_Loyalty_Status"].map(LOYALTY_MAP)

    # Normalize riders/drivers into a demand score (riders per driver)
    df["demand_score"] = df["Number_of_Riders"] / df["Number_of_Drivers"].replace(0, 1)
    df["demand_score"] = df["demand_score"].clip(0.5, 5.0)

    df["driver_count"] = df["Number_of_Drivers"]
    df["ride_duration"] = df["Expected_Ride_Duration"]
    df["num_past_rides"] = df["Number_of_Past_Rides"]
    df["avg_rating"] = df["Average_Ratings"]

    # Target: actual price
    df["price"] = df["Historical_Cost_of_Ride"]

    # Also compute multiplier for reference
    df["price_multiplier"] = (df["price"] / BASE_PRICE).clip(1.0, 2.5)

    return df


def generate_synthetic_data(n=5000):
    """Fallback if no CSV found."""
    np.random.seed(42)
    hours = np.random.randint(0, 24, n)
    demand_score = np.random.uniform(0.5, 2.0, n)
    driver_count = np.random.randint(1, 50, n)
    is_raining = np.random.randint(0, 2, n)
    zone = np.random.randint(0, 3, n)
    vehicle_type = np.random.randint(0, 2, n)
    loyalty = np.random.randint(0, 3, n)
    ride_duration = np.random.randint(10, 170, n)
    num_past_rides = np.random.randint(0, 100, n)
    avg_rating = np.random.uniform(3.5, 5.0, n)

    price = (
        BASE_PRICE
        + 0.3 * demand_score * BASE_PRICE
        + 0.2 * is_raining * BASE_PRICE
        - 0.01 * driver_count * BASE_PRICE
        + 1.5 * ride_duration
        + 10 * vehicle_type
        + 5 * loyalty
    ).clip(BASE_PRICE, BASE_PRICE * 2.5)

    return pd.DataFrame({
        "hour": hours,
        "demand_score": demand_score,
        "driver_count": driver_count,
        "is_raining": is_raining,
        "zone": zone,
        "vehicle_type": vehicle_type,
        "loyalty": loyalty,
        "ride_duration": ride_duration,
        "num_past_rides": num_past_rides,
        "avg_rating": avg_rating,
        "price": price
    })


FEATURES = [
    "hour", "demand_score", "driver_count", "zone",
    "vehicle_type", "loyalty", "ride_duration",
    "num_past_rides", "avg_rating"
]
# Note: is_raining kept as bonus feature in main.py inference,
# not in dataset (dataset has no rain column) so excluded from training


def train():
    csv_path = "dynamic_pricing.csv"

    if os.path.exists(csv_path):
        print(f"Loading real dataset from {csv_path}...")
        df = load_and_prepare(csv_path)
        # is_raining not in real dataset — set to 0 for training
        df["is_raining"] = 0
        print(f"Dataset loaded: {len(df)} rows")
    else:
        print("No CSV found — using synthetic data.")
        print("Place your CSV as rideshare_data.csv in pricing-engine/ for real training.")
        df = generate_synthetic_data()
        df["is_raining"] = np.random.randint(0, 2, len(df))

    all_features = FEATURES + ["is_raining"]
    X = df[all_features]
    y = df["price"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    mae = mean_absolute_error(y_test, preds)
    print(f"MAE: ₹{mae:.2f}")
    print(f"Sample predictions: {preds[:5].round(2)}")
    print(f"Sample actuals:     {y_test.values[:5].round(2)}")

    with open("model.pkl", "wb") as f:
        pickle.dump(model, f)

    # Save feature list so main.py always uses the same order
    with open("features.pkl", "wb") as f:
        pickle.dump(all_features, f)

    print("model.pkl and features.pkl saved.")


if __name__ == "__main__":
    train()