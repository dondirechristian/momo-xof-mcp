"""Catalogue statique des pays et services de paiement de la zone UEMOA (XOF).

Aucune I/O, aucun appel réseau. Toute modification fait monter
CATALOGUE_VERSION.

Le modèle sépare délibérément deux choses que l'on confond souvent :

1. Le PAYS — code ISO, indicatif, longueur nationale, format E.164. Données
   stables et fiables : ce sont elles qui servent à valider une saisie.
2. Les SERVICES DE PAIEMENT disponibles dans ce pays. Ils n'ont aucun lien
   avec les préfixes téléphoniques. Wave le montre bien : ce n'est pas un
   opérateur télécom, il fonctionne sur n'importe quel numéro du pays et ne
   possède donc aucune plage de numérotation. Un modèle qui rattacherait les
   services aux préfixes ne saurait pas le représenter.

Les préfixes, quand ils sont connus, vivent dans `prefix_hints` au niveau du
PAYS et associent un préfixe à un RÉSEAU TÉLÉCOM — jamais à un service de
paiement. Ils sont indicatifs : la portabilité du numéro suffit à les prendre
en défaut, et plusieurs régulateurs allouent par tranches plus fines que deux
chiffres. Ne jamais s'en servir pour router un paiement : c'est l'agrégateur
qui détermine l'opérateur réel à partir du numéro complet.

Quand une plage n'est pas connue de source sûre, `confidence` vaut "none" et
`networks_by_prefix` reste vide. On n'invente pas un préfixe.
"""

from __future__ import annotations

from typing import Any, Final

# Date de dernière revue du catalogue. À faire monter à chaque correction.
CATALOGUE_VERSION: Final[str] = "2026-09-18"

CURRENCY: Final[str] = "XOF"

# Le franc CFA ouest-africain n'a pas de sous-unité : les montants sont des
# entiers. Rappelé ici pour que l'appelant n'ait pas à le deviner.
CURRENCY_DECIMALS: Final[int] = 0

PREFIX_DISCLAIMER: Final[str] = (
    "Prefix hints map a number prefix to a TELECOM NETWORK, never to a payment "
    "service: Wave and other non-telco wallets run on any national mobile "
    "number and own no prefix range at all. Hints are indicative only. Number "
    "portability alone defeats them, several regulators allocate in blocks "
    "finer than two digits, and national renumbering happens. Use them for "
    "input hints, never to route a payment: the aggregator determines the real "
    "operator from the full number. When a range is not known from an "
    "authoritative source, confidence is 'none' and the map is empty."
)

# Types de service, pour que l'appelant sache à quoi il a affaire.
#   mno_wallet         — porte-monnaie adossé à un réseau mobile
#   independent_wallet — porte-monnaie indépendant de tout réseau (Wave)
_MNO_WALLET: Final[str] = "mno_wallet"
_INDEPENDENT_WALLET: Final[str] = "independent_wallet"

_NO_PREFIX_DATA: Final[dict[str, Any]] = {
    "confidence": "none",
    "source": "",
    "networks_by_prefix": {},
}


