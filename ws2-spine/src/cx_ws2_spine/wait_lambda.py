"""WS2 Wait Lambda — SP-9: task-token wait, inbox-driven early resume, 30-min park.

Called by the Step Functions spine after the Turn step sends a reply.
Stores the task token, then immediately checks the inbox:
  - if messages are waiting → resume right away
  - otherwise → return (Step Functions waits for send_task_success from ingest)
"""
from __future__ import annotations
import json, os, time
from typing import Any


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    import sys; sys.path.insert(0, "/var/task")
    from cx_lib.ddb import to_ddb, from_ddb, get_table
    import boto3
    from boto3.dynamodb.conditions import Key, Attr

    session_id: str = event["sessionId"]
    task_token: str = event.get("taskToken", "")
    reply: str = event.get("reply", "")
    channel: str = event.get("channel", "")
    channel_address: str = event.get("channelAddress", "")

    sessions_tbl = get_table("SESSIONS_TABLE_NAME")
    inbox_tbl = get_table("INBOX_TABLE_NAME")

    # Send the reply first
    if reply and channel:
        from cx_ws1_channels.delivery import deliver
        address = channel_address.split(":", 1)[-1] if ":" in channel_address else channel_address
        deliver(session_id, reply, channel, address)

    # Store task token in session so ingest can resume us
    sessions_tbl.update_item(
        Key={"sessionId": session_id},
        UpdateExpression="SET taskToken = :t",
        ExpressionAttributeValues={":t": task_token},
    )

    # Check for already-queued inbox items (B3 fix)
    resp = inbox_tbl.query(
        KeyConditionExpression=Key("sessionId").eq(session_id),
        FilterExpression=Attr("state").eq("queued"),
        Limit=1,
    )
    if resp.get("Items"):
        # Resume immediately — clear the token first
        sessions_tbl.update_item(
            Key={"sessionId": session_id},
            UpdateExpression="REMOVE taskToken",
        )
        sfn = boto3.client("stepfunctions", region_name=os.environ.get("AWS_REGION", "us-east-1"))
        try:
            sfn.send_task_success(taskToken=task_token, output=json.dumps({"resumed": True, "reason": "inbox_nonempty"}))
        except Exception:
            pass

    return {"sessionId": session_id, "waiting": True}
