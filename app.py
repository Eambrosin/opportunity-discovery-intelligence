from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from account_enrichment import assess_qualification_readiness, enrich_account
from ai_insights import generate_evidence_aware_brief
from contact_discovery import discover_linkedin_contacts, discover_linkedin_market_professionals
from discovery_engine import (
    TargetProfile,
    build_search_queries,
    qualification_handoff,
    screen_candidates,
)
from presets import PRESETS, get_preset, profile_id_for
from sales_intelligence import build_sales_intelligence
from territory_intelligence import (
    apply_territory_intelligence,
    build_territory_search_queries,
    enrich_contacts_with_readiness,
    territory_breakdown,
    territory_gaps,
    territory_summary,
    technology_landscape,
)
from territory_profiles import (
    TERRITORIES,
    all_cluster_ids,
    cluster_labels,
    get_territory,
    priority_cluster_ids,
)
from vendor_profiles import VENDOR_PROFILES, get_vendor_profile
from web_discovery import discover_with_tavily


st.set_page_config(
    page_title="Opportunity Discovery Intelligence",
    page_icon="🔎",
    layout="wide",
)

APP_DIR = Path(__file__).parent
SAMPLE_PATH = APP_DIR / "data" / "sample_company_universe.csv"
DEPLOYMENT_REVISION = "2026-09-29-sales-intelligence-2"


def split_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    text = str(value).strip()
    if text.lower() in {"nan", "none", "<na>", "null"}:
        return default
    return text


