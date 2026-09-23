"""Serveur MCP `momo_xof_mcp` — déclaration de l'instance et des outils.

v0.1 : les trois outils de la liste figée sont implémentés, chacun écrit à
partir d'appels réels observés et consignés dans docs/API-CINETPAY.md.

Attention à une asymétrie de l'API, source d'erreur : à l'initialisation le
sort de la transaction est dans `details`, à la consultation il est à la
racine. Voir `cinetpay.py`.

`momo_initiate_payment` déplace de l'argent réel. Ses garde-fous sont dans
`config.py` (verrou sandbox, plafond de montant) et dans le corps de l'outil
(montant entier positif, référence fournie par l'appelant et plafonnée à
30 caractères). Ne jamais en relâcher un pour faire passer un test.

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

from .cinetpay import CinetPayError, check_payment_status, initiate_payment
from .config import ConfigurationError, load_config
from .operators import SUPPORTED_COUNTRY_CODES, build_catalogue, find_country
from .phone import InvalidMsisdn, normalize_msisdn


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


@mcp.tool(
    name="momo_initiate_payment",
    description=(
        "Request a mobile money payment from a customer in the XOF zone. "
        "IMPORTANT: this REQUESTS a payment, it never confirms one. A successful "
        "call means the aggregator accepted the request and returned a payment "
        "link; the customer has not paid yet and no money has moved. The final "
        "outcome arrives asynchronously and must be checked separately. "
        "Returns a payment_url that the customer must open to complete the "
        "payment, plus the transaction identifiers needed to reconcile it. "
        "The caller must supply a unique reference for idempotency; it is never "
        "generated silently. Amounts are whole XOF: the franc has no decimals. "
        "A server-side ceiling rejects amounts above the configured maximum."
    ),
    annotations=ToolAnnotations(
        title="Request a mobile money payment (moves real money)",
        readOnlyHint=False,
        destructiveHint=True,
        # La référence marchand doit être unique côté CinetPay, mais le
        # comportement d'un rappel avec la même référence n'a pas été observé.
        # On ne promet donc pas l'idempotence.
        idempotentHint=False,
        openWorldHint=True,
    ),
)
async def momo_initiate_payment(
    amount: Annotated[
        int,
        Field(
            description=(
                "Amount in whole XOF. The West African CFA franc has no decimal "
                "subunit, so this must be an integer — never a float. Rejected "
                "above the server's configured ceiling."
            ),
            examples=[500, 2000],
        ),
    ],
    reference: Annotated[
        str,
        Field(
            description=(
                "Your own unique reference for this payment, used for "
                "idempotency and reconciliation. Maximum 30 characters. It is "
                "returned unchanged by the aggregator. Never reuse one, and "
                "never let it be generated for you: you need it to match the "
                "payment back to your order."
            ),
            examples=["CMD-2026-0042", "invoice-8871"],
        ),
    ],
    description: Annotated[
        str,
        Field(
            description="Short label shown to the customer on the payment page.",
            examples=["Commande 42 - SOTECHDI"],
        ),
    ],
    client_email: Annotated[
        str,
        Field(
            description="Customer email address. Required by the aggregator.",
            examples=["client@example.com"],
        ),
    ],
    client_first_name: Annotated[
        str,
        Field(
            description="Customer first name, 2 to 255 characters. Required.",
            examples=["Aminata"],
        ),
    ],
    client_last_name: Annotated[
        str,
        Field(
            description="Customer last name, 2 to 255 characters. Required.",
            examples=["Ouedraogo"],
        ),
    ],
    customer_phone: Annotated[
        str | None,
        Field(
            description=(
                "Optional customer mobile number. Give it in E.164 form "
                "(+22670123456), or in national form together with 'country'. "
                "It pre-fills the payment page. Omit it to let the customer "
                "enter their own number."
            ),
            examples=["+22670123456", "70123456"],
        ),
    ] = None,
    country: Annotated[
        str | None,
        Field(
            description=(
                "ISO 3166-1 alpha-2 country code, needed only to interpret a "
                "national-format 'customer_phone'. Use momo_list_operators to "
                "see the supported countries."
            ),
            examples=["BF", "CI"],
        ),
    ] = None,
) -> str:
    """Déclenche une demande de paiement. Ne confirme jamais un paiement."""
    try:
        config = load_config()
    except ConfigurationError as exc:
        raise ToolError(str(exc)) from exc

    if amount <= 0:
        raise ToolError(f"Amount must be greater than zero, got {amount}.")

    if amount > config.max_amount:
        raise ToolError(
            f"Amount {amount} XOF exceeds the server-side ceiling of "
            f"{config.max_amount} XOF (MOMO_MAX_AMOUNT). This limit is enforced "
            "by this server, not by the aggregator. Raise it deliberately in "
            "the server configuration if this payment is legitimate."
        )

    cleaned_reference = reference.strip()
    if not cleaned_reference:
        raise ToolError(
            "A reference is required and must be supplied by you, never "
            "generated for you: it is what lets you match this payment back to "
            "your order."
        )
    if len(cleaned_reference) > 30:
        raise ToolError(
            f"Reference is {len(cleaned_reference)} characters, but the "
            "aggregator accepts at most 30."
        )

    normalized_phone: str | None = None
    if customer_phone:
        try:
            normalized_phone = normalize_msisdn(customer_phone, country)
        except InvalidMsisdn as exc:
            raise ToolError(str(exc)) from exc

    try:
        result = await initiate_payment(
            config,
            reference=cleaned_reference,
            amount=amount,
            description=description,
            client_email=client_email,
            client_first_name=client_first_name,
            client_last_name=client_last_name,
            customer_phone=normalized_phone,
        )
    except CinetPayError as exc:
        raise ToolError(str(exc)) from exc

    result["currency"] = "XOF"
    result["environment"] = config.env
    result["what_this_means"] = (
        "The payment has been REQUESTED, not completed. No money has moved yet. "
        "Send the customer to payment_url to pay. The final outcome is not in "
        "this response and arrives asynchronously."
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool(
    name="momo_check_payment_status",
    description=(
        "Check what became of a payment you requested earlier. Read-only: it "
        "never moves money and never changes anything. Accepts either the "
        "merchant reference you supplied when initiating, or the transaction_id "
        "returned then. Returns a stable status plus the aggregator's own "
        "status and code, and says whether the outcome is final. A payment that "
        "was requested but never completed by the customer ends up FAILED, "
        "which is final — it does not stay pending forever. The customer's "
        "phone number is returned masked, never in full."
    ),
    annotations=ToolAnnotations(
        title="Check a mobile money payment status",
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    ),
)
async def momo_check_payment_status(
    reference: Annotated[
        str,
        Field(
            description=(
                "Either the merchant reference you supplied to "
                "momo_initiate_payment, or the transaction_id it returned. Both "
                "address the same payment."
            ),
            examples=["CMD-2026-0042", "69fe371559c34c6f98971be5c8f4e4df"],
        ),
    ],
) -> str:
    """Consulte le statut d'un paiement. Ne déplace rien."""
    try:
        config = load_config()
    except ConfigurationError as exc:
        raise ToolError(str(exc)) from exc

    cleaned = reference.strip()
    if not cleaned:
        raise ToolError(
            "A reference is required: either the merchant reference you used "
            "when initiating the payment, or the transaction_id returned then."
        )

    try:
        result = await check_payment_status(config, reference=cleaned)
    except CinetPayError as exc:
        raise ToolError(str(exc)) from exc

    result["environment"] = config.env
    if not result["is_final"]:
        result["what_this_means"] = (
            "This payment is still in flight. Nothing is settled yet: do not "
            "treat it as paid, and check again later."
        )
    elif result["status"] == "succeeded":
        result["what_this_means"] = "The customer paid. This outcome is final."
    else:
        result["what_this_means"] = (
            "This payment will not complete. The outcome is final, so checking "
            "again will not change it; start a new payment with a fresh "
            "reference if the customer still wants to pay."
        )
    return json.dumps(result, ensure_ascii=False, indent=2)
