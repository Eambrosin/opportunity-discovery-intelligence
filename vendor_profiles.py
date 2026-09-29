from __future__ import annotations

VENDOR_PROFILE_SCHEMA_VERSION = "1.0"

DELEO_NORTH_ITALY = {
    "vendor_profile_id": "deleo_north_italy",
    "name": "DELEO — North Italy Commercial Program",
    "company": "DELEO",
    "market_profile_id": "medical_aesthetics",
    "territory_profile_id": "it_north_medical_aesthetics",
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
        "This profile supports commercial discovery and discussion planning. "
        "It does not recommend a specific device or establish clinical, regulatory "
        "or professional eligibility."
    ),
}

VENDOR_PROFILES = {
    "None / Generic": None,
    DELEO_NORTH_ITALY["name"]: DELEO_NORTH_ITALY,
}


def get_vendor_profile(name: str) -> dict | None:
    return VENDOR_PROFILES.get(name)