def safe_number(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def get_secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return value or os.getenv(name, "")


def update_account_in_session(
    company_name: str,
    source_url: str,
    values: dict,
) -> None:
    dataframe = st.session_state.get(
        "ranked_candidates",
        pd.DataFrame(),
    )
    if not isinstance(dataframe, pd.DataFrame) or dataframe.empty:
        return

    mask = (
        dataframe["company_name"]
        .fillna("")
        .astype(str)
        .eq(str(company_name))
    )

    if source_url and "source_url" in dataframe.columns:
        source_mask = (
            dataframe["source_url"]
            .fillna("")
            .astype(str)
            .eq(str(source_url))
        )
        if source_mask.any():
            mask = mask & source_mask

    for key, value in values.items():
        if key not in dataframe.columns:
            dataframe[key] = pd.NA
        dataframe.loc[mask, key] = value

    st.session_state.ranked_candidates = dataframe


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

    territory_mode = False
    territory = None
    vendor_profile = None
    selected_cluster_ids = []
    selected_territory_regions = []

    if profile_id_for(preset_name) == "medical_aesthetics":
        st.header("Territory Intelligence")
        territory_mode = st.toggle(
            "Territory Intelligence Mode",
            value=True,
            help=(
                "Adds province/city targeting, account opportunity scoring, "
                "technology signals, contact readiness and territory-gap analytics."
            ),
        )

        if territory_mode:
            territory_name = st.selectbox(
                "Territory",
                list(TERRITORIES.keys()),
            )
            territory = get_territory(territory_name)

            selected_territory_regions = st.multiselect(
                "Regions in scope",
                options=territory["regions"],
                default=territory["regions"],
            )

            vendor_name = st.selectbox(
                "Commercial program",
                list(VENDOR_PROFILES.keys()),
                index=(
                    list(VENDOR_PROFILES.keys()).index(
                        "DELEO — North Italy Commercial Program"
                    )
                    if "DELEO — North Italy Commercial Program" in VENDOR_PROFILES
                    else 0
                ),
                help=(
                    "Vendor profiles add discussion themes and technology-fit signals "
                    "without turning evidence into unsupported product recommendations."
                ),
            )
            vendor_profile = get_vendor_profile(vendor_name)

            scope_mode = st.radio(
                "Territory coverage",
                [
                    "Priority clusters",
                    "Full territory",
                    "Custom clusters",
                ],
                help=(
                    "Priority clusters control search-credit use. Full territory covers "
                    "all configured provinces. Custom lets you choose exact clusters."
                ),
            )

            territory_labels = cluster_labels(territory)
            region_cluster_ids = [
                cluster["cluster_id"]
                for cluster in territory["clusters"]
                if cluster["region"] in selected_territory_regions
            ]

            if scope_mode == "Priority clusters":
                selected_cluster_ids = [
                    cid
                    for cid in priority_cluster_ids(territory)
                    if cid in region_cluster_ids
                ]
            elif scope_mode == "Full territory":
                selected_cluster_ids = [
                    cid
                    for cid in all_cluster_ids(territory)
                    if cid in region_cluster_ids
                ]
            else:
                selected_cluster_ids = st.multiselect(
                    "Commercial clusters",
                    options=region_cluster_ids,
                    default=[
                        cid
                        for cid in priority_cluster_ids(territory)
                        if cid in region_cluster_ids
                    ],
                    format_func=lambda cid: territory_labels.get(cid, cid),
                )

            if vendor_profile:
                st.caption(
                    f"Commercial program: {vendor_profile['company']} · "
                    f"{len(vendor_profile.get('support_themes', []))} support themes · "
                    "no automatic device recommendation."
                )

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

        if territory_mode and territory:
            default_queries = max(4, min(len(selected_cluster_ids), 18))
            max_query_budget = max(8, min(max(len(selected_cluster_ids), 8), 24))
        else:
            default_queries = 7 if "Medical Aesthetics" in preset_name else 6
            max_query_budget = 10

        query_budget = st.slider(
            "Search breadth (queries)",
            min_value=(1 if territory_mode and territory else 4),
            max_value=max_query_budget,
            value=min(default_queries, max_query_budget),
            help=(
                "In Territory Mode, one query is normally allocated per commercial cluster. "
                "Higher breadth improves coverage but uses more search credits."
            ),
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
    market_profile_id=profile_id_for(preset_name),
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

if "searched_cluster_ids" not in st.session_state:
    st.session_state.searched_cluster_ids = []

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
            if territory_mode and territory:
                if not selected_cluster_ids:
                    st.warning("Select at least one territory cluster before running discovery.")
                    st.stop()
                queries = build_territory_search_queries(
                    profile=profile,
                    territory=territory,
                    cluster_ids=selected_cluster_ids,
                    max_queries=query_budget,
                )
                st.session_state.searched_cluster_ids = selected_cluster_ids[: len(queries)]
            else:
                queries = build_search_queries(profile, max_queries=query_budget)
                st.session_state.searched_cluster_ids = []

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

        ranked_result = screen_candidates(source_df, profile)

        if territory_mode and territory and source_mode != "Public web (Tavily)":
            st.session_state.searched_cluster_ids = list(selected_cluster_ids)

        if territory_mode and territory:
            ranked_result = apply_territory_intelligence(
                ranked=ranked_result,
                territory=territory,
                vendor_profile=vendor_profile,
            )

        st.session_state.ranked_candidates = ranked_result

    except Exception as exc:
        st.error(f"Discovery failed: {exc}")

raw_ranked = st.session_state.ranked_candidates

if (
    isinstance(raw_ranked, pd.DataFrame)
    and not raw_ranked.empty
    and territory_mode
    and territory
):
    raw_ranked = apply_territory_intelligence(
        ranked=raw_ranked,
        territory=territory,
        vendor_profile=vendor_profile,
    )
    st.session_state.ranked_candidates = raw_ranked

if isinstance(raw_ranked, pd.DataFrame) and not raw_ranked.empty:
    readiness_rows = raw_ranked.apply(
        lambda row: pd.Series(
            assess_qualification_readiness(row.to_dict())
        ),
        axis=1,
    )
    for readiness_column in readiness_rows.columns:
        raw_ranked[readiness_column] = readiness_rows[readiness_column]

    sales_rows = raw_ranked.apply(
        lambda row: pd.Series(
            build_sales_intelligence(
                row.to_dict(),
                profile=profile,
                vendor_profile=vendor_profile,
            )
        ),
        axis=1,
    )
    for sales_column in sales_rows.columns:
        raw_ranked[sales_column] = sales_rows[sales_column]

    st.session_state.ranked_candidates = raw_ranked

if raw_ranked.empty:
    st.info(
        "Configure the target market on the left and run discovery. "
        "The sample dataset works without any external API key."
    )
    st.stop()

if "target_account_ready" in raw_ranked.columns:
    ranked = raw_ranked[
        raw_ranked["target_account_ready"].fillna(False).astype(bool)
    ].copy()
else:
    ranked = raw_ranked.copy()

held_back = raw_ranked.loc[
    ~raw_ranked.index.isin(ranked.index)
].copy()

if ranked.empty:
    st.warning(
        "The search returned research evidence, but no sufficiently clear target accounts "
        "were identified. Review the held-back results or broaden the search."
    )
    with st.expander(
        f"Held-back research results ({len(held_back)})",
        expanded=True,
    ):
        held_columns = [
            "company_name",
            "commercial_track",
            "target_account_reason",
            "account_identity_status",
            "discovery_score",
            "source_domain",
            "source_url",
        ]
        st.dataframe(
            held_back[
                [column for column in held_columns if column in held_back.columns]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "source_url": st.column_config.LinkColumn("Source"),
            },
        )
    st.stop()

top = ranked[ranked["recommended_action"] != "Exclude"].copy()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Raw Search Results", len(raw_ranked))
m2.metric("Target Account Candidates", len(ranked))
m3.metric("80+ Fit", int((top["discovery_score"] >= 80).sum()))
m4.metric(
    "High Confidence",
    int(
        (
            top.get(
                "account_evidence_confidence",
                top["confidence"],
            )
            == "High"
        ).sum()
    ),
)
m5.metric(
    "Average Discovery Score",
    f"{top['discovery_score'].mean():.1f}" if not top.empty else "0.0",
)

if not held_back.empty:
    with st.expander(
        f"Held-back / partner research results ({len(held_back)})",
        expanded=False,
    ):
        st.caption(
            "These results remain available for research but are excluded from the target-account "
            "ranking and qualification handoff because they look like content pages, directories, "
            "suppliers/partners or otherwise ambiguous entities."
        )
        held_columns = [
            "company_name",
            "commercial_track",
            "target_account_reason",
            "account_identity_status",
            "discovery_score",
            "confidence",
            "source_domain",
            "source_url",
        ]
        st.dataframe(
            held_back[
                [column for column in held_columns if column in held_back.columns]
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "source_url": st.column_config.LinkColumn("Source"),
            },
        )

if "qualification_readiness_status" in ranked.columns:
    st.subheader("Qualification Readiness")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric(
        "Ready for Qualification",
        int(
            (
                ranked["qualification_readiness_status"]
                == "Ready for Qualification"
            ).sum()
        ),
    )
    q2.metric(
        "Enrich First",
        int(
            (
                ranked["qualification_readiness_status"]
                == "Enrich Before Qualification"
            ).sum()
        ),
    )
    q3.metric(
        "Research Required",
        int(
            (
                ranked["qualification_readiness_status"]
                == "Research Required"
            ).sum()
        ),
    )
    q4.metric(
        "Average Research Readiness",
        f"{ranked['qualification_readiness_score'].mean():.0f}/100",
    )
    st.caption(
        "Qualification Readiness measures evidence completeness only. "
        "It is separate from Account Opportunity and does not predict a sale."
    )

if territory_mode and territory and "account_opportunity_score" in ranked.columns:
    st.subheader("Territory Command Center")
    territory_metrics = territory_summary(ranked, territory)

    t1, t2, t3, t4, t5, t6 = st.columns(6)
    t1.metric("Territory Accounts", territory_metrics["accounts"])
    t2.metric("80+ Opportunity", territory_metrics["high_opportunity"])
    t3.metric(
        "Source-Verified Location",
        territory_metrics["source_observed_location"],
    )
    t4.metric(
        "Scope-Inferred Location",
        territory_metrics["scope_inferred_location"],
        help="Mapped from the search scope and still requiring location verification.",
    )
    t5.metric(
        "Source Coverage",
        f"{territory_metrics['research_coverage']:.0f}%",
        help=(
            "Share of discovered candidates whose location is supported by source evidence. "
            "Search-scope inference is excluded. This is not market share."
        ),
    )
    t6.metric(
        "Eligibility Validation",
        territory_metrics["eligibility_validation"],
    )

    region_view = territory_breakdown(ranked, "territory_region")
    province_view = territory_breakdown(ranked, "territory_province")

    if not region_view.empty:
        if int(region_view["high_opportunity"].sum()) > 0:
            region_chart = px.bar(
                region_view,
                x="territory_region",
                y="high_opportunity",
                hover_data=["accounts", "average_opportunity_score", "high_confidence"],
                title="80+ Opportunity Accounts by Region",
                labels={
                    "territory_region": "Region",
                    "high_opportunity": "80+ Opportunity Accounts",
                },
            )
        else:
            region_chart = px.bar(
                region_view,
                x="territory_region",
                y="average_opportunity_score",
                hover_data=["accounts", "high_confidence"],
                title="Average Account Opportunity Score by Region",
                labels={
                    "territory_region": "Region",
                    "average_opportunity_score": "Average Opportunity Score",
                },
            )
            st.caption(
                "No account currently exceeds the strict 80+ threshold, so the chart shows "
                "average opportunity quality by region instead of an empty high-opportunity chart."
            )
        st.plotly_chart(region_chart, use_container_width=True)

    if not province_view.empty:
        st.markdown("**Province intelligence**")
        st.dataframe(
            province_view,
            use_container_width=True,
            hide_index=True,
        )

    if selected_cluster_ids:
        gaps = territory_gaps(
            ranked=ranked,
            territory=territory,
            cluster_ids=selected_cluster_ids,
            searched_cluster_ids=st.session_state.get("searched_cluster_ids", []),
        )
        if not gaps.empty:
            with st.expander("Territory coverage & research gaps", expanded=False):
                st.caption(
                    "Coverage gaps describe the current discovery dataset, not the total addressable market."
                )
                st.dataframe(gaps, use_container_width=True, hide_index=True)

st.subheader("Target Account Candidate Ranking")

ranking_view = ranked.copy()
ranking_view["market_country"] = (
    ranking_view["country"]
    .fillna("")
    .astype(str)
    .str.strip()
    .replace("", profile.countries[0] if profile.countries else "")
)
ranking_view["market_industry"] = (
    ranking_view["industry"]
    .fillna("")
    .astype(str)
    .str.strip()
    .replace("", profile.industry)
)
ranking_view["account_type"] = ranking_view.get(
    "commercial_track",
    pd.Series([""] * len(ranking_view), index=ranking_view.index),
)
if "account_evidence_confidence" in ranking_view.columns:
    ranking_view["confidence"] = ranking_view["account_evidence_confidence"]

display_columns = [
    "company_name",
    "account_opportunity_score",
    "qualification_readiness_status",
    "qualification_readiness_score",
    "sales_motion",
    "buyer_access_status",
    "territory_province",
    "territory_city",
    "account_type",
    "confidence",
    "discovery_score",
    "recommended_action",
    "enrichment_status",
    "account_data_completeness",
    "market_country",
    "market_industry",
    "company_size",
    "why_relevant",
    "professional_setting",
    "commercial_track",
    "target_account_reason",
    "account_identity_score",
    "account_identity_status",
    "territory_status",
    "territory_region",
    "observed_technology_axes",
    "source_domain",
    "source_url",
]
st.dataframe(
    ranking_view[
        [column for column in display_columns if column in ranking_view.columns]
    ],
    use_container_width=True,
    hide_index=True,
    column_config={
        "source_url": st.column_config.LinkColumn("Source"),
    },
)

chart_df = top.head(15)
if not chart_df.empty:
    chart_score = (
        "account_opportunity_score"
        if territory_mode and "account_opportunity_score" in chart_df.columns
        else "discovery_score"
    )
    chart_title = (
        "Top Territory Opportunities"
        if chart_score == "account_opportunity_score"
        else "Top Discovery Opportunities"
    )
    fig = px.bar(
        chart_df.sort_values(chart_score),
        x=chart_score,
        y="company_name",
        orientation="h",
        title=chart_title,
        labels={
            chart_score: (
                "Account Opportunity Score"
                if chart_score == "account_opportunity_score"
                else "Discovery Score"
            ),
            "company_name": "Company",
        },
    )
    st.plotly_chart(fig, use_container_width=True)

with st.expander("Account Enrichment — Top Accounts", expanded=False):
    st.caption(
        "Optional enrichment searches public web evidence for a direct account website, "
        "public phone/email/address and additional market-fit signals. "
        "Run it selectively to control search-credit usage."
    )

    enrichment_tavily_key = server_tavily_key or tavily_key

    batch_max = min(5, max(1, len(ranked)))
    batch_count = st.slider(
        "Accounts to enrich",
        min_value=1,
        max_value=batch_max,
        value=min(3, batch_max),
        key="batch_enrichment_count",
    )

    if not enrichment_tavily_key:
        st.info(
            "Configure TAVILY_API_KEY to enable Account Enrichment."
        )
    elif st.button(
        "Enrich Top Accounts",
        key="enrich_top_accounts",
    ):
        enriched_count = 0
        progress = st.progress(0)
        status_box = st.empty()

        batch_accounts = ranked.copy()
        opportunity_column = (
            "account_opportunity_score"
            if "account_opportunity_score" in batch_accounts.columns
            else "discovery_score"
        )

        if "qualification_readiness_score" in batch_accounts.columns:
            batch_accounts = batch_accounts.sort_values(
                [opportunity_column, "qualification_readiness_score"],
                ascending=[False, True],
            )
        else:
            batch_accounts = batch_accounts.sort_values(
                opportunity_column,
                ascending=False,
            )

        if "enrichment_status" in batch_accounts.columns:
            not_enriched = ~batch_accounts[
                "enrichment_status"
            ].fillna("").astype(str).eq("Enriched")
            if not_enriched.any():
                batch_accounts = batch_accounts[not_enriched]

        batch_accounts = batch_accounts.head(batch_count).copy()

        for position, (_, account_row) in enumerate(
            batch_accounts.iterrows(),
            start=1,
        ):
            account_name = str(account_row.get("company_name", ""))
            status_box.write(
                f"Enriching {position}/{batch_count}: {account_name}"
            )
            try:
                enrichment = enrich_account(
                    account=account_row.to_dict(),
                    api_key=enrichment_tavily_key,
                    fit_terms=profile.required_keywords,
                    country=(
                        profile.countries[0]
                        if profile.countries
                        else "Italy"
                    ),
                )
                update_account_in_session(
                    company_name=account_name,
                    source_url=safe_text(account_row.get("source_url", "")),
                    values=enrichment,
                )
                enriched_count += 1
            except Exception as exc:
                st.warning(
                    f"Could not enrich {account_name}: {exc}"
                )

            progress.progress(position / batch_count)

        status_box.success(
            f"Account enrichment completed for {enriched_count}/{batch_count} accounts."
        )
        st.rerun()

st.subheader("Opportunity Workspace")

selected_company = st.selectbox(
    "Select a candidate",
    ranked["company_name"].astype(str).tolist(),
)
selected = ranked[ranked["company_name"].astype(str) == selected_company].iloc[0]

if territory_mode and "account_opportunity_score" in selected.index:
    w1, w2, w3, w4 = st.columns(4)
    w1.metric("Account Opportunity", f"{selected['account_opportunity_score']:.1f}")
    w2.metric(
        "Evidence Confidence",
        selected.get(
            "account_evidence_confidence",
            selected["confidence"],
        ),
    )
    w3.metric("Territory Status", selected.get("territory_status", ""))
    w4.metric(
        "Province",
        selected.get("territory_province", "") or "Needs validation",
    )
else:
    w1, w2, w3 = st.columns(3)
    w1.metric("Discovery Score", f"{selected['discovery_score']:.1f}")
    w2.metric("Confidence", selected["confidence"])
    w3.metric("Next Step", selected["recommended_action"])

st.markdown(f"**Why relevant:** {selected['why_relevant']}")
st.markdown(
    f"**Source-native fields not yet verified:** "
    f"{selected['unknowns_to_validate'] or 'None identified'}"
)
st.caption(
    "Territory and market-profile context are evaluated separately below, so a field can "
    "be absent from the source record even when the territory layer has stronger evidence."
)
if selected.get("matched_keywords"):
    st.markdown(f"**Observed fit signals:** {selected['matched_keywords']}")
if selected.get("professional_setting"):
    st.markdown(f"**Professional setting:** {selected['professional_setting']}")
if selected.get("commercial_track"):
    st.markdown(f"**Commercial track:** {selected['commercial_track']}")

if selected.get("qualification_readiness_status"):
    st.markdown(
        f"**Qualification readiness:** "
        f"{selected['qualification_readiness_status']} "
        f"({safe_number(selected.get('qualification_readiness_score', 0)):.0f}/100)"
    )
    readiness_evidence = safe_text(
        selected.get("qualification_readiness_evidence", "")
    )
    if readiness_evidence:
        st.caption(
            f"Readiness evidence: {readiness_evidence}. "
            "This measures research completeness, not likelihood of sale."
        )

sales_motion = safe_text(selected.get("sales_motion", ""))
if sales_motion:
    st.subheader("Sales Intelligence")
    s1, s2 = st.columns(2)
    s1.metric("Recommended Sales Motion", sales_motion)
    s2.metric(
        "Buyer Access",
        safe_text(
            selected.get("buyer_access_status", ""),
            "Buyer access not established",
        ),
    )

    commercial_hypothesis = safe_text(
        selected.get("commercial_hypothesis", "")
    )
    if commercial_hypothesis:
        st.markdown(
            f"**Commercial hypothesis:** {commercial_hypothesis}"
        )

    commercial_angle = safe_text(
        selected.get("commercial_angle", "")
    )
    if commercial_angle:
        st.markdown(
            f"**Evidence-based commercial angle:** {commercial_angle}"
        )

    next_best_action = safe_text(
        selected.get("next_best_action", "")
    )
    if next_best_action:
        st.markdown(
            f"**Next best action:** {next_best_action}"
        )

    sales_gaps = safe_text(
        selected.get("sales_evidence_gaps", "")
    )
    if sales_gaps:
        st.markdown(
            f"**Evidence gaps to close:** {sales_gaps}"
        )

    qualification_questions = safe_text(
        selected.get("qualification_questions", "")
    )
    if qualification_questions:
        questions = [
            item.strip()
            for item in qualification_questions.split(" | ")
            if item.strip()
        ]
        with st.expander(
            "Qualification questions",
            expanded=False,
        ):
            for question in questions:
                st.markdown(f"- {question}")

    risk_flags = safe_text(
        selected.get("commercial_risk_flags", "")
    )
    if risk_flags:
        st.warning(
            f"Validation flags: {risk_flags}"
        )

    st.caption(
        safe_text(
            selected.get("sales_intelligence_basis", ""),
            "Observed public evidence + deterministic qualification logic; "
            "no purchase intent or win probability inferred.",
        )
    )

if territory_mode and "territory_location_basis" in selected.index:
    st.markdown(
        "**Territory mapping:** "
        f"{selected.get('territory_region', '')} · "
        f"{selected.get('territory_province', '')} · "
        f"{selected.get('territory_city', '') or 'city not verified'} "
        f"— {selected.get('territory_location_basis', '')}"
    )

    if selected.get("observed_technology_axes"):
        st.markdown(
            f"**Observed technology/treatment axes:** "
            f"{selected['observed_technology_axes']}"
        )
    if selected.get("technology_evidence"):
        st.markdown(
            f"**Observed evidence terms:** {selected['technology_evidence']}"
        )
    if selected.get("technology_validation_questions"):
        st.markdown(
            f"**Commercial validation:** "
            f"{selected['technology_validation_questions']}"
        )

    if vendor_profile:
        landscape = technology_landscape(selected, vendor_profile)
        if not landscape.empty:
            st.markdown("**Technology landscape — evidence view**")
            st.dataframe(
                landscape,
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Not observed means not present in the current evidence set — it does not mean the clinic does not offer that technology."
            )

source_url = safe_text(selected.get("source_url", ""))
source_snippet = safe_text(selected.get("source_snippet", ""))

if source_url:
    st.markdown(f"**Primary evidence source:** {source_url}")

if source_snippet:
    evidence_preview = source_snippet[:650]
    if len(source_snippet) > 650:
        evidence_preview += "…"
    st.caption(evidence_preview)

    with st.expander("View full source evidence excerpt", expanded=False):
        st.write(source_snippet)

with st.expander("Explainable score"):
    st.markdown("**Discovery fit score**")
    breakdown = selected["score_breakdown"]
    if isinstance(breakdown, str):
        try:
            breakdown = json.loads(breakdown)
        except Exception:
            pass
    st.json(breakdown)

    if selected.get("account_opportunity_breakdown"):
        st.markdown("**Territory account opportunity score**")
        account_breakdown = selected.get("account_opportunity_breakdown")
        if isinstance(account_breakdown, str):
            try:
                account_breakdown = json.loads(account_breakdown)
            except Exception:
                pass
        st.json(account_breakdown)
        st.caption(
            "The territory score combines discovery fit with location evidence, professional "
            "setting and observed technology/treatment evidence. It does not infer deal value."
        )

st.subheader("Account Enrichment")
st.caption(
    "Searches public web evidence for a direct account website, public business contact "
    "channels and additional fit signals. Enrichment is evidence-only and does not infer "
    "deal value, buying intent or device eligibility."
)

selected_enrichment_key = f"account_enrichment::{selected_company}"
enrichment_tavily_key = server_tavily_key or tavily_key

if not enrichment_tavily_key:
    st.info("Configure TAVILY_API_KEY to enable Account Enrichment.")
else:
    if st.button(
        "Enrich Selected Account",
        key=f"enrich_selected::{selected_company}",
    ):
        try:
            with st.spinner(
                f"Enriching public account evidence for {selected_company}..."
            ):
                enrichment = enrich_account(
                    account=selected.to_dict(),
                    api_key=enrichment_tavily_key,
                    fit_terms=profile.required_keywords,
                    country=(
                        profile.countries[0]
                        if profile.countries
                        else "Italy"
                    ),
                )

                update_account_in_session(
                    company_name=selected_company,
                    source_url=safe_text(selected.get("source_url", "")),
                    values=enrichment,
                )
                st.session_state[selected_enrichment_key] = enrichment
            st.rerun()
        except Exception as exc:
            st.error(f"Account enrichment failed: {exc}")

enrichment_status = safe_text(selected.get("enrichment_status", ""))
if enrichment_status:
    e1, e2, e3 = st.columns(3)
    e1.metric(
        "Enrichment Status",
        enrichment_status,
    )
    e2.metric(
        "Account Data Completeness",
        f"{safe_number(selected.get('account_data_completeness', 0)):.0f}%",
    )
    e3.metric(
        "Website Evidence",
        safe_text(selected.get("website_evidence_status", ""), "Needs verification"),
    )

    account_website = safe_text(selected.get("account_website", ""))
    if account_website:
        st.markdown(f"**Account website:** {account_website}")

    public_address = safe_text(selected.get("public_address", ""))
    if public_address:
        st.markdown(f"**Public address:** {public_address}")

    public_phone = safe_text(selected.get("public_phone", ""))
    public_email = safe_text(selected.get("public_email", ""))
    if public_phone:
        st.markdown(f"**Public phone:** {public_phone}")
    if public_email:
        st.markdown(f"**Public email:** {public_email}")

    public_contact_form = (
        str(selected.get("public_contact_form", "")).strip().lower()
        in {"true", "1", "yes"}
    )
    if public_contact_form:
        st.markdown("**Public contact form:** observed on the official website")

    st.markdown(
        f"**Contact-channel status:** "
        f"{safe_text(selected.get('contact_channel_status', ''), 'No public contact channel observed')}"
    )

    enrichment_fit = safe_text(selected.get("enrichment_fit_signals", ""))
    if enrichment_fit:
        st.markdown(
            f"**Additional public fit evidence:** {enrichment_fit}"
        )

    enrichment_source = safe_text(
        selected.get("enrichment_source_url", "")
    )
    if enrichment_source:
        st.markdown(
            f"**Primary enrichment evidence:** {enrichment_source}"
        )

    st.caption(
        "Public contact details can change. Verify the current website, phone, email and "
        "address before commercial use."
    )
else:
    st.caption(
        "This account has not yet been enriched. Use the button above or the Top Accounts "
        "batch enrichment workflow."
    )

st.subheader("Public Contact & LinkedIn Discovery")
st.caption(
    "Finds publicly indexed LinkedIn profile snippets for the selected account. "
    "It does not log into LinkedIn, scrape private pages or claim unverified contact details."
)

contact_key = f"linkedin_contacts::{selected_company}"
contact_status_key = f"linkedin_contact_status::{selected_company}"
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
                location_parts = [
                    str(selected.get("territory_city") or "").strip(),
                    str(selected.get("territory_province") or "").strip(),
                    str(selected.get("territory_region") or "").strip(),
                ]
                location_context = " ".join(
                    part for part in location_parts if part
                )

                contacts = discover_linkedin_contacts(
                    company_name=selected_company,
                    country=contact_country,
                    target_roles=profile.target_roles,
                    api_key=contact_tavily_key,
                    max_results=8,
                    location_context=location_context,
                )

                if territory_mode:
                    contacts = enrich_contacts_with_readiness(
                        contacts=contacts,
                        account_row=selected,
                    )

            st.session_state[contact_key] = contacts
            if isinstance(contacts, pd.DataFrame) and not contacts.empty:
                raw_profile_count = int(
                    contacts.get(
                        "raw_profile_count",
                        pd.Series([len(contacts)]),
                    ).iloc[0]
                )
                held_back_profile_count = int(
                    contacts.get(
                        "held_back_profile_count",
                        pd.Series([0]),
                    ).iloc[0]
                )
                st.session_state[contact_status_key] = (
                    f"Found {len(contacts)} plausible LinkedIn profile match"
                    f"{'es' if len(contacts) != 1 else ''}"
                    + (
                        f"; {held_back_profile_count} weak homonym/profile match"
                        f"{'es' if held_back_profile_count != 1 else ''} held back."
                        if held_back_profile_count
                        else "."
                    )
                )
            else:
                st.session_state[contact_status_key] = (
                    "No publicly indexed LinkedIn person profiles were found for this "
                    "account in the current search. This does not mean no LinkedIn profile exists."
                )

            if isinstance(contacts, pd.DataFrame) and not contacts.empty:
                top_contact = contacts.iloc[0]
                top_relevance = float(
                    top_contact.get("contact_relevance_score", 0) or 0
                )
                top_confidence = str(
                    top_contact.get("contact_confidence", "") or ""
                )

                decision_values = {
                    "decision_maker_candidate_found": bool(
                        top_relevance >= 75
                    ),
                    "decision_maker_verified": bool(
                        top_relevance >= 100
                        and top_confidence == "High"
                    ),
                    "decision_maker_name": str(
                        top_contact.get("person_name", "") or ""
                    ),
                    "decision_maker_headline": str(
                        top_contact.get("headline", "") or ""
                    ),
                    "decision_maker_linkedin": str(
                        top_contact.get("linkedin_url", "") or ""
                    ),
                    "decision_maker_confidence": top_confidence,
                    "decision_maker_relevance_score": top_relevance,
                }

                update_account_in_session(
                    company_name=selected_company,
                    source_url=str(selected.get("source_url", "") or ""),
                    values=decision_values,
                )

            st.rerun()
        except Exception as exc:
            st.session_state[contact_status_key] = (
                f"Contact discovery failed: {exc}"
            )
            st.error(f"Contact discovery failed: {exc}")

    contact_status_message = st.session_state.get(contact_status_key, "")
    if contact_status_message:
        if contact_status_message.startswith("Found "):
            st.success(contact_status_message)
        elif contact_status_message.startswith("Contact discovery failed:"):
            st.error(contact_status_message)
        else:
            st.warning(contact_status_message)

    contacts = st.session_state.get(contact_key, pd.DataFrame())
    if isinstance(contacts, pd.DataFrame) and not contacts.empty:
        contact_columns = [
            "person_name",
            "headline",
            "contact_relevance_score",
            "contact_confidence",
            "matched_target_roles",
            "professional_role_signal",
            "location_match_evidence",
            "why_contact",
            "contact_readiness_score",
            "contact_status",
            "suggested_outreach_angle",
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

        outreach_handoff = pd.DataFrame(
            {
                "schema_version": "1.0",
                "source_stage": "IDENTIFY",
                "market_profile_id": profile.market_profile_id,
                "contact_name": contacts["person_name"],
                "company": selected_company,
                "country": contact_country,
                "industry": profile.industry,
                "deal_type": "Prospecting",
                "deal_value_usd": 0,
                "deal_value_status": "unknown",
                "engagement_signal": "cold",
                "engagement_status": "unverified",
                "score": float(selected["discovery_score"]),
                "recommended_action": str(selected["recommended_action"]),
                "score_rationale": str(selected["why_relevant"]),
                "linkedin_url": contacts["linkedin_url"],
                "contact_headline": contacts["headline"],
                "outreach_angle": contacts["suggested_outreach_angle"],
                "professional_setting": str(selected.get("professional_setting") or ""),
                "territory_profile_id": str(selected.get("territory_profile_id") or ""),
                "vendor_profile_id": str(selected.get("vendor_profile_id") or ""),
                "territory_region": str(selected.get("territory_region") or ""),
                "territory_province": str(selected.get("territory_province") or ""),
                "territory_city": str(selected.get("territory_city") or ""),
                "territory_cluster_id": str(selected.get("territory_cluster_id") or ""),
                "account_opportunity_score": float(
                    selected.get("account_opportunity_score")
                    or selected.get("discovery_score")
                    or 0
                ),
                "territory_status": str(selected.get("territory_status") or ""),
                "contact_readiness_score": contacts.get(
                    "contact_readiness_score",
                    pd.Series([0] * len(contacts)),
                ),
                "contact_status": contacts.get(
                    "contact_status",
                    pd.Series([""] * len(contacts)),
                ),
                "account_website": safe_text(
                    selected.get("account_website", "")
                ),
                "public_phone": safe_text(
                    selected.get("public_phone", "")
                ),
                "public_email": safe_text(
                    selected.get("public_email", "")
                ),
                "public_address": safe_text(
                    selected.get("public_address", "")
                ),
                "public_contact_form": (
                    str(selected.get("public_contact_form", "")).strip().lower()
                    in {"true", "1", "yes"}
                ),
                "enrichment_status": safe_text(
                    selected.get("enrichment_status", "")
                ),
                "account_data_completeness": safe_number(
                    selected.get("account_data_completeness", 0)
                ),
                "website_evidence_status": safe_text(
                    selected.get("website_evidence_status", "")
                ),
            }
        )
        st.download_button(
            "Download Adaptive Outreach Handoff",
            outreach_handoff.to_csv(index=False),
            file_name="adaptive_outreach_handoff.csv",
            mime="text/csv",
            help="Compatible with the Adaptive Outreach Intelligence portfolio application.",
        )

        st.caption(
            "Use profile evidence as a starting point. Verify the current role and company "
            "before outreach; public search indexes can be stale."
        )
    else:
        if not contact_status_message:
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
                professional_locations = (
                    selected_territory_regions
                    if territory_mode and selected_territory_regions
                    else []
                )
                if (
                    territory_mode
                    and "Trentino-Alto Adige" in professional_locations
                ):
                    professional_locations = (
                        professional_locations
                        + ["Bolzano Bozen Südtirol"]
                    )

                professionals = discover_linkedin_market_professionals(
                    industry=profile.industry,
                    country=profile.countries[0] if profile.countries else "",
                    target_roles=profile.target_roles,
                    market_terms=profile.required_keywords + profile.search_archetypes,
                    api_key=contact_tavily_key,
                    max_results=12,
                    locations=professional_locations,
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

st.subheader("Continue the Workflow")
st.caption(
    "Turn the current discovery research into a working commercial queue before exporting data."
)

queue_columns = [
    "company_name",
    "account_opportunity_score",
    "qualification_readiness_status",
    "qualification_readiness_score",
    "sales_motion",
    "buyer_access_status",
    "territory_province",
    "next_best_action",
]
queue_view = ranked[
    [column for column in queue_columns if column in ranked.columns]
].head(10).copy()

if not queue_view.empty:
    st.markdown("**Commercial action queue — top accounts**")
    st.dataframe(
        queue_view,
        use_container_width=True,
        hide_index=True,
    )

selected_motion = safe_text(
    selected.get("sales_motion", ""),
    "Research & Validate",
)
selected_next_action = safe_text(
    selected.get("next_best_action", ""),
    "Review the evidence and complete qualification research.",
)
selected_readiness = safe_text(
    selected.get("qualification_readiness_status", ""),
    "Research Required",
)

c1, c2, c3 = st.columns(3)
c1.metric("Selected Account", selected_company)
c2.metric("Current Sales Motion", selected_motion)
c3.metric("Qualification State", selected_readiness)

st.info(
    f"Next action for {selected_company}: {selected_next_action}"
)

nav_a, nav_b = st.columns(2)
with nav_a:
    st.link_button(
        "Open PRIORITIZE — Lead Qualification",
        "https://lead-qualification-scorer-eambrosin.streamlit.app/",
        use_container_width=True,
    )
with nav_b:
    st.link_button(
        "Open ENGAGE — Adaptive Outreach",
        "https://outreach-sequence-generator-7dcmglcxfnmszlodg8lqre.streamlit.app/",
        use_container_width=True,
    )

st.subheader("Export & Handoff")

target_csv = ranked.drop(
    columns=["score_breakdown"],
    errors="ignore",
).to_csv(index=False)

st.download_button(
    "Download Target Account Results",
    target_csv,
    file_name=(
        "territory_target_accounts.csv"
        if territory_mode
        else "opportunity_target_accounts.csv"
    ),
    mime="text/csv",
)

raw_csv = raw_ranked.drop(
    columns=["score_breakdown"],
    errors="ignore",
).to_csv(index=False)

with st.expander("Raw research export", expanded=False):
    st.caption(
        "Includes held-back content pages, directories and partner/vendor signals for audit or later research."
    )
    st.download_button(
        "Download Raw Discovery Research",
        raw_csv,
        file_name="raw_discovery_research.csv",
        mime="text/csv",
    )

if territory_mode and territory:
    st.caption(
        "Territory exports include account opportunity, province/city mapping, "
        "technology signals and research-status fields. Location inferred only from "
        "search scope remains explicitly marked for verification."
    )

handoff = qualification_handoff(top, profile=profile)
if handoff.empty:
    st.warning(
        "No target accounts are available for qualification handoff yet. "
        "The current discovery results require additional account-identity validation."
    )
else:
    excluded_from_handoff = max(len(top) - len(handoff), 0)

    if "qualification_readiness_status" in handoff.columns:
        qualification_ready_handoff = handoff[
            handoff["qualification_readiness_status"]
            .fillna("")
            .astype(str)
            .eq("Ready for Qualification")
        ].copy()
    else:
        qualification_ready_handoff = pd.DataFrame()

    st.download_button(
        "Download Qualification Handoff",
        handoff.to_csv(index=False),
        file_name="qualification_handoff.csv",
        mime="text/csv",
        help=(
            "Exports all target-account candidates that passed account-identity screening. "
            "Use Qualification Readiness to decide which should be worked first."
        ),
    )

    if not qualification_ready_handoff.empty:
        st.download_button(
            "Download Qualification-Ready Only",
            qualification_ready_handoff.to_csv(index=False),
            file_name="qualification_ready_handoff.csv",
            mime="text/csv",
            help=(
                "Exports only accounts with sufficient research completeness "
                "for the next qualification stage."
            ),
        )

    readiness_count = len(qualification_ready_handoff)
    st.caption(
        f"{len(handoff)} target-account candidates available for PRIORITIZE; "
        f"{readiness_count} currently meet the research-readiness threshold."
        + (
            f" {excluded_from_handoff} content/document or ambiguous results were held back."
            if excluded_from_handoff
            else ""
        )
        + " Deal value, company size and engagement remain explicitly unverified until qualified."
    )

