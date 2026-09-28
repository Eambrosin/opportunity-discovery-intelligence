from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_insights import generate_evidence_aware_brief
from discovery_engine import (
    TargetProfile,
    build_search_queries,
    qualification_handoff,
    screen_candidates,
)
from web_discovery import discover_with_tavily


st.set_page_config(
    page_title="Opportunity Discovery Intelligence",
    page_icon="🔎",
    layout="wide",
)

APP_DIR = Path(__file__).parent
SAMPLE_PATH = APP_DIR / "data" / "sample_company_universe.csv"

st.title("🔎 Opportunity Discovery Intelligence")
st.caption(
    "Evidence-aware target-account discovery for Business Development, GTM and international growth."
)

with st.sidebar:
    st.header("Target Market Profile")

    industry = st.text_input("Target industry", value="Renewable Energy")
    countries_text = st.text_input("Target countries", value="Italy, France")
    regions_text = st.text_input("Target regions", value="Europe")
    models_text = st.text_input(
        "Preferred business models",
        value="Distributor, Wholesaler",
    )
    keywords_text = st.text_input(
        "Required keywords",
        value="solar, photovoltaic, storage",
    )
    excluded_text = st.text_input(
        "Excluded keywords",
        value="residential installer",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        min_size = st.number_input("Min employees", min_value=0, value=20, step=10)
    with col_b:
        max_size = st.number_input("Max employees", min_value=0, value=500, step=50)

    target_roles_text = st.text_input(
        "Target functions",
        value="Business Development, Commercial, Procurement",
    )
    value_proposition = st.text_area(
        "What are you offering?",
        value="International commercial partnership and market-expansion support.",
    )

    st.header("Discovery Source")
    source_mode = st.radio(
        "Source",
        ["Sample dataset", "Upload CSV", "Public web (Tavily)"],
    )

    uploaded = None
    tavily_key = ""
    max_results = 5

    if source_mode == "Upload CSV":
        uploaded = st.file_uploader("Upload company universe CSV", type=["csv"])
    elif source_mode == "Public web (Tavily)":
        tavily_key = st.text_input("Tavily API key", type="password")
        max_results = st.slider("Results per search query", 3, 10, 5)

    run = st.button("Discover & Rank", type="primary", use_container_width=True)


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


profile = TargetProfile(
    industry=industry,
    countries=split_values(countries_text),
    regions=split_values(regions_text),
    business_models=split_values(models_text),
    required_keywords=split_values(keywords_text),
    excluded_keywords=split_values(excluded_text),
    min_company_size=int(min_size) if min_size else None,
    max_company_size=int(max_size) if max_size else None,
    target_roles=split_values(target_roles_text),
    value_proposition=value_proposition,
)

if "ranked_candidates" not in st.session_state:
    st.session_state.ranked_candidates = pd.DataFrame()

if run:
    try:
        if source_mode == "Sample dataset":
            source_df = pd.read_csv(SAMPLE_PATH)

        elif source_mode == "Upload CSV":
            if uploaded is None:
                st.warning("Upload a CSV before running discovery.")
                st.stop()
            source_df = pd.read_csv(uploaded)

        else:
            queries = build_search_queries(profile)
            if not queries:
                st.warning("Define at least an industry, market or business model.")
                st.stop()

            st.write("**Generated discovery queries**")
            st.code("\n".join(queries))

            source_df = discover_with_tavily(
                queries=queries,
                api_key=tavily_key,
                max_results_per_query=max_results,
            )

        st.session_state.ranked_candidates = screen_candidates(source_df, profile)

    except Exception as exc:
        st.error(f"Discovery failed: {exc}")

ranked = st.session_state.ranked_candidates

if ranked.empty:
    st.info(
        "Configure the target market on the left and run discovery. "
        "The sample dataset works without any external API key."
    )
    st.stop()

top = ranked[ranked["recommended_action"] != "Exclude"].copy()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Candidates", len(ranked))
m2.metric("80+ Fit", int((top["discovery_score"] >= 80).sum()))
m3.metric("High Confidence", int((top["confidence"] == "High").sum()))
m4.metric(
    "Average Discovery Score",
    f"{top['discovery_score'].mean():.1f}" if not top.empty else "0.0",
)

st.subheader("Target Account Ranking")

display_columns = [
    "company_name",
    "country",
    "industry",
    "business_model",
    "company_size",
    "discovery_score",
    "confidence",
    "recommended_action",
    "why_relevant",
    "source_url",
]
st.dataframe(
    ranked[[column for column in display_columns if column in ranked.columns]],
    use_container_width=True,
    hide_index=True,
)

chart_df = top.head(15)
if not chart_df.empty:
    fig = px.bar(
        chart_df.sort_values("discovery_score"),
        x="discovery_score",
        y="company_name",
        orientation="h",
        title="Top Discovery Opportunities",
        labels={"discovery_score": "Discovery Score", "company_name": "Company"},
    )
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Opportunity Workspace")

selected_company = st.selectbox(
    "Select a candidate",
    ranked["company_name"].astype(str).tolist(),
)
selected = ranked[ranked["company_name"].astype(str) == selected_company].iloc[0]

w1, w2, w3 = st.columns(3)
w1.metric("Discovery Score", f"{selected['discovery_score']:.1f}")
w2.metric("Confidence", selected["confidence"])
w3.metric("Next Step", selected["recommended_action"])

st.markdown(f"**Why relevant:** {selected['why_relevant']}")
st.markdown(
    f"**Unknowns to validate:** {selected['unknowns_to_validate'] or 'None identified'}"
)
if selected.get("source_url"):
    st.markdown(f"**Evidence:** {selected['source_url']}")
if selected.get("source_snippet"):
    st.write(selected["source_snippet"])

with st.expander("Explainable score"):
    breakdown = selected["score_breakdown"]
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except Exception:
            pass
    st.json(breakdown)

st.subheader("Optional AI Evidence Brief")
st.caption(
    "AI is used only after deterministic discovery scoring and is instructed not to invent company facts."
)
openai_key = st.text_input("OpenAI API key (optional)", type="password")

if st.button("Generate Evidence-Aware Brief"):
    brief = generate_evidence_aware_brief(
        selected.to_dict(),
        {
            "industry": profile.industry,
            "countries": profile.countries,
            "regions": profile.regions,
            "business_models": profile.business_models,
            "required_keywords": profile.required_keywords,
            "target_roles": profile.target_roles,
            "value_proposition": profile.value_proposition,
        },
        api_key=openai_key or None,
    )
    if brief is None:
        st.warning("Provide an OpenAI API key to generate the optional brief.")
    else:
        st.json(brief)

st.subheader("Export")

csv = ranked.drop(columns=["score_breakdown"], errors="ignore").to_csv(index=False)
st.download_button(
    "Download Discovery Results",
    csv,
    file_name="opportunity_discovery_results.csv",
    mime="text/csv",
)

handoff = qualification_handoff(top)
st.download_button(
    "Download Qualification Handoff Template",
    handoff.to_csv(index=False),
    file_name="qualification_handoff.csv",
    mime="text/csv",
)
st.caption(
    "The qualification handoff intentionally sets estimated deal value to 0 and engagement to cold. "
    "Validate and enrich those fields before using it for formal opportunity qualification."
)
