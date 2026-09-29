from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from ai_insights import generate_evidence_aware_brief
from contact_discovery import discover_linkedin_contacts, discover_linkedin_market_professionals
from discovery_engine import (
    TargetProfile,
    build_search_queries,
    qualification_handoff,
    screen_candidates,
)
from presets import PRESETS, get_preset
from web_discovery import discover_with_tavily


st.set_page_config(
    page_title="Opportunity Discovery Intelligence",
    page_icon="🔎",
    layout="wide",
)

APP_DIR = Path(__file__).parent
SAMPLE_PATH = APP_DIR / "data" / "sample_company_universe.csv"


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, "")


server_tavily_key = get_secret("TAVILY_API_KEY")
server_openai_key = get_secret("OPENAI_API_KEY")


st.title("🔎 Opportunity Discovery Intelligence")
st.caption(
    "Evidence-aware account discovery, market adaptation and public-contact intelligence "
    "for Business Development, GTM and international growth."
)

with st.sidebar:
    st.header("Target Market Profile")

    preset_name = st.selectbox(
        "Market preset",
        list(PRESETS.keys()),
        help="Start from a reusable commercial scenario, then customize every field.",
    )
    preset = get_preset(preset_name)
    preset_key = preset_name.lower().replace(" ", "_").replace("—", "-")

    industry = st.text_input(
        "Target industry",
        value=preset["industry"],
        key=f"industry_{preset_key}",
    )
    countries_text = st.text_input(
        "Target countries",
        value=preset["countries"],
        key=f"countries_{preset_key}",
    )
    regions_text = st.text_input(
        "Target regions",
        value=preset["regions"],
        key=f"regions_{preset_key}",
    )
    models_text = st.text_area(
        "Customer / business-model types",
        value=preset["business_models"],
        height=100,
        key=f"models_{preset_key}",
        help="Comma-separated target account types. Local-language variants improve discovery.",
    )
    keywords_text = st.text_area(
        "Fit signals / keywords",
        value=preset["keywords"],
        height=100,
        key=f"keywords_{preset_key}",
        help="Positive signals. They are treated as evidence clues, not an all-or-nothing checklist.",
    )
    excluded_text = st.text_input(
        "Excluded signals",
        value=preset["excluded_keywords"],
        key=f"excluded_{preset_key}",
    )
    search_archetypes_text = st.text_area(
        "Discovery archetypes / local market terms",
        value=preset["search_archetypes"],
        height=100,
        key=f"archetypes_{preset_key}",
        help="Localized phrases used to generate more realistic market searches.",
    )

    col_a, col_b = st.columns(2)
    with col_a:
        min_size = st.number_input(
            "Min employees",
            min_value=0,
            value=int(preset["min_size"]),
            step=10,
            key=f"min_size_{preset_key}",
        )
    with col_b:
        max_size = st.number_input(
            "Max employees",
            min_value=0,
            value=int(preset["max_size"]),
            step=50,
            key=f"max_size_{preset_key}",
        )

    target_roles_text = st.text_area(
        "Target decision-maker roles",
        value=preset["target_roles"],
        height=100,
        key=f"roles_{preset_key}",
    )
    value_proposition = st.text_area(
        "What are you offering?",
        value=preset["value_proposition"],
        key=f"value_{preset_key}",
    )

    if preset.get("note"):
        st.info(preset["note"])

    st.header("Discovery Source")
    source_mode = st.radio(
        "Source",
        ["Sample dataset", "Upload CSV", "Public web (Tavily)"],
    )

    uploaded = None
    tavily_key = server_tavily_key
    max_results = 4
    query_budget = 6

    if source_mode == "Upload CSV":
        uploaded = st.file_uploader("Upload company universe CSV", type=["csv"])

    elif source_mode == "Public web (Tavily)":
        if tavily_key:
            st.success("Public web discovery is configured.")
        else:
            st.warning(
                "Public web discovery is not configured on the server. "
                "Add TAVILY_API_KEY to Streamlit Secrets, or provide a temporary key below."
            )
            tavily_key = st.text_input(
                "Temporary Tavily API key",
                type="password",
                help="Used only for the current session and not stored by the app.",
            )

        query_budget = st.slider(
            "Search breadth (queries)",
            min_value=4,
            max_value=10,
            value=7 if "Medical Aesthetics" in preset_name else 6,
            help="Higher breadth can improve fragmented-market coverage but uses more search credits.",
        )
        max_results = st.slider(
            "Results per query",
            min_value=3,
            max_value=8,
            value=5 if "Medical Aesthetics" in preset_name else 4,
        )

    run = st.button("Discover & Rank", type="primary", use_container_width=True)


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
    search_archetypes=split_values(search_archetypes_text),
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
            queries = build_search_queries(profile, max_queries=query_budget)
            if not queries:
                st.warning("Define at least an industry, market or customer type.")
                st.stop()

            st.write("**Generated discovery queries**")
            st.code("\n".join(queries))

            source_df = discover_with_tavily(
                queries=queries,
                api_key=tavily_key,
                max_results_per_query=max_results,
                search_depth="basic",
                exclude_domains=[
                    "linkedin.com",
                    "facebook.com",
                    "instagram.com",
                    "youtube.com",
                    "wikipedia.org",
                    "pinterest.com",
                ],
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
    "source_domain",
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
if selected.get("matched_keywords"):
    st.markdown(f"**Observed fit signals:** {selected['matched_keywords']}")
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

st.subheader("Public Contact & LinkedIn Discovery")
st.caption(
    "Finds publicly indexed LinkedIn profile snippets for the selected account. "
    "It does not log into LinkedIn, scrape private pages or claim unverified contact details."
)

contact_key = f"linkedin_contacts::{selected_company}"
contact_tavily_key = server_tavily_key or tavily_key

if not contact_tavily_key:
    st.info("Configure TAVILY_API_KEY to enable public LinkedIn contact discovery.")
else:
    contact_country = (
        str(selected.get("country") or "").strip()
        or (profile.countries[0] if profile.countries else "")
    )

    if st.button("Find Public LinkedIn Contacts"):
        try:
            with st.spinner("Searching public professional-profile evidence..."):
                contacts = discover_linkedin_contacts(
                    company_name=selected_company,
                    country=contact_country,
                    target_roles=profile.target_roles,
                    api_key=contact_tavily_key,
                    max_results=8,
                )
            st.session_state[contact_key] = contacts
        except Exception as exc:
            st.error(f"Contact discovery failed: {exc}")

    contacts = st.session_state.get(contact_key, pd.DataFrame())
    if isinstance(contacts, pd.DataFrame) and not contacts.empty:
        contact_columns = [
            "person_name",
            "headline",
            "contact_relevance_score",
            "contact_confidence",
            "matched_target_roles",
            "why_contact",
            "linkedin_url",
            "source_snippet",
        ]
        st.dataframe(
            contacts[[column for column in contact_columns if column in contacts.columns]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "linkedin_url": st.column_config.LinkColumn("LinkedIn"),
            },
        )
        st.download_button(
            "Download Contact Shortlist",
            contacts.to_csv(index=False),
            file_name="public_linkedin_contact_shortlist.csv",
            mime="text/csv",
        )
        st.caption(
            "Use profile evidence as a starting point. Verify the current role and company "
            "before outreach; public search indexes can be stale."
        )
    else:
        st.caption(
            "Select a strong account and run contact discovery to identify likely decision makers."
        )

    st.markdown("**Market-level professional discovery**")
    st.caption(
        "Useful for fragmented markets where the professional can be the lead itself, "
        "such as aesthetic physicians, dermatologists, clinic owners and estheticians."
    )

    market_professional_key = f"market_professionals::{preset_name}"
    if st.button("Find Market Professionals on LinkedIn"):
        try:
            with st.spinner("Searching public professional-profile evidence across the target market..."):
                professionals = discover_linkedin_market_professionals(
                    industry=profile.industry,
                    country=profile.countries[0] if profile.countries else "",
                    target_roles=profile.target_roles,
                    market_terms=profile.required_keywords + profile.search_archetypes,
                    api_key=contact_tavily_key,
                    max_results=12,
                )
            st.session_state[market_professional_key] = professionals
        except Exception as exc:
            st.error(f"Market professional discovery failed: {exc}")

    professionals = st.session_state.get(market_professional_key, pd.DataFrame())
    if isinstance(professionals, pd.DataFrame) and not professionals.empty:
        professional_columns = [
            "person_name",
            "headline",
            "professional_relevance_score",
            "professional_confidence",
            "matched_target_roles",
            "matched_market_signals",
            "suggested_outreach_angle",
            "linkedin_url",
            "source_snippet",
        ]
        st.dataframe(
            professionals[
                [column for column in professional_columns if column in professionals.columns]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "linkedin_url": st.column_config.LinkColumn("LinkedIn"),
            },
        )
        st.download_button(
            "Download Market Professional Shortlist",
            professionals.to_csv(index=False),
            file_name="public_linkedin_market_professionals.csv",
            mime="text/csv",
        )

st.subheader("Optional AI Evidence Brief")
st.caption(
    "AI is used only after deterministic discovery scoring and is instructed not to invent company facts."
)

openai_key = server_openai_key

if openai_key:
    st.caption("AI evidence brief is enabled.")
else:
    openai_key = st.text_input(
        "OpenAI API key (optional)",
        type="password",
        help="Optional. Add OPENAI_API_KEY to Streamlit Secrets to enable this for all visitors.",
    )

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
            "search_archetypes": profile.search_archetypes,
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
