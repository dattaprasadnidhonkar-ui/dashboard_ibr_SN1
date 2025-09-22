
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import re

st.set_page_config(page_title="Estee vs Shiffa Analytics", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower())

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
    lower_cols = [c.lower() for c in cols]
    for key, cands in COMMON_CANDIDATES.items():
        match = find_first_match(cols, cands)
        mapping[key] = match
    return mapping

def ensure_datetime(s):
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.to_datetime(pd.Series(s), errors="coerce")

def summarize_kpis(df, m):
    rev = df[m["revenue"]].sum() if m.get("revenue") else np.nan
    units = df[m["units"]].sum() if m.get("units") else np.nan
    orders = df[m["order_id"]].nunique() if m.get("order_id") else np.nan
    margin = df[m["margin"]].sum() if m.get("margin") else np.nan
    aov = rev / orders if (isinstance(orders,(int,float)) and orders and not np.isnan(orders)) else np.nan
    return {
        "Revenue": rev,
        "Units": units,
        "Orders": orders,
        "Margin": margin,
        "AOV": aov
    }

def kpi_cards(kpis, cols=5):
    cols_list = st.columns(cols)
    for i, (k,v) in enumerate(kpis.items()):
        with cols_list[i%cols]:
            st.metric(k, f"{v:,.2f}" if isinstance(v,(int,float)) and not np.isnan(v) else "—")

def plot_if(df, condition, fig_fn, note):
    if condition:
        fig = fig_fn()
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info(note)

def correlation_heatmap(df_num):
    corr = df_num.corr(numeric_only=True)
    fig = px.imshow(corr, aspect="auto", title="Correlation Heatmap")
    return fig

def pareto_chart(df, value_col, label_col, top_n=20, title="Pareto of Items"):
    tmp = df.groupby(label_col, dropna=False)[value_col].sum().sort_values(ascending=False).head(top_n).reset_index()
    tmp["cum_pct"] = (tmp[value_col].cumsum() / tmp[value_col].sum()) * 100.0
    fig = go.Figure()
    fig.add_bar(x=tmp[label_col], y=tmp[value_col], name=value_col)
    fig.add_scatter(x=tmp[label_col], y=tmp["cum_pct"], mode="lines+markers", name="Cumulative %", yaxis="y2")
    fig.update_layout(
        title=title,
        yaxis=dict(title=value_col),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0,100])
    )
    return fig

def seasonality_heatmap(df, date_col, value_col, title="Seasonality Heatmap"):
    dt = pd.to_datetime(df[date_col], errors="coerce")
    data = df.copy()
    data["Year"] = dt.dt.year
    data["Month"] = dt.dt.month
    pivot = data.pivot_table(index="Year", columns="Month", values=value_col, aggfunc="sum")
    fig = px.imshow(pivot, aspect="auto", title=title, labels=dict(color=value_col))
    return fig

def prepare_time_series(df, date_col, value_col):
    d = df[[date_col, value_col]].dropna()
    d[date_col] = pd.to_datetime(d[date_col], errors="coerce")
    d = d.groupby(pd.Grouper(key=date_col, freq="MS"))[value_col].sum().reset_index()
    return d

def add_topn_bar(df, value_col, label_col, title, top_n=15):
    gp = df.groupby(label_col, dropna=False)[value_col].sum().sort_values(ascending=False).head(top_n).reset_index()
    return px.bar(gp, x=label_col, y=value_col, title=title)

def adaptive_number_cols(df):
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    return num_cols

# -----------------------------
# Load Data
# -----------------------------
st.sidebar.header("Data & Settings")

default_path = Path("data/ibr_final_responses_for_dashboard_2.xlsx")
uploaded = st.sidebar.file_uploader("Upload Excel (.xlsx)", type=["xlsx"])

if uploaded:
    xls = pd.ExcelFile(uploaded)
    workbook_name = uploaded.name
else:
    # Try local default
    if default_path.exists():
        xls = pd.ExcelFile(default_path)
        workbook_name = default_path.name
    else:
        st.stop()

st.sidebar.success(f"Loaded workbook: {workbook_name}")
sheets = xls.sheet_names

# Auto-detect brand sheets
def detect_sheet(name_list, keyword):
    pats = [keyword.lower()]
    for s in name_list:
        if any(p in s.lower() for p in pats):
            return s
    return None

estee_sheet = detect_sheet(sheets, "estee") or detect_sheet(sheets, "estée") or detect_sheet(sheets, "lauder")
shiffa_sheet = detect_sheet(sheets, "shiffa")

