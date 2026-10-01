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
from milano_discovery import build_milano_discovery_plan
from presets import PRESETS, get_preset, profile_id_for
from sales_intelligence import build_sales_intelligence
from field_sales_intelligence import (
    build_field_sales_intelligence,
    revenue_target_scenarios,
)

try:
    from field_sales_intelligence import revenue_execution_capacity
except ImportError:
    def revenue_execution_capacity(
        vendor_profile,
        *,
        field_days_per_month,
        qualified_visits_per_day,
    ):
        """Backward-compatible fallback for stale Streamlit module caches."""
        scenarios = revenue_target_scenarios(vendor_profile)
        if scenarios.empty:
            return pd.DataFrame()

        field_days = max(0, int(field_days_per_month))
        visits_per_day = max(0.0, float(qualified_visits_per_day))
        visits_per_month = field_days * visits_per_day

        result = scenarios.copy()
        result["field_days_per_month"] = field_days
        result["qualified_visits_per_day"] = visits_per_day
        result["qualified_visits_per_month"] = round(visits_per_month, 1)

        if visits_per_month <= 0:
            result["required_visit_to_sale_conversion_pct"] = 0.0
            result["visits_per_required_sale"] = 0.0
            return result

        exact_units_per_month = (
            result["annual_target_eur"]
            / result["average_ticket_eur"]
            / 12
        )
        result["required_visit_to_sale_conversion_pct"] = (
            exact_units_per_month / visits_per_month * 100
        ).round(2)
        result["visits_per_required_sale"] = (
            visits_per_month / exact_units_per_month
        ).round(1)
        return result
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
DEPLOYMENT_REVISION = "2026-10-01-milano-discovery-import-fix"


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


def safe_filename(value: str) -> str:
    return (
        str(value or "account")
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("\\", "_")
    )


