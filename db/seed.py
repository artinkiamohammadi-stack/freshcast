"""
db/seed.py — Seeds the database with synthetic perishable goods data.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SYNTHETIC_PRODUCT_NAMES = {
    "FOODS_3_001_CA_1": ("Whole Milk 1L",       "Dairy",     7,  "litres"),
    "FOODS_3_002_CA_1": ("Greek Yogurt 500g",   "Dairy",     14, "units"),
    "FOODS_3_003_CA_1": ("Cheddar Cheese 250g", "Dairy",     21, "units"),
    "FOODS_3_004_CA_1": ("Butter 250g",         "Dairy",     30, "units"),
    "FOODS_3_005_CA_1": ("Heavy Cream 250ml",   "Dairy",     10, "units"),
    "FOODS_3_006_CA_1": ("Tomatoes 1kg",        "Produce",    5, "kg"),
    "FOODS_3_007_CA_1": ("Iceberg Lettuce",     "Produce",    4, "units"),
    "FOODS_3_008_CA_1": ("Strawberries 250g",   "Produce",    3, "units"),
    "FOODS_3_009_CA_1": ("Bananas 1kg",         "Produce",    6, "kg"),
    "FOODS_3_010_CA_1": ("Baby Spinach 200g",   "Produce",    5, "units"),
    "FOODS_3_011_CA_1": ("Chicken Breast 500g", "Meat",       3, "units"),
    "FOODS_3_012_CA_1": ("Ground Beef 500g",    "Meat",       3, "units"),
    "FOODS_3_013_CA_1": ("Salmon Fillet 300g",  "Seafood",    2, "units"),
    "FOODS_3_014_CA_1": ("Sourdough Bread",     "Bakery",     4, "units"),
    "FOODS_3_015_CA_1": ("Croissants 4-pack",   "Bakery",     2, "units"),
    "FOODS_3_016_CA_1": ("Orange Juice 1L",     "Beverages", 14, "litres"),
    "FOODS_3_017_CA_1": ("Eggs 12-pack",        "Dairy",     21, "units"),
    "FOODS_3_018_CA_1": ("Sliced Turkey 200g",  "Deli",       5, "units"),
    "FOODS_3_019_CA_1": ("Hummus 200g",         "Deli",      10, "units"),
    "FOODS_3_020_CA_1": ("Bell Peppers 500g",   "Produce",    7, "units"),
    "FOODS_3_021_CA_1": ("Cucumber",            "Produce",    7, "units"),
    "FOODS_3_022_CA_1": ("Avocado",             "Produce",    4, "units"),
    "FOODS_3_023_CA_1": ("Broccoli",            "Produce",    5, "units"),
    "FOODS_3_024_CA_1": ("Mushrooms 250g",      "Produce",    4, "units"),
    "FOODS_3_025_CA_1": ("Cottage Cheese 250g", "Dairy",     14, "units"),
    "FOODS_3_026_CA_1": ("Pita Bread 6-pack",   "Bakery",     5, "units"),
    "FOODS_3_027_CA_1": ("Cream Cheese 150g",   "Dairy",     21, "units"),
    "FOODS_3_028_CA_1": ("Sour Cream 200g",     "Dairy",     14, "units"),
    "FOODS_3_029_CA_1": ("Mozzarella 250g",     "Dairy",     10, "units"),
    "FOODS_3_030_CA_1": ("Blueberries 150g",    "Produce",    3, "units"),
}


def run_seed():
    import pandas as pd
    from api.database import SessionLocal
    from api.models.db_models import Product

    db = SessionLocal()
    try:
        if db.query(Product).count() > 0:
            log.info("Database already seeded — skipping.")
            return
    finally:
        db.close()

    _seed_synthetic()


def _seed_synthetic():
    import pandas as pd
    from api.database import engine
    from ml.synthetic_data import generate_synthetic_data

    log.info("Generating synthetic sales data...")
    df = generate_synthetic_data()
    log.info("Generated %d rows for %d products", len(df), df["product_id"].nunique())

    products_df = pd.DataFrame([
        {"product_id": pid, "name": name, "category": cat,
         "shelf_life_days": shelf, "unit": unit}
        for pid, (name, cat, shelf, unit) in SYNTHETIC_PRODUCT_NAMES.items()
    ])
    products_df.to_sql("products", engine, if_exists="append", index=False)

    sales_df = df[["product_id", "sale_date", "units_sold", "price"]].copy()
    sales_df["sale_date"] = sales_df["sale_date"].astype(str)
    log.info("Inserting %d sales rows...", len(sales_df))
    sales_df.to_sql("sales_history", engine, if_exists="append", index=False,
                    chunksize=1000, method="multi")
    log.info("Synthetic seed complete — %d products, %d rows.", len(products_df), len(sales_df))


if __name__ == "__main__":
    run_seed()
