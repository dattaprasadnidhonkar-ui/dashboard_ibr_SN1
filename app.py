
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re, io

st.set_page_config(page_title="Estee vs Shiffa Analytics", layout="wide")

COMMON_CANDIDATES = {
    "date": ["date","order_date","invoice_date","month","period","week","year"],
    "revenue": ["revenue","sales","net_sales","amount","value","turnover"],
    "units": ["units","quantity","qty","volume","pieces"],
    "price": ["price","unit_price","asp","aov"],
    "margin": ["margin","gross_margin","profit","gp","contribution"],
    "category": ["category","segment","line","family"],
    "product": ["product","sku","item","material"],
    "region": ["region","country","market","area"],
    "channel": ["channel","store","retailer","partner"],
    "order_id": ["order_id","invoice","receipt","bill_no"],
    "customer": ["customer","client","account","shopper_id"],
    "brand": ["brand"]
}

def find_first_match(cols, candidates):
    cols_lower = {c.lower(): c for c in cols}
    for c in candidates:
        if c in cols_lower:
            return cols_lower[c]
    return None

def auto_map_columns(df: pd.DataFrame):
    mapping = {}
    cols = list(df.columns)
    for key, cands in COMMON_CANDIDATES.items():
        match = find_first_match(cols, cands)
        mapping[key] = match
    return mapping

def summarize_kpis(df, m):
    rev = df[m["revenue"]].sum() if m.get("revenue") else np.nan
    units = df[m["units"]].sum() if m.get("units") else np.nan
    orders = df[m["order_id"]].nunique() if m.get("order_id") else np.nan
    margin = df[m["margin"]].sum() if m.get("margin") else np.nan
    aov = rev / orders if (isinstance(orders,(int,float)) and orders and not np.isnan(orders)) else np.nan
    return {"Revenue": rev, "Units": units, "Orders": orders, "Margin": margin, "AOV": aov}

def correlation_heatmap(df_num):
    corr = df_num.corr(numeric_only=True)
    return px.imshow(corr, aspect="auto", title="Correlation Heatmap")

def pareto_chart(df, value_col, label_col, top_n=20, title="Pareto of Items"):
    tmp = df.groupby(label_col, dropna=False)[value_col].sum().sort_values(ascending=False).head(top_n).reset_index()
    tmp["cum_pct"] = (tmp[value_col].cumsum() / tmp[value_col].sum()) * 100.0
    fig = go.Figure()
    fig.add_bar(x=tmp[label_col], y=tmp[value_col], name=value_col)
    fig.add_scatter(x=tmp[label_col], y=tmp["cum_pct"], mode="lines+markers", name="Cumulative %", yaxis="y2")
    fig.update_layout(title=title, yaxis=dict(title=value_col), yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0,100]))
    return fig

def seasonality_heatmap(df, date_col, value_col, title="Seasonality Heatmap"):
    dt = pd.to_datetime(df[date_col], errors="coerce")
    data = df.copy()
    data["Year"] = dt.dt.year
    data["Month"] = dt.dt.month
    pivot = data.pivot_table(index="Year", columns="Month", values=value_col, aggfunc="sum")
    return px.imshow(pivot, aspect="auto", title=title, labels=dict(color=value_col))

def prepare_time_series(df, date_col, value_col):
    d = df[[date_col, value_col]].dropna()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.groupby(pd.Grouper(key=date_col, freq="MS"))[value_col].sum().reset_index()
    return d

def add_topn_bar(df, value_col, label_col, title, top_n=15):
    gp = df.groupby(label_col, dropna=False)[value_col].sum().sort_values(ascending=False).head(top_n).reset_index()
    return px.bar(gp, x=label_col, y=value_col, title=title)

# -----------------------------
# Data loading via BYTES (hashable)
# -----------------------------
st.sidebar.header("Data & Settings")
default_path = Path("data/ibr_final_responses_for_dashboard_2.xlsx")
uploaded = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

