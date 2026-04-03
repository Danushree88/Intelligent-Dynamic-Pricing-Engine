from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import redis
import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Demand Service")

r = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

def get_db():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=os.getenv("POSTGRES_PORT", 5432),
        dbname=os.getenv("POSTGRES_DB", "pricingdb"),
        user=os.getenv("POSTGRES_USER", "pricinguser"),
        password=os.getenv("POSTGRES_PASSWORD", "pricingpass")
    )

VALID_ZONES = {"A", "B", "C", "D"}
DEFAULT_DEMAND = {"A": 1.2, "B": 1.0, "C": 1.5, "D": 0.8}


class DemandUpdate(BaseModel):
    zone: str
    demand_score: float


@app.get("/demand/{zone}")
def get_demand(zone: str):
    if zone not in VALID_ZONES:
        raise HTTPException(status_code=400, detail="Invalid zone")

    # Try Redis first
    cached = r.get(f"demand:{zone}")
    if cached:
        return {"zone": zone, "demand_score": float(cached), "source": "redis"}

    # Fall back to PostgreSQL
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT demand_score FROM demand_data WHERE zone = %s ORDER BY updated_at DESC LIMIT 1", (zone,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            score = float(row[0])
            r.setex(f"demand:{zone}", 30, score)  # cache for 30s
            return {"zone": zone, "demand_score": score, "source": "postgres"}
    except Exception as e:
        pass  # fall through to default

    # Default fallback
    return {"zone": zone, "demand_score": DEFAULT_DEMAND.get(zone, 1.0), "source": "default"}


@app.post("/demand")
def update_demand(update: DemandUpdate):
    if update.zone not in VALID_ZONES:
        raise HTTPException(status_code=400, detail="Invalid zone")

    # Write to Redis (fast, 60s TTL)
    r.setex(f"demand:{update.zone}", 60, update.demand_score)

    # Write to PostgreSQL (persistent)
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO demand_data (zone, demand_score) VALUES (%s, %s)",
            (update.zone, update.demand_score)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        pass  # Redis write succeeded, DB is secondary

    return {"status": "updated", "zone": update.zone, "demand_score": update.demand_score}


@app.get("/health")
def health():
    return {"status": "ok", "service": "demand-service"}