"""Serveur MCP `momo_xof_mcp` — déclaration de l'instance et des outils.

v0.1 : seul `momo_list_operators` est implémenté. Les deux autres outils de la
liste figée (`momo_initiate_payment`, `momo_check_payment_status`) ne sont pas
encore écrits — ils attendent une réponse réelle de l'API sandbox de
l'agrégateur, conformément à la règle « aucun appel API écrit à l'aveugle ».

Transport stdio : rien ne doit jamais être écrit sur stdout en dehors du
protocole MCP. Pas de `print`, pas de logging vers stdout.
"""

from __future__ import annotations

import json
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .operators import SUPPORTED_COUNTRY_CODES, build_catalogue, find_country

mcp = FastMCP("momo_xof_mcp")


@mcp.tool(
    name="momo_list_operators",
    description=(
        "List the countries of the West African CFA franc (XOF) zone and the "
        "mobile money services available in each. For every one of the eight "
        "UEMOA countries it returns the ISO code, international dialing code, "
        "national number length and E.164 format, then the payment services on "
        "offer, and finally optional prefix hints. Purely static: no network "
        "call, no credentials needed. Use it before initiating a payment to "
        "check that a country and a service are in scope and that a phone "
        "number has the expected shape. Payment services are unrelated to "
        "number prefixes: independent wallets such as Wave run on any national "
        "mobile number. Prefix hints, when present, map a prefix to a telecom "
        "network only, are defeated by number portability, and must never be "
        "used to route a payment."
    ),
    annotations=ToolAnnotations(
        title="List XOF countries and mobile money services",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def momo_list_operators(
    country: Annotated[
        str | None,
        Field(
            description=(
                "Optional ISO 3166-1 alpha-2 country code, to restrict the "
                "listing to a single country, for example 'BF' for Burkina Faso "
                "or 'CI' for Cote d'Ivoire. Case-insensitive. Omit it to list "
                "all eight UEMOA countries."
            ),
            examples=["BF", "CI", "SN"],
        ),
    ] = None,
) -> str:
    """Retourne le catalogue statique, éventuellement filtré sur un pays."""
    country_code: str | None = None

    if country is not None:
        candidate = country.strip()
        if find_country(candidate) is None:
            raise ValueError(
                f"Unknown country code {candidate!r}. Expected an ISO 3166-1 "
                f"alpha-2 code among {', '.join(SUPPORTED_COUNTRY_CODES)}, or "
                "omit the 'country' argument to list every UEMOA country."
            )
        country_code = candidate.upper()

    catalogue = build_catalogue(country_code)
    return json.dumps(catalogue, ensure_ascii=False, indent=2)
