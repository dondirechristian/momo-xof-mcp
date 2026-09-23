"""Tests de `build_status_result`, à partir de réponses réellement observées.

Les charges utiles ci-dessous sont recopiées de `docs/API-CINETPAY.md` :
ce sont de vraies réponses de la sandbox, pas des inventions.
"""

from __future__ import annotations

import pytest

from momo_xof_mcp.cinetpay import CinetPayError, build_status_result

# Observée le 2026-09-23 : demande initiée la veille, jamais honorée.
ABANDONED = {
    "code": 2010,
    "status": "FAILED",
    "merchant_transaction_id": "e2e-16c3f19e37",
    "transaction_id": "daa3dcf52578408f8093c6c55d792bb8",
    "user": None,
}

# Forme documentée d'un paiement abouti.
PAID = {
    "code": 100,
    "status": "SUCCESS",
    "merchant_transaction_id": "MY-ORDER-ID-08082116",
    "transaction_id": "3de579e7ec43451a9463d45d21a4cf48",
    "user": {
        "name": "Doe John",
        "email": "john.doe@gmail.com",
        "phone_number": "+2250707000000",
    },
    "payment_method": "OM",
}


class TestAbandonedPayment:
    def test_it_is_failed_not_pending(self):
        # Le piege : une demande que personne n'honore ne reste pas en
        # attente, elle finit FAILED. Un agent qui sonderait en boucle en
        # attendant autre chose tournerait indefiniment.
        assert build_status_result(ABANDONED)["status"] == "failed"

    def test_it_is_final(self):
        assert build_status_result(ABANDONED)["is_final"] is True

    def test_the_raw_status_is_kept(self):
        result = build_status_result(ABANDONED)
        assert result["provider_status"] == "FAILED"
        assert result["provider_code"] == 2010

    def test_a_null_user_does_not_raise(self):
        # `user` vaut null hors succes, observe meme sur une transaction
        # terminee. Y acceder sans verifier leverait.
        assert build_status_result(ABANDONED)["customer"] is None

    def test_missing_payment_method_is_tolerated(self):
        # La reponse reelle n'a pas ce champ, l'exemple de la doc si.
        assert build_status_result(ABANDONED)["payment_method"] is None


class TestPaidPayment:
    def test_it_is_succeeded_and_final(self):
        result = build_status_result(PAID)
        assert result["status"] == "succeeded"
        assert result["is_final"] is True

    def test_the_customer_phone_is_masked(self):
        # CLAUDE.md : jamais un numero complet. Il est masque avant de sortir
        # d'ici, pas seulement avant d'etre journalise.
        masked = build_status_result(PAID)["customer"]["phone_masked"]
        assert masked == "+225 07 ** ** ** 00"
        assert "0707000000" not in masked

    def test_the_rest_of_the_customer_is_kept(self):
        customer = build_status_result(PAID)["customer"]
        assert customer["name"] == "Doe John"
        assert customer["email"] == "john.doe@gmail.com"

    def test_the_full_number_appears_nowhere_in_the_result(self):
        import json

        assert "+2250707000000" not in json.dumps(build_status_result(PAID))


class TestUnknownStatus:
    def test_an_unmapped_status_raises_instead_of_guessing(self):
        # Rabattre un statut inconnu sur « paye » ou « non paye » serait la
        # pire erreur possible sur un serveur de paiement.
        with pytest.raises(CinetPayError) as excinfo:
            build_status_result({"code": 9999, "status": "WAITING_CUSTOMER"})
        assert "Refusing to guess" in str(excinfo.value)

    def test_a_missing_status_raises(self):
        with pytest.raises(CinetPayError):
            build_status_result({"code": 100})
