# FreshCast — Demand Forecasting for Perishable Goods

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-1.4+-F7931E?style=flat&logo=scikit-learn&logoColor=white)
![Plotly](https://img.shields.io/badge/Plotly.js-2.32-3F4F75?style=flat&logo=plotly&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat&logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)

FreshCast is a full-stack demand forecasting system built for perishable goods retailers. It predicts how many units of each product — milk, chicken, strawberries, bread — a store will need over the next 7–28 days, helping operations teams avoid two costly outcomes: overstocking (spoilage and waste) and understocking (lost sales and empty shelves). The system uses a Random Forest model trained on two years of daily sales history, surfaces shortage and overstock alerts from real demand signals, and presents everything through an interactive Plotly.js dashboard with no page reloads.

---

## Features

- **7 to 28-day demand forecasts** with confidence intervals per product
- **Shortage and overstock alerts** — detected by comparing recent 7-day actuals against the model forecast
- **Per-product accuracy** displayed as a percentage, with "Unpredictable" shown for products with insufficient demand volume
- **Interactive forecast chart** — actual history + forecast line + confidence band, all daily resolution
- **Product Dictionary** — all 30 products grouped by category with shelf-life colour coding
- **Supply Risk table** — all products ranked by risk level with trend indicators
- **One-click model retraining** from the dashboard UI
- **Runs locally with SQLite** (no Docker needed) or in Docker with MySQL

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11, FastAPI, SQLAlchemy |
| ML | scikit-learn RandomForestRegressor, pandas, NumPy |
| Database | SQLite (local) / MySQL 8 (Docker) |
| Frontend | Vanilla HTML/CSS/JS, Plotly.js |
| Containerisation | Docker, docker-compose, Nginx |

---

## Getting Started — Local (no Docker)

**Requirements:** Python 3.11+

```bash
git clone https://github.com/your-username/freshcast.git
cd freshcast

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

cp .env.example .env
```

Then either double-click `run.bat` or run manually:

```bash
set DATABASE_URL=sqlite:///./freshcast.db
set MODEL_DIR=./models
set PYTHONPATH=.
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000**

On first boot the server automatically:
1. Creates the database tables
2. Seeds 21,900 rows of synthetic sales data (30 products × 730 days)
3. Trains the initial Random Forest model

---

## Getting Started — Docker

**Requirements:** Docker Desktop

```bash
git clone https://github.com/your-username/freshcast.git
cd freshcast
docker-compose up --build
```

Open **http://localhost**

The compose stack starts a MySQL container, waits for it to be ready, runs the FastAPI app (which seeds and trains on first boot), and serves the frontend through Nginx.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/products` | List all 30 products |
| `GET` | `/products/{id}/history?days=28` | Last N days of sales history |
| `GET` | `/forecast/{id}?days=7` | Demand forecast (1–28 days ahead) |
| `POST` | `/retrain` | Retrain the model on all current sales data |
| `GET` | `/model-info` | Model version, MAE, RMSE, training timestamp |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Interactive Swagger UI |

---

## ML Model

### Algorithm
Random Forest Regressor (scikit-learn) — chosen for its robustness on small tabular datasets, built-in handling of non-linear seasonality, no requirement for feature scaling, and interpretable feature importances.

### Training strategy
A single **global model** is trained across all products simultaneously. Rather than 30 per-product models (each with ~700 rows), the global model sees 21,000 training rows. Each product's demand pattern is encoded entirely in its lag and rolling features — the product ID is not a feature.

The last 28 days per product are held out for evaluation (time-series split, no shuffling).

### Features (13 total)

| Category | Features |
|---|---|
| Calendar | `day_of_week`, `day_of_month`, `week_of_year`, `month`, `is_weekend` |
| Lag sales | `lag_7`, `lag_14`, `lag_28` |
| Rolling stats | `rolling_mean_7`, `rolling_mean_28`, `rolling_std_7` |
| Price | `price`, `price_vs_avg` |

### Forecasting
Multi-day forecasts use **iterative 1-day-ahead** prediction: each predicted value is appended to the history and used as the lag input for the next day. Confidence intervals are ±1.5 × `rolling_std_7` of recent actuals.

### Unpredictable threshold
Products with average daily demand below **16 units** are excluded from model training and evaluation. When the forecast endpoint is called for these products, it returns `insufficient: true` and the dashboard shows the sales history only, with a note explaining why forecasting is unreliable at low volumes.

### Per-product MAE
After training, the model evaluates each product individually on its 28-day holdout set. These per-product MAE values are stored in the model artifact and shown in the server logs after every training run.

---

## Screenshots


<img width="953" height="408" alt="2026-04-30 14_24_01-FreshCast — Demand Forecasting for Perishable Goods - Brave" src="https://github.com/user-attachments/assets/9340453a-66fc-431d-9315-3cf2522e8afa" />








<img width="952" height="411" alt="2026-04-30 14_25_03-FreshCast — Demand Forecasting for Perishable Goods - Brave" src="https://github.com/user-attachments/assets/7dfa13b3-622d-4e76-ae11-ae22dd310e16" />










<img width="952" height="395" alt="2026-04-30 14_25_46-FreshCast — Demand Forecasting for Perishable Goods - Brave" src="https://github.com/user-attachments/assets/cd0f5baa-b5c9-4dcd-905e-4b5473692da8" />




---

## Future Improvements

- **Real POS data integration** — replace synthetic data with a live feed from a point-of-sale or WMS system
- **LSTM model upgrade** — experiment with a sequence model for longer-horizon forecasts where temporal dependencies matter more
- **Azure deployment** — containerise and deploy to Azure Container Apps with Azure Database for MySQL, CI/CD via GitHub Actions

