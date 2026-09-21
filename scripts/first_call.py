"""
Sonde manuelle CinetPay — à exécuter AVANT d'écrire `momo_initiate_payment`.

Objectif : obtenir une vraie réponse de l'API sandbox et la lire. Les formats
de statut, les codes d'erreur et la forme exacte des numéros ne s'apprennent
pas dans la documentation, ils s'apprennent dans la réponse.

Écrite à partir du contrat relevé dans docs/API-CINETPAY.md, pas de mémoire.
Deux appels enchaînés :

    POST /v1/oauth/login   -> access_token (JWT, token_type "bearer")
    POST /v1/payment       -> Authorization: Bearer <access_token>

Le second en-tête est **déduit** de `token_type: "bearer"` ; la documentation
ne le montre pas. Un 401 le réfuterait, et c'est une des choses que cette
sonde est là pour trancher.

CE QUE CETTE SONDE NE FAIT PAS
------------------------------
Elle envoie `direct_pay: false`. L'API rend alors une `payment_url` sans rien
pousser vers un téléphone : personne ne reçoit de demande de paiement, aucun
compte n'est débité. C'est délibéré pour un premier appel. Le mode direct,
qui sollicite réellement un combiné et exige un OTP pour Orange, fera l'objet
d'une seconde sonde, en connaissance de cause.

Usage :
    cp .env.example .env      # puis remplir MOMO_API_KEY / MOMO_API_PASSWORD
    pip install -e .
    python scripts/first_call.py

Puis coller la sortie dans le contexte de Claude Code. Les valeurs sensibles
sont masquées avant affichage ; relire quand même avant de coller.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any

import httpx
from dotenv import load_dotenv

from momo_xof_mcp.phone import mask_msisdn

load_dotenv()

# Base sandbox par défaut, pour qu'un .env réduit à la clé et au mot de passe
# suffise. Relevée sur le tableau de bord, cf. docs/API-CINETPAY.md.
BASE_URL = (os.getenv("MOMO_BASE_URL") or "https://api.cinetpay.net").rstrip("/")
API_KEY = os.getenv("MOMO_API_KEY", "")
API_PASSWORD = os.getenv("MOMO_API_PASSWORD", "")
ENV = os.getenv("MOMO_ENV", "sandbox")
TIMEOUT = float(os.getenv("MOMO_TIMEOUT", "30"))

# Les trois URL sont obligatoires côté CinetPay, mais la sonde n'en reçoit
# jamais rien : aucun paiement ne se conclut en direct_pay: false. On retombe
# donc sur example.com, domaine réservé par la RFC 2606, pour n'avoir que deux
# valeurs à saisir dans .env. Le vrai outil, lui, exigera de vraies URL.
_INERT = "https://example.com/momo"
NOTIFY_URL = os.getenv("MOMO_CALLBACK_URL") or f"{_INERT}/notify"
SUCCESS_URL = os.getenv("MOMO_SUCCESS_URL") or f"{_INERT}/success"
FAILED_URL = os.getenv("MOMO_FAILED_URL") or f"{_INERT}/failed"
_URLS_ARE_INERT = not os.getenv("MOMO_CALLBACK_URL")

# Identité client : l'API l'exige. Valeurs synthétiques par défaut, sur le
# domaine example.com réservé par la RFC 2606. Surchargeables si besoin.
CLIENT_EMAIL = os.getenv("MOMO_TEST_EMAIL", "sandbox@example.com")
CLIENT_FIRST_NAME = os.getenv("MOMO_TEST_FIRST_NAME", "Sandbox")
CLIENT_LAST_NAME = os.getenv("MOMO_TEST_LAST_NAME", "Probe")

# Numéro de test, FACULTATIF et vide par défaut. Aucun numéro n'est inventé
# ici. Non renseigné, le champ n'est simplement pas envoyé — ce qui est sans
# conséquence puisque direct_pay vaut false.
TEST_MSISDN = os.getenv("MOMO_TEST_MSISDN", "")

TEST_AMOUNT = 100  # XOF, entier — le franc CFA n'a pas de décimale

# Clés dont la valeur ne doit jamais s'afficher en clair.
_SECRET_KEYS = {"access_token", "api_key", "api_password", "apikey", "password"}
_PHONE_KEYS = {"client_phone_number", "phone", "phone_number", "msisdn"}


def mask_secret(value: str) -> str:
    """Masque une valeur sensible avant affichage."""
    if not value:
        return "(vide)"
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def redact(payload: Any) -> Any:
    """Recopie une structure en masquant jetons, clés et numéros.

    CLAUDE.md interdit de journaliser un numéro complet, une clé d'API, ou un
    corps de réponse contenant l'un des deux. La sortie de cette sonde étant
    destinée à être collée dans une conversation, elle passe par ici.
    """
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            if key in _SECRET_KEYS and isinstance(value, str):
                cleaned[key] = mask_secret(value)
            elif key in _PHONE_KEYS and isinstance(value, str):
                cleaned[key] = mask_msisdn(value)
            else:
                cleaned[key] = redact(value)
        return cleaned
    if isinstance(payload, list):
        return [redact(item) for item in payload]
    return payload


def show(label: str, response: httpx.Response) -> Any:
    """Affiche une réponse masquée. Retourne le corps décodé, non masqué."""
    print(f"\n--- {label} ---")
    print(f"statut HTTP : {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        print("corps (non-JSON) :")
        print(response.text[:2000])
        return None
    print("corps :")
    print(json.dumps(redact(body), indent=2, ensure_ascii=False))
    return body


def check_configuration() -> None:
    """Arrête net si la configuration est incomplète ou dangereuse."""
    if ENV != "sandbox":
        raise SystemExit(
            f"MOMO_ENV vaut {ENV!r}. Cette sonde ne s'exécute qu'en sandbox. "
            "Elle n'a aucune raison de toucher un endpoint de production."
        )

    if "api.cinetpay.net" not in BASE_URL:
        raise SystemExit(
            f"MOMO_BASE_URL vaut {BASE_URL!r}, ce qui n'est pas la base sandbox "
            "CinetPay attendue (https://api.cinetpay.net). Vérifier .env."
        )

    missing = [
        name
        for name, value in (
            ("MOMO_API_KEY", API_KEY),
            ("MOMO_API_PASSWORD", API_PASSWORD),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Variables manquantes dans .env : "
            + ", ".join(missing)
            + ".\n\nÀ faire :\n"
            "  1. Tableau de bord CinetPay, page « API & sécurité », définir le\n"
            "     mot de passe API (il vaut « Non configuré » par défaut).\n"
            "  2. Copier .env.example en .env, puis y renseigner MOMO_API_KEY\n"
            "     et MOMO_API_PASSWORD. Rien d'autre n'est obligatoire.\n"
            "  .env est ignoré par git : aucun risque de le committer."
        )

    for name, url in (
        ("MOMO_CALLBACK_URL", NOTIFY_URL),
        ("MOMO_SUCCESS_URL", SUCCESS_URL),
        ("MOMO_FAILED_URL", FAILED_URL),
    ):
        if len(url) > 120:
            raise SystemExit(f"{name} dépasse 120 caractères, limite de l'API.")


async def login(client: httpx.AsyncClient) -> str:
    """Échange api_key / api_password contre un jeton d'accès."""
    response = await client.post(
        f"{BASE_URL}/v1/oauth/login",
        json={"api_key": API_KEY, "api_password": API_PASSWORD},
        headers={"Content-Type": "application/json"},
    )
    body = show("1. POST /v1/oauth/login", response)

    if response.status_code != 200 or not isinstance(body, dict):
        raise SystemExit(
            "Authentification échouée. Vérifier MOMO_API_KEY et "
            "MOMO_API_PASSWORD dans .env. Le mot de passe API se définit sur "
            "le tableau de bord, page « API & sécurité »."
        )

    token = body.get("access_token")
    if not token:
        raise SystemExit(f"Pas d'access_token dans la réponse. Champs reçus : {sorted(body)}")

    print(f"\njeton     : {mask_secret(token)}")
    print(f"type      : {body.get('token_type')}")
    print(f"expire en : {body.get('expires_in')} s")
    return token


