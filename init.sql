-- Tables created by Person A for the shared DB

CREATE TABLE IF NOT EXISTS demand_data (
    id SERIAL PRIMARY KEY,
    zone VARCHAR(1) NOT NULL,
    demand_score FLOAT NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pricing_logs (
    id SERIAL PRIMARY KEY,
    zone VARCHAR(1),
    hour INT,
    is_raining INT,
    demand_score FLOAT,
    driver_count INT,
    final_price FLOAT,
    competitor_price FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Person B adds rides table in their init
CREATE TABLE IF NOT EXISTS rides (
    id SERIAL PRIMARY KEY,
    zone VARCHAR(1),
    hour INT,
    is_raining INT,
    price FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Seed some default demand data
INSERT INTO demand_data (zone, demand_score) VALUES
    ('A', 1.2), ('B', 1.0), ('C', 1.5), ('D', 0.8);