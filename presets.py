from __future__ import annotations

PRESETS = {
    "Custom": {
        "industry": "Renewable Energy",
        "countries": "Italy, France",
        "regions": "Europe",
        "business_models": "Distributor, Wholesaler",
        "keywords": "solar, photovoltaic, storage",
        "excluded_keywords": "residential installer",
        "min_size": 20,
        "max_size": 500,
        "target_roles": "Business Development, Commercial, Procurement",
        "search_archetypes": "",
        "value_proposition": "International commercial partnership and market-expansion support.",
        "note": "",
    },
    "Medical Aesthetics — Clinics & Practitioners (Italy)": {
        "industry": "Medical Aesthetics",
        "countries": "Italy",
        "regions": "Europe",
        "business_models": (
            "Aesthetic Medicine Clinic, Clinica di medicina estetica, "
            "Dermatology Clinic, Studio dermatologico, "
            "Plastic Surgery Clinic, Studio di chirurgia plastica, "
            "Medical Practice, Studio medico, "
            "Aesthetic Center, Centro estetico, Esthetician, Estetista"
        ),
        "keywords": (
            "medicina estetica, medico estetico, dermatologia estetica, "
            "chirurgia plastica, criolipolisi, cryolipolysis, body contouring, "
            "laser estetico, fotobiomodulazione, LED, ringiovanimento cutaneo, "
            "rimodellamento corpo, cellulite, skin rejuvenation"
        ),
        "excluded_keywords": "tattoo only, hair salon only",
        "min_size": 0,
        "max_size": 250,
        "target_roles": (
            "Titolare, Founder, Direttore Sanitario, Medical Director, "
            "Medico Estetico, Aesthetic Physician, Dermatologo, Dermatologist, "
            "Chirurgo Plastico, Plastic Surgeon, Clinic Manager, Practice Manager, "
            "Estetista, Esthetician"
        ),
        "search_archetypes": (
            "clinica medicina estetica, medico estetico studio, "
            "dermatologo medicina estetica, chirurgo plastico medicina estetica, "
            "centro estetico tecnologie, estetista trattamenti corpo, medical spa"
        ),
        "value_proposition": (
            "Advanced aesthetic-medical technology supported by training, service, "
            "marketing enablement and patient-development support."
        ),
        "note": (
            "Medical-aesthetics preset. Aesthetic centers and estheticians are included "
            "as discovery candidates, but device eligibility must be validated by product "
            "classification and local professional-use requirements before outreach."
        ),
    },
}


def get_preset(name: str) -> dict:
    return PRESETS.get(name, PRESETS["Custom"]).copy()
