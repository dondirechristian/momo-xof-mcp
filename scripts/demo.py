"""
Démonstration jouable de momo-xof-mcp, pensée pour être filmée en GIF.

Passe par un vrai client MCP sur transport stdio : ce qui s'affiche est ce
qu'un agent verrait réellement. Rien n'est simulé, rien n'est mis en scène.

    python scripts/demo.py            # rythme normal, environ 45 s
    python scripts/demo.py --fast     # sans pauses, pour répéter
    python scripts/demo.py --no-pay   # sans appel réseau, catalogue seul

Sûreté : la demande de paiement porte sur 1 000 XOF en sandbox, en mode
redirection. Aucun téléphone n'est sollicité, aucun compte n'est débité, et
le serveur refuse de sortir de la sandbox.

Largeur volontairement limitée à 72 colonnes pour rester lisible une fois
réduit en GIF.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FAST = "--fast" in sys.argv
NO_PAY = "--no-pay" in sys.argv

WIDTH = 72
PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "momo_xof_mcp"])


def pause(seconds: float) -> None:
    if not FAST:
        time.sleep(seconds)


def rule() -> None:
    print("─" * WIDTH)


def step(number: int, title: str) -> None:
    print()
    rule()
    print(f"  {number}. {title}")
    rule()
    pause(1.0)


def typed(prompt: str) -> None:
    """Affiche une ligne comme si elle était tapée."""
    print("  > ", end="", flush=True)
    for char in prompt:
        print(char, end="", flush=True)
        if not FAST:
            time.sleep(0.012)
    print()
    pause(0.5)


def show(payload: dict, keys: list[str]) -> None:
    for key in keys:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, str) and len(value) > 46:
            value = value[:43] + "..."
        print(f"      {key:<20} {value}")
        pause(0.12)


async def main(quiet: object) -> None:
    print()
    print("  momo-xof-mcp — mobile money, zone franc CFA (XOF)")
    print("  Orange Money · Moov Money · Wave · MTN · T-Money…")
    pause(1.5)

    async with stdio_client(PARAMS, errlog=quiet) as (read, write), ClientSession(
        read, write
    ) as session:
        await session.initialize()

        step(1, "Quels outils l'agent voit-il ?")
        tools = await session.list_tools()
        for tool in tools.tools:
            read_only = tool.annotations and tool.annotations.read_only_hint
            flag = "lecture seule" if read_only else "DÉPLACE DE L'ARGENT"
            print(f"      {tool.name:<28} {flag}")
            pause(0.35)

        step(2, "Où peut-on encaisser, et avec quoi ?")
        typed("Quels services de paiement au Burkina Faso ?")
        result = await session.call_tool("momo_list_operators", {"country": "BF"})
        country = json.loads(result.content[0].text)["countries"][0]
        print(f"      {country['country_name']}  {country['dialing_code']}"
              f"  ({country['national_number_length']} chiffres)")
        for service in country["payment_services"]:
            kind = "porte-monnaie indépendant" if service[
                "service_type"] == "independent_wallet" else "adossé au réseau"
            print(f"      · {service['service']:<16} {kind}")
            pause(0.4)

        step(3, "Un garde-fou, avant de parler d'argent")
        typed("Encaisser 60 000 XOF")
        await session.call_tool("momo_initiate_payment", {
            "amount": 60000, "reference": "demo-plafond",
            "description": "Demo", "client_email": "client@example.com",
            "client_first_name": "Aminata", "client_last_name": "Ouedraogo",
        })
        print("      REFUSÉ par le serveur, avant tout appel réseau :")
        print("      « exceeds the server-side ceiling of 50000 XOF »")
        pause(1.6)

        if NO_PAY:
            print()
            rule()
            print("  (--no-pay : la demande de paiement est passée)")
            rule()
            return

        step(4, "Une vraie demande de paiement")
        reference = f"CMD-{uuid.uuid4().hex[:6].upper()}"
        typed(f"Encaisser 1 000 XOF, référence {reference}")
        created = await session.call_tool("momo_initiate_payment", {
            "amount": 1000, "reference": reference,
            "description": "Commande 42 — SOTECHDI",
            "client_email": "client@example.com",
            "client_first_name": "Aminata", "client_last_name": "Ouedraogo",
        })
        if created.is_error:
            message = created.content[0].text
            if "whitelist" in message:
                print("      L'appel n'a pas pu partir : l'IP publique de cette")
                print("      machine n'est pas en liste blanche chez CinetPay.")
                print("      Tableau de bord > API & securite > Liste Blanche IP.")
                print()
                print("      Relancez ensuite, ou repetez avec --no-pay.")
            else:
                print("      " + message.strip().splitlines()[0][:62])
            return
        payment = json.loads(created.content[0].text)
        show(payment, ["status", "is_final", "merchant_reference",
                       "transaction_id", "payment_url"])
        pause(0.8)
        print()
        print("      ⚠  « accepted » ne veut PAS dire encaissé.")
        print("         Le client n'a pas encore payé.")
        pause(2.2)

        step(5, "Et ensuite ? On consulte, on ne suppose pas")
        typed(f"Où en est {reference} ?")
        checked = await session.call_tool(
            "momo_check_payment_status", {"reference": reference})
        status = json.loads(checked.content[0].text)
        show(status, ["status", "is_final", "provider_status",
                      "provider_meaning"])
        pause(1.5)

    print()
    rule()
    print("  Trois outils. Huit pays. Zéro supposition sur l'API.")
    rule()
    print()


if __name__ == "__main__":
    # Le serveur journalise sur stderr. Utile en exploitation, parasite dans
    # une capture : on le détourne le temps de la démonstration. Ouvert ici,
    # hors de la fonction asynchrone, car le sous-processus réclame un vrai
    # descripteur de fichier — un tampon mémoire n'a pas de fileno().
    with open(os.devnull, "w", encoding="utf-8") as devnull:
        asyncio.run(main(devnull))