def read_bytes_and_sheets(uploaded, default_path):
    if uploaded is not None:
        file_bytes = uploaded.getvalue()
        workbook_name = uploaded.name
    else:
        if not default_path.exists():
            st.error("No file uploaded and default file not found in /data.")
            st.stop()
        file_bytes = default_path.read_bytes()
        workbook_name = default_path.name
    xls = pd.ExcelFile(io.BytesIO(file_bytes))
    return file_bytes, workbook_name, xls.sheet_names

file_bytes, workbook_name, sheets = read_bytes_and_sheets(uploaded, default_path)
st.sidebar.success(f"Loaded workbook: {workbook_name}")

def detect_sheet(name_list, keyword):
    for s in name_list:
        if keyword.lower() in s.lower():
            return s
    return None

estee_guess = detect_sheet(sheets, "estee") or detect_sheet(sheets, "estée") or detect_sheet(sheets, "lauder") or sheets[0]
shiffa_guess = detect_sheet(sheets, "shiffa") or (sheets[1] if len(sheets)>1 else sheets[0])

estee_sheet = st.sidebar.selectbox("Estee Lauder sheet", options=sheets, index=sheets.index(estee_guess))
shiffa_sheet = st.sidebar.selectbox("Shiffa sheet", options=sheets, index=sheets.index(shiffa_guess))

@st.cache_data(show_spinner=False)
def load_df_from_bytes(file_bytes: bytes, sheet: str):
    bio = io.BytesIO(file_bytes)
    df = pd.read_excel(bio, sheet_name=sheet)
    df.columns = [c.strip() for c in df.columns]
    return df

df_estee = load_df_from_bytes(file_bytes, estee_sheet)
df_shiffa = load_df_from_bytes(file_bytes, shiffa_sheet)

st.sidebar.divider()
st.sidebar.subheader("Column Mapper")

def mapper_ui(label, df):
    auto = auto_map_columns(df)
    m = {}
    for key in ["date","revenue","units","price","margin","category","product","region","channel","order_id","customer","brand"]:
        opts = [None]+list(df.columns)
        idx = opts.index(auto.get(key)) if auto.get(key) in df.columns else 0
        m[key] = st.sidebar.selectbox(f"{label}: {key} column", options=opts, index=idx)
    return m

mapper_estee = mapper_ui("Estee", df_estee)
mapper_shiffa = mapper_ui("Shiffa", df_shiffa)

tab1, tab2, tab3 = st.tabs(["💄 Estee Lauder", "🌿 Shiffa", "⚖️ Comparative"])

