"""
ml/synthetic_data.py — Generates realistic synthetic perishable goods sales data.

Replaces the M5 Kaggle dataset so the project runs without any downloads.

Realistic patterns baked in:
  - Weekly seasonality  : Friday/Saturday peak, Monday dip
  - Monthly seasonality : dairy peaks in winter, produce peaks in summer
  - Long-term trend     : slight growth over the 2-year window
  - Promotions          : random ~8% of days, +35% sales boost
  - Price variation     : small weekly fluctuations + promo discounts
  - Noise               : Poisson-distributed (natural for count data)

Output DataFrame columns (same contract as data_loader.py):
  product_id | sale_date | units_sold | price
"""

import numpy as np
import pandas as pd
from datetime import date

# Reproducible randomness
RNG = np.random.default_rng(seed=42)

# Date range: 2 full years of daily data
START_DATE = date(2022, 1, 1)
END_DATE   = date(2023, 12, 31)

# Base daily demand and price per product.
# (base_units_per_day, base_price, winter_boost, summer_boost)
# Tuned so effective avg demand (after seasonal/DOW/trend/promo) lands in 20–150 units/day.
PRODUCT_PROFILES = {
    "FOODS_3_001_CA_1": (116, 2.99, 1.15, 0.90),  # Whole Milk 1L          avg ~130
    "FOODS_3_002_CA_1": ( 54, 1.89, 1.05, 1.10),  # Greek Yogurt 500g      avg ~61
    "FOODS_3_003_CA_1": ( 27, 3.49, 1.10, 0.95),  # Cheddar Cheese 250g    avg ~30
    "FOODS_3_004_CA_1": ( 22, 2.79, 1.12, 0.92),  # Butter 250g            avg ~25
    "FOODS_3_005_CA_1": ( 18, 1.99, 1.05, 1.05),  # Heavy Cream 250ml      avg ~20
    "FOODS_3_006_CA_1": ( 63, 1.49, 0.85, 1.30),  # Tomatoes 1kg           avg ~70
    "FOODS_3_007_CA_1": ( 36, 0.99, 0.80, 1.35),  # Iceberg Lettuce        avg ~40
    "FOODS_3_008_CA_1": ( 27, 2.29, 0.75, 1.45),  # Strawberries 250g      avg ~30
    "FOODS_3_009_CA_1": ( 71, 0.89, 0.90, 1.20),  # Bananas 1kg            avg ~80
    "FOODS_3_010_CA_1": ( 45, 2.49, 0.82, 1.25),  # Baby Spinach 200g      avg ~50
    "FOODS_3_011_CA_1": ( 58, 5.99, 1.00, 1.00),  # Chicken Breast 500g    avg ~65
    "FOODS_3_012_CA_1": ( 34, 4.99, 1.00, 1.05),  # Ground Beef 500g       avg ~38
    "FOODS_3_013_CA_1": ( 20, 7.99, 1.00, 1.10),  # Salmon Fillet 300g     avg ~22
    "FOODS_3_014_CA_1": ( 49, 3.49, 1.05, 0.95),  # Sourdough Bread        avg ~55
    "FOODS_3_015_CA_1": ( 20, 2.99, 1.05, 0.90),  # Croissants 4-pack      avg ~22
    "FOODS_3_016_CA_1": ( 40, 2.49, 1.08, 0.95),  # Orange Juice 1L        avg ~45
    "FOODS_3_017_CA_1": ( 80, 3.29, 1.10, 0.95),  # Eggs 12-pack           avg ~90
    "FOODS_3_018_CA_1": ( 18, 4.49, 1.00, 1.00),  # Sliced Turkey 200g     avg ~20
    "FOODS_3_019_CA_1": ( 18, 2.19, 0.95, 1.10),  # Hummus 200g            avg ~20
    "FOODS_3_020_CA_1": ( 31, 1.79, 0.88, 1.20),  # Bell Peppers 500g      avg ~35
    "FOODS_3_021_CA_1": ( 38, 0.79, 0.85, 1.15),  # Cucumber               avg ~43
    "FOODS_3_022_CA_1": ( 25, 1.29, 0.80, 1.10),  # Avocado                avg ~28
    "FOODS_3_023_CA_1": ( 31, 1.59, 0.85, 1.20),  # Broccoli               avg ~35
    "FOODS_3_024_CA_1": ( 22, 2.09, 0.90, 1.00),  # Mushrooms 250g         avg ~25
    "FOODS_3_025_CA_1": ( 18, 1.99, 1.05, 1.00),  # Cottage Cheese 250g    avg ~20
    "FOODS_3_026_CA_1": ( 20, 1.49, 1.00, 0.95),  # Pita Bread 6-pack      avg ~22
    "FOODS_3_027_CA_1": ( 20, 2.49, 1.08, 0.92),  # Cream Cheese 150g      avg ~22
    "FOODS_3_028_CA_1": ( 20, 1.79, 1.05, 0.95),  # Sour Cream 200g        avg ~22
    "FOODS_3_029_CA_1": ( 22, 3.29, 1.02, 1.05),  # Mozzarella 250g        avg ~25
    "FOODS_3_030_CA_1": ( 18, 2.99, 0.70, 1.40),  # Blueberries 150g       avg ~20
}

