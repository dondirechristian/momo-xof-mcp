"""Normalisation et masquage des numéros de téléphone de la zone UEMOA.

Écrit avant tout appel à l'agrégateur, conformément à CLAUDE.md : un numéro
mal normalisé est la première cause de paiement envoyé au mauvais endroit.

Deux fonctions, deux responsabilités opposées :

- `normalize_msisdn` est STRICTE. Elle refuse tout ce qu'elle ne comprend pas,
  avec un message qui dit quoi corriger. Jamais de « meilleur effort » : un
  numéro douteux doit arrêter la demande de paiement, pas la laisser partir.
- `mask_msisdn` est TOLÉRANTE. Elle sert dans les chemins de journalisation et
  ne lève jamais : une fonction de masquage qui plante en produisant un log
  est précisément ce qui finit par écrire un numéro complet dans un fichier.

Piège de la zone : il n'y a pas de préfixe interurbain à retirer. Le 0 initial
de `01`, `05` ou `07` fait partie du numéro national en Côte d'Ivoire, au
Bénin et au Burkina. Ne jamais « nettoyer » un zéro de tête.
"""

from __future__ import annotations

import re

from .operators import SUPPORTED_COUNTRY_CODES, find_country

# Séparateurs tolérés dans une saisie humaine : espaces (y compris insécables),
# tirets, points, parenthèses, barres de fraction.
_SEPARATORS = re.compile(r"[\s  ().\-/]")

_DIGITS_ONLY = re.compile(r"\A\d+\Z")


class InvalidMsisdn(ValueError):
    """Numéro inexploitable. Le message dit toujours quoi corriger."""


def _clean(raw: str) -> str:
    """Retire les séparateurs et normalise le préfixe international."""
    cleaned = _SEPARATORS.sub("", raw.strip())
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    return cleaned


def _expectation(country: dict) -> str:
    """Fragment de message : ce qu'on attendait pour ce pays."""
    return (
        f"{country['country_name']} expects {country['national_number_length']} "
        f"digits after {country['dialing_code']}, i.e. {country['e164_example']}"
    )


def normalize_msisdn(raw: str, country_code: str | None = None) -> str:
    """Normalise un numéro en E.164, ou lève `InvalidMsisdn`.

    Accepte une saisie internationale (`+22670123456`, `0022670123456`,
    `+226 70 12 34 56`) sans autre indication, et une saisie nationale
    (`70123456`) à condition que `country_code` soit fourni.

    Le pays et la longueur sont vérifiés l'un contre l'autre : un numéro dont
    la longueur ne correspond pas au plan national est refusé, jamais complété
    ni tronqué.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise InvalidMsisdn(
            "Empty phone number. Provide it in E.164 form, for example "
            "+22670123456, or pass the national number together with a country "
            f"code among {', '.join(SUPPORTED_COUNTRY_CODES)}."
        )

    declared = None
    if country_code is not None:
        declared = find_country(country_code)
        if declared is None:
            raise InvalidMsisdn(
                f"Unknown country code {country_code!r}. Expected an ISO 3166-1 "
                f"alpha-2 code among {', '.join(SUPPORTED_COUNTRY_CODES)}."
            )

    cleaned = _clean(raw)

    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if not _DIGITS_ONLY.match(digits):
            raise InvalidMsisdn(
                f"Phone number {raw!r} contains characters that are neither "
                "digits nor separators. Expected E.164, for example +22670123456."
            )
        return _from_international(raw, digits, declared)

    if not _DIGITS_ONLY.match(cleaned):
        raise InvalidMsisdn(
            f"Phone number {raw!r} contains characters that are neither digits "
            "nor separators. Expected E.164, for example +22670123456."
        )

    if declared is None:
        raise InvalidMsisdn(
            f"Phone number {raw!r} has no country indication. Either use E.164 "
            "form starting with '+' (for example +22670123456), or pass a "
            f"country code among {', '.join(SUPPORTED_COUNTRY_CODES)}."
        )

    return _from_national(raw, cleaned, declared)


def _from_international(raw: str, digits: str, declared: dict | None) -> str:
    """Traite une saisie déjà internationale."""
    for country in (declared,) if declared else _all_countries():
        prefix = country["dialing_code"].lstrip("+")
        if digits.startswith(prefix):
            national = digits[len(prefix) :]
            if len(national) != country["national_number_length"]:
                raise InvalidMsisdn(
                    f"Phone number {raw!r} has {len(national)} digits after "
                    f"{country['dialing_code']}, but {_expectation(country)}."
                )
            return "+" + digits

    if declared is not None:
        raise InvalidMsisdn(
            f"Phone number {raw!r} does not start with the dialing code of "
            f"{declared['country_name']} ({declared['dialing_code']}). Either "
            "fix the number or pass the country it really belongs to."
        )

    known = ", ".join(f"{c['dialing_code']} {c['country_code']}" for c in _all_countries())
    raise InvalidMsisdn(
        f"Phone number {raw!r} does not start with a supported dialing code. "
        f"Supported: {known}."
    )


def _from_national(raw: str, digits: str, country: dict) -> str:
    """Traite une saisie nationale, pays connu."""
    prefix = country["dialing_code"].lstrip("+")

    if len(digits) == country["national_number_length"]:
        return f"+{prefix}{digits}"

    # Saisie internationale sans le '+' : 22670123456.
    if digits.startswith(prefix) and len(digits) == len(prefix) + country["national_number_length"]:
        return f"+{digits}"

    raise InvalidMsisdn(
        f"Phone number {raw!r} has {len(digits)} digits, but {_expectation(country)}. "
        "Note that the leading 0 of prefixes such as 01, 05 or 07 is part of the "
        "national number and must not be removed."
    )


def _all_countries() -> list[dict]:
    """Les pays du catalogue, dans l'ordre déclaré."""
    return [find_country(code) for code in SUPPORTED_COUNTRY_CODES]  # type: ignore[misc]


def mask_msisdn(value: object) -> str:
    """Masque un numéro pour la journalisation. Ne lève jamais.

    `+22670123456` devient `+226 70 ** ** 56` : assez pour reconnaître un
    numéro dans un incident, trop peu pour le composer ou l'identifier.

    Toute entrée non reconnue retombe sur un masque intégral plutôt que sur
    une exception, parce que cette fonction est appelée depuis les chemins de
    log : y lever une erreur reviendrait à risquer d'y écrire le numéro brut.
    """
    try:
        text = value if isinstance(value, str) else str(value)
        cleaned = _clean(text)
        digits = cleaned.removeprefix("+")

        if not _DIGITS_ONLY.match(digits):
            return "(masked)"

        for country in _all_countries():
            prefix = country["dialing_code"].lstrip("+")
            if digits.startswith(prefix) and len(digits) == len(prefix) + country[
                "national_number_length"
            ]:
                return f"{country['dialing_code']} {_mask_national(digits[len(prefix):])}"

        return _mask_national(digits)
    except Exception:  # noqa: BLE001 — un log ne doit jamais faire tomber l'appelant
        return "(masked)"


def _mask_national(digits: str) -> str:
    """Garde les deux premiers et les deux derniers chiffres, masque le reste."""
    if len(digits) <= 4:
        return "*" * len(digits)

    middle = len(digits) - 4
    groups = [
        "*" * min(2, middle - offset) for offset in range(0, middle, 2)
    ]
    return " ".join([digits[:2], *groups, digits[-2:]])
