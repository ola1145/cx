"""DataStack -- 11 DynamoDB tables + S3 buckets + EventBridge bus."""
from __future__ import annotations

import aws_cdk as cdk
import aws_cdk.aws_dynamodb as dynamodb
import aws_cdk.aws_events as events
import aws_cdk.aws_s3 as s3
from constructs import Construct


class DataStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str = "sandbox",
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        removal = (
            cdk.RemovalPolicy.DESTROY
            if stage == "sandbox"
            else cdk.RemovalPolicy.RETAIN
        )

        # ── Sessions ──────────────────────────────────────────────────────────
        self.sessions = dynamodb.Table(
            self, "Sessions",
            table_name=f"cx-{stage}-sessions",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            time_to_live_attribute="ttl",
        )
        self.sessions.add_global_secondary_index(
            index_name="identity-index",
            partition_key=dynamodb.Attribute(
                name="identity_key", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Inbox ──────────────────────────────────────────────────────────────
        self.inbox = dynamodb.Table(
            self, "Inbox",
            table_name=f"cx-{stage}-inbox",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="item_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            time_to_live_attribute="ttl",
        )

        # ── Turns ──────────────────────────────────────────────────────────────
        self.turns = dynamodb.Table(
            self, "Turns",
            table_name=f"cx-{stage}-turns",
            partition_key=dynamodb.Attribute(
                name="session_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="turn_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
        )

        # ── Identities ──────────────────────────────────────────────────────────
        self.identities = dynamodb.Table(
            self, "Identities",
            table_name=f"cx-{stage}-identities",
            partition_key=dynamodb.Attribute(
                name="identity_key", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
        )
        self.identities.add_global_secondary_index(
            index_name="tenant-index",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Idempotency ──────────────────────────────────────────────────────────
        self.idempotency = dynamodb.Table(
            self, "Idempotency",
            table_name=f"cx-{stage}-idempotency",
            partition_key=dynamodb.Attribute(
                name="idem_key", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            time_to_live_attribute="ttl",
        )

        # ── LinkCodes ──────────────────────────────────────────────────────────
        self.link_codes = dynamodb.Table(
            self, "LinkCodes",
            table_name=f"cx-{stage}-link-codes",
            partition_key=dynamodb.Attribute(
                name="code", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            time_to_live_attribute="ttl",
        )

        # ── Consents ──────────────────────────────────────────────────────────
        self.consents = dynamodb.Table(
            self, "Consents",
            table_name=f"cx-{stage}-consents",
            partition_key=dynamodb.Attribute(
                name="subject", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="consent_type", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            point_in_time_recovery=True,
        )

        # ── Tenants ──────────────────────────────────────────────────────────
        self.tenants = dynamodb.Table(
            self, "Tenants",
            table_name=f"cx-{stage}-tenants",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            point_in_time_recovery=True,
        )
        self.tenants.add_global_secondary_index(
            index_name="billing-status-index",
            partition_key=dynamodb.Attribute(
                name="billing_status", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="created_at", type=dynamodb.AttributeType.NUMBER
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Routing ──────────────────────────────────────────────────────────
        self.routing = dynamodb.Table(
            self, "Routing",
            table_name=f"cx-{stage}-routing",
            partition_key=dynamodb.Attribute(
                name="e164", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
            point_in_time_recovery=True,
        )

        # ── NumberOrders ──────────────────────────────────────────────────────
        self.number_orders = dynamodb.Table(
            self, "NumberOrders",
            table_name=f"cx-{stage}-number-orders",
            partition_key=dynamodb.Attribute(
                name="order_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
        )
        self.number_orders.add_global_secondary_index(
            index_name="tenant-index",
            partition_key=dynamodb.Attribute(
                name="tenant_id", type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # ── Counters ──────────────────────────────────────────────────────────
        self.counters = dynamodb.Table(
            self, "Counters",
            table_name=f"cx-{stage}-counters",
            partition_key=dynamodb.Attribute(
                name="counter_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=removal,
        )

        # ── S3 buckets ──────────────────────────────────────────────────────────
        self.enrich_bucket = s3.Bucket(
            self, "EnrichBucket",
            bucket_name=f"1145cx-{stage}-enrich",
            removal_policy=removal,
            auto_delete_objects=(stage == "sandbox"),
            lifecycle_rules=[
                s3.LifecycleRule(expiration=cdk.Duration.days(30))
            ],
        )

        self.assets_bucket = s3.Bucket(
            self, "AssetsBucket",
            bucket_name=f"1145cx-{stage}-assets",
            removal_policy=removal,
            auto_delete_objects=(stage == "sandbox"),
        )

        # ── EventBridge bus ──────────────────────────────────────────────────
        self.ops_bus = events.EventBus(
            self, "OpsBus",
            event_bus_name=f"1145cx-{stage}-ops",
        )

        # ── Outputs ──────────────────────────────────────────────────────────
        cdk.CfnOutput(self, "SessionsTableName", value=self.sessions.table_name)
        cdk.CfnOutput(self, "TenantsTableName", value=self.tenants.table_name)
        cdk.CfnOutput(self, "RoutingTableName", value=self.routing.table_name)
        cdk.CfnOutput(self, "EnrichBucketName", value=self.enrich_bucket.bucket_name)
        cdk.CfnOutput(self, "OpsBusName", value=self.ops_bus.event_bus_name)
