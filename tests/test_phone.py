"""Tests de normalisation et de masquage des numéros.

Aucun appel réseau, aucun numéro réel : les numéros sont construits à partir
des longueurs du catalogue, chiffres neutres.
"""

from __future__ import annotations

import pytest

from momo_xof_mcp.operators import SUPPORTED_COUNTRY_CODES, find_country
from momo_xof_mcp.phone import InvalidMsisdn, mask_msisdn, normalize_msisdn


class TestInternationalInput:
    """Saisie déjà internationale : le pays n'est pas nécessaire."""

    def test_already_e164_is_returned_unchanged(self):
        assert normalize_msisdn("+22670123456") == "+22670123456"

    def test_double_zero_prefix_becomes_plus(self):
        assert normalize_msisdn("0022670123456") == "+22670123456"

    @pytest.mark.parametrize(
        "raw",
        [
            "+226 70 12 34 56",
            "+226-70-12-34-56",
            "+226.70.12.34.56",
            "  +22670123456  ",
            "+226 (70) 12 34 56",
        ],
    )
    def test_separators_are_tolerated(self, raw):
        assert normalize_msisdn(raw) == "+22670123456"

    def test_country_is_inferred_from_dialing_code(self):
        assert normalize_msisdn("+2250701234567") == "+2250701234567"

    def test_wrong_length_is_refused(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("+2267012345")
        message = str(excinfo.value)
        assert "7 digits after +226" in message
        assert "8 digits" in message

    def test_unsupported_dialing_code_is_refused(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("+33612345678")
        assert "does not start with a supported dialing code" in str(excinfo.value)


class TestNationalInput:
    """Saisie nationale : le pays est obligatoire."""

    def test_national_number_with_country(self):
        assert normalize_msisdn("70123456", "BF") == "+22670123456"

    def test_country_code_is_case_insensitive(self):
        assert normalize_msisdn("70123456", "bf") == "+22670123456"

    def test_national_without_country_is_refused(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("70123456")
        assert "no country indication" in str(excinfo.value)

    def test_international_without_plus_is_accepted_with_country(self):
        assert normalize_msisdn("22670123456", "BF") == "+22670123456"

    def test_unknown_country_code_is_refused(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("70123456", "ZZ")
        assert "Unknown country code" in str(excinfo.value)

    def test_wrong_length_mentions_the_leading_zero_trap(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("7012345", "BF")
        assert "leading 0" in str(excinfo.value)


class TestLeadingZeroIsPartOfTheNumber:
    """Le 0 de tête n'est pas un préfixe interurbain : ne jamais le retirer."""

    def test_ivorian_number_keeps_its_leading_zero(self):
        assert normalize_msisdn("0701234567", "CI") == "+2250701234567"

    def test_beninese_number_keeps_its_leading_zero(self):
        assert normalize_msisdn("0196123456", "BJ") == "+2290196123456"

    def test_stripping_the_zero_makes_it_too_short(self):
        with pytest.raises(InvalidMsisdn):
            normalize_msisdn("701234567", "CI")


class TestCountryMismatch:
    def test_declared_country_must_match_the_dialing_code(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("+22670123456", "CI")
        assert "does not start with the dialing code" in str(excinfo.value)


class TestRejectedInput:
    @pytest.mark.parametrize("raw", ["", "   ", "abc", "+226ABCDEFGH", "+226"])
    def test_garbage_is_refused(self, raw):
        with pytest.raises(InvalidMsisdn):
            normalize_msisdn(raw)

    def test_error_message_is_actionable(self):
        with pytest.raises(InvalidMsisdn) as excinfo:
            normalize_msisdn("")
        message = str(excinfo.value)
        assert "+22670123456" in message
        assert "BF" in message


class TestEveryCountryRoundTrips:
    """Un numéro de la bonne longueur passe pour chacun des huit pays."""

    @pytest.mark.parametrize("code", SUPPORTED_COUNTRY_CODES)
    def test_national_length_is_accepted(self, code):
        country = find_country(code)
        national = "1" * country["national_number_length"]
        expected = f"{country['dialing_code']}{national}"
        assert normalize_msisdn(national, code) == expected

    @pytest.mark.parametrize("code", SUPPORTED_COUNTRY_CODES)
    def test_one_digit_short_is_refused(self, code):
        country = find_country(code)
        national = "1" * (country["national_number_length"] - 1)
        with pytest.raises(InvalidMsisdn):
            normalize_msisdn(national, code)


class TestMasking:
    """Le masquage ne doit jamais lever, ni laisser passer un numéro complet."""

    def test_matches_the_format_required_by_claude_md(self):
        assert mask_msisdn("+22676123426") == "+226 76 ** ** 26"

    def test_longer_national_number(self):
        assert mask_msisdn("+2250701234567") == "+225 07 ** ** ** 67"

    def test_odd_length_national_number(self):
        assert mask_msisdn("+221771234567") == "+221 77 ** ** * 67"

    def test_full_number_never_appears_in_the_mask(self):
        raw = "+22676123426"
        assert raw.lstrip("+") not in mask_msisdn(raw).replace(" ", "")

    @pytest.mark.parametrize(
        "value",
        ["", "   ", None, 12345, "abc", "not a number at all", object()],
    )
    def test_never_raises(self, value):
        assert isinstance(mask_msisdn(value), str)

    def test_unrecognised_input_is_fully_masked(self):
        assert mask_msisdn("abc") == "(masked)"

    def test_middle_digits_are_gone(self):
        # 70 12 34 56 : seuls 70 et 56 doivent survivre.
        masked = mask_msisdn("+22670123456")
        assert masked == "+226 70 ** ** 56"
        assert "12" not in masked
        assert "34" not in masked
