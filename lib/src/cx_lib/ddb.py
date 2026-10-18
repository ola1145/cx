"""DynamoDB codec — fixes issue B2 (float/Decimal crashes).

Every DynamoDB read and write in this codebase goes through this module.
A lint rule enforces this: direct table.put_item() outside lib/ is banned.

Usage::

    from cx_lib.ddb import to_ddb, from_ddb, DdbEncoder, get_table

    # Write
    table.put_item(Item=to_ddb({"price": 25.50, "confidence": 0.85}))

    # Read
    raw = table.get_item(Key={"sessionId": sid})["Item"]
    data = from_ddb(raw)   # Decimals become float/int

    # JSON serialisation
    import json
    json.dumps(data, cls=DdbEncoder)
"""

from __future__ import annotations

import json
import os
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key as DdbKey  # noqa: F401 – re-exported for callers

__all__ = ["to_ddb", "from_ddb", "DdbEncoder", "get_table", "DdbKey"]


def _float_to_decimal(value: float) -> Decimal:
    """Convert a float to a Decimal without floating-point noise."""
    return Decimal(str(value))


def to_ddb(obj: Any) -> Any:  # noqa: ANN401
    """Recursively convert Python types to DynamoDB-safe types.

    float → Decimal (via str to avoid noise)
    int   → unchanged (DynamoDB accepts int)
    None  → unchanged (callers may filter separately)
    """
    if isinstance(obj, dict):
        return {k: to_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_ddb(v) for v in obj]
    if isinstance(obj, float):
        return _float_to_decimal(obj)
    return obj


def from_ddb(obj: Any) -> Any:  # noqa: ANN401
    """Recursively convert DynamoDB types back to Python types.

    Decimal with no fractional part → int
    Decimal with fractional part    → float
    """
    if isinstance(obj, dict):
        return {k: from_ddb(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [from_ddb(v) for v in obj]
    if isinstance(obj, Decimal):
        if obj == obj.to_integral_value(rounding=ROUND_HALF_UP):
            return int(obj)
        return float(obj)
    return obj


class DdbEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal and other DynamoDB return types."""

    def default(self, obj: object) -> object:
        if isinstance(obj, Decimal):
            if obj == obj.to_integral_value(rounding=ROUND_HALF_UP):
                return int(obj)
            return float(obj)
        return super().default(obj)


def get_table(table_name_env_var: str) -> Any:  # noqa: ANN401
    """Return a DynamoDB Table resource.

    In tests, set the env var to the DynamoDB Local endpoint:
        os.environ["DYNAMODB_ENDPOINT"] = "http://localhost:8000"

    Args:
        table_name_env_var: Name of the env var that holds the table name,
                            e.g. "SESSIONS_TABLE_NAME".
    """
    table_name = os.environ[table_name_env_var]
    endpoint = os.environ.get("DYNAMODB_ENDPOINT")
    kwargs: dict[str, str] = {}
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    ddb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"), **kwargs)
    return ddb.Table(table_name)


def validate_decimal(value: Any, field_name: str = "value") -> Decimal:  # noqa: ANN401
    """Parse and validate a Decimal from any numeric input.

    Raises ValueError if the value cannot be converted.
    """
    try:
        if isinstance(value, Decimal):
            return value
        if isinstance(value, float | int):
            return _float_to_decimal(float(value))
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"Cannot convert {field_name}={value!r} to Decimal") from exc
