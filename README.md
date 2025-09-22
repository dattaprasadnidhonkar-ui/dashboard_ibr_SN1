# Estee vs Shiffa — Interactive Analytics Dashboard (Streamlit)

An adaptive Streamlit dashboard that reads your multi‑sheet Excel workbook and builds rich, interactive visuals for two brands (Estee Lauder & Shiffa) plus a comparative analysis.  
Designed to be **copy‑paste deployable** on Streamlit Cloud via GitHub.

## 🚀 Quick Start (Local)
```bash
# (optional) python -m venv .venv && source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## ☁️ Deploy on Streamlit Cloud
1. Push this folder to a **public GitHub repo**.
2. In Streamlit Cloud, **New app** → choose the repo and branch → set `app.py` as the entry file.
3. Add your Excel file to the repo (recommended path: `data/ibr_final_responses_for_dashboard_2.xlsx`).

## 📂 Project Structure
```
.
├── app.py
├── requirements.txt
├── README.md
└── data/
    └── ibr_final_responses_for_dashboard_2.xlsx  # put your workbook here
```

## 📄 Data Notes
- The app will auto‑detect sheet names containing **"estee"** and **"shiffa"** (case‑insensitive).  
  If auto‑detection fails, use the sidebar selectors to pick the sheets manually.
- It also tries to auto‑map common columns (date/time, revenue/sales, units/qty, product/category, region/channel).  
  If something looks off, use the **Column Mapper** in the sidebar to remap columns.

## ✨ Visuals (15+)
Per brand (Estee / Shiffa), the app renders (as available from your columns):
1. KPI header (Revenue, Units, AOV, Margin, #Orders)
2. Revenue over Time (line)
3. Units over Time (line)
4. Revenue by Category (bar)
5. Revenue by Product (top N bar)
6. Revenue by Region / Country (bar or map-ready format)
7. Channel Mix (pie / donut)
8. Price vs Units (scatter)
9. Revenue Distribution (histogram)
10. Outliers & Spread (box)
11. Correlation Heatmap (numerics)
12. Pareto of Products (cumulative contribution)
13. Weekday / Month Seasonality (heatmap)
14. Cohort (first-order month) — if date + customer present
15. Basket Size / AOV Trend — if order-level fields present

Comparative Tab (cross-brand):
1. Revenue Trend: Estee vs Shiffa
2. Units Trend: Estee vs Shiffa
3. Category Mix Comparison
4. Region/Market Split Comparison
5. Price–Quantity Elasticity Sketch (scatter with trendlines)
6. KPI Delta Cards (Revenue, Units, AOV, Margin)
7. Similarity Matrix (category/region distributions compared)

> The app is **defensive**: visuals appear only if required fields exist. Otherwise, a helpful note is displayed.

## 🛠 Column Heuristics
- **Date**: `date, order_date, invoice_date, month, period, week, year`
- **Revenue**: `revenue, sales, net_sales, amount, value, turnover`
- **Units**: `units, quantity, qty, volume, pieces`
- **Price**: `price, unit_price, asp, aov`
- **Margin**: `margin, gross_margin, profit, gp, contribution`
- **Category**: `category, segment, line, family`
- **Product**: `product, sku, item, material`
- **Region**: `region, country, market, area`
- **Channel**: `channel, store, retailer, partner`
- **Order ID**: `order_id, invoice, receipt, bill_no`
- **Customer**: `customer, client, account, shopper_id`

## 🧩 Troubleshooting
- If some visuals are blank, double‑check the **Column Mapper** and your sheet selections.
- Large files may require Streamlit Cloud’s file size limits consideration. Keep your repo clean and consider CSV if needed.

---
*Generated on: 2025-09-22 06:40 *
