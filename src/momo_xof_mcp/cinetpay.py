"""Client CinetPay — authentification et initialisation de paiement.

Écrit à partir de `docs/API-CINETPAY.md`, lui-même rempli à partir d'appels
réels. Rien ici ne vient d'une supposition sur la documentation.

RÈGLE CARDINALE de cette API, vérifiée sur deux appels : le niveau racine et
l'objet `details` ne décrivent pas la même chose.

    racine   code/status -> sort de la requête HTTP
    details  code/status -> sort de la transaction

Une requête rejetée et une demande acceptée répondent **toutes deux**
`HTTP 200` avec `"status": "OK"` à la racine. Seul `details.status` les
distingue. Ne jamais conclure au succès depuis la racine.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Final

import httpx

from .config import Config

# Correspondance explicite entre les statuts de l'agrégateur et un vocabulaire
# stable, exigée par CLAUDE.md. Aucun statut n'est inventé : toute valeur
# absente de cette table ressort en "unknown" avec la valeur brute, jamais
# rabattue en silence sur un statut voisin.
#
# En gras dans docs/API-CINETPAY.md, les valeurs réellement observées :
# INITIATED et INVALID_PARAMS. Les autres sont documentées par CinetPay.
STATUS_MAP: Final[dict[str, str]] = {
    "INITIATED": "accepted",
    "PENDING": "pending",
    "SUCCESS": "succeeded",
    "FAILED": "failed",
    "INVALID_PARAMS": "rejected",
}

# Statuts au-delà desquels plus rien ne bougera.
FINAL_STATUSES: Final[frozenset[str]] = frozenset({"succeeded", "failed", "rejected"})

# Marge retranchée à expires_in, pour ne pas présenter un jeton qui expire
# pendant le vol.
_TOKEN_SAFETY_MARGIN: Final[int] = 60


class CinetPayError(Exception):
    """Échec d'appel côté agrégateur. Le message est destiné à l'appelant."""


def map_status(raw: str | None) -> str:
    """Traduit un statut de l'agrégateur vers le vocabulaire stable."""
    if not raw:
        return "unknown"
    return STATUS_MAP.get(raw.upper(), "unknown")


