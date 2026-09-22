"""Configuration lue depuis l'environnement, avec ses garde-fous.

Lue à l'appel, pas à l'import : un serveur MCP démarre avant que le client
n'ait forcément fini de pousser son environnement, et une erreur de
configuration doit remonter comme une erreur d'outil lisible, pas comme un
plantage au chargement du module.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

# Seul hôte sandbox connu, relevé sur le tableau de bord (docs/API-CINETPAY.md).
SANDBOX_HOST: Final[str] = "api.cinetpay.net"

DEFAULT_MAX_AMOUNT: Final[int] = 50_000
DEFAULT_TIMEOUT: Final[float] = 30.0


class ConfigurationError(Exception):
    """Configuration absente ou incohérente. Le message dit quoi corriger."""


@dataclass(frozen=True)
class Config:
    """Configuration effective du serveur."""

    env: str
    base_url: str
    api_key: str
    api_password: str
    notify_url: str
    success_url: str
    failed_url: str
    max_amount: int
    timeout: float


def _required(name: str, hint: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(
            f"{name} is not set. {hint} Put it in the server's .env file, never "
            "in the repository."
        )
    return value


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"{name} must be a whole number of XOF, got {raw!r}. The West "
            "African CFA franc has no decimal subunit."
        ) from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero, got {value}.")
    return value


def load_config() -> Config:
    """Construit la configuration, ou lève `ConfigurationError`."""
    env = os.getenv("MOMO_ENV", "sandbox").strip().lower()
    if env not in {"sandbox", "production"}:
        raise ConfigurationError(
            f"MOMO_ENV must be 'sandbox' or 'production', got {env!r}."
        )

    base_url = os.getenv("MOMO_BASE_URL", "").strip().rstrip("/")

    if env == "sandbox":
        # Verrou exigé par CLAUDE.md : en sandbox, aucun appel ne doit partir
        # vers un endpoint de production. Le seul hôte sandbox connu est
        # api.cinetpay.net ; tout le reste est refusé, y compris une URL de
        # production correcte.
        if not base_url:
            base_url = f"https://{SANDBOX_HOST}"
        if SANDBOX_HOST not in base_url:
            raise ConfigurationError(
                f"MOMO_ENV is 'sandbox' but MOMO_BASE_URL points at {base_url!r}, "
                f"which is not the CinetPay sandbox host ({SANDBOX_HOST}). "
                "Refusing to call a non-sandbox endpoint while in sandbox mode. "
                "Either fix MOMO_BASE_URL or set MOMO_ENV=production deliberately."
            )
    elif not base_url:
        raise ConfigurationError(
            "MOMO_ENV is 'production' but MOMO_BASE_URL is empty. The CinetPay "
            "production base URL has not been established for this project "
            "(see docs/API-CINETPAY.md); it must be set explicitly, never guessed."
        )

    return Config(
        env=env,
        base_url=base_url,
        api_key=_required("MOMO_API_KEY", "This is the CinetPay API key."),
        api_password=_required(
            "MOMO_API_PASSWORD",
            "This is the CinetPay API password, set on the dashboard under "
            "'API & securite'; it is 'Non configure' until you define it.",
        ),
        notify_url=_required(
            "MOMO_CALLBACK_URL",
            "CinetPay requires notify_url on every payment; it cannot be empty.",
        ),
        success_url=_required(
            "MOMO_SUCCESS_URL", "CinetPay requires success_url on every payment."
        ),
        failed_url=_required(
            "MOMO_FAILED_URL", "CinetPay requires failed_url on every payment."
        ),
        max_amount=_positive_int("MOMO_MAX_AMOUNT", DEFAULT_MAX_AMOUNT),
        timeout=float(os.getenv("MOMO_TIMEOUT", "").strip() or DEFAULT_TIMEOUT),
    )
