from __future__ import annotations

VENDOR_PROFILE_SCHEMA_VERSION = "1.0"

DELEO_NORTH_ITALY = {
    "vendor_profile_id": "deleo_north_italy",
    "name": "DELEO — North Italy Commercial Program",
    "company": "DELEO",
    "market_profile_id": "medical_aesthetics",
    "territory_profile_id": "it_north_medical_aesthetics",
    "annual_revenue_target_eur": 1_000_000,
    "ticket_range_eur": [15_000, 40_000],
    "ticket_scenarios_eur": [15_000, 25_000, 30_000, 40_000],
    "default_planning_ticket_eur": 27_500,
    "field_execution": {
        "milan_target_visits_per_day": [6, 7],
        "outside_milan_note": (
            "Reduce planned visits as travel time and geographic dispersion increase; "
            "prioritize account value and cluster density over a fixed visit quota."
        ),
    },
    "solution_families": [
        {
            "name": "CRISTAL Pro — Cryolipolysis / Localized Fat",
            "technology_axes": ["Silhouette / Body Contouring"],
            "signals": [
                "criolipolisi",
                "cryolipolysis",
                "grasso localizzato",
                "adiposità localizzata",
                "localized fat",
                "body contouring",
                "body sculpting",
            ],
            "qualification_questions": [
                "How important is localized-fat reduction within the current treatment mix?",
                "Which cryolipolysis or body-contouring technology is installed today?",
                "Where do you see limitations in throughput, treatment coverage or patient demand?",
            ],
        },
        {
            "name": "CRISTAL Fit — Muscle Toning / Pelvic Floor",
            "technology_axes": ["Silhouette / Body Contouring"],
            "signals": [
                "tonificazione muscolare",
                "muscle toning",
                "muscle stimulation",
                "pavimento pelvico",
                "pelvic floor",
                "incontinenza urinaria",
                "glutei",
                "addome",
            ],
            "qualification_questions": [
                "Is muscle toning or pelvic-floor treatment part of the current service portfolio?",
                "Which patient profiles are generating the strongest demand for muscle-toning protocols?",
                "Would a complementary body-contouring protocol create additional revenue per patient?",
            ],
        },
        {
            "name": "CONTOUR HIFU — Lifting / Skin Tightening",
            "technology_axes": ["Skin / Regeneration"],
            "signals": [
                "hifu",
                "ultrasuoni focalizzati",
                "focused ultrasound",
                "lifting viso",
                "skin tightening",
                "rassodamento",
                "collagene",
                "riduzione rughe",
            ],
            "qualification_questions": [
                "How strong is current demand for non-invasive lifting and skin-tightening treatments?",
                "Which HIFU or tightening technology is installed today?",
                "What would need to improve for the clinic to consider an additional or replacement platform?",
            ],
        },
        {
            "name": "ORIGIN — Fractional Laser / Skin Rejuvenation",
            "technology_axes": ["Skin / Regeneration"],
            "signals": [
                "laser frazionato",
                "fractional laser",
                "erbium glass",
                "cicatrici acne",
                "acne scars",
                "melasma",
                "lesioni pigmentarie",
                "skin rejuvenation",
                "ringiovanimento",
                "smagliature",
                "rughe",
            ],
            "qualification_questions": [
                "Which skin-rejuvenation indications generate the most demand today?",
                "Which laser platform is currently installed and where are its operational or clinical limitations?",
                "How important are low-downtime protocols for the clinic's patient base?",
            ],
        },
        {
            "name": "CRISTAL Body-Layering — Multi-Technology Body Program",
            "technology_axes": ["Silhouette / Body Contouring", "Skin / Regeneration"],
            "signals": [
                "body contouring",
                "rimodellamento corporeo",
                "body layering",
                "criolipolisi",
                "tonificazione muscolare",
                "skin tightening",
                "radiofrequenza corpo",
            ],
            "qualification_questions": [
                "Would the clinic benefit from combining fat reduction, muscle toning and skin firming in one commercial pathway?",
                "How are body-contouring patients currently moved between complementary treatments?",
                "What is the average commercial value of a complete body-contouring patient journey today?",
            ],
        },
    ],
    "technology_axes": {
        "Silhouette / Body Contouring": [
            "body contouring",
            "body sculpting",
            "rimodellamento corpo",
            "rimodellamento corporeo",
            "criolipolisi",
            "cryolipolysis",
            "cellulite",
            "adiposità",
            "adipose",
            "radiofrequenza corpo",
        ],
        "Skin / Regeneration": [
            "skin rejuvenation",
            "ringiovanimento cutaneo",
            "ringiovanimento viso",
            "fotobiomodulazione",
            "photobiomodulation",
            "led",
            "laser frazionato",
            "fractional laser",
            "microneedling",
            "micro needling",
            "hifu",
            "skin tightening",
        ],
        "Vascular": [
            "vascolare",
            "vascular",
            "capillari",
            "telangiectasia",
            "couperose",
            "ktp",
        ],
        "Tattoo Removal": [
            "rimozione tatuaggi",
            "tattoo removal",
            "détatouage",
            "laser tatuaggi",
        ],
    },
    "non_target_vendor_signals": [
        "allergan aesthetics",
        "abbvie",
        "btx bar",
        "deleo",
    ],
    "support_themes": [
        "Continuous training",
        "Warranty and after-sales service",
        "Scientific support",
        "Premium marketing tools",
        "Patient-development support",
        "Localized events and launch support",
        "KOL and educational content",
    ],
    "discussion_themes": [
        "Current treatment portfolio",
        "Installed technology and current provider",
        "Patient demand and treatment mix",
        "Training and onboarding expectations",
        "Service and after-sales expectations",
        "Marketing and patient-development support",
        "Investment timing and decision process",
        "Professional/device eligibility where applicable",
    ],
    "public_sources": [
        "https://www.deleo.fr/fr/contactez-nous/",
        "https://www.deleo.fr/fr/devenir-distributeur/",
        "https://www.deleo.fr/fr/blog/medecine-esthetique-mutation-2026/",
    ],
    "note": (
        "This profile supports commercial discovery, territory planning and discussion planning. "
        "Product-family matches are hypotheses from observed commercial signals, not clinical "
        "recommendations. Ticket values are planning scenarios only and do not establish pricing, "
        "purchase intent, regulatory eligibility or professional eligibility."
    ),
}

VENDOR_PROFILES = {
    "None / Generic": None,
    DELEO_NORTH_ITALY["name"]: DELEO_NORTH_ITALY,
}


def get_vendor_profile(name: str) -> dict | None:
    return VENDOR_PROFILES.get(name)