def _hints(confidence: str, source: str, by_network: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    """Construit un bloc `prefix_hints`.

    En entrée, les plages sont groupées par réseau — c'est ainsi que les
    régulateurs les publient et c'est lisible. En sortie, elles sont aplaties
    en `préfixe -> réseau`, forme directement exploitable pour une recherche.
    """
    flat: dict[str, str] = {}
    for network, prefixes in by_network.items():
        for prefix in prefixes:
            if prefix in flat:
                raise ValueError(
                    f"Préfixe {prefix} attribué deux fois : {flat[prefix]} et {network}."
                )
            flat[prefix] = network
    return {
        "confidence": confidence,
        "source": source,
        "networks_by_prefix": dict(sorted(flat.items())),
    }


# `e164_example` est un gabarit, pas un numéro : les X marquent les chiffres
# libres. Cela donne la longueur exacte sans laisser croire qu'un préfixe
# particulier est attesté quand il ne l'est pas.
_COUNTRIES: Final[tuple[dict[str, Any], ...]] = (
    {
        "country_code": "BJ",
        "country_name": "Benin",
        "dialing_code": "+229",
        "national_number_length": 10,
        "e164_example": "+22901XXXXXXXX",
        "notes": (
            "Since 30 November 2024 every Benin mobile number is 10 digits and "
            "begins with 01, whichever the operator. That 01 is a national "
            "renumbering prefix: it identifies nobody. Historical per-operator "
            "blocks are not reproduced here without an authoritative source."
        ),
        "payment_services": (
            {
                "service_id": "mtn_momo_bj",
                "service": "MTN MoMo",
                "provider": "MTN Benin",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "moov_money_bj",
                "service": "Moov Money",
                "provider": "Moov Africa Benin",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "celtiis_cash_bj",
                "service": "Celtiis Cash",
                "provider": "Celtiis",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
    {
        "country_code": "BF",
        "country_name": "Burkina Faso",
        "dialing_code": "+226",
        "national_number_length": 8,
        "e164_example": "+226XXXXXXXX",
        "notes": (
            "Prefix hints name the licensed network, which is not always the "
            "commercial brand: ONATEL/Telmob trades as Moov Africa, and Airtel "
            "Burkina Faso now belongs to Orange. A number in an Airtel range is "
            "therefore reachable through Orange Money."
        ),
        "payment_services": (
            {
                "service_id": "orange_money_bf",
                "service": "Orange Money",
                "provider": "Orange Burkina Faso",
                "service_type": _MNO_WALLET,
                "notes": "Also serves the former Airtel Burkina Faso ranges.",
            },
            {
                "service_id": "moov_money_bf",
                "service": "Moov Money",
                "provider": "ONATEL / Telmob, trading as Moov Africa",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "wave_bf",
                "service": "Wave",
                "provider": "Wave Mobile Money",
                "service_type": _INDEPENDENT_WALLET,
                "notes": "Runs on any Burkinabe mobile number; owns no prefix range.",
            },
        ),
        # ONATEL/Telmob opère commercialement sous la marque Moov Africa, et
        # Airtel Burkina Faso est passé sous Orange. Les noms ci-dessous sont
        # ceux des attributaires au plan de numérotation, pas ceux des marques.
        "prefix_hints": _hints(
            confidence="high",
            source="ARCEP Burkina Faso / ITU national numbering plan, 4 May 2023",
            by_network={
                "ONATEL / Telmob": (
                    "01", "02", "03",
                    "50", "51", "52",
                    "60", "61", "62", "63",
                    "70", "71", "72", "73",
                ),
                "Orange Burkina Faso": ("05", "06", "07", "54", "57"),
                "Airtel Burkina Faso": (
                    "55", "56",
                    "64", "65", "66", "67",
                    "74", "75", "76", "77",
                ),
                "Telecel Faso": ("58", "68", "69", "78", "79"),
            },
        ),
    },
    {
        "country_code": "CI",
        "country_name": "Cote d'Ivoire",
        "dialing_code": "+225",
        "national_number_length": 10,
        "e164_example": "+225XXXXXXXXXX",
        "notes": (
            "National numbers moved to 10 digits on 31 January 2021. The two "
            "leading digits identify the mobile network."
        ),
        "payment_services": (
            {
                "service_id": "orange_money_ci",
                "service": "Orange Money",
                "provider": "Orange Cote d'Ivoire",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "mtn_momo_ci",
                "service": "MTN MoMo",
                "provider": "MTN Cote d'Ivoire",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "moov_money_ci",
                "service": "Moov Money",
                "provider": "Moov Africa Cote d'Ivoire",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "wave_ci",
                "service": "Wave",
                "provider": "Wave Mobile Money",
                "service_type": _INDEPENDENT_WALLET,
                "notes": "Runs on any Ivorian mobile number; owns no prefix range.",
            },
        ),
        "prefix_hints": _hints(
            confidence="high",
            source="National numbering plan in force since 31 January 2021",
            by_network={
                "Moov Africa Cote d'Ivoire": ("01",),
                "MTN Cote d'Ivoire": ("05",),
                "Orange Cote d'Ivoire": ("07",),
            },
        ),
    },
    {
        "country_code": "GW",
        "country_name": "Guinea-Bissau",
        "dialing_code": "+245",
        "national_number_length": 7,
        "e164_example": "+245XXXXXXX",
        "notes": "Smallest market of the zone. No prefix allocation held from an authoritative source.",
        "payment_services": (
            {
                "service_id": "orange_money_gw",
                "service": "Orange Money",
                "provider": "Orange Bissau",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
    {
        "country_code": "ML",
        "country_name": "Mali",
        "dialing_code": "+223",
        "national_number_length": 8,
        "e164_example": "+223XXXXXXXX",
        "notes": "No prefix allocation held from an authoritative source.",
        "payment_services": (
            {
                "service_id": "orange_money_ml",
                "service": "Orange Money",
                "provider": "Orange Mali",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "moov_money_ml",
                "service": "Moov Money",
                "provider": "Moov Africa Malitel",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "wave_ml",
                "service": "Wave",
                "provider": "Wave Mobile Money",
                "service_type": _INDEPENDENT_WALLET,
                "notes": "Runs on any Malian mobile number; owns no prefix range.",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
    {
        "country_code": "NE",
        "country_name": "Niger",
        "dialing_code": "+227",
        "national_number_length": 8,
        "e164_example": "+227XXXXXXXX",
        "notes": (
            "Orange left Niger in 2023; its assets were taken over by Zamani "
            "Telecom, so Orange Money is not available here. No prefix "
            "allocation held from an authoritative source."
        ),
        "payment_services": (
            {
                "service_id": "airtel_money_ne",
                "service": "Airtel Money",
                "provider": "Airtel Niger",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "moov_money_ne",
                "service": "Moov Money",
                "provider": "Moov Africa Niger",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
    {
        "country_code": "SN",
        "country_name": "Senegal",
        "dialing_code": "+221",
        "national_number_length": 9,
        "e164_example": "+221XXXXXXXXX",
        # L'ARTP alloue par tranches de 3 à 4 chiffres, et la portabilité du
        # numéro existe au Sénégal depuis 2015. Un mapping à 2 chiffres du type
        # « 77 = Orange » produit donc des faux positifs : on n'en publie aucun.
        "notes": (
            "The regulator (ARTP) allocates in blocks of 3 to 4 digits, and "
            "number portability has been in force since 2015. A 2-digit "
            "prefix-to-operator mapping produces false positives, so none is "
            "published here."
        ),
        "payment_services": (
            {
                "service_id": "orange_money_sn",
                "service": "Orange Money",
                "provider": "Sonatel / Orange Senegal",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "free_money_sn",
                "service": "Free Money",
                "provider": "Free Senegal",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "emoney_sn",
                "service": "E-Money",
                "provider": "Expresso Senegal",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "wave_sn",
                "service": "Wave",
                "provider": "Wave Mobile Money",
                "service_type": _INDEPENDENT_WALLET,
                "notes": "Runs on any Senegalese mobile number; owns no prefix range.",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
    {
        "country_code": "TG",
        "country_name": "Togo",
        "dialing_code": "+228",
        "national_number_length": 8,
        "e164_example": "+228XXXXXXXX",
        "notes": "No prefix allocation held from an authoritative source.",
        "payment_services": (
            {
                "service_id": "tmoney_tg",
                "service": "T-Money",
                "provider": "Togocom / Togocel",
                "service_type": _MNO_WALLET,
                "notes": "",
            },
            {
                "service_id": "moov_money_tg",
                "service": "Moov Money",
                "provider": "Moov Africa Togo",
                "service_type": _MNO_WALLET,
                "notes": "Marketed locally as Flooz.",
            },
        ),
        "prefix_hints": _NO_PREFIX_DATA,
    },
)

SUPPORTED_COUNTRY_CODES: Final[tuple[str, ...]] = tuple(
    country["country_code"] for country in _COUNTRIES
)


def _as_payload(country: dict[str, Any]) -> dict[str, Any]:
    """Convertit une entrée interne en structure JSON-sérialisable."""
    hints = country["prefix_hints"]
    return {
        "country_code": country["country_code"],
        "country_name": country["country_name"],
        "dialing_code": country["dialing_code"],
        "national_number_length": country["national_number_length"],
        "e164_example": country["e164_example"],
        "notes": country["notes"],
        "payment_services": [
            {
                "service_id": service["service_id"],
                "service": service["service"],
                "provider": service["provider"],
                "service_type": service["service_type"],
                "notes": service["notes"],
            }
            for service in country["payment_services"]
        ],
        "prefix_hints": {
            "confidence": hints["confidence"],
            "source": hints["source"],
            "networks_by_prefix": dict(hints["networks_by_prefix"]),
        },
    }


def find_country(country_code: str) -> dict[str, Any] | None:
    """Retrouve un pays par code ISO 3166-1 alpha-2. Insensible à la casse."""
    needle = country_code.strip().upper()
    for country in _COUNTRIES:
        if country["country_code"] == needle:
            return country
    return None


def build_catalogue(country_code: str | None = None) -> dict[str, Any]:
    """Construit la charge utile de `momo_list_operators`.

    `country_code` à None renvoie les huit pays de l'UEMOA. Le code pays est
    supposé déjà validé par l'appelant (voir `find_country`).
    """
    if country_code is None:
        selected: tuple[dict[str, Any], ...] = _COUNTRIES
    else:
        country = find_country(country_code)
        selected = (country,) if country is not None else ()

    return {
        "currency": CURRENCY,
        "currency_decimals": CURRENCY_DECIMALS,
        "catalogue_version": CATALOGUE_VERSION,
        "prefix_disclaimer": PREFIX_DISCLAIMER,
        "country_count": len(selected),
        "countries": [_as_payload(country) for country in selected],
    }