async def initiate_payment(client: httpx.AsyncClient, token: str, reference: str) -> None:
    """Initialise une transaction, sans solliciter aucun téléphone."""
    payload: dict[str, Any] = {
        "currency": "XOF",
        "merchant_transaction_id": reference,
        "amount": TEST_AMOUNT,
        "lang": "fr",
        "designation": "Sonde technique momo-xof-mcp",
        "client_email": CLIENT_EMAIL,
        "client_first_name": CLIENT_FIRST_NAME,
        "client_last_name": CLIENT_LAST_NAME,
        "success_url": SUCCESS_URL,
        "failed_url": FAILED_URL,
        "notify_url": NOTIFY_URL,
        "direct_pay": False,
    }
    if TEST_MSISDN:
        payload["client_phone_number"] = TEST_MSISDN

    print("\ncorps envoyé :")
    print(json.dumps(redact(payload), indent=2, ensure_ascii=False))

    response = await client.post(
        f"{BASE_URL}/v1/payment",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    show("2. POST /v1/payment", response)

    if response.status_code == 401:
        print(
            "\n401 : le jeton n'est pas accepté en en-tête Authorization: Bearer. "
            "C'était une déduction tirée de token_type. Relever dans la "
            "documentation comment le jeton doit voyager."
        )


async def main() -> None:
    check_configuration()

    reference = f"probe-{uuid.uuid4().hex[:12]}"  # 18 caractères, limite à 30

    print(f"base      : {BASE_URL}")
    print(f"clé       : {mask_secret(API_KEY)}")
    print(f"réf       : {reference}")
    print(f"montant   : {TEST_AMOUNT} XOF")
    print("direct_pay: False  (aucun téléphone sollicité)")
    if _URLS_ARE_INERT:
        print("URL       : example.com par défaut, rien n'y sera envoyé")
    if TEST_MSISDN:
        print(f"numéro    : {mask_msisdn(TEST_MSISDN)}")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            token = await login(client)
            await initiate_payment(client, token, reference)
        except httpx.RequestError as exc:
            raise SystemExit(f"Échec réseau : {exc!r}") from exc

    print("\n" + "-" * 60)
    print("À noter avant de coder :")
    print("  - où se trouve l'identifiant de transaction dans la réponse")
    print("  - quelles valeurs de statut apparaissent, et lesquelles sont finales")
    print("  - la forme des erreurs (code, message, champ fautif)")
    print("  - si la référence marchand est renvoyée telle qu'envoyée")
    print("  - ce que contient details.code, et sa correspondance avec status")


if __name__ == "__main__":
    asyncio.run(main())
