# API Contracts

Base URL (via Nginx gateway): http://localhost:80
Direct service URLs for local testing also listed.

---

## POST /price
Service: pricing-engine (direct: http://localhost:8001)

Request:
{
  "zone": "A",       // string: A, B, C, or D
  "hour": 18,        // int: 0–23
  "is_raining": 1    // int: 0 or 1
}

Response:
{
  "price": 320.50,
  "explanation": {
    "base_price": "₹120",
    "demand_effect": "+₹45.0",
    "rain_effect": "+₹24.0",
    "low_driver_effect": "+₹18.0",
    "peak_hour_effect": "+₹12.0",
    "final_price": "₹320.5"
  },
  "competitor_price": 290.0
}

---

## GET /demand/{zone}
Service: demand-service (direct: http://localhost:8002)

Response:
{ "zone": "A", "demand_score": 1.5, "source": "redis" }

## POST /demand
Request: { "zone": "A", "demand_score": 1.8 }
Response: { "status": "updated", "zone": "A", "demand_score": 1.8 }

---

## GET /drivers/{zone}
Service: driver-service (direct: http://localhost:8003)

Response:
{ "zone": "A", "driver_count": 12, "source": "redis" }

## POST /drivers
Request: { "zone": "A", "driver_count": 8 }
Response: { "status": "updated", "zone": "A", "driver_count": 8 }

---

## GET /compete/{zone}
Service: competitor-service (direct: http://localhost:8005)

Response:
{
  "zone": "A",
  "competitor_price": 270.0,
  "cheapest_competitor": "rapido",
  "all_prices": { "uber": 310, "ola": 290, "rapido": 270 }
}

---

## POST /log  (written by Person B — Analytics Service)
## GET /insights  (written by Person B — Analytics Service)
## POST /ride  (written by Person B — Ride Service)