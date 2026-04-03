from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Driver Service")

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

VALID_ZONES = {"A", "B", "C", "D"}
DEFAULT_DRIVERS = {"A": 15, "B": 25, "C": 10, "D": 30}


class DriverUpdate(BaseModel):
    zone: str
    driver_count: int


@app.get("/drivers/{zone}")
def get_drivers(zone: str):
    if zone not in VALID_ZONES:
        raise HTTPException(status_code=400, detail="Invalid zone")

    cached = r.get(f"drivers:{zone}")
    if cached:
        return {"zone": zone, "driver_count": int(cached), "source": "redis"}

    # Default if Redis is empty (system just started)
    default = DEFAULT_DRIVERS.get(zone, 20)
    r.setex(f"drivers:{zone}", 60, default)
    return {"zone": zone, "driver_count": default, "source": "default"}


@app.post("/drivers")
def update_drivers(update: DriverUpdate):
    if update.zone not in VALID_ZONES:
        raise HTTPException(status_code=400, detail="Invalid zone")
    if update.driver_count < 0:
        raise HTTPException(status_code=400, detail="driver_count cannot be negative")

    r.setex(f"drivers:{update.zone}", 60, update.driver_count)
    return {"status": "updated", "zone": update.zone, "driver_count": update.driver_count}


@app.get("/health")
def health():
    return {"status": "ok", "service": "driver-service"}