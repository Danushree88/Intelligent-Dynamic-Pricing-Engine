from fastapi import FastAPI, HTTPException

app = FastAPI(title="Competitor Service")

# Mock competitor price table — simulates Ola/Rapido pricing
# In a real system this would scrape or call an external API
COMPETITOR_PRICES = {
    "A": {"uber": 310, "ola": 290, "rapido": 270},
    "B": {"uber": 200, "ola": 185, "rapido": 175},
    "C": {"uber": 420, "ola": 400, "rapido": 380},
    "D": {"uber": 160, "ola": 150, "rapido": 140},
}


@app.get("/compete/{zone}")
def get_competitor_price(zone: str):
    if zone not in COMPETITOR_PRICES:
        raise HTTPException(status_code=400, detail="Invalid zone")

    prices = COMPETITOR_PRICES[zone]
    # Return the lowest competitor price as the benchmark
    cheapest_competitor = min(prices, key=prices.get)
    return {
        "zone": zone,
        "competitor_price": prices[cheapest_competitor],
        "cheapest_competitor": cheapest_competitor,
        "all_prices": prices
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "competitor-service"}