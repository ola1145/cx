"""DataStack: ALL stateful resources for 1145cx.

WARNING: NEVER rename a construct ID — it replaces the resource and destroys data.
This stack owns all DynamoDB tables and S3 buckets.
Other stacks receive table/bucket handles as constructor arguments.
"""
from __future__ import annotations
from typing import Any
import aws_cdk as cdk
from aws_cdk import aws_dynamodb as ddb, aws_s3 as s3, RemovalPolicy
from constructs import Construct


class DataStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, cfg: Any, **kwargs: Any) -> None:
        super().__init__(scope, id, **kwargs)
        is_sandbox = getattr(cfg, "env", "sandbox") == "sandbox"
        removal = RemovalPolicy.DESTROY if is_sandbox else RemovalPolicy.RETAIN
        pitr = ddb.PointInTimeRecoverySpecification(point_in_time_recovery_enabled=True)

        base: dict[str, Any] = dict(billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
                                    removal_policy=removal, time_to_live_attribute="expires_at")
        pitr_base = {**base, "point_in_time_recovery_specification": pitr}

        # ── Tables (IDs are permanent — do NOT rename) ──────────────────────────
        self.sessions = ddb.Table(self, "Sessions",
            partition_key=ddb.Attribute(name="sessionId", type=ddb.AttributeType.STRING), **base)
        self.inbox = ddb.Table(self, "Inbox",
            partition_key=ddb.Attribute(name="sessionId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="tsMsgId", type=ddb.AttributeType.STRING), **base)
        self.turns = ddb.Table(self, "Turns",
            partition_key=ddb.Attribute(name="sessionId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="turnSeq", type=ddb.AttributeType.STRING), **base)
        self.identities = ddb.Table(self, "Identities",
            partition_key=ddb.Attribute(name="channelAddress", type=ddb.AttributeType.STRING), **base)
        self.idempotency = ddb.Table(self, "Idempotency",
            partition_key=ddb.Attribute(name="providerMsgId", type=ddb.AttributeType.STRING), **base)
        self.link_codes = ddb.Table(self, "LinkCodes",
            partition_key=ddb.Attribute(name="code", type=ddb.AttributeType.STRING), **base)
        self.consents = ddb.Table(self, "Consents",
            partition_key=ddb.Attribute(name="subjectId", type=ddb.AttributeType.STRING),
            sort_key=ddb.Attribute(name="typeTs", type=ddb.AttributeType.STRING), **pitr_base)
        self.tenants = ddb.Table(self, "Tenants",
            partition_key=ddb.Attribute(name="tenantId", type=ddb.AttributeType.STRING), **pitr_base)
        self.routing = ddb.Table(self, "Routing",
            partition_key=ddb.Attribute(name="e164", type=ddb.AttributeType.STRING), **pitr_base)
        self.number_orders = ddb.Table(self, "NumberOrders",
            partition_key=ddb.Attribute(name="tenantId", type=ddb.AttributeType.STRING), **base)
        self.counters = ddb.Table(self, "Counters",
            partition_key=ddb.Attribute(name="kindScopeWindow", type=ddb.AttributeType.STRING), **base)

        # ── Enrich S3 bucket ────────────────────────────────────────────────────
        self.enrich_bucket = s3.Bucket(self, "EnrichBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True, versioned=False, removal_policy=removal,
            auto_delete_objects=is_sandbox,
            lifecycle_rules=[s3.LifecycleRule(expiration=cdk.Duration.days(30))])

        # ── Outputs ─────────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "SessionsTableName", value=self.sessions.table_name)
        cdk.CfnOutput(self, "TenantsTableName", value=self.tenants.table_name)
        cdk.CfnOutput(self, "RoutingTableName", value=self.routing.table_name)
        cdk.CfnOutput(self, "EnrichBucketName", value=self.enrich_bucket.bucket_name)
