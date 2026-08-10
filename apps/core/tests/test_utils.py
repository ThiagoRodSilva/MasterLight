"""Testes das utils transversais (generate_code, money_fmt)."""

import re
from decimal import Decimal

from django.test import SimpleTestCase

from apps.core.utils import generate_code, money_fmt


class TestGenerateCode(SimpleTestCase):
    def test_default_length_and_charset(self):
        code = generate_code()
        assert len(code) == 8
        assert re.fullmatch(r"[A-Z0-9]{8}", code)

    def test_custom_length(self):
        assert len(generate_code(12)) == 12


class TestMoneyFmt(SimpleTestCase):
    def test_decimal(self):
        assert money_fmt(Decimal("1234.56")) == "R$ 1.234,56"

    def test_int(self):
        assert money_fmt(19) == "R$ 19,00"

    def test_invalid_returns_zero(self):
        assert money_fmt(None) == "R$ 0,00"
        assert money_fmt("abc") == "R$ 0,00"
