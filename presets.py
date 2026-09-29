from __future__ import annotations

PROFILE_SCHEMA_VERSION = "1.0"

PRESETS = {
    "Custom": {
        "profile_id": "custom",
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
        "note": "Fully customizable profile. All fields can be changed before discovery.",
    },
    "Renewable Energy — Distributors & EPC": {
        "profile_id": "renewable_energy",
        "industry": "Renewable Energy",
        "countries": "Italy, France",
        "regions": "Europe",
        "business_models": "Distributor, Wholesaler, EPC, Energy Solutions Provider",
        "keywords": "solar, photovoltaic, storage, inverter, battery, renewable energy",
        "excluded_keywords": "residential installer only",
        "min_size": 20,
        "max_size": 1000,
        "target_roles": "Commercial Director, Business Development, Procurement, Purchasing, Partnerships",
        "search_archetypes": "solar distributor, photovoltaic wholesaler, EPC renewable energy, energy storage distributor",
        "value_proposition": "Cross-border commercial development, sourcing and market-expansion support.",
        "note": "",
    },
    "Agribusiness — Importers & Distributors": {
        "profile_id": "agribusiness",
        "industry": "Agribusiness",
        "countries": "Italy, Spain, UAE",
        "regions": "Europe, MENA",
        "business_models": "Importer, Distributor, Wholesaler, Food Processor, Trading Company",
        "keywords": "import, distribution, food ingredients, commodities, sugar, coffee, beef, procurement",
        "excluded_keywords": "",
        "min_size": 20,
        "max_size": 2000,
        "target_roles": "Procurement Director, Purchasing Manager, Import Manager, Commercial Director, International Trade, Business Development",
        "search_archetypes": "food importer, commodity importer, food distributor, agribusiness trading company",
        "value_proposition": "Reliable international sourcing, supplier access and cross-border commercial development.",
        "note": "",
    },
    "Logistics & Trade — Freight & Trade Services": {
        "profile_id": "logistics_trade",
        "industry": "Logistics & Trade",
        "countries": "Italy, Brazil",
        "regions": "Europe, LATAM",
        "business_models": "Freight Forwarder, Logistics Provider, Customs Broker, Shipping Agency, Trade Services",
        "keywords": "freight forwarding, customs, shipping, import export, logistics, supply chain",
        "excluded_keywords": "",
        "min_size": 20,
        "max_size": 5000,
        "target_roles": "Commercial Director, Sales Director, Business Development, Trade Lane Manager, Partnerships, Managing Director",
        "search_archetypes": "freight forwarder, customs broker, logistics provider, shipping agency, international trade services",
        "value_proposition": "International business development, trade-lane growth and cross-border partnership support.",
        "note": "",
    },
    "Fintech — Partnerships & Enterprise": {
        "profile_id": "fintech",
        "industry": "Fintech",
        "countries": "Italy, Spain, UAE",
        "regions": "Europe, MENA",
        "business_models": "Fintech, Payments, SaaS, Financial Technology Platform",
        "keywords": "payments, embedded finance, digital banking, fintech, B2B, platform",
        "excluded_keywords": "",
        "min_size": 20,
        "max_size": 3000,
        "target_roles": "Head of Partnerships, Business Development, Commercial Director, Growth, Strategy, Country Manager",
        "search_archetypes": "B2B fintech, payments platform, embedded finance company, digital banking platform",
        "value_proposition": "Strategic partnerships, GTM and international market-development support.",
        "note": "",
    },
    "Real Estate — International Sales & Investment": {
        "profile_id": "real_estate",
        "industry": "Real Estate",
        "countries": "Italy, UAE",
        "regions": "Europe, MENA",
        "business_models": "Developer, Brokerage, Investment Company, Property Advisory",
        "keywords": "real estate, property investment, developer, brokerage, international buyers",
        "excluded_keywords": "",
        "min_size": 10,
        "max_size": 5000,
        "target_roles": "Sales Director, Business Development, Partnerships, International Sales, Investment Director, Managing Director",
        "search_archetypes": "real estate developer, international property brokerage, property investment company",
        "value_proposition": "International buyer development, strategic partnerships and cross-border commercial expansion.",
        "note": "",
    },
    "Government / Public Sector — Vendors & Procurement": {
        "profile_id": "government_public_sector",
        "industry": "Government / Public Sector",
        "countries": "Brazil, Italy",
        "regions": "LATAM, Europe",
        "business_models": "Public Institution, Government Agency, Public Utility, Government Supplier",
        "keywords": "public procurement, tender, government contract, public services, institutional",
        "excluded_keywords": "",
        "min_size": 0,
        "max_size": 100000,
        "target_roles": "Procurement, Contract Management, Institutional Relations, Program Director, Commercial Director",
        "search_archetypes": "public procurement authority, government supplier, public utility, municipal procurement",
        "value_proposition": "Structured B2G business development, procurement intelligence and contract-development support.",
        "note": "",
    },
    "Medical Aesthetics — Clinics & Practitioners (Italy)": {
        "profile_id": "medical_aesthetics",
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
            "Aesthetic centers and estheticians are discovery candidates, but device eligibility "
            "must be validated by product classification and local professional-use requirements."
        ),
    },
}


def get_preset(name: str) -> dict:
    return PRESETS.get(name, PRESETS["Custom"]).copy()


def profile_id_for(name: str) -> str:
    return get_preset(name).get("profile_id", "custom")
