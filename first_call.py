"""
Sonde manuelle — à exécuter AVANT d'écrire la moindre ligne du serveur MCP.

Objectif : obtenir une vraie réponse de l'API sandbox et la lire. Les formats
de statut, les codes d'erreur et la forme exacte des numéros ne s'apprennent
pas dans la documentation, ils s'apprennent dans la réponse.

Usage :
    cp .env.example .env      # puis remplir
    pip install httpx python-dotenv
    python scripts/first_call.py

Adapter les trois TODO ci-dessous à l'agrégateur retenu, puis coller la sortie
dans le contexte de Claude Code avant de lui demander le premier outil.
"""

import asyncio
import json
import os
import uuid

import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("MOMO_BASE_URL", "").rstrip("/")
API_KEY = os.getenv("MOMO_API_KEY", "")
SITE_ID = os.getenv("MOMO_SITE_ID", "")
TIMEOUT = float(os.getenv("MOMO_TIMEOUT", "30"))

# Numéro de test fourni par l'agrégateur pour son sandbox.
# Ne jamais mettre ici un vrai numéro personnel.
TEST_MSISDN = "+226XXXXXXXX"
TEST_AMOUNT = 100  # XOF, entier


def mask(value: str) -> str:
    """Masque une valeur sensible avant affichage."""
    if not value:
        return "(vide)"
    return value[:4] + "*" * max(0, len(value) - 8) + value[-4:]


async def main() -> None:
    if not BASE_URL or not API_KEY:
        raise SystemExit(
            "MOMO_BASE_URL ou MOMO_API_KEY manquant. "
            "Copier .env.example en .env et le remplir."
        )

    reference = f"probe-{uuid.uuid4().hex[:12]}"

    # TODO 1 — chemin exact de l'endpoint de collecte, selon l'agrégateur
    url = f"{BASE_URL}/payment"

    # TODO 2 — schéma d'authentification réel (en-tête Bearer, clé dans le corps,
    # signature HMAC...). Vérifier dans la doc de l'agrégateur.
    headers = {"Content-Type": "application/json"}

    # TODO 3 — noms de champs réels attendus par l'agrégateur
    payload = {
        "apikey": API_KEY,
        "site_id": SITE_ID,
        "transaction_id": reference,
        "amount": TEST_AMOUNT,
        "currency": "XOF",
        "customer_phone_number": TEST_MSISDN,
        "description": "Sonde technique momo-xof-mcp",
    }

    print(f"POST  {url}")
    print(f"clé   {mask(API_KEY)}")
    print(f"réf   {reference}")
    print("-" * 60)

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            raise SystemExit(f"Échec réseau : {exc!r}")

    print(f"statut HTTP : {response.status_code}")
    print("corps :")
    try:
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print(response.text)

    print("-" * 60)
    print("À noter avant de coder :")
    print("  - où se trouve l'identifiant de transaction dans la réponse")
    print("  - quelles valeurs de statut existent, et lesquelles sont finales")
    print("  - la forme des erreurs (code, message, champ fautif)")
    print("  - si le numéro est renvoyé normalisé ou tel qu'envoyé")


if __name__ == "__main__":
    asyncio.run(main())