def render_status_card(
    label: str,
    value,
    caption: str = "",
) -> None:
    with st.container(border=True):
        st.caption(label)
        st.markdown(
            f"**{safe_text(value, 'Not available')}**"
        )
        if caption:
            st.caption(caption)


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
                    "Milano deep dive",
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

            if scope_mode == "Milano deep dive":
                selected_cluster_ids = (
                    ["lombardia_milano"]
                    if "lombardia_milano" in region_cluster_ids
                    else []
                )
                if selected_cluster_ids:
                    st.caption(
                        "Milano deep dive rotates multiple medical-aesthetics search angles "
                        "inside the Milano cluster before expanding geographically."
                    )
                else:
                    st.warning(
                        "Milano deep dive requires Lombardia to remain selected in Regions in scope."
                    )
            elif scope_mode == "Priority clusters":
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
            if scope_mode == "Milano deep dive":
                default_queries = 8
                max_query_budget = 10
            else:
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
            max_value=10,
            value=6 if "Medical Aesthetics" in preset_name else 4,
            help=(
                "For a focused Milano deep dive, 6–8 results per query can materially improve "
                "account density. Broader settings consume more search credits."
            ),
        )

        if territory_mode and territory and len(selected_cluster_ids) == 1:
            selected_label = territory_labels.get(
                selected_cluster_ids[0],
                selected_cluster_ids[0],
            )
            st.caption(
                f"Deep-dive mode available for {selected_label}: increase Search breadth to rotate "
                "multiple clinic/practitioner search angles within the same cluster."
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
                query_plan = []
                if scope_mode == "Milano deep dive":
                    query_plan = build_milano_discovery_plan(query_budget)
                    queries = [item.query for item in query_plan]
                else:
                    queries = build_territory_search_queries(
                        profile=profile,
                        territory=territory,
                        cluster_ids=selected_cluster_ids,
                        max_queries=query_budget,
                    )
                st.session_state.searched_cluster_ids = list(selected_cluster_ids)
            else:
                queries = build_search_queries(profile, max_queries=query_budget)
                st.session_state.searched_cluster_ids = []

            if not queries:
                st.warning("Define at least an industry, market or customer type.")
                st.stop()

            st.write("**Generated discovery queries**")
            dq1, dq2, dq3 = st.columns(3)
            dq1.metric("Requested Queries", query_budget)
            dq2.metric("Generated Queries", len(queries))
            dq3.metric("Results / Query", max_results)

            if len(queries) < query_budget:
                st.warning(
                    f"Only {len(queries)} distinct queries were generated from a requested "
                    f"budget of {query_budget}. Review the search profile before interpreting coverage."
                )

            if territory_mode and territory and scope_mode == "Milano deep dive":
                plan_df = pd.DataFrame(
                    [
                        {
                            "Pass": item.stage,
                            "Purpose": item.objective,
                            "Query": item.query,
                        }
                        for item in query_plan
                    ]
                )
                st.dataframe(
                    plan_df,
                    use_container_width=True,
                    hide_index=True,
                )
            else:
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

            stage_map = {}
            if territory_mode and territory and scope_mode == "Milano deep dive":
                stage_map = {
                    item.query: item.stage
                    for item in query_plan
                }
                source_df["discovery_pass"] = (
                    source_df.get("discovery_query", pd.Series(dtype=str))
                    .map(stage_map)
                    .fillna("Unclassified")
                )

            st.session_state.discovery_run_diagnostics = {
                "requested_queries": int(query_budget),
                "generated_queries": int(len(queries)),
                "results_per_query": int(max_results),
                "unique_raw_results": int(len(source_df)),
                "scope_mode": scope_mode if territory_mode and territory else "",
                "query_stage_map": stage_map,
            }

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

    field_sales_rows = raw_ranked.apply(
        lambda row: pd.Series(
            build_field_sales_intelligence(
                row.to_dict(),
                vendor_profile=vendor_profile,
            )
        ),
        axis=1,
    )
    for field_sales_column in field_sales_rows.columns:
        raw_ranked[field_sales_column] = field_sales_rows[field_sales_column]

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
m3.metric("80+ Discovery Fit", int((top["discovery_score"] >= 80).sum()))
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

run_diag = st.session_state.get("discovery_run_diagnostics", {})
if run_diag and source_mode == "Public web (Tavily)":
    generated_queries = int(run_diag.get("generated_queries", 0) or 0)
    results_per_query = int(run_diag.get("results_per_query", 0) or 0)
    potential_slots = generated_queries * results_per_query
    unique_yield = (
        len(raw_ranked) / potential_slots * 100
        if potential_slots > 0
        else 0.0
    )
    target_retention = (
        len(ranked) / len(raw_ranked) * 100
        if len(raw_ranked) > 0
        else 0.0
    )
    with st.expander("Discovery efficiency diagnostics", expanded=False):
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Search Result Slots", potential_slots)
        d2.metric("Unique Result Yield", f"{unique_yield:.0f}%")
        d3.metric("Target Retention", f"{target_retention:.0f}%")
        d4.metric("Unique Target Accounts", len(ranked))
        st.caption(
            "Unique Result Yield shows how much query overlap exists before qualification. "
            "Target Retention shows how much of the unique research set survives account screening. "
            "Low yield suggests broader search angles; low retention suggests noisy discovery inputs."
        )

        if (
            run_diag.get("scope_mode") == "Milano deep dive"
            and "discovery_pass" in raw_ranked.columns
        ):
            pass_order = [
                "Market Core",
                "Technology / Treatment",
                "Geographic Coverage",
                "Unclassified",
            ]
            pass_rows = []
            for discovery_pass in pass_order:
                raw_pass = raw_ranked[
                    raw_ranked["discovery_pass"].astype(str) == discovery_pass
                ]
                if raw_pass.empty:
                    continue
                target_pass = ranked[
                    ranked["discovery_pass"].astype(str) == discovery_pass
                ]
                pass_rows.append(
                    {
                        "Pass": discovery_pass,
                        "First-seen unique results": len(raw_pass),
                        "Target accounts": len(target_pass),
                        "Retention": (
                            f"{(len(target_pass) / len(raw_pass) * 100):.0f}%"
                            if len(raw_pass)
                            else "0%"
                        ),
                    }
                )

            if pass_rows:
                st.markdown("**Three-pass contribution**")
                st.dataframe(
                    pd.DataFrame(pass_rows),
                    use_container_width=True,
                    hide_index=True,
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

    if vendor_profile:
        target_scenarios = revenue_target_scenarios(vendor_profile)
        if not target_scenarios.empty:
            annual_target = int(target_scenarios["annual_target_eur"].iloc[0])
            st.markdown(
                f"**Revenue planning benchmark:** €{annual_target:,.0f} annual target"
            )
            st.dataframe(
                target_scenarios.rename(
                    columns={
                        "average_ticket_eur": "Average Ticket (€)",
                        "units_per_year": "Units / Year",
                        "units_per_month": "Units / Month",
                        "annual_target_eur": "Annual Target (€)",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )
            field_cfg = vendor_profile.get("field_execution", {})
            milan_visits = field_cfg.get("milan_target_visits_per_day", [])
            if len(milan_visits) >= 2:
                st.caption(
                    f"Milano planning assumption: {milan_visits[0]}–{milan_visits[1]} "
                    "qualified clinic visits/day when account density and scheduling allow it. "
                    "Outside Milano, daily visit volume should fall as travel time increases."
                )

            with st.expander("€1M Revenue Execution Model", expanded=False):
                st.caption(
                    "Capacity planning only — not a forecast. Adjust the field rhythm to see "
                    "the visit-to-sale conversion mathematically required by each average-ticket scenario."
                )
                rc1, rc2 = st.columns(2)
                with rc1:
                    field_days_per_month = st.slider(
                        "Field days / month",
                        min_value=10,
                        max_value=22,
                        value=18,
                        step=1,
                        key="revenue_capacity_field_days",
                    )
                with rc2:
                    qualified_visits_per_day = st.slider(
                        "Qualified clinic visits / field day",
                        min_value=2.0,
                        max_value=7.0,
                        value=6.5,
                        step=0.5,
                        key="revenue_capacity_visits_day",
                        help=(
                            "6–7 can represent a dense Milano day. Reduce this assumption "
                            "when planning dispersed provinces."
                        ),
                    )

                execution_model = revenue_execution_capacity(
                    vendor_profile,
                    field_days_per_month=field_days_per_month,
                    qualified_visits_per_day=qualified_visits_per_day,
                )
                if not execution_model.empty:
                    execution_view = execution_model[
                        [
                            "average_ticket_eur",
                            "units_per_month",
                            "qualified_visits_per_month",
                            "required_visit_to_sale_conversion_pct",
                            "visits_per_required_sale",
                        ]
                    ].rename(
                        columns={
                            "average_ticket_eur": "Average Ticket (€)",
                            "units_per_month": "Units / Month",
                            "qualified_visits_per_month": "Qualified Visits / Month",
                            "required_visit_to_sale_conversion_pct": "Required Visit→Sale (%)",
                            "visits_per_required_sale": "Visits / Required Sale",
                        }
                    )
                    st.dataframe(
                        execution_view,
                        use_container_width=True,
                        hide_index=True,
                    )
                    st.caption(
                        "The model deliberately separates activity capacity from forecast probability. "
                        "Real conversion should be learned from field results and updated over time."
                    )

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
    "visit_priority",
    "visit_priority_score",
    "product_fit_family",
    "product_fit_status",
    "planning_opportunity_value_eur",
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

    batch_max = min(10, max(1, len(ranked)))
    batch_count = st.slider(
        "Accounts to prepare",
        min_value=1,
        max_value=batch_max,
        value=min(5, batch_max),
        key="batch_enrichment_count",
        help=(
            "Prepares the highest-priority field accounts by enriching public website, "
            "contact and fit evidence. Larger batches consume more Tavily search credits."
        ),
    )

    if not enrichment_tavily_key:
        st.info(
            "Configure TAVILY_API_KEY to enable Account Enrichment."
        )
    elif st.button(
        "Prepare Top Field Accounts",
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

        sort_columns = []
        sort_ascending = []
        if "visit_priority_score" in batch_accounts.columns:
            sort_columns.append("visit_priority_score")
            sort_ascending.append(False)
        sort_columns.append(opportunity_column)
        sort_ascending.append(False)
        if "qualification_readiness_score" in batch_accounts.columns:
            sort_columns.append("qualification_readiness_score")
            sort_ascending.append(True)

        batch_accounts = batch_accounts.sort_values(
            sort_columns,
            ascending=sort_ascending,
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
                f"Preparing field account {position}/{len(batch_accounts)}: {account_name}"
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

        st.session_state["field_preparation_notice"] = (
            f"Prepared {enriched_count}/{len(batch_accounts)} field accounts. "
            "Qualification readiness and field priority have been recalculated."
        )
        st.rerun()

if st.session_state.get("field_preparation_notice"):
    st.success(st.session_state.pop("field_preparation_notice"))

st.subheader("Account Intelligence Workspace")

selected_company = st.selectbox(
    "Select a candidate",
    ranked["company_name"].astype(str).tolist(),
)
selected = ranked[ranked["company_name"].astype(str) == selected_company].iloc[0]

field_decision = safe_text(
    selected.get("visit_priority", ""),
    "Research before field allocation",
)
field_score = safe_number(selected.get("visit_priority_score", 0))
field_city = safe_text(selected.get("territory_city", ""))
field_province = safe_text(selected.get("territory_province", ""))
field_location = field_city or field_province or "Location to verify"
product_family = safe_text(
    selected.get("product_fit_family", ""),
    "Needs discovery",
)
product_status = safe_text(selected.get("product_fit_status", ""))
field_next_action = safe_text(
    selected.get("field_next_best_action", ""),
    safe_text(selected.get("next_best_action", ""), "Complete qualification research"),
)

why_now_parts = []
if safe_text(selected.get("account_evidence_confidence", "")) == "High":
    why_now_parts.append("high evidence confidence")
location_basis = safe_text(selected.get("territory_location_basis", ""))
if location_basis.startswith("Source-observed"):
    why_now_parts.append(f"{field_location} location verified")
if safe_text(selected.get("qualification_readiness_status", "")) == "Ready for Qualification":
    why_now_parts.append("research-ready")
buyer_access = safe_text(selected.get("buyer_access_status", ""))
if "contact path" in buyer_access.lower() or "business contact" in buyer_access.lower():
    why_now_parts.append("public contact path")
if safe_text(selected.get("professional_setting", "")):
    why_now_parts.append("medical-setting evidence")

why_now = " · ".join(why_now_parts[:4]) or "Complete the remaining evidence gaps before allocating field time."

if product_family == "Needs discovery":
    deleo_hypothesis = "No product-specific evidence yet — discover the clinic need before pitching a device."
else:
    deleo_hypothesis = (
        f"{product_family}"
        + (f" — {product_status}" if product_status else "")
    )

validation_focus = safe_text(
    selected.get("technology_validation_questions", ""),
    "Current treatment portfolio, installed technology, patient demand and investment timing",
)

with st.container(border=True):
    st.markdown("### 🚗 Field Decision Brief")
    fd1, fd2 = st.columns(2)
    with fd1:
        st.markdown("**VISIT DECISION**")
        st.markdown(f"{field_decision} · {field_location} · {field_score:.0f}/100")
        st.markdown("**WHY NOW**")
        st.markdown(why_now)
        st.markdown("**NEXT ACTION**")
        st.markdown(field_next_action)
    with fd2:
        st.markdown("**DELEO HYPOTHESIS**")
        st.markdown(deleo_hypothesis)
        st.markdown("**WHAT TO DISCOVER**")
        st.markdown(validation_focus)

if territory_mode and "account_opportunity_score" in selected.index:
    w1, w2, w3, w4, w5 = st.columns(5)
    with w1:
        st.metric(
            "Account Opportunity",
            f"{selected['account_opportunity_score']:.1f}",
        )
    with w2:
        render_status_card(
            "Evidence Confidence",
            selected.get(
                "account_evidence_confidence",
                selected["confidence"],
            ),
        )
    with w3:
        render_status_card(
            "Territory Status",
            selected.get("territory_status", ""),
        )
    with w4:
        render_status_card(
            "Visit Priority",
            selected.get("visit_priority", "")
            or "Needs validation",
            f"{safe_number(selected.get('visit_priority_score', 0)):.0f}/100",
        )
    with w5:
        render_status_card(
            "Province",
            selected.get("territory_province", "")
            or "Needs validation",
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
    with s1:
        render_status_card(
            "Sales Motion",
            sales_motion,
            "Recommended next commercial motion based on observed evidence.",
        )
    with s2:
        render_status_card(
            "Buyer Access",
            safe_text(
                selected.get("buyer_access_status", ""),
                "Buyer access not established",
            ),
            "Publicly observed access path; decision authority may still require validation.",
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

field_visit_priority = safe_text(selected.get("visit_priority", ""))
if field_visit_priority:
    st.subheader("Field Sales Intelligence")
    f1, f2, f3 = st.columns(3)
    with f1:
        render_status_card(
            "Visit Priority",
            field_visit_priority,
            f"{safe_number(selected.get('visit_priority_score', 0)):.0f}/100 field-allocation score",
        )
    with f2:
        render_status_card(
            "Product-Fit Hypothesis",
            safe_text(selected.get("product_fit_family", ""), "Needs discovery"),
            safe_text(selected.get("product_fit_status", "")),
        )
    with f3:
        planning_value = safe_number(selected.get("planning_opportunity_value_eur", 0))
        planning_status = safe_text(selected.get("planning_value_status", ""))
        planning_label = (
            "Qualified Opportunity Value"
            if planning_status == "Account-specific value"
            else "Planning Ticket Scenario"
        )
        planning_caption = (
            safe_text(selected.get("planning_value_basis", ""))
            if planning_status == "Account-specific value"
            else "Commercial planning reference only — not an account valuation or forecast."
        )
        render_status_card(
            planning_label,
            f"€{planning_value:,.0f}" if planning_value else "Not available",
            planning_caption,
        )

    product_basis = safe_text(selected.get("product_fit_basis", ""))
    if product_basis:
        st.markdown(f"**Why this product family is worth testing:** {product_basis}")

    field_objective = safe_text(selected.get("field_visit_objective", ""))
    if field_objective:
        st.markdown(f"**Visit objective:** {field_objective}")

    field_next = safe_text(selected.get("field_next_best_action", ""))
    if field_next:
        st.markdown(f"**Field next best action:** {field_next}")

    field_questions = safe_text(selected.get("field_opening_questions", ""))
    if field_questions:
        questions = [
            item.strip()
            for item in field_questions.split(" | ")
            if item.strip()
        ]
        with st.expander("Questions to ask in the clinic", expanded=True):
            st.caption(
                "The data gets you to the right door. These questions are designed to discover "
                "the real need before proposing a solution."
            )
            for question in questions:
                st.markdown(f"- {question}")

    st.caption(
        safe_text(
            selected.get("field_sales_basis", ""),
            "Evidence-aware field-sales planning; no purchase intent or win probability inferred.",
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
    compact_evidence = " ".join(source_snippet.split())
    evidence_preview = compact_evidence[:320]
    if len(compact_evidence) > 320:
        evidence_preview += "…"
    st.markdown(f"**Evidence preview:** {evidence_preview}")

    with st.expander("View raw source evidence excerpt", expanded=False):
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
            "Account Opportunity measures account attractiveness using discovery fit, verified "
            "territory evidence, professional setting and account-identity evidence. Product/technology "
            "evidence is evaluated separately in Product Fit and Visit Priority."
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

st.subheader("Public Contact & LinkedIn Validation")
st.caption(
    "Finds and validates publicly indexed LinkedIn person-profile evidence for the selected account. "
    "Weak homonyms are held back; the workflow does not log into LinkedIn, scrape private pages "
    "or claim unverified contact details."
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
        ]
        st.dataframe(
            contacts[[column for column in contact_columns if column in contacts.columns]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "linkedin_url": st.column_config.LinkColumn("LinkedIn"),
            },
        )
        with st.expander("View contact evidence excerpts", expanded=False):
            evidence_columns = [
                column
                for column in [
                    "person_name",
                    "linkedin_url",
                    "source_snippet",
                ]
                if column in contacts.columns
            ]
            st.dataframe(
                contacts[evidence_columns],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "linkedin_url": st.column_config.LinkColumn("LinkedIn"),
                },
            )

        st.download_button(
            "Download Contact Shortlist",
            contacts.to_csv(index=False),
            file_name=(
                f"{safe_filename(selected_company)}"
                "_linkedin_contact_shortlist.csv"
            ),
            mime="text/csv",
        )

        outreach_handoff = pd.DataFrame(
            {
                "schema_version": "2.0",
                "source_stage": "IDENTIFY_CONTACT_VALIDATED",
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
                "score": safe_number(
                    selected.get(
                        "account_opportunity_score",
                        selected.get("discovery_score", 0),
                    )
                ),
                "discovery_score": safe_number(
                    selected.get("discovery_score", 0)
                ),
                "recommended_action": safe_text(
                    selected.get(
                        "next_best_action",
                        selected.get("recommended_action", ""),
                    )
                ),
                "score_rationale": safe_text(
                    selected.get(
                        "commercial_hypothesis",
                        selected.get("why_relevant", ""),
                    )
                ),
                "linkedin_url": contacts["linkedin_url"],
                "contact_headline": contacts["headline"],
                "contact_outreach_angle": contacts["suggested_outreach_angle"],
                "contact_relevance_score": contacts.get(
                    "contact_relevance_score",
                    pd.Series([0] * len(contacts)),
                ),
                "contact_confidence": contacts.get(
                    "contact_confidence",
                    pd.Series([""] * len(contacts)),
                ),
                "professional_role_signal": contacts.get(
                    "professional_role_signal",
                    pd.Series([""] * len(contacts)),
                ),
                "location_match_evidence": contacts.get(
                    "location_match_evidence",
                    pd.Series([""] * len(contacts)),
                ),
                "contact_match_rationale": contacts.get(
                    "why_contact",
                    pd.Series([""] * len(contacts)),
                ),
                "outreach_angle": safe_text(
                    selected.get("commercial_angle", "")
                ),
                "professional_setting": safe_text(
                    selected.get("professional_setting", "")
                ),
                "account_type": safe_text(
                    selected.get("account_type", "")
                ),
                "commercial_track": safe_text(
                    selected.get("commercial_track", "")
                ),
                "territory_profile_id": safe_text(
                    selected.get("territory_profile_id", "")
                ),
                "vendor_profile_id": safe_text(
                    selected.get("vendor_profile_id", "")
                ),
                "vendor_company": (
                    safe_text(vendor_profile.get("company", ""))
                    if vendor_profile
                    else ""
                ),
                "territory_region": safe_text(
                    selected.get("territory_region", "")
                ),
                "territory_province": safe_text(
                    selected.get("territory_province", "")
                ),
                "territory_city": safe_text(
                    selected.get("territory_city", "")
                ),
                "territory_cluster_id": safe_text(
                    selected.get("territory_cluster_id", "")
                ),
                "territory_status": safe_text(
                    selected.get("territory_status", "")
                ),
                "territory_location_basis": safe_text(
                    selected.get("territory_location_basis", "")
                ),
                "account_opportunity_score": safe_number(
                    selected.get(
                        "account_opportunity_score",
                        selected.get("discovery_score", 0),
                    )
                ),
                "qualification_readiness_score": safe_number(
                    selected.get("qualification_readiness_score", 0)
                ),
                "qualification_readiness_status": safe_text(
                    selected.get("qualification_readiness_status", "")
                ),
                "qualification_readiness_evidence": safe_text(
                    selected.get("qualification_readiness_evidence", "")
                ),
                "sales_motion": safe_text(
                    selected.get("sales_motion", "")
                ),
                "buyer_access_status": safe_text(
                    selected.get("buyer_access_status", "")
                ),
                "commercial_hypothesis": safe_text(
                    selected.get("commercial_hypothesis", "")
                ),
                "commercial_angle": safe_text(
                    selected.get("commercial_angle", "")
                ),
                "next_best_action": safe_text(
                    selected.get("next_best_action", "")
                ),
                "qualification_questions": safe_text(
                    selected.get("qualification_questions", "")
                ),
                "sales_evidence_gaps": safe_text(
                    selected.get("sales_evidence_gaps", "")
                ),
                "commercial_risk_flags": safe_text(
                    selected.get("commercial_risk_flags", "")
                ),
                "sales_intelligence_basis": safe_text(
                    selected.get("sales_intelligence_basis", "")
                ),
                "observed_technology_axes": safe_text(
                    selected.get("observed_technology_axes", "")
                ),
                "product_fit_family": safe_text(
                    selected.get("product_fit_family", "")
                ),
                "product_fit_score": safe_number(
                    selected.get("product_fit_score", 0)
                ),
                "product_fit_status": safe_text(
                    selected.get("product_fit_status", "")
                ),
                "product_fit_basis": safe_text(
                    selected.get("product_fit_basis", "")
                ),
                "planning_opportunity_value_eur": safe_number(
                    selected.get("planning_opportunity_value_eur", 0)
                ),
                "planning_value_status": safe_text(
                    selected.get("planning_value_status", "")
                ),
                "planning_value_basis": safe_text(
                    selected.get("planning_value_basis", "")
                ),
                "visit_priority": safe_text(
                    selected.get("visit_priority", "")
                ),
                "visit_priority_score": safe_number(
                    selected.get("visit_priority_score", 0)
                ),
                "visit_priority_basis": safe_text(
                    selected.get("visit_priority_basis", "")
                ),
                "field_visit_objective": safe_text(
                    selected.get("field_visit_objective", "")
                ),
                "field_opening_questions": safe_text(
                    selected.get("field_opening_questions", "")
                ),
                "field_next_best_action": safe_text(
                    selected.get("field_next_best_action", "")
                ),
                "technology_validation_questions": safe_text(
                    selected.get("technology_validation_questions", "")
                ),
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
                "website_evidence_status": safe_text(
                    selected.get("website_evidence_status", "")
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
                "contact_channel_status": safe_text(
                    selected.get("contact_channel_status", "")
                ),
                "enrichment_status": safe_text(
                    selected.get("enrichment_status", "")
                ),
                "account_data_completeness": safe_number(
                    selected.get("account_data_completeness", 0)
                ),
                "decision_maker_name": safe_text(
                    selected.get("decision_maker_name", "")
                ),
                "decision_maker_headline": safe_text(
                    selected.get("decision_maker_headline", "")
                ),
                "decision_maker_linkedin": safe_text(
                    selected.get("decision_maker_linkedin", "")
                ),
                "decision_maker_confidence": safe_text(
                    selected.get("decision_maker_confidence", "")
                ),
                "decision_maker_relevance_score": safe_number(
                    selected.get("decision_maker_relevance_score", 0)
                ),
                "primary_evidence_url": safe_text(
                    selected.get("source_url", "")
                ),
                "enrichment_evidence_url": safe_text(
                    selected.get("enrichment_evidence_url", "")
                ),
            }
        )
        handoff_col, engage_col = st.columns(2)
        with handoff_col:
            st.download_button(
                "Download ENGAGE Handoff v2",
                outreach_handoff.to_csv(index=False),
                file_name=(
                    f"{safe_filename(selected_company)}"
                    "_engage_handoff_v2.csv"
                ),
                mime="text/csv",
                help="Evidence-aware v2 handoff for the Adaptive Outreach Intelligence application.",
                use_container_width=True,
            )
        with engage_col:
            st.link_button(
                "Open ENGAGE — Adaptive Outreach",
                "https://outreach-sequence-generator-7dcmglcxfnmszlodg8lqre.streamlit.app/",
                use_container_width=True,
            )

        st.caption(
            "Download the ENGAGE Handoff v2 and upload that CSV in ENGAGE. "
            "Use public-profile evidence as a starting point and verify the current role "
            "before prospect-facing outreach; public search indexes can be stale."
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

st.subheader("Execution Handoff")
st.caption(
    "Turn the current discovery research into a working commercial queue before exporting data."
)

queue_columns = [
    "company_name",
    "visit_priority",
    "visit_priority_score",
    "account_opportunity_score",
    "qualification_readiness_status",
    "product_fit_family",
    "territory_province",
    "territory_city",
    "field_next_best_action",
]
queue_view = ranked.copy()
queue_sort_columns = [
    column
    for column in [
        "visit_priority_score",
        "qualification_readiness_score",
        "account_opportunity_score",
    ]
    if column in queue_view.columns
]
if queue_sort_columns:
    queue_view = queue_view.sort_values(
        queue_sort_columns,
        ascending=[False] * len(queue_sort_columns),
    )
queue_view = queue_view[
    [column for column in queue_columns if column in queue_view.columns]
].head(12).copy()

if not queue_view.empty:
    st.markdown("**Commercial action queue — field priority**")
    st.dataframe(
        queue_view,
        use_container_width=True,
        hide_index=True,
    )
    st.download_button(
        "Download Field Action Queue",
        queue_view.to_csv(index=False),
        file_name="field_action_queue.csv",
        mime="text/csv",
        help="Operational shortlist sorted by current field-allocation priority.",
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
c2.metric(
    "Field Decision",
    safe_text(selected.get("visit_priority", ""), selected_motion),
)
c3.metric("Qualification State", selected_readiness)

st.info(
    f"Next action for {selected_company}: "
    f"{safe_text(selected.get('field_next_best_action', ''), selected_next_action)}"
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