# Last N days per product that receive a demand shock (same as trainer holdout window)
SHOCK_DAYS = 7

# Demand events applied to the last SHOCK_DAYS of specific products.
# Values < 1 simulate a supply disruption  → recent sales LOW  → forecast > history → SHORTAGE alert
# Values > 1 simulate a demand surge       → recent sales HIGH → forecast < history → OVERSTOCK alert
DEMAND_EVENTS = {
    "FOODS_3_011_CA_1": 0.28,   # Chicken Breast  — supply disruption
    "FOODS_3_013_CA_1": 0.25,   # Salmon Fillet   — supply chain issue
    "FOODS_3_017_CA_1": 2.10,   # Eggs 12-pack    — holiday surge
    "FOODS_3_001_CA_1": 1.85,   # Whole Milk      — promotional drive
}

# Day-of-week multipliers (0=Mon … 6=Sun)
DOW_MULTIPLIERS = [0.82, 0.85, 0.90, 0.95, 1.18, 1.30, 1.00]

# Month multipliers for "winter products" (dairy, bakery)
WINTER_MONTHS = {12: 1.20, 1: 1.18, 2: 1.12, 11: 1.08, 3: 1.05,
                 4: 1.00, 5: 0.95, 6: 0.90, 7: 0.88, 8: 0.90, 9: 0.95, 10: 1.00}
# Month multipliers for "summer products" (produce, fruit)
SUMMER_MONTHS = {6: 1.25, 7: 1.30, 8: 1.25, 5: 1.10, 9: 1.05,
                 4: 1.00, 10: 0.95, 3: 0.90, 11: 0.88, 2: 0.85, 1: 0.85, 12: 0.88}


def generate_synthetic_data() -> pd.DataFrame:
    """
    Generate 2 years of daily sales for all 30 products.
    Returns a DataFrame with columns: product_id, sale_date, units_sold, price
    """
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    all_rows = []

    for product_id, (base_units, base_price, winter_mult, summer_mult) in PRODUCT_PROFILES.items():
        units_series = _generate_product_series(dates, base_units, base_price, winter_mult, summer_mult)
        if product_id in DEMAND_EVENTS:
            mult = DEMAND_EVENTS[product_id]
            units_series["units"][-SHOCK_DAYS:] = np.round(
                units_series["units"][-SHOCK_DAYS:] * mult
            ).astype(float)
        for i, d in enumerate(dates):
            all_rows.append({
                "product_id": product_id,
                "sale_date":  d.date(),
                "units_sold": units_series["units"][i],
                "price":      units_series["price"][i],
            })

    df = pd.DataFrame(all_rows)
    return df


def _generate_product_series(dates, base_units, base_price, winter_mult, summer_mult):
    n = len(dates)

    # --- Seasonal multiplier per day ---
    seasonal = np.array([
        WINTER_MONTHS[d.month] * winter_mult + SUMMER_MONTHS[d.month] * (summer_mult - 1.0)
        for d in dates
    ])

    # --- Day-of-week multiplier ---
    dow = np.array([DOW_MULTIPLIERS[d.dayofweek] for d in dates])

    # --- Slight upward growth trend over the 2 years ---
    trend = 1.0 + np.linspace(0, 0.12, n)

    # --- Promotion flags (~8% of days, random but not clustered) ---
    promo = RNG.random(n) < 0.08

    # --- Combine all multipliers to get expected daily demand ---
    expected = base_units * seasonal * dow * trend
    expected[promo] *= 1.35    # promotion boosts sales by 35%

    # --- Sample actual sales from Poisson distribution ---
    # Poisson is natural for count data: mean = expected, variance = expected
    units = RNG.poisson(np.maximum(expected, 0.5)).astype(float)

    # --- Price: base price with small weekly noise + promo discount ---
    price_noise = RNG.normal(0, 0.03, n)          # ±3% random fluctuation
    prices = base_price * (1 + price_noise)
    prices[promo] *= 0.85                          # 15% off during promotions
    prices = np.clip(prices, base_price * 0.70, base_price * 1.20)
    prices = np.round(prices, 2)

    return {"units": units, "price": prices}


if __name__ == "__main__":
    df = generate_synthetic_data()
    print(f"Generated {len(df):,} rows for {df['product_id'].nunique()} products")
    print(f"Date range: {df['sale_date'].min()} → {df['sale_date'].max()}")
    print(df.groupby("product_id")[["units_sold"]].mean().round(1).head(10))
