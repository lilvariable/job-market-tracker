"""
dashboard/app.py - Job Market Tracker Streamlit Dashboard

Run from the project root:
    streamlit run dashboard/app.py
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Make src/ importable so we can reuse DB_PATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from db import DB_PATH

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Market Tracker",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="metric-container"] {
    background: #161B22;
    border: 1px solid #30363D;
    border-radius: 10px;
    padding: 16px 20px;
}
[data-testid="stMetricLabel"] {
    color: #8B949E;
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
    color: #E6EDF3;
    font-size: 1.8rem;
    font-weight: 700;
}
.section-header {
    color: #8B949E;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin: 2rem 0 0.75rem 0;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid #21262D;
}
[data-testid="stSidebar"] {
    background: #0D1117;
    border-right: 1px solid #21262D;
}
.block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Data loading ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    postings = pd.read_sql_query(
        "SELECT id, title, company, location, search_query, pulled_date, posted_date FROM job_postings",
        conn,
    )
    skills = pd.read_sql_query(
        "SELECT posting_id, skill, category FROM job_skills",
        conn,
    )
    conn.close()
    postings["pulled_date"] = pd.to_datetime(postings["pulled_date"], errors="coerce")
    return postings, skills

postings_df, skills_df = load_data()
merged = skills_df.merge(
    postings_df[["id", "search_query", "pulled_date"]],
    left_on="posting_id",
    right_on="id",
)

# ── Category color map ───────────────────────────────────────────────────────
CATEGORY_COLORS = {
    "Language":         "#6366F1",
    "Database":         "#8B5CF6",
    "Cloud":            "#EC4899",
    "Data Engineering": "#F59E0B",
    "ML/AI":            "#10B981",
    "Analysis":         "#3B82F6",
    "Statistics":       "#06B6D4",
    "Dev Tools":        "#84CC16",
    "Soft Skills":      "#F97316",
}

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Filters")
    role_options = ["All roles"] + sorted(postings_df["search_query"].dropna().unique().tolist())
    selected_role = st.selectbox("Role type", role_options)

    st.markdown("---")
    st.markdown("### About")
    st.markdown(
        "Tracks entry-level data roles pulled weekly from the Adzuna API. "
        "Skills extracted via keyword matching across job descriptions."
    )
    last_pull = postings_df["pulled_date"].max()
    if pd.notna(last_pull):
        st.markdown(f"**Last updated:** {last_pull.strftime('%b %d, %Y')}")
    st.markdown("[View on GitHub](https://github.com/lilvariable/job-market-tracker)")

# ── Apply filters ─────────────────────────────────────────────────────────────
if selected_role == "All roles":
    filtered_postings = postings_df
    filtered_merged = merged
else:
    filtered_postings = postings_df[postings_df["search_query"] == selected_role]
    filtered_merged = merged[merged["search_query"] == selected_role]

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# Entry-Level Data Job Market")
st.markdown(
    f"Tracking **{len(postings_df):,}** postings across "
    f"**{postings_df['search_query'].nunique()}** role types — updated weekly via GitHub Actions."
)

# ── KPI cards ─────────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Overview</p>', unsafe_allow_html=True)
k1, k2, k3, k4 = st.columns(4)

top_skill = (
    filtered_merged.groupby("skill")["posting_id"].nunique().idxmax()
    if not filtered_merged.empty else "—"
)
k1.metric("Total Postings", f"{len(filtered_postings):,}")
k2.metric("Unique Companies", f"{filtered_postings['company'].nunique():,}")
k3.metric("Skills Tracked", f"{filtered_merged['skill'].nunique():,}")
k4.metric("Top Skill", top_skill)

# ── Top skills bar chart ──────────────────────────────────────────────────────
st.markdown('<p class="section-header">Most In-Demand Skills</p>', unsafe_allow_html=True)

top_n = st.slider("Number of skills to display", min_value=10, max_value=30, value=20, step=5)

skill_counts = (
    filtered_merged.groupby(["skill", "category"])["posting_id"]
    .nunique()
    .reset_index()
    .rename(columns={"posting_id": "postings"})
    .sort_values("postings", ascending=True)
    .tail(top_n)
)

fig_bar = px.bar(
    skill_counts,
    x="postings",
    y="skill",
    color="category",
    orientation="h",
    color_discrete_map=CATEGORY_COLORS,
    labels={"postings": "Number of postings", "skill": ""},
    template="plotly_dark",
)
fig_bar.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    legend_title="Category",
    height=max(400, top_n * 26),
    margin=dict(l=0, r=20, t=10, b=40),
    font=dict(color="#E6EDF3"),
    xaxis=dict(gridcolor="#21262D"),
    yaxis=dict(gridcolor="rgba(0,0,0,0)"),
)
st.plotly_chart(fig_bar, use_container_width=True)

# ── Role × Skill heatmap ──────────────────────────────────────────────────────
st.markdown('<p class="section-header">Skills by Role Type</p>', unsafe_allow_html=True)
st.caption("How often each top skill appears across role types.")

top_skills_list = (
    merged.groupby("skill")["posting_id"]
    .nunique()
    .sort_values(ascending=False)
    .head(25)
    .index.tolist()
)

heatmap_data = (
    merged[merged["skill"].isin(top_skills_list)]
    .groupby(["search_query", "skill"])["posting_id"]
    .nunique()
    .reset_index()
    .rename(columns={"posting_id": "postings", "search_query": "role"})
    .pivot(index="role", columns="skill", values="postings")
    .fillna(0)
)
heatmap_data.index = (
    heatmap_data.index
    .str.replace("entry level", "", case=False)
    .str.replace("junior", "", case=False)
    .str.strip()
    .str.title()
)

fig_heat = go.Figure(data=go.Heatmap(
    z=heatmap_data.values,
    x=heatmap_data.columns.tolist(),
    y=heatmap_data.index.tolist(),
    colorscale=[[0, "#161B22"], [0.3, "#312E81"], [0.7, "#4F46E5"], [1.0, "#A5B4FC"]],
    hoverongaps=False,
    hovertemplate="<b>%{y}</b><br>%{x}: %{z:.0f} postings<extra></extra>",
))
fig_heat.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=280,
    margin=dict(l=0, r=0, t=10, b=80),
    font=dict(color="#E6EDF3"),
    xaxis=dict(tickangle=-40),
)
st.plotly_chart(fig_heat, use_container_width=True)

# ── Category breakdown + Top companies ───────────────────────────────────────
st.markdown('<p class="section-header">Breakdown</p>', unsafe_allow_html=True)
col_cat, col_comp = st.columns(2)

with col_cat:
    st.markdown("**Skills by category**")
    cat_counts = (
        filtered_merged.groupby("category")["posting_id"]
        .nunique()
        .reset_index()
        .rename(columns={"posting_id": "postings"})
        .sort_values("postings", ascending=False)
    )
    fig_pie = px.pie(
        cat_counts,
        names="category",
        values="postings",
        color="category",
        color_discrete_map=CATEGORY_COLORS,
        hole=0.45,
        template="plotly_dark",
    )
    fig_pie.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        height=320,
        margin=dict(l=0, r=0, t=10, b=0),
        font=dict(color="#E6EDF3"),
        showlegend=True,
        legend=dict(orientation="v", x=1, y=0.5),
    )
    fig_pie.update_traces(
        textinfo="percent",
        hovertemplate="%{label}: %{value} postings<extra></extra>",
    )
    st.plotly_chart(fig_pie, use_container_width=True)

with col_comp:
    st.markdown("**Top hiring companies**")
    company_counts = (
        filtered_postings["company"]
        .dropna()
        .value_counts()
        .head(10)
        .reset_index()
    )
    company_counts.columns = ["company", "postings"]

    fig_comp = px.bar(
        company_counts.sort_values("postings"),
        x="postings",
        y="company",
        orientation="h",
        template="plotly_dark",
        color_discrete_sequence=["#6366F1"],
        labels={"postings": "Postings", "company": ""},
    )
    fig_comp.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=320,
        margin=dict(l=0, r=20, t=10, b=40),
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#21262D"),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig_comp, use_container_width=True)

# ── Posting trend ─────────────────────────────────────────────────────────────
st.markdown('<p class="section-header">Postings Over Time</p>', unsafe_allow_html=True)
st.caption("New postings ingested per pull date — grows each Monday as GitHub Actions runs.")

trend = (
    filtered_postings.dropna(subset=["pulled_date"])
    .groupby(["pulled_date", "search_query"])
    .size()
    .groupby(level="search_query")
    .cumsum()
    .reset_index(name="postings")
)

if len(trend["pulled_date"].unique()) > 1:
    fig_trend = px.line(
        trend,
        x="pulled_date",
        y="postings",
        color="search_query",
        markers=True,
        template="plotly_dark",
        labels={
            "pulled_date": "Pull date",
            "postings": "New postings",
            "search_query": "Role",
        },
    )
    fig_trend.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=300,
        margin=dict(l=0, r=20, t=10, b=40),
        font=dict(color="#E6EDF3"),
        xaxis=dict(gridcolor="#21262D"),
        yaxis=dict(gridcolor="#21262D"),
        legend_title="Role type",
    )
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info(
        "Trend data will appear after multiple weekly pulls accumulate. "
        "Check back after the GitHub Actions job has run a few times."
    )