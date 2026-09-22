"""Tests des garde-fous du paiement — configuration et statuts.

Aucun appel réseau : ces tests ne doivent jamais déclencher un paiement,
même en sandbox. Ils portent sur les fonctions pures, là où les erreurs
coûteuses se préviennent.
"""

from __future__ import annotations

import pytest

from momo_xof_mcp.cinetpay import FINAL_STATUSES, STATUS_MAP, map_status
from momo_xof_mcp.config import ConfigurationError, load_config

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
            ("INITIATED", "accepted"),
            ("PENDING", "pending"),
            ("SUCCESS", "succeeded"),
            ("FAILED", "failed"),
            ("INVALID_PARAMS", "rejected"),
        ],
    )
    def test_every_documented_status_is_mapped(self, provider, expected):
        assert map_status(provider) == expected

    def test_mapping_is_case_insensitive(self):
        assert map_status("initiated") == "accepted"

    @pytest.mark.parametrize("value", ["WAITING_CUSTOMER", "", None, "OK"])
    def test_an_unmapped_status_never_becomes_a_neighbour(self, value):
        # Rabattre un statut inconnu sur « accepted » ou « failed » serait
        # inventer une information. Il ressort en "unknown", et l'appelant
        # doit trancher.
        assert map_status(value) == "unknown"

    def test_initiated_is_not_final(self):
        assert "accepted" not in FINAL_STATUSES

    def test_pending_is_not_final(self):
        assert "pending" not in FINAL_STATUSES

    @pytest.mark.parametrize("status", ["succeeded", "failed", "rejected"])
    def test_terminal_statuses_are_final(self, status):
        assert status in FINAL_STATUSES

    def test_no_mapped_status_is_a_raw_provider_value(self):
        # Le vocabulaire stable ne doit pas se confondre avec celui de
        # l'agrégateur, sinon le mapping ne sert à rien.
        assert not set(STATUS_MAP.values()) & set(STATUS_MAP)

    def test_success_never_maps_to_accepted(self):
        # Le piège inverse : un paiement réussi ne doit pas ressortir comme
        # une simple demande acceptée, ni l'inverse.
        assert map_status("SUCCESS") != map_status("INITIATED")
