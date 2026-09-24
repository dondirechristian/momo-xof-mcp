"""Table des statuts CinetPay et traduction vers un vocabulaire stable.

Recopiée de la section « Codes de statut » de la documentation CinetPay,
relevée le 2026-09-23. C'est une table **unique** : les statuts de haut niveau
et ceux de l'objet `details` y puisent tous les deux. `OK` (200) et
`NOT_ALLOWED` (2011) y côtoient `INITIATED` (2001).

Deux principes, imposés par CLAUDE.md :

1. **Ne jamais inventer un statut.** Toute valeur absente de cette table
   ressort en `unknown` et fait lever l'appelant, plutôt que d'être rabattue
   sur un voisin plausible.
2. **La finalité vient de l'agrégateur, pas de l'intuition.** La colonne
   « Statut final » de la documentation est recopiée telle quelle. Elle
   surprend par endroits — `EXPIRED` n'est pas final, `INSUFFICIENT_BALANCE`
   l'est — et c'est précisément pourquoi on ne la devine pas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Status:
    """Une ligne de la table des statuts CinetPay."""

    code: int
    stable: str
    is_final: bool
    meaning: str


# Vocabulaire stable exposé par le serveur. Il ne changera pas au gré des
# évolutions de l'agrégateur : c'est tout l'intérêt de la traduction.
#
#   ok               requête acceptée au niveau protocole
#   accepted         demande enregistrée, le client doit agir
#   pending          le client a commencé à payer
#   succeeded        argent encaissé
#   failed           le paiement n'aboutira pas
#   expired          le client n'a pas agi à temps
#   duplicate        référence déjà utilisée
#   otp_invalid      code OTP faux ou périmé
#   customer_problem compte client inconnu ou bloqué
#   rejected         requête malformée
#   auth_error       identifiants, jeton ou liste blanche
#   not_found        ressource introuvable
#   provider_error   erreur interne de l'agrégateur
STATUS_TABLE: Final[dict[str, Status]] = {
    "OK": Status(200, "ok", False, "Operation succeeded"),
    "SUCCESS": Status(100, "succeeded", True, "Transaction processed successfully"),
    "OPERATION_ERROR": Status(-1, "provider_error", False, "An error occurred"),
    "NOT_FOUND": Status(404, "not_found", False, "Not found"),
    "INVALID_CREDENTIALS": Status(1005, "auth_error", False, "Credentials are invalid"),
    "INVALID_PARAMS": Status(1004, "rejected", False, "Parameters are invalid"),
    "EXPIRED_TOKEN": Status(1003, "auth_error", False, "Authentication token expired"),
    "INVALID_TOKEN": Status(1002, "auth_error", False, "Authentication token invalid"),
    "TRANSACTION_EXIST": Status(1200, "duplicate", True, "The transaction already exists"),
    # Observé le 2026-09-24 en rejouant une référence déjà utilisée. L'API a
    # répondu `TRANSACTION_ALREADY_EXIST` avec le code **2010**, alors que la
    # table officielle annonce `TRANSACTION_EXIST` avec le code **1200**. Ni
    # le nom ni le code ne correspondent, et 2010 est par ailleurs documenté
    # comme `FAILED` : le même code porte donc deux statuts distincts.
    # Les deux entrées sont conservées : la documentée parce qu'elle peut
    # sortir ailleurs (transferts ?), l'observée parce que c'est celle que
    # rend l'initialisation de paiement.
    "TRANSACTION_ALREADY_EXIST": Status(
        2010, "duplicate", True, "The transaction already exists (observed spelling)"
    ),
    "INITIATED": Status(2001, "accepted", False, "Initiated, waiting for the customer"),
    "PENDING": Status(2002, "pending", False, "The customer started the payment"),
    "EXPIRED": Status(2003, "expired", False, "Expired, the customer did not confirm"),
    "OTP_ERROR": Status(2004, "otp_invalid", False, "The OTP code is incorrect"),
    "OTP_EXPIRED": Status(2008, "otp_invalid", False, "The OTP code has expired"),
    "INSUFFICIENT_BALANCE": Status(
        2005, "failed", True, "The merchant balance is insufficient"
    ),
    "USER_NOT_FOUND": Status(2006, "customer_problem", False, "The user does not exist"),
    "USER_IS_BLOCKED": Status(2007, "customer_problem", False, "The user is blocked"),
    "FAILED": Status(2010, "failed", True, "The payment failed"),
    "NOT_ALLOWED": Status(2011, "auth_error", False, "This IP is not whitelisted"),
}

UNKNOWN: Final[str] = "unknown"

# Statuts stables après lesquels plus rien ne bougera, déduits de la colonne
# « Statut final » et d'elle seule.
FINAL_STABLE_STATUSES: Final[frozenset[str]] = frozenset(
    entry.stable for entry in STATUS_TABLE.values() if entry.is_final
)

# Statuts stables qui signalent une demande vivante, dont l'issue reste à
# connaître par interrogation.
IN_FLIGHT_STATUSES: Final[frozenset[str]] = frozenset({"accepted", "pending"})


def lookup(raw: str | None) -> Status | None:
    """Retrouve une ligne de la table. Insensible à la casse."""
    if not raw:
        return None
    return STATUS_TABLE.get(raw.strip().upper())


def map_status(raw: str | None) -> str:
    """Traduit un statut de l'agrégateur vers le vocabulaire stable."""
    entry = lookup(raw)
    return entry.stable if entry else UNKNOWN


def is_final(raw: str | None) -> bool:
    """Dit si l'agrégateur considère ce statut comme définitif.

    Un statut inconnu n'est jamais présenté comme final : affirmer qu'une
    transaction est close sans le savoir est la pire des deux erreurs.
    """
    entry = lookup(raw)
    return bool(entry and entry.is_final)
