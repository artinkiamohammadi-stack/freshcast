"""
ml/data_loader.py — Reads the M5 Kaggle CSV files and returns a clean DataFrame.

The M5 dataset is stored in "wide" format: each column is a day (d_1, d_2 … d_1941).
We convert it to "long" format: one row per (product, date).
We then join in real calendar dates and weekly sell prices.

Output DataFrame columns:
  product_id  | str   — e.g. "FOODS_3_001_CA_1"
  sale_date   | date  — actual calendar date
  units_sold  | float — number of units sold that day
  price       | float — sell price that week (NaN → filled forward)
"""

import os
import logging
import pandas as pd

log = logging.getLogger(__name__)

# Use all three FOODS departments to get varied demand patterns across products.
# FOODS_1 = pantry/packaged, FOODS_2 = deli/prepared, FOODS_3 = fresh/perishable.
# Picking top 10 from each gives 30 products with meaningfully different behaviour.
TARGET_STORE = "CA_1"
TARGET_DEPTS = ["FOODS_1", "FOODS_2", "FOODS_3"]
TOP_N_PER_DEPT = 10          # 10 from each dept = 30 products total


def load_m5_data(data_dir: str) -> pd.DataFrame:
    """
    Parse the three M5 CSV files and return a clean long-format DataFrame.
    Raises FileNotFoundError if any CSV is missing.
    """
    sales_path  = os.path.join(data_dir, "sales_train_validation.csv")
    cal_path    = os.path.join(data_dir, "calendar.csv")
    prices_path = os.path.join(data_dir, "sell_prices.csv")

    for path in (sales_path, cal_path, prices_path):
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Required M5 file not found: {path}\n"
                "Download from https://www.kaggle.com/competitions/m5-forecasting-accuracy/data"
            )

    log.info("Reading M5 CSV files from %s", data_dir)
    sales_df  = pd.read_csv(sales_path)
    cal_df    = pd.read_csv(cal_path)
    price_df  = pd.read_csv(prices_path)

    # --- Filter to one store, all three FOODS departments ---
    mask = (sales_df["store_id"] == TARGET_STORE) & (sales_df["dept_id"].isin(TARGET_DEPTS))
    sales_df = sales_df[mask].copy()
    log.info("After store/dept filter: %d items", len(sales_df))

    # --- Pick top N items per department so we get variety across all 3 ---
    day_cols = [c for c in sales_df.columns if c.startswith("d_")]
    sales_df["total"] = sales_df[day_cols].sum(axis=1)
    top_items = (
        sales_df.groupby("dept_id", group_keys=False)
        .apply(lambda g: g.nlargest(TOP_N_PER_DEPT, "total"))
        ["item_id"].tolist()
    )
    sales_df = sales_df[sales_df["item_id"].isin(top_items)].copy()
    log.info("Kept top %d items across %s: %s…", len(top_items), TARGET_DEPTS, top_items[:5])

    # --- Melt wide → long ---
    id_cols  = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id", "total"]
    long_df  = sales_df.melt(
        id_vars=id_cols,
        value_vars=day_cols,
        var_name="d",
        value_name="units_sold",
    )

    # --- Join calendar to get actual dates and SNAP flag ---
    cal_cols = ["d", "date", "wm_yr_wk", "snap_CA"]
    long_df = long_df.merge(cal_df[cal_cols], on="d", how="left")
    long_df["sale_date"] = pd.to_datetime(long_df["date"]).dt.date

    # --- Join sell prices (prices are per store/item/week) ---
    price_df = price_df[price_df["store_id"] == TARGET_STORE].copy()
    long_df = long_df.merge(
        price_df[["item_id", "wm_yr_wk", "sell_price"]],
        on=["item_id", "wm_yr_wk"],
        how="left",
    )

    # Forward-fill any missing prices within each product
    long_df = long_df.sort_values(["item_id", "sale_date"])
    long_df["sell_price"] = long_df.groupby("item_id")["sell_price"].ffill()

    # Build the product_id in the same format as seed.py (ITEM_STORE)
    long_df["product_id"] = long_df["item_id"] + "_" + long_df["store_id"]

    # --- Final tidy output (keep dept_id so seed.py can use it as category) ---
    result = long_df[["product_id", "dept_id", "sale_date", "units_sold", "sell_price"]].copy()
    result = result.rename(columns={"sell_price": "price"})
    result = result.dropna(subset=["units_sold"]).reset_index(drop=True)

    log.info(
        "M5 load complete: %d rows, %d products, date range %s → %s",
        len(result),
        result["product_id"].nunique(),
        result["sale_date"].min(),
        result["sale_date"].max(),
    )
    return result
