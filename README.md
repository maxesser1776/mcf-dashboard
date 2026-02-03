# 🧭 Macro Capital Flow Dashboard

A Python-based macroeconomic dashboard designed to visualize global liquidity, credit spreads, yield curves, FX stress, and inflation trends — all from high-frequency public data.

---

## 📦 Features

* **Federal Reserve Plumbing**: TGA, RRP, and balance sheet dynamics
* **Yield Curve & Policy Rates**: 2s10s spread, SOFR
* **Credit Market Stress**: High yield vs investment grade spreads
* **FX & Global Dollar Stress**: DXY and key EM FX pairs
* **Growth & Inflation**: CPI, Core PCE, employment, and retail sales

---

## 🔧 Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/macro-dashboard.git
cd macro-dashboard
```

### 2. Create Environment and Install Requirements

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set Up FRED API Key

Create a `.env` file at the root with:

```
FRED_API_KEY=your_fred_api_key_here
```

Get your API key at: [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)

---

## 🔁 Update Data

Run all pipelines:

```bash
python run_all_pipelines.py
```

This will populate `/data/processed/` with the latest cleaned CSVs.

---

## 📊 Launch Dashboard

```bash
streamlit run dashboard/app.py
```

Open the link Streamlit provides in your browser.

---

## 📂 Project Structure

```
macro_dashboard/
├── data/
│   ├── raw/
│   └── processed/
├── pipelines/          # Data collectors and transformers
├── dashboard/          # Streamlit app interface
├── utils/              # API, plotting, and CSV loaders
├── run_all_pipelines.py
├── requirements.txt
└── .env
```

---

## 📈 Data Sources

* [FRED API](https://fred.stlouisfed.org)
* [FiscalData.Treasury.gov](https://fiscaldata.treasury.gov)
* [New York Fed](https://www.newyorkfed.org/markets/data-hub)
* [Yahoo Finance](https://finance.yahoo.com)

---

## ✅ Status

> v0.1 – Core functionality live: all data pipelines, dashboard sections, and charting in place.

Planned additions: macro factor scoring, alert system, and streaming updates.

---

## 📄 License

MIT — feel free to fork, extend, and contribute.

---

Made with ❤️ by macro engineers and capital flow explorers.
