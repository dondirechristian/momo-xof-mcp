"""Tests des garde-fous du paiement — configuration et statuts.

Aucun appel réseau : ces tests ne doivent jamais déclencher un paiement,
même en sandbox. Ils portent sur les fonctions pures, là où les erreurs
coûteuses se préviennent.
"""

from __future__ import annotations

import pytest

from momo_xof_mcp.config import ConfigurationError, load_config
from momo_xof_mcp.statuses import (
    FINAL_STABLE_STATUSES,
    IN_FLIGHT_STATUSES,
    STATUS_TABLE,
    is_final,
    map_status,
)

_COMPLETE_ENV = {
    "MOMO_ENV": "sandbox",
    "MOMO_BASE_URL": "https://api.cinetpay.net",
    "MOMO_API_KEY": "sk_test_dummy",
    "MOMO_API_PASSWORD": "dummy_password",
    "MOMO_CALLBACK_URL": "https://example.com/momo/notify",
    "MOMO_SUCCESS_URL": "https://example.com/momo/success",
    "MOMO_FAILED_URL": "https://example.com/momo/failed",
}


@pytest.fixture
def env(monkeypatch):
    """Environnement complet et valide, que chaque test dégrade à sa guise."""
    for name in list(_COMPLETE_ENV) + ["MOMO_MAX_AMOUNT", "MOMO_TIMEOUT"]:
        monkeypatch.delenv(name, raising=False)
    for name, value in _COMPLETE_ENV.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


class TestSandboxLock:
    """CLAUDE.md : en sandbox, refuser tout endpoint de production."""

    def test_sandbox_accepts_the_sandbox_host(self, env):
        assert load_config().base_url == "https://api.cinetpay.net"

    def test_sandbox_refuses_a_foreign_host(self, env):
        env.setenv("MOMO_BASE_URL", "https://api.production.example.com")
        with pytest.raises(ConfigurationError) as excinfo:
            load_config()
        message = str(excinfo.value)
        assert "sandbox" in message
        assert "Refusing" in message

    def test_sandbox_defaults_to_the_sandbox_host(self, env):
        env.delenv("MOMO_BASE_URL")
        assert "api.cinetpay.net" in load_config().base_url

    def test_production_refuses_an_unset_base_url(self, env):
        env.setenv("MOMO_ENV", "production")
        env.delenv("MOMO_BASE_URL")
        with pytest.raises(ConfigurationError) as excinfo:
            load_config()
        assert "never guessed" in str(excinfo.value)

    def test_unknown_environment_is_refused(self, env):
        env.setenv("MOMO_ENV", "staging")
        with pytest.raises(ConfigurationError):
            load_config()


class TestRequiredSettings:
    @pytest.mark.parametrize(
        "name",
        [
            "MOMO_API_KEY",
            "MOMO_API_PASSWORD",
            "MOMO_CALLBACK_URL",
            "MOMO_SUCCESS_URL",
            "MOMO_FAILED_URL",
        ],
    )
    def test_each_one_is_required(self, env, name):
        env.delenv(name)
        with pytest.raises(ConfigurationError) as excinfo:
            load_config()
        assert name in str(excinfo.value)

    def test_the_message_says_where_secrets_belong(self, env):
        env.delenv("MOMO_API_KEY")
        with pytest.raises(ConfigurationError) as excinfo:
            load_config()
        assert ".env" in str(excinfo.value)


class TestAmountCeiling:
    def test_default_ceiling(self, env):
        assert load_config().max_amount == 50_000

    def test_ceiling_is_configurable(self, env):
        env.setenv("MOMO_MAX_AMOUNT", "250000")
        assert load_config().max_amount == 250_000

    def test_a_decimal_ceiling_is_refused(self, env):
        # XOF n'a pas de décimale : accepter 5000.50 serait accepter un montant
        # qui n'existe pas dans cette devise.
        env.setenv("MOMO_MAX_AMOUNT", "5000.50")
        with pytest.raises(ConfigurationError) as excinfo:
            load_config()
        assert "no decimal" in str(excinfo.value)

    @pytest.mark.parametrize("value", ["0", "-1"])
    def test_a_non_positive_ceiling_is_refused(self, env, value):
        env.setenv("MOMO_MAX_AMOUNT", value)
        with pytest.raises(ConfigurationError):
            load_config()


