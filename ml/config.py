# ml/config.py — Shared ML configuration constants.
# Change MIN_DEMAND_THRESHOLD to adjust which products are treated as unpredictable.

MIN_DEMAND_THRESHOLD = 16  # avg daily units sold; products below this are excluded from forecasting

# Products with artificial demand shocks in the last 28 days (for shortage/overstock demo).
# Excluded from MAE evaluation so their synthetic anomalies don't pollute model metrics.
SHOCK_PRODUCTS = {
    "FOODS_3_001_CA_1",   # Whole Milk     — overstock demo (holiday surge)
    "FOODS_3_011_CA_1",   # Chicken Breast — shortage demo (supply disruption)
    "FOODS_3_013_CA_1",   # Salmon Fillet  — shortage demo (supply chain issue)
    "FOODS_3_017_CA_1",   # Eggs 12-pack   — overstock demo (seasonal spike)
}
