-- FreshCast database schema
-- This file runs automatically when the MySQL Docker container starts for the first time.

CREATE DATABASE IF NOT EXISTS freshcast;
USE freshcast;

-- One row per perishable product we track
CREATE TABLE IF NOT EXISTS products (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    product_id   VARCHAR(50) UNIQUE NOT NULL,  -- e.g. "FOODS_3_001_CA_1"
    name         VARCHAR(100) NOT NULL,         -- human-readable, e.g. "Whole Milk"
    category     VARCHAR(50),                   -- Dairy, Produce, Bakery, etc.
    shelf_life_days INT DEFAULT 7,             -- how many days before spoilage
    unit         VARCHAR(20) DEFAULT 'units'   -- units, kg, litres
);

-- Daily sales records loaded from M5 dataset
CREATE TABLE IF NOT EXISTS sales_history (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    product_id  VARCHAR(50) NOT NULL,
    sale_date   DATE NOT NULL,
    units_sold  FLOAT NOT NULL,
    price       FLOAT,
    INDEX idx_product_date (product_id, sale_date)
);

-- Model-generated forecasts stored here after each training/prediction run
CREATE TABLE IF NOT EXISTS forecasts (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    product_id       VARCHAR(50) NOT NULL,
    forecast_date    DATE NOT NULL,
    predicted_units  FLOAT NOT NULL,
    confidence_low   FLOAT,   -- lower bound of prediction interval
    confidence_high  FLOAT,   -- upper bound of prediction interval
    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_product_forecast (product_id, forecast_date)
);

-- Metadata about each model training run (used for model versioning)
CREATE TABLE IF NOT EXISTS model_metadata (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    model_version VARCHAR(50) NOT NULL,   -- e.g. "v1_20240101_120000"
    trained_at    DATETIME NOT NULL,
    mae           FLOAT,                  -- Mean Absolute Error on hold-out set
    rmse          FLOAT,                  -- Root Mean Squared Error
    n_products    INT,                    -- how many products were trained on
    feature_names TEXT                    -- JSON list of feature column names
);