class TestStatusMapping:
    """CLAUDE.md : ne jamais inventer un statut."""

    @pytest.mark.parametrize(
        ("provider", "expected"),
        [
            ("OK", "ok"),
            ("SUCCESS", "succeeded"),
            ("OPERATION_ERROR", "provider_error"),
            ("NOT_FOUND", "not_found"),
            ("INVALID_CREDENTIALS", "auth_error"),
            ("INVALID_PARAMS", "rejected"),
            ("EXPIRED_TOKEN", "auth_error"),
            ("INVALID_TOKEN", "auth_error"),
            ("TRANSACTION_EXIST", "duplicate"),
            ("INITIATED", "accepted"),
            ("PENDING", "pending"),
            ("EXPIRED", "expired"),
            ("OTP_ERROR", "otp_invalid"),
            ("OTP_EXPIRED", "otp_invalid"),
            ("INSUFFICIENT_BALANCE", "failed"),
            ("USER_NOT_FOUND", "customer_problem"),
            ("USER_IS_BLOCKED", "customer_problem"),
            ("FAILED", "failed"),
            ("NOT_ALLOWED", "auth_error"),
        ],
    )
    def test_every_documented_status_is_mapped(self, provider, expected):
        assert map_status(provider) == expected

    def test_the_table_covers_the_documented_list_plus_observations(self):
        # Dix-neuf lignes documentées, plus TRANSACTION_ALREADY_EXIST, observé
        # le 2026-09-24 et absent de la table officielle.
        assert len(STATUS_TABLE) == 20

    def test_codes_match_the_documentation(self):
        expected = {
            "OK": 200, "SUCCESS": 100, "OPERATION_ERROR": -1, "NOT_FOUND": 404,
            "INVALID_CREDENTIALS": 1005, "INVALID_PARAMS": 1004,
            "EXPIRED_TOKEN": 1003, "INVALID_TOKEN": 1002,
            "TRANSACTION_EXIST": 1200, "INITIATED": 2001, "PENDING": 2002,
            "EXPIRED": 2003, "OTP_ERROR": 2004, "OTP_EXPIRED": 2008,
            "INSUFFICIENT_BALANCE": 2005, "USER_NOT_FOUND": 2006,
            "USER_IS_BLOCKED": 2007, "FAILED": 2010, "NOT_ALLOWED": 2011,
        }
        observed = {n: e.code for n, e in STATUS_TABLE.items() if n in expected}
        assert observed == expected

    def test_mapping_is_case_insensitive(self):
        assert map_status("initiated") == "accepted"

    @pytest.mark.parametrize("value", ["WAITING_CUSTOMER", "", None, "PAID"])
    def test_an_unmapped_status_never_becomes_a_neighbour(self, value):
        # Rabattre un statut inconnu sur « accepted » ou « failed » serait
        # inventer une information. Il ressort en "unknown", et l'appelant
        # doit trancher.
        assert map_status(value) == "unknown"


class TestStatusFinality:
    """La colonne « Statut final » vient de CinetPay, pas de l'intuition."""

    @pytest.mark.parametrize(
        "provider",
        ["SUCCESS", "TRANSACTION_EXIST", "INSUFFICIENT_BALANCE", "FAILED"],
    )
    def test_the_four_documented_final_statuses(self, provider):
        assert is_final(provider) is True

    def test_five_statuses_are_final(self):
        # Quatre documentés, plus TRANSACTION_ALREADY_EXIST.
        assert sum(1 for entry in STATUS_TABLE.values() if entry.is_final) == 5

    @pytest.mark.parametrize("provider", ["INITIATED", "PENDING"])
    def test_an_in_flight_payment_is_never_final(self, provider):
        assert is_final(provider) is False
        assert map_status(provider) in IN_FLIGHT_STATUSES

    def test_expired_is_not_final_however_surprising(self):
        # Contre-intuitif, et c'est pour cela qu'on ne le devine pas : la
        # documentation marque EXPIRED « Statut final : Non ».
        assert is_final("EXPIRED") is False

    def test_invalid_params_is_not_final(self):
        # Corrige une erreur de la première version, qui le classait final.
        assert is_final("INVALID_PARAMS") is False

    def test_an_unknown_status_is_never_claimed_final(self):
        # Affirmer qu'une transaction est close sans le savoir est la pire
        # des deux erreurs possibles.
        assert is_final("WAITING_CUSTOMER") is False
        assert is_final(None) is False

    def test_final_stable_statuses_are_derived_not_hardcoded(self):
        assert FINAL_STABLE_STATUSES == {"succeeded", "duplicate", "failed"}

    def test_success_and_initiated_never_collapse(self):
        # Le piège inverse : un paiement réussi ne doit pas ressortir comme
        # une simple demande acceptée, ni l'inverse.
        assert map_status("SUCCESS") != map_status("INITIATED")

    def test_the_observed_duplicate_spelling_is_mapped(self):
        # La documentation annonce TRANSACTION_EXIST / 1200. L'API rend en
        # realite TRANSACTION_ALREADY_EXIST / 2010, et 2010 est par ailleurs
        # le code de FAILED. Les deux orthographes sont acceptees.
        assert map_status("TRANSACTION_ALREADY_EXIST") == "duplicate"
        assert map_status("TRANSACTION_EXIST") == "duplicate"

    def test_the_observed_duplicate_is_final(self):
        assert is_final("TRANSACTION_ALREADY_EXIST") is True

    def test_a_replayed_reference_is_not_reported_as_a_failure(self):
        # Le piege : 2010 est le code de FAILED. Rabattre le doublon sur
        # "failed" ferait croire a un paiement echoue alors que le premier
        # est peut-etre en cours, voire deja regle.
        assert map_status("TRANSACTION_ALREADY_EXIST") != map_status("FAILED")
