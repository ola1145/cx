"""WS10 Ops -- sweeper Lambda.

Runs every 15 min via EventBridge:
- Sweeps stuck Step Functions executions (> 24h in non-terminal state)
- Drains dead-letter queues and emits ops events
- Emits CloudWatch metrics for tenant/session counts
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3

from cx_lib.logging import get_logger

log = get_logger("ws10.sweeper")

STATE_MACHINE_ARN = os.environ.get("SPINE_STATE_MACHINE_ARN", "")
DLQ_URL = os.environ.get("DLQ_URL", "")
OPS_BUS = os.environ.get("OPS_BUS", "1145cx-ops")
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "cx-sessions")
TENANTS_TABLE = os.environ.get("TENANTS_TABLE", "cx-tenants")
METRIC_NS = os.environ.get("METRIC_NS", "1145cx")

_sfn = boto3.client("stepfunctions")
_sqs = boto3.client("sqs")
_events = boto3.client("events")
_cw = boto3.client("cloudwatch")
_ddb = boto3.resource("dynamodb")


def handler(event: dict, context: Any) -> dict:
    now = int(time.time())
    results: dict[str, int] = {
        "stuck_executions_stopped": 0,
        "dlq_messages_processed": 0,
    }

    # 1. Find and abort stuck executions
    if STATE_MACHINE_ARN:
        results["stuck_executions_stopped"] = _sweep_executions(now)

    # 2. Drain DLQ
    if DLQ_URL:
        results["dlq_messages_processed"] = _drain_dlq()

    # 3. Emit CloudWatch metrics
    _emit_metrics()

    log.info("sweeper.complete", **results)
    return results


def _sweep_executions(now: int) -> int:
    """Abort Step Functions executions stuck longer than 24 h."""
    cutoff_ms = (now - 86400) * 1000
    stopped = 0
    try:
        paginator = _sfn.get_paginator("list_executions")
        for page in paginator.paginate(
            stateMachineArn=STATE_MACHINE_ARN,
            statusFilter="RUNNING",
        ):
            for ex in page.get("executions", []):
                started = ex["startDate"].timestamp() * 1000
                if started < cutoff_ms:
                    try:
                        _sfn.stop_execution(
                            executionArn=ex["executionArn"],
                            cause="Sweeper: execution exceeded 24h TTL",
                        )
                        _emit_ops("ExecutionSwept", {"executionArn": ex["executionArn"]})
                        stopped += 1
                        log.warning(
                            "sweeper.execution_stopped",
                            arn=ex["executionArn"],
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.error("sweeper.stop_failed", arn=ex["executionArn"], error=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.error("sweeper.list_failed", error=str(exc))
    return stopped


def _drain_dlq() -> int:
    """Read up to 100 DLQ messages, emit as ops events, then delete."""
    processed = 0
    try:
        for _ in range(10):  # up to 10 polls × 10 = 100 messages
            resp = _sqs.receive_message(
                QueueUrl=DLQ_URL,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=1,
            )
            msgs = resp.get("Messages", [])
            if not msgs:
                break
            entries = []
            for msg in msgs:
                try:
                    body = json.loads(msg["Body"])
                except Exception:  # noqa: BLE001
                    body = {"raw": msg["Body"]}
                _emit_ops("DLQMessage", {"body": body})
                entries.append({
                    "Id": msg["MessageId"],
                    "ReceiptHandle": msg["ReceiptHandle"],
                })
                processed += 1
            _sqs.delete_message_batch(QueueUrl=DLQ_URL, Entries=entries)
    except Exception as exc:  # noqa: BLE001
        log.error("dlq.drain_failed", error=str(exc))
    return processed


def _emit_metrics() -> None:
    """Push high-level counts to CloudWatch."""
    try:
        # Count live tenants
        tenants_table = _ddb.Table(TENANTS_TABLE)
        live_count = tenants_table.scan(
            Select="COUNT",
            FilterExpression=boto3.dynamodb.conditions.Attr("status").eq("live"),
        ).get("Count", 0)

        sessions_table = _ddb.Table(SESSIONS_TABLE)
        active_count = sessions_table.scan(
            Select="COUNT",
            FilterExpression=boto3.dynamodb.conditions.Attr("status").is_in(
                ["collecting", "reviewing", "billing", "numbering"]
            ),
        ).get("Count", 0)

        _cw.put_metric_data(
            Namespace=METRIC_NS,
            MetricData=[
                {
                    "MetricName": "LiveTenants",
                    "Value": live_count,
                    "Unit": "Count",
                },
                {
                    "MetricName": "ActiveOnboardingSessions",
                    "Value": active_count,
                    "Unit": "Count",
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("metrics.failed", error=str(exc))


def _emit_ops(detail_type: str, detail: dict) -> None:
    try:
        _events.put_events(Entries=[{
            "Source": "1145cx.ws10",
            "DetailType": detail_type,
            "Detail": json.dumps(detail),
            "EventBusName": OPS_BUS,
        }])
    except Exception as exc:  # noqa: BLE001
        log.warning("ops_event.failed", detail_type=detail_type, error=str(exc))
