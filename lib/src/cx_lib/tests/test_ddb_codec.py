"""Tests for DynamoDB codec (B2 fix)."""
from __future__ import annotations
import json, sys
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from cx_lib.ddb import to_ddb, from_ddb, DdbEncoder

def test_float_becomes_decimal():
    result = to_ddb({"price": 25.50})
    assert isinstance(result["price"], Decimal)
    assert result["price"] == Decimal("25.5")

def test_decimal_becomes_float():
    result = from_ddb({"price": Decimal("25.50")})
    assert isinstance(result["price"], float)
    assert result["price"] == 25.5

def test_decimal_whole_becomes_int():
    result = from_ddb({"count": Decimal("5")})
    assert isinstance(result["count"], int)
    assert result["count"] == 5

def test_nested_conversion():
    orig = {"services": [{"name": "Haircut", "price": 35.0}]}
    ddb_form = to_ddb(orig)
    assert isinstance(ddb_form["services"][0]["price"], Decimal)
    back = from_ddb(ddb_form)
    assert back["services"][0]["price"] == 35.0

def test_json_encoder_decimal():
    data = {"price": Decimal("25.50"), "count": Decimal("3")}
    result = json.loads(json.dumps(data, cls=DdbEncoder))
    assert result["price"] == 25.5
    assert result["count"] == 3
