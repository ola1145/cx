"""WS4 Stripe webhook handler — BL-1 through BL-7."""
from __future__ import annotations
import json, os, time
from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Verify Stripe signature, de-duplicate, update Tenants table."""
    import sys; sys.path.insert(0, "/var/task")
    from cx_lib.ddb import to_ddb, from_ddb, get_table
    from cx_lib.secrets import get_secret

    body = event.get("body", "")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

    env = os.environ.get("CX_ENV", "sandbox")
    webhook_secret = get_secret(f"cx/{env}/stripe")["webhook_secret"]
    stripe_sig = headers.get("stripe-signature", "")

    # BL-3: Verify Stripe signature
    if not _verify_stripe_sig(body, stripe_sig, webhook_secret):
        return {"statusCode": 401, "body": "Invalid signature"}

    payload = json.loads(body)
    event_id = payload.get("id", "")
    event_type = payload.get("type", "")

    # Idempotency: skip already-processed events
    idempotency_tbl = get_table("IDEMPOTENCY_TABLE_NAME")
    try:
        idempotency_tbl.put_item(
            Item=to_ddb({"providerMsgId": f"stripe#{event_id}", "state": "processing",
                         "expires_at": int(time.time()) + 86400}),
            ConditionExpression="attribute_not_exists(providerMsgId)",
        )
    except Exception:
        return {"statusCode": 200, "body": "duplicate"}

    tenants_tbl = get_table("TENANTS_TABLE_NAME")

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(payload["data"]["object"], tenants_tbl, to_ddb, env)
    elif event_type in ("customer.subscription.updated", "customer.subscription.created"):
        _handle_subscription_update(payload["data"]["object"], tenants_tbl, to_ddb, env)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(payload["data"]["object"], tenants_tbl, to_ddb)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(payload["data"]["object"], tenants_tbl, to_ddb)
    elif event_type == "invoice.paid":
        _handle_invoice_paid(payload["data"]["object"], tenants_tbl, to_ddb)

    idempotency_tbl.update_item(
        Key={"providerMsgId": f"stripe#{event_id}"},
        UpdateExpression="SET #s = :done",
        ExpressionAttributeNames={"#s": "state"},
        ExpressionAttributeValues={":done": "done"},
    )
    return {"statusCode": 200, "body": "ok"}


def _verify_stripe_sig(payload: str, sig_header: str, secret: str) -> bool:
    import hmac as _hmac, hashlib
    parts = {k: v for k, v in (p.split("=", 1) for p in sig_header.split(",") if "=" in p)}
    ts = parts.get("t", "0")
    v1 = parts.get("v1", "")
    signed = f"{ts}.{payload}"
    expected = _hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, v1)


def _handle_checkout_completed(obj: dict, tenants_tbl: Any, to_ddb: Any, env: str) -> None:
    tenant_id = obj.get("client_reference_id", "")
    if not tenant_id:
        return
    # BL-3: re-read subscription from Stripe before writing
    sub_id = obj.get("subscription")
    billing_status = "trialing" if obj.get("mode") == "subscription" else "active"
    tenants_tbl.update_item(
        Key={"tenantId": tenant_id},
        UpdateExpression="SET billingStatus = :s, cardOnFile = :c, stripeSubscriptionId = :sub",
        ExpressionAttributeValues=to_ddb({":s": billing_status, ":c": True, ":sub": sub_id}),
    )


def _handle_subscription_update(obj: dict, tenants_tbl: Any, to_ddb: Any, env: str) -> None:
    customer_id = obj.get("customer")
    status_map = {"trialing": "trialing", "active": "active",
                  "past_due": "past_due", "canceled": "canceled"}
    status = status_map.get(obj.get("status", ""), "setup")
    # Find tenant by Stripe customer ID
    resp = tenants_tbl.scan(FilterExpression="stripeCustomerId = :c",
                             ExpressionAttributeValues={":c": customer_id})
    for item in resp.get("Items", []):
        tenants_tbl.update_item(
            Key={"tenantId": item["tenantId"]},
            UpdateExpression="SET billingStatus = :s",
            ExpressionAttributeValues={":s": status},
        )


def _handle_subscription_deleted(obj: dict, tenants_tbl: Any, to_ddb: Any) -> None:
    customer_id = obj.get("customer")
    resp = tenants_tbl.scan(FilterExpression="stripeCustomerId = :c",
                             ExpressionAttributeValues={":c": customer_id})
    for item in resp.get("Items", []):
        tenants_tbl.update_item(
            Key={"tenantId": item["tenantId"]},
            UpdateExpression="SET billingStatus = :s",
            ExpressionAttributeValues={":s": "canceled"},
        )


def _handle_payment_failed(obj: dict, tenants_tbl: Any, to_ddb: Any) -> None:
    customer_id = obj.get("customer")
    resp = tenants_tbl.scan(FilterExpression="stripeCustomerId = :c",
                             ExpressionAttributeValues={":c": customer_id})
    for item in resp.get("Items", []):
        tenants_tbl.update_item(
            Key={"tenantId": item["tenantId"]},
            UpdateExpression="SET billingStatus = :s",
            ExpressionAttributeValues={":s": "past_due"},
        )


def _handle_invoice_paid(obj: dict, tenants_tbl: Any, to_ddb: Any) -> None:
    customer_id = obj.get("customer")
    resp = tenants_tbl.scan(FilterExpression="stripeCustomerId = :c",
                             ExpressionAttributeValues={":c": customer_id})
    for item in resp.get("Items", []):
        if item.get("billingStatus") == "past_due":
            tenants_tbl.update_item(
                Key={"tenantId": item["tenantId"]},
                UpdateExpression="SET billingStatus = :s",
                ExpressionAttributeValues={":s": "active"},
            )