estee_sheet = st.sidebar.selectbox("Estee Lauder sheet", options=sheets, index=sheets.index(estee_sheet) if estee_sheet in sheets else 0)
shiffa_sheet = st.sidebar.selectbox("Shiffa sheet", options=sheets, index=sheets.index(shiffa_sheet) if shiffa_sheet in sheets else (1 if len(sheets)>1 else 0))

@st.cache_data(show_spinner=False)
def load_df(xls, sheet):
    df = pd.read_excel(xls, sheet_name=sheet)
    # Make all column names consistent
    df.columns = [c.strip() for c in df.columns]
    return df

df_estee = load_df(xls, estee_sheet)
df_shiffa = load_df(xls, shiffa_sheet)

st.sidebar.divider()
st.sidebar.subheader("Column Mapper")

def mapper_ui(label, df):
    auto = auto_map_columns(df)
    m = {}
    for key in ["date","revenue","units","price","margin","category","product","region","channel","order_id","customer","brand"]:
        m[key] = st.sidebar.selectbox(f"{label}: {key} column", options=[None]+list(df.columns), index=( [None]+list(df.columns) ).index(auto.get(key)) if auto.get(key) in df.columns else 0)
    return m

mapper_estee = mapper_ui("Estee", df_estee)
mapper_shiffa = mapper_ui("Shiffa", df_shiffa)

# Tabs
tab1, tab2, tab3 = st.tabs(["💄 Estee Lauder", "🌿 Shiffa", "⚖️ Comparative"])

# -----------------------------
# Brand Tab Template
# -----------------------------
def brand_tab(df, m, brand_label):
    st.markdown(f"## {brand_label}")
    # KPIs
    kpis = summarize_kpis(df, m)
    kpi_cards(kpis)

    # Time series
    if m["date"] and m["revenue"]:
        d_rev = prepare_time_series(df, m["date"], m["revenue"])
        fig = px.line(d_rev, x=m["date"], y=m["revenue"], title="Revenue Over Time")
        st.plotly_chart(fig, use_container_width=True)

    if m["date"] and m["units"]:
        d_units = prepare_time_series(df, m["date"], m["units"])
        fig = px.line(d_units, x=m["date"], y=m["units"], title="Units Over Time")
        st.plotly_chart(fig, use_container_width=True)

    cols = st.columns(2)
    with cols[0]:
        # Category
        if m["category"] and m["revenue"]:
            st.plotly_chart(add_topn_bar(df, m["revenue"], m["category"], "Revenue by Category"), use_container_width=True)
        elif m["category"] and m["units"]:
            st.plotly_chart(add_topn_bar(df, m["units"], m["category"], "Units by Category"), use_container_width=True)
        else:
            st.info("Provide a Category column to see Category bars.")

    with cols[1]:
        # Product Top N
        if m["product"] and m["revenue"]:
            st.plotly_chart(add_topn_bar(df, m["revenue"], m["product"], "Top Products by Revenue"), use_container_width=True)
        elif m["product"] and m["units"]:
            st.plotly_chart(add_topn_bar(df, m["units"], m["product"], "Top Products by Units"), use_container_width=True)
        else:
            st.info("Provide a Product column to see Top products.")

    cols2 = st.columns(2)
    with cols2[0]:
        # Region/Country
        if m["region"] and m["revenue"]:
            st.plotly_chart(add_topn_bar(df, m["revenue"], m["region"], "Revenue by Region"), use_container_width=True)
        elif m["region"] and m["units"]:
            st.plotly_chart(add_topn_bar(df, m["units"], m["region"], "Units by Region"), use_container_width=True)
        else:
            st.info("Provide a Region column to see Geo split.")

    with cols2[1]:
        # Channel
        if m["channel"] and m["revenue"]:
            ch = df.groupby(m["channel"], dropna=False)[m["revenue"]].sum().reset_index()
            fig = px.pie(ch, names=m["channel"], values=m["revenue"], hole=0.45, title="Channel Mix")
            st.plotly_chart(fig, use_container_width=True)
        elif m["channel"] and m["units"]:
            ch = df.groupby(m["channel"], dropna=False)[m["units"]].sum().reset_index()
            fig = px.pie(ch, names=m["channel"], values=m["units"], hole=0.45, title="Channel Mix (Units)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Provide a Channel column to see Channel mix.")

    # Scatter: Price vs Units
    if m["price"] and m["units"]:
        fig = px.scatter(df, x=m["price"], y=m["units"], trendline="ols", title="Price vs Units")
        st.plotly_chart(fig, use_container_width=True)

    # Histograms & Box
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if num_cols:
        st.plotly_chart(px.histogram(df, x=num_cols[0], nbins=30, title=f"Distribution of {num_cols[0]}"), use_container_width=True)
        if len(num_cols) > 1:
            st.plotly_chart(px.box(df, y=num_cols[1], title=f"Box Plot of {num_cols[1]}"), use_container_width=True)

        # Correlation heatmap
        st.plotly_chart(correlation_heatmap(df[num_cols]), use_container_width=True)

    # Pareto (Products)
    if m["product"] and (m["revenue"] or m["units"]):
        value_col = m["revenue"] or m["units"]
        st.plotly_chart(pareto_chart(df, value_col=value_col, label_col=m["product"], title="Pareto: Product Contribution"), use_container_width=True)

    # Seasonality heatmap
    if m["date"] and (m["revenue"] or m["units"]):
        value_col = m["revenue"] or m["units"]
        st.plotly_chart(seasonality_heatmap(df, m["date"], value_col, title="Seasonality Heatmap (Year x Month)"), use_container_width=True)

    # AOV trend (if order_id & revenue)
    if m["order_id"] and m["revenue"] and m["date"]:
        tmp = df[[m["order_id"], m["revenue"], m["date"]]].copy()
        tmp[m["date"]] = pd.to_datetime(tmp[m["date"]], errors="coerce")
        g = tmp.groupby([pd.Grouper(key=m["date"], freq="MS")])[m["revenue"]].sum() / tmp.groupby([pd.Grouper(key=m["date"], freq="MS")])[m["order_id"]].nunique()
        aov_df = g.reset_index().rename(columns={0:"AOV"})
        aov_df.columns = [m["date"], "AOV"]
        st.plotly_chart(px.line(aov_df, x=m["date"], y="AOV", title="AOV Trend"), use_container_width=True)

