"""WS7 Number ordering — NB-1 through NB-9. All money ops behind NUMBER_ORDER_ENABLED."""
from __future__ import annotations
import os
import time
import uuid
from decimal import Decimal
from typing import Any


def search_available_numbers(area_code: str, *, max_results: int = 3) -> list[dict]:
    """NB-3: Search for available numbers. Drop no-price or over-ceiling results (S5).
    Returns empty list unless NUMBER_ORDER_ENABLED=true (sandbox safety gate).
    """
    if os.environ.get("NUMBER_ORDER_ENABLED", "false").lower() != "true":
        return []

    max_monthly = Decimal(str(os.environ.get("MAX_MONTHLY_USD", "5")))
    max_upfront = Decimal(str(os.environ.get("MAX_UPFRONT_USD", "2")))

    # Real Telnyx call — only reaches here when enabled
    import json
    import urllib.request
    from cx_lib.secrets import get_secret

    env = os.environ.get("CX_ENV", "sandbox")
    api_key = get_secret(f"cx/{env}/telnyx")["api_key"]
    url = (
        "https://api.telnyx.com/v2/available_phone_numbers"
        f"?filter[national_destination_code]={area_code}"
        "&filter[features][]=voice&filter[features][]=sms&page[size]=10"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    offers = []
    for num in data.get("data", []):
        cost = num.get("cost_information") or {}
        monthly = Decimal(str(cost.get("monthly_cost") or "0"))
        upfront = Decimal(str(cost.get("upfront_cost") or "0"))
        if not monthly:
            continue  # no price data → skip
        if monthly > max_monthly or upfront > max_upfront:
            continue  # over ceiling → skip
        offers.append({
            "e164": num.get("phone_number"),
            "area_code": area_code,
            "monthly_usd": monthly,
            "setup_usd": upfront,
            "provider": "telnyx",
        })
        if len(offers) >= max_results:
            break
    return offers


def order_number(
    tenant_id: str,
    e164: str,
    orders_tbl: Any,
    to_ddb: Any,
) -> dict:
    """NB-5: Write order record BEFORE calling the carrier. No automatic retry (S6)."""
    if os.environ.get("NUMBER_ORDER_ENABLED", "false").lower() != "true":
        raise RuntimeError("NUMBER_ORDER_ENABLED is false")

    # Write order record first — prevents a second order if the Lambda retries (NB-5)
    from botocore.exceptions import ClientError

    order = {
        "tenantId": tenant_id,
        "reference": tenant_id,
        "provider": "telnyx",
        "e164": e164,
        "state": "ordering",
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expires_at": int(time.time()) + 30 * 86400,
    }
    try:
        orders_tbl.put_item(
            Item=to_ddb(order),
            ConditionExpression="attribute_not_exists(tenantId)",  # 1 number per tenant
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise RuntimeError("Tenant already has a number order") from e
        raise

    import json
    import urllib.request
    from cx_lib.secrets import get_secret

    env = os.environ.get("CX_ENV", "sandbox")
    api_key = get_secret(f"cx/{env}/telnyx")["api_key"]
    payload = json.dumps({"phone_number": e164, "customer_reference": tenant_id}).encode()
    req = urllib.request.Request(
        "https://api.telnyx.com/v2/phone_numbers/orders",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    order_id = result.get("data", {}).get("id")
    orders_tbl.update_item(
        Key={"tenantId": tenant_id},
        UpdateExpression="SET #s = :ordered, providerOrderId = :oid",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues=to_ddb({":ordered": "ordered", ":oid": order_id}),
    )
    return {"tenant_id": tenant_id, "order_id": order_id, "e164": e164}


def assign_number(
    tenant_id: str,
    e164: str,
    routing_tbl: Any,
    to_ddb: Any,
) -> None:
    """NB-6: Write Routing record mapping e164 → tenant_id (not session_id — D5 fix)."""
    from cx_lib.secrets import get_secret

    env = os.environ.get("CX_ENV", "sandbox")
    connection_id = get_secret(f"cx/{env}/telnyx")["connection_id"]
    routing_tbl.put_item(Item=to_ddb({
        "e164": e164,
        "tenantId": tenant_id,
        "provider": "telnyx",
        "providerNumberId": e164,
        "voiceConnectionId": connection_id,
        "assignedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }))
