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
from typing import Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, InputRequiredResult, ToolAnnotations
from mcp.types import Tool as MCPTool
from pydantic import Field

from .operators import SUPPORTED_COUNTRY_CODES, build_catalogue, find_country


class _StrictArgsMCPServer(MCPServer):
    """MCPServer qui refuse un argument inconnu au lieu de l'ignorer.

    Les paramètres d'outil sont déclarés à plat (voir CLAUDE.md). Le modèle
    d'arguments que le SDK génère hérite d'`ArgModelBase`, dont la config
    Pydantic laisse `extra` à « ignore » : un argument mal orthographié est
    accepté sans bruit et l'outil retombe sur sa valeur par défaut.

    Tolérable sur un outil en lecture seule. Inacceptable sur un outil qui
    déplace de l'argent : `montant` au lieu d'`amount`, ou une référence
    d'idempotence mal nommée, doit échouer bruyamment. On refuse donc en
    amont, pour tous les outils du serveur, présents et à venir.
    """

    async def list_tools(self) -> list[MCPTool]:
        """Annonce aux clients que les champs inconnus sont refusés."""
        tools = await super().list_tools()
        for tool in tools:
            if tool.input_schema.get("type") == "object":
                tool.input_schema.setdefault("additionalProperties", False)
        return tools

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: Context[Any, Any] | None = None,
    ) -> CallToolResult | InputRequiredResult:
        """Rejette les arguments inconnus avant toute exécution."""
        tool = self._tool_manager.get_tool(name)
        if tool is not None:
            accepted = set(tool.parameters.get("properties", {}))
            unknown = sorted(set(arguments) - accepted)
            if unknown:
                raise ToolError(
                    f"Unknown argument(s) for tool {name}: {', '.join(unknown)}. "
                    f"Accepted argument(s): {', '.join(sorted(accepted)) or 'none'}. "
                    "Check the spelling: arguments are never ignored silently, so "
                    "that a mistyped field on a payment request fails loudly "
                    "instead of falling back to a default."
                )
        return await super().call_tool(name, arguments, context)


mcp = _StrictArgsMCPServer("momo_xof_mcp")


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
            # ToolError, pas ValueError : en 2.x une exception quelconque est
            # traitée comme un crash et le message est retiré de la réponse.
            # Le modèle ne verrait que « Error executing tool ». Or tout
            # l'intérêt de ce message est d'être lu et corrigé par l'appelant.
            raise ToolError(
                f"Unknown country code {candidate!r}. Expected an ISO 3166-1 "
                f"alpha-2 code among {', '.join(SUPPORTED_COUNTRY_CODES)}, or "
                "omit the 'country' argument to list every UEMOA country."
            )
        country_code = candidate.upper()

    catalogue = build_catalogue(country_code)
    return json.dumps(catalogue, ensure_ascii=False, indent=2)