# -----------------------------
# Render Tabs
# -----------------------------
with tab1:
    brand_tab(df_estee, mapper_estee, "Estee Lauder")

with tab2:
    brand_tab(df_shiffa, mapper_shiffa, "Shiffa")

with tab3:
    st.markdown("## Comparative Analysis")
    # Align on date
    if mapper_estee["date"] and mapper_shiffa["date"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = prepare_time_series(df_estee, mapper_estee["date"], mapper_estee["revenue"]).rename(columns={mapper_estee["date"]: "Date", mapper_estee["revenue"]: "Revenue"})
        s = prepare_time_series(df_shiffa, mapper_shiffa["date"], mapper_shiffa["revenue"]).rename(columns={mapper_shiffa["date"]: "Date", mapper_shiffa["revenue"]: "Revenue"})
        e["Brand"] = "Estee"
        s["Brand"] = "Shiffa"
        ts = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.line(ts, x="Date", y="Revenue", color="Brand", title="Revenue Trend: Estee vs Shiffa"), use_container_width=True)

    if mapper_estee["date"] and mapper_shiffa["date"] and mapper_estee["units"] and mapper_shiffa["units"]:
        e = prepare_time_series(df_estee, mapper_estee["date"], mapper_estee["units"]).rename(columns={mapper_estee["date"]: "Date", mapper_estee["units"]: "Units"})
        s = prepare_time_series(df_shiffa, mapper_shiffa["date"], mapper_shiffa["units"]).rename(columns={mapper_shiffa["date"]: "Date", mapper_shiffa["units"]: "Units"})
        e["Brand"] = "Estee"
        s["Brand"] = "Shiffa"
        ts = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.line(ts, x="Date", y="Units", color="Brand", title="Units Trend: Estee vs Shiffa"), use_container_width=True)

    # KPI Deltas
    k_e = summarize_kpis(df_estee, mapper_estee)
    k_s = summarize_kpis(df_shiffa, mapper_shiffa)
    cols = st.columns(3)
    with cols[0]:
        st.metric("Δ Revenue (Estee - Shiffa)", f"{(k_e['Revenue']-k_s['Revenue']):,.2f}" if all([isinstance(k_e['Revenue'],(int,float)), isinstance(k_s['Revenue'],(int,float))]) else "—")
    with cols[1]:
        st.metric("Δ Units (Estee - Shiffa)", f"{(k_e['Units']-k_s['Units']):,.2f}" if all([isinstance(k_e['Units'],(int,float)), isinstance(k_s['Units'],(int,float))]) else "—")
    with cols[2]:
        aov_e = k_e["AOV"] if isinstance(k_e["AOV"],(int,float)) else np.nan
        aov_s = k_s["AOV"] if isinstance(k_s["AOV"],(int,float)) else np.nan
        st.metric("Δ AOV (Estee - Shiffa)", f"{(aov_e - aov_s):,.2f}" if not (np.isnan(aov_e) or np.isnan(aov_s)) else "—")

    # Category Mix Comparison
    if mapper_estee["category"] and mapper_shiffa["category"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = df_estee.groupby(mapper_estee["category"])[mapper_estee["revenue"]].sum().reset_index()
        s = df_shiffa.groupby(mapper_shiffa["category"])[mapper_shiffa["revenue"]].sum().reset_index()
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        e.columns = ["Category","Revenue","Brand"]
        s.columns = ["Category","Revenue","Brand"]
        mix = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.bar(mix, x="Category", y="Revenue", color="Brand", barmode="group", title="Category Mix Comparison"), use_container_width=True)

    # Region Split Comparison
    if mapper_estee["region"] and mapper_shiffa["region"] and mapper_estee["revenue"] and mapper_shiffa["revenue"]:
        e = df_estee.groupby(mapper_estee["region"])[mapper_estee["revenue"]].sum().reset_index()
        s = df_shiffa.groupby(mapper_shiffa["region"])[mapper_shiffa["revenue"]].sum().reset_index()
        e["Brand"] = "Estee"; s["Brand"] = "Shiffa"
        e.columns = ["Region","Revenue","Brand"]
        s.columns = ["Region","Revenue","Brand"]
        mix = pd.concat([e,s], ignore_index=True)
        st.plotly_chart(px.bar(mix, x="Region", y="Revenue", color="Brand", barmode="group", title="Region Split Comparison"), use_container_width=True)

    # Price–Quantity scatter with trend
    if mapper_estee["price"] and mapper_estee["units"]:
        df1 = df_estee[[mapper_estee["price"], mapper_estee["units"]]].copy()
        df1.columns = ["Price","Units"]; df1["Brand"]="Estee"
    else:
        df1 = pd.DataFrame(columns=["Price","Units","Brand"])

    if mapper_shiffa["price"] and mapper_shiffa["units"]:
        df2 = df_shiffa[[mapper_shiffa["price"], mapper_shiffa["units"]]].copy()
        df2.columns = ["Price","Units"]; df2["Brand"]="Shiffa"
    else:
        df2 = pd.DataFrame(columns=["Price","Units","Brand"])

    if not df1.empty or not df2.empty:
        both = pd.concat([df1, df2], ignore_index=True)
        st.plotly_chart(px.scatter(both, x="Price", y="Units", color="Brand", trendline="ols", title="Price–Quantity Elasticity (Sketch)"), use_container_width=True)

    # Similarity of distributions (Category, Region) via cosine similarity
    def distribution_similarity(col, value_col):
        if not (mapper_estee[col] and mapper_shiffa[col] and mapper_estee[value_col] and mapper_shiffa[value_col]):
            return None
        e = df_estee.groupby(mapper_estee[col])[mapper_estee[value_col]].sum()
        s = df_shiffa.groupby(mapper_shiffa[col])[mapper_shiffa[value_col]].sum()
        # align index
        idx = sorted(set(e.index).union(set(s.index)))
        e = e.reindex(idx).fillna(0)
        s = s.reindex(idx).fillna(0)
        num = (e*s).sum()
        den = np.sqrt((e**2).sum()) * np.sqrt((s**2).sum())
        cos = float(num/den) if den else np.nan
        return cos

    cols2 = st.columns(2)
    with cols2[0]:
        sim_cat = distribution_similarity("category","revenue")
        st.metric("Category Mix Similarity (cosine)", f"{sim_cat:.3f}" if isinstance(sim_cat,(int,float)) and not np.isnan(sim_cat) else "—")
    with cols2[1]:
        sim_reg = distribution_similarity("region","revenue")
        st.metric("Region Mix Similarity (cosine)", f"{sim_reg:.3f}" if isinstance(sim_reg,(int,float)) and not np.isnan(sim_reg) else "—")

st.caption("Tip: Use the sidebar to remap columns if any chart looks off.")

