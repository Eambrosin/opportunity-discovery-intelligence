from __future__ import annotations

TERRITORY_SCHEMA_VERSION = "1.0"

NORTH_ITALY_MEDICAL_AESTHETICS = {
    "territory_profile_id": "it_north_medical_aesthetics",
    "name": "North Italy — Lombardia · Veneto · Trentino-Alto Adige",
    "country": "Italy",
    "market_profile_id": "medical_aesthetics",
    "regions": ["Lombardia", "Veneto", "Trentino-Alto Adige"],
    "note": (
        "Commercial territory for medical-aesthetics account development. "
        "Location inference distinguishes source-observed evidence from search-scope inference."
    ),
    "clusters": [
        {
            "cluster_id": "lombardia_milano",
            "region": "Lombardia",
            "province": "Milano",
            "province_aliases": ["Milano", "Milan"],
            "cities": ["Milano", "Sesto San Giovanni", "Rho", "Legnano"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_monza_brianza",
            "region": "Lombardia",
            "province": "Monza e della Brianza",
            "province_aliases": ["Monza e della Brianza", "Monza Brianza", "Brianza"],
            "cities": ["Monza", "Vimercate", "Desio", "Seregno"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_bergamo",
            "region": "Lombardia",
            "province": "Bergamo",
            "province_aliases": ["Bergamo"],
            "cities": ["Bergamo", "Treviglio", "Seriate"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_brescia",
            "region": "Lombardia",
            "province": "Brescia",
            "province_aliases": ["Brescia"],
            "cities": ["Brescia", "Desenzano del Garda", "Montichiari"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_como",
            "region": "Lombardia",
            "province": "Como",
            "province_aliases": ["Como"],
            "cities": ["Como", "Cantù", "Erba"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_lecco",
            "region": "Lombardia",
            "province": "Lecco",
            "province_aliases": ["Lecco"],
            "cities": ["Lecco", "Merate"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_varese",
            "region": "Lombardia",
            "province": "Varese",
            "province_aliases": ["Varese"],
            "cities": ["Varese", "Busto Arsizio", "Gallarate", "Saronno"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_pavia",
            "region": "Lombardia",
            "province": "Pavia",
            "province_aliases": ["Pavia"],
            "cities": ["Pavia", "Vigevano"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_cremona",
            "region": "Lombardia",
            "province": "Cremona",
            "province_aliases": ["Cremona"],
            "cities": ["Cremona", "Crema"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_mantova",
            "region": "Lombardia",
            "province": "Mantova",
            "province_aliases": ["Mantova", "Mantua"],
            "cities": ["Mantova", "Castiglione delle Stiviere"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_lodi",
            "region": "Lombardia",
            "province": "Lodi",
            "province_aliases": ["Lodi"],
            "cities": ["Lodi"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "lombardia_sondrio",
            "region": "Lombardia",
            "province": "Sondrio",
            "province_aliases": ["Sondrio", "Valtellina"],
            "cities": ["Sondrio"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_verona",
            "region": "Veneto",
            "province": "Verona",
            "province_aliases": ["Verona"],
            "cities": ["Verona", "Villafranca di Verona", "Legnago"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_vicenza",
            "region": "Veneto",
            "province": "Vicenza",
            "province_aliases": ["Vicenza"],
            "cities": ["Vicenza", "Bassano del Grappa", "Schio"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_padova",
            "region": "Veneto",
            "province": "Padova",
            "province_aliases": ["Padova", "Padua"],
            "cities": ["Padova", "Abano Terme", "Cittadella"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_treviso",
            "region": "Veneto",
            "province": "Treviso",
            "province_aliases": ["Treviso"],
            "cities": ["Treviso", "Conegliano", "Castelfranco Veneto"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_venezia",
            "region": "Veneto",
            "province": "Venezia",
            "province_aliases": ["Venezia", "Venice"],
            "cities": ["Venezia", "Mestre", "Mirano"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_belluno",
            "region": "Veneto",
            "province": "Belluno",
            "province_aliases": ["Belluno"],
            "cities": ["Belluno", "Feltre"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "veneto_rovigo",
            "region": "Veneto",
            "province": "Rovigo",
            "province_aliases": ["Rovigo"],
            "cities": ["Rovigo"],
            "priority": False,
            "languages": ["it"],
        },
        {
            "cluster_id": "taa_trento",
            "region": "Trentino-Alto Adige",
            "province": "Trento",
            "province_aliases": ["Trento", "Trentino"],
            "cities": ["Trento", "Rovereto", "Riva del Garda"],
            "priority": True,
            "languages": ["it"],
        },
        {
            "cluster_id": "taa_bolzano",
            "region": "Trentino-Alto Adige",
            "province": "Bolzano / Bozen",
            "province_aliases": ["Bolzano", "Bozen", "Alto Adige", "Südtirol", "South Tyrol"],
            "cities": [
                "Bolzano",
                "Bozen",
                "Merano",
                "Meran",
                "Bressanone",
                "Brixen",
                "Brunico",
                "Bruneck",
            ],
            "priority": True,
            "languages": ["it", "de"],
        },
    ],
}

TERRITORIES = {
    NORTH_ITALY_MEDICAL_AESTHETICS["name"]: NORTH_ITALY_MEDICAL_AESTHETICS,
}


def get_territory(name: str) -> dict:
    return TERRITORIES[name]


def priority_cluster_ids(territory: dict) -> list[str]:
    return [
        cluster["cluster_id"]
        for cluster in territory.get("clusters", [])
        if cluster.get("priority")
    ]


def all_cluster_ids(territory: dict) -> list[str]:
    return [cluster["cluster_id"] for cluster in territory.get("clusters", [])]


def cluster_labels(territory: dict) -> dict[str, str]:
    labels = {}
    for cluster in territory.get("clusters", []):
        cities = cluster.get("cities", [])
        anchor = cities[0] if cities else cluster.get("province", "")
        labels[cluster["cluster_id"]] = (
            f"{cluster.get('region', '')} · {cluster.get('province', '')}"
            + (f" · {anchor}" if anchor and anchor != cluster.get("province") else "")
        )
    return labels
