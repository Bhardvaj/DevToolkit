"""Unit tests for DevToolkit Spotlight inline calculation and utility mode."""

from __future__ import annotations

import re
import pytest
from clients.spotlight.modes.calc import evaluate_calc_query


def test_calc_basic_arithmetic():
    res = evaluate_calc_query("2 + 2")
    assert len(res) == 1
    assert res[0]["title"] == "4"
    assert res[0]["badge"] == "CALC"


def test_calc_math_functions():
    res = evaluate_calc_query("sqrt(16)")
    assert len(res) == 1
    assert res[0]["title"] == "4"

    res_cos = evaluate_calc_query("cos(0)")
    assert len(res_cos) == 1
    assert res_cos[0]["title"] == "1"


def test_calc_hex_and_bin():
    res_hex = evaluate_calc_query("255 in hex")
    assert len(res_hex) == 1
    assert res_hex[0]["title"] == "0xFF"
    assert res_hex[0]["badge"] == "CONV"

    res_dec = evaluate_calc_query("0xff in dec")
    assert len(res_dec) == 1
    assert res_dec[0]["title"] == "255"

    res_bin = evaluate_calc_query("10 in bin")
    assert len(res_bin) == 1
    assert res_bin[0]["title"] == "0b1010"


def test_calc_unit_conversion():
    res = evaluate_calc_query("16 gb in mb")
    assert len(res) == 1
    assert res[0]["title"] == "16384 MB"
    assert res[0]["badge"] == "UNIT"


def test_calc_uuid_generation():
    res = evaluate_calc_query("uuid")
    assert len(res) == 1
    assert res[0]["badge"] == "UUID"
    # Verify standard UUID4 format (36 chars with hyphens)
    assert re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", res[0]["title"])


def test_calc_epoch_timestamp():
    res = evaluate_calc_query("epoch")
    assert len(res) >= 1
    assert res[0]["badge"] == "EPOCH"
    assert res[0]["title"].isdigit()


def test_calc_invalid_expression():
    res = evaluate_calc_query("invalid_syntax +++")
    assert len(res) == 1
    assert "Cannot evaluate" in res[0]["title"]
    assert res[0]["badge"] == "ERROR"