class _TokenCache:
    """Garde le jeton entre deux appels.

    `expires_in` valait 86 400 s en réel contre 5 767 s dans l'exemple de la
    documentation : la durée est lue dans la réponse, jamais codée en dur.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    def get(self) -> str | None:
        if self._token and time.monotonic() < self._expires_at:
            return self._token
        return None

    def set(self, token: str, expires_in: int) -> None:
        self._token = token
        self._expires_at = time.monotonic() + max(0, expires_in - _TOKEN_SAFETY_MARGIN)

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock


_TOKEN_CACHE = _TokenCache()


def _describe_failure(body: Any, http_status: int) -> str:
    """Construit un message actionnable depuis une réponse en échec.

    Les erreurs de haut niveau portent `description`, celles de transaction
    portent `message` dans `details`. Lire l'un sans l'autre produit un
    message vide.
    """
    if not isinstance(body, dict):
        return f"CinetPay returned HTTP {http_status} with an unreadable body."

    code = body.get("code")
    status = body.get("status")
    description = body.get("description") or body.get("message") or ""

    if code == 2011 or "withlist" in str(description).lower():
        return (
            "CinetPay refused the call: this server's public IP is not in the "
            "account's IP whitelist. Add it on the dashboard under "
            "'API & securite' > 'Liste Blanche IP'. Note that an empty "
            "whitelist rejects every call, despite what the dashboard says."
        )

    return f"CinetPay refused the call (HTTP {http_status}, code {code}, {status}): {description}"


def _describe_rejection(details: dict[str, Any]) -> str:
    """Message actionnable pour un `INVALID_PARAMS`, champ par champ."""
    message = details.get("message") or "CinetPay rejected the payment request."
    errors = details.get("errors")

    if isinstance(errors, dict) and errors:
        lines = []
        for field, messages in errors.items():
            if isinstance(messages, list):
                lines.append(f"  - {field}: {'; '.join(str(m) for m in messages)}")
            else:
                lines.append(f"  - {field}: {messages}")
        return f"{message}\n" + "\n".join(lines)

    return str(message)


async def _get_token(client: httpx.AsyncClient, config: Config) -> str:
    """Récupère un jeton, depuis le cache si possible."""
    cached = _TOKEN_CACHE.get()
    if cached:
        return cached

    async with _TOKEN_CACHE.lock:
        cached = _TOKEN_CACHE.get()
        if cached:
            return cached

        try:
            response = await client.post(
                f"{config.base_url}/v1/oauth/login",
                json={"api_key": config.api_key, "api_password": config.api_password},
                headers={"Content-Type": "application/json"},
            )
        except httpx.RequestError as exc:
            raise CinetPayError(
                f"Could not reach CinetPay at {config.base_url}: {exc.__class__.__name__}. "
                "Check network access and MOMO_BASE_URL."
            ) from exc

        try:
            body = response.json()
        except ValueError:
            body = None

        if response.status_code != 200 or not isinstance(body, dict):
            raise CinetPayError(_describe_failure(body, response.status_code))

        token = body.get("access_token")
        if not token:
            raise CinetPayError(
                "CinetPay accepted the credentials but returned no access_token. "
                f"Fields received: {sorted(body)}."
            )

        _TOKEN_CACHE.set(str(token), int(body.get("expires_in") or 0))
        return str(token)


async def initiate_payment(
    config: Config,
    *,
    reference: str,
    amount: int,
    description: str,
    client_email: str,
    client_first_name: str,
    client_last_name: str,
    customer_phone: str | None = None,
) -> dict[str, Any]:
    """Initialise une demande de paiement. Ne confirme jamais un paiement.

    Retourne la charge utile normalisée. Lève `CinetPayError` si l'appel
    échoue ou si l'agrégateur rejette la requête.
    """
    payload: dict[str, Any] = {
        "currency": "XOF",
        "merchant_transaction_id": reference,
        "amount": amount,
        "lang": "fr",
        "designation": description,
        "client_email": client_email,
        "client_first_name": client_first_name,
        "client_last_name": client_last_name,
        "success_url": config.success_url,
        "failed_url": config.failed_url,
        "notify_url": config.notify_url,
        # Mode redirection : l'API rend une payment_url et ne sollicite aucun
        # combiné. Le mode direct exige un OTP dont le flux n'a pas été
        # observé ; il reste hors périmètre v0.1.
        "direct_pay": False,
    }
    if customer_phone:
        payload["client_phone_number"] = customer_phone

    async with httpx.AsyncClient(timeout=config.timeout) as client:
        token = await _get_token(client, config)

        try:
            response = await client.post(
                f"{config.base_url}/v1/payment",
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.RequestError as exc:
            raise CinetPayError(
                f"Could not reach CinetPay at {config.base_url}: "
                f"{exc.__class__.__name__}. The payment request may or may not "
                f"have been received; check reference {reference!r} on the "
                "dashboard before retrying with the same reference."
            ) from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise CinetPayError(
            f"CinetPay returned HTTP {response.status_code} with a non-JSON body."
        ) from exc

    if response.status_code != 200 or not isinstance(body, dict):
        raise CinetPayError(_describe_failure(body, response.status_code))

    details = body.get("details")
    if not isinstance(details, dict):
        raise CinetPayError(
            "CinetPay returned no 'details' object, so the outcome of the "
            "transaction is unknown. The root-level status describes the HTTP "
            "request only and must not be read as success."
        )

    provider_status = str(details.get("status") or "")
    status = map_status(provider_status)

    if status == "rejected":
        raise CinetPayError(_describe_rejection(details))

    if status == "unknown":
        raise CinetPayError(
            f"CinetPay returned an unmapped transaction status {provider_status!r} "
            f"(code {details.get('code')}). Refusing to guess what it means. "
            "Record it in docs/API-CINETPAY.md and add it to STATUS_MAP."
        )

    return {
        "status": status,
        "is_final": status in FINAL_STATUSES,
        "provider_status": provider_status,
        "provider_code": details.get("code"),
        "provider_message": details.get("message"),
        "merchant_reference": body.get("merchant_transaction_id"),
        "transaction_id": body.get("transaction_id"),
        "payment_url": body.get("payment_url"),
        "must_be_redirected": details.get("must_be_redirected"),
    }