def brand_tab(df, m, brand_label):
    st.markdown(f"## {brand_label}")
    kpis = summarize_kpis(df, m)
    cols_kpi = st.columns(5)
    for i, (k,v) in enumerate(kpis.items()):
        with cols_kpi[i%5]:
            st.metric(k, f"{v:,.2f}" if isinstance(v,(int,float)) and not np.isnan(v) else "—")

    if m["date"] and m["revenue"]:
        d_rev = prepare_time_series(df, m["date"], m["revenue"])
        st.plotly_chart(px.line(d_rev, x=m["date"], y=m["revenue"], title="Revenue Over Time"), use_container_width=True)
    if m["date"] and m["units"]:
        d_units = prepare_time_series(df, m["date"], m["units"])
        st.plotly_chart(px.line(d_units, x=m["date"], y=m["units"], title="Units Over Time"), use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        if m["category"] and (m["revenue"] or m["units"]):
            val = m["revenue"] or m["units"]
            st.plotly_chart(add_topn_bar(df, val, m["category"], f"{'Revenue' if m['revenue'] else 'Units'} by Category"), use_container_width=True)
        else:
            st.info("Provide a Category column to see Category bars.")
    with c2:
        if m["product"] and (m["revenue"] or m["units"]):
            val = m["revenue"] or m["units"]
            st.plotly_chart(add_topn_bar(df, val, m["product"], f"Top Products by {'Revenue' if m['revenue'] else 'Units'}"), use_container_width=True)
        else:
            st.info("Provide a Product column to see Top products.")

    c3, c4 = st.columns(2)
    with c3:
        if m["region"] and (m["revenue"] or m["units"]):
            val = m["revenue"] or m["units"]
            st.plotly_chart(add_topn_bar(df, val, m["region"], f"{'Revenue' if m['revenue'] else 'Units'} by Region"), use_container_width=True)
        else:
            st.info("Provide a Region column to see Geo split.")
    with c4:
        if m["channel"] and (m["revenue"] or m["units"]):
            val = m["revenue"] or m["units"]
            ch = df.groupby(m["channel"], dropna=False)[val].sum().reset_index()
            st.plotly_chart(px.pie(ch, names=m["channel"], values=val, hole=0.45, title="Channel Mix"), use_container_width=True)
        else:
            st.info("Provide a Channel column to see Channel mix.")

    if m["price"] and m["units"]:
        st.plotly_chart(px.scatter(df, x=m["price"], y=m["units"], trendline="ols", title="Price vs Units"), use_container_width=True)

    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if num_cols:
        st.plotly_chart(px.histogram(df, x=num_cols[0], nbins=30, title=f"Distribution of {num_cols[0]}"), use_container_width=True)
        if len(num_cols) > 1:
            st.plotly_chart(px.box(df, y=num_cols[1], title=f"Box Plot of {num_cols[1]}"), use_container_width=True)
        st.plotly_chart(correlation_heatmap(df[num_cols]), use_container_width=True)

    if m["product"] and (m["revenue"] or m["units"]):
        val = m["revenue"] or m["units"]
        st.plotly_chart(pareto_chart(df, value_col=val, label_col=m["product"], title="Pareto: Product Contribution"), use_container_width=True)

    if m["date"] and (m["revenue"] or m["units"]):
        val = m["revenue"] or m["units"]
        st.plotly_chart(seasonality_heatmap(df, m["date"], val, title="Seasonality Heatmap (Year x Month)"), use_container_width=True)

    if m["order_id"] and m["revenue"] and m["date"]:
        tmp = df[[m["order_id"], m["revenue"], m["date"]]].copy()
        tmp[m["date"]] = pd.to_datetime(tmp[m["date"]], errors="coerce")
        g = tmp.groupby([pd.Grouper(key=m["date"], freq="MS")])[m["revenue"]].sum() / tmp.groupby([pd.Grouper(key=m["date"], freq="MS")])[m["order_id"]].nunique()
        aov_df = g.reset_index().rename(columns={m["date"]:"Date", 0:"AOV"})
        aov_df.columns = ["Date", "AOV"]
        st.plotly_chart(px.line(aov_df, x="Date", y="AOV", title="AOV Trend"), use_container_width=True)

with tab1:
    brand_tab(df_estee, mapper_estee, "Estee Lauder")

with tab2:
    brand_tab(df_shiffa, mapper_shiffa, "Shiffa")

with tab3:
    st.markdown("## Comparative Analysis")
    if mapper_estee["date"] and mapper_shiffa["date"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = prepare_time_series(df_estee, mapper_estee["date"], mapper_estee["revenue"]).rename(columns={mapper_estee["date"]: "Date", mapper_estee["revenue"]: "Revenue"})
        s = prepare_time_series(df_shiffa, mapper_shiffa["date"], mapper_shiffa["revenue"]).rename(columns={mapper_shiffa["date"]: "Date", mapper_shiffa["revenue"]: "Revenue"})
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        ts = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.line(ts, x="Date", y="Revenue", color="Brand", title="Revenue Trend: Estee vs Shiffa"), use_container_width=True)

    if mapper_estee["date"] and mapper_shiffa["date"] and mapper_estee["units"] and mapper_shiffa["units"]:
        e = prepare_time_series(df_estee, mapper_estee["date"], mapper_estee["units"]).rename(columns={mapper_estee["date"]: "Date", mapper_estee["units"]: "Units"})
        s = prepare_time_series(df_shiffa, mapper_shiffa["date"], mapper_shiffa["units"]).rename(columns={mapper_shiffa["date"]: "Date", mapper_shiffa["units"]: "Units"})
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        ts = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.line(ts, x="Date", y="Units", color="Brand", title="Units Trend: Estee vs Shiffa"), use_container_width=True)

    k_e = summarize_kpis(df_estee, mapper_estee)
    k_s = summarize_kpis(df_shiffa, mapper_shiffa)
    cA, cB, cC = st.columns(3)
    with cA:
        st.metric("Δ Revenue (Estee - Shiffa)", f"{(k_e['Revenue']-k_s['Revenue']):,.2f}" if all([isinstance(k_e['Revenue'],(int,float)), isinstance(k_s['Revenue'],(int,float))]) else "—")
    with cB:
        st.metric("Δ Units (Estee - Shiffa)", f"{(k_e['Units']-k_s['Units']):,.2f}" if all([isinstance(k_e['Units'],(int,float)), isinstance(k_s['Units'],(int,float))]) else "—")
    with cC:
        aov_e = k_e["AOV"] if isinstance(k_e["AOV"],(int,float)) else np.nan
        aov_s = k_s["AOV"] if isinstance(k_s["AOV"],(int,float)) else np.nan
        st.metric("Δ AOV (Estee - Shiffa)", f"{(aov_e - aov_s):,.2f}" if not (np.isnan(aov_e) or np.isnan(aov_s)) else "—")

    if mapper_estee["category"] and mapper_shiffa["category"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = df_estee.groupby(mapper_estee["category"])[mapper_estee["revenue"]].sum().reset_index()
        s = df_shiffa.groupby(mapper_shiffa["category"])[mapper_shiffa["revenue"]].sum().reset_index()
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        e.columns = ["Category","Revenue","Brand"]; s.columns = ["Category","Revenue","Brand"]
        mix = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.bar(mix, x="Category", y="Revenue", color="Brand", barmode="group", title="Category Mix Comparison"), use_container_width=True)

    if mapper_estee["region"] and mapper_shiffa["region"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = df_estee.groupby(mapper_estee["region"])[mapper_estee["revenue"]].sum().reset_index()
        s = df_shiffa.groupby(mapper_shiffa["region"])[mapper_shiffa["revenue"]].sum().reset_index()
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        e.columns = ["Region","Revenue","Brand"]; s.columns = ["Region","Revenue","Brand"]
        mix = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.bar(mix, x="Region", y="Revenue", color="Brand", barmode="group", title="Region Split Comparison"), use_container_width=True)

    df1 = pd.DataFrame(columns=["Price","Units","Brand"])
    if mapper_estee["price"] and mapper_estee["units"]:
        d1 = df_estee[[mapper_estee["price"], mapper_estee["units"]]].copy()
        d1.columns = ["Price","Units"]; d1["Brand"]="Estee"
        df1 = pd.concat([df1, d1], ignore_index=True)
    if mapper_shiffa["price"] and mapper_shiffa["units"]:
        d2 = df_shiffa[[mapper_shiffa["price"], mapper_shiffa["units"]]].copy()
        d2.columns = ["Price","Units"]; d2["Brand"]="Shiffa"
        df1 = pd.concat([df1, d2], ignore_index=True)
    if not df1.empty:
        st.plotly_chart(px.scatter(df1, x="Price", y="Units", color="Brand", trendline="ols", title="Price–Quantity Elasticity (Sketch)"), use_container_width=True)

st.caption("Tip: Use the sidebar to remap columns if any chart looks off.")
