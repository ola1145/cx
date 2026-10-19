"""ChannelStack -- WS1 API Gateway + Lambda functions."""
from __future__ import annotations

import aws_cdk as cdk
import aws_cdk.aws_apigateway as apigw
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_iam as iam
import aws_cdk.aws_logs as logs
from constructs import Construct


class ChannelStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str = "sandbox",
        data_stack: object = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ds = data_stack  # shorthand

        common_env = {
            "STAGE": stage,
            "SESSIONS_TABLE": f"cx-{stage}-sessions",
            "INBOX_TABLE": f"cx-{stage}-inbox",
            "IDEMPOTENCY_TABLE": f"cx-{stage}-idempotency",
            "LINK_CODES_TABLE": f"cx-{stage}-link-codes",
            "ROUTING_TABLE": f"cx-{stage}-routing",
            "OPS_BUS": f"1145cx-{stage}-ops",
            "ENRICH_BUCKET": f"1145cx-{stage}-enrich",
        }

        layer = lambda_.LayerVersion.from_layer_version_arn(
            self, "CxLibLayer",
            layer_version_arn=self.node.try_get_context("cx_lib_layer_arn") or "arn:aws:lambda:us-east-1:000000000000:layer:cx-lib:1",
        )

        # ── Ingest Lambda ──────────────────────────────────────────────────────
        self.ingest_fn = lambda_.Function(
            self, "IngestFn",
            function_name=f"cx-{stage}-ws1-ingest",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="cx_ws1_channels.ingest.handler",
            code=lambda_.Code.from_asset("ws1-channels/src"),
            environment=common_env,
            timeout=cdk.Duration.seconds(29),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # ── Delivery Lambda ────────────────────────────────────────────────────
        self.delivery_fn = lambda_.Function(
            self, "DeliveryFn",
            function_name=f"cx-{stage}-ws1-delivery",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="cx_ws1_channels.delivery.handler",
            code=lambda_.Code.from_asset("ws1-channels/src"),
            environment={
                **common_env,
                "TELNYX_API_KEY_SECRET": f"cx/{stage}/telnyx_api_key",
                "TELEGRAM_TOKEN_SECRET": f"cx/{stage}/telegram_token",
            },
            timeout=cdk.Duration.seconds(30),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # ── IAM grants ────────────────────────────────────────────────────────
        if ds:
            ds.sessions.grant_read_write_data(self.ingest_fn)
            ds.inbox.grant_read_write_data(self.ingest_fn)
            ds.idempotency.grant_read_write_data(self.ingest_fn)
            ds.link_codes.grant_read_write_data(self.ingest_fn)
            ds.routing.grant_read_data(self.ingest_fn)
            ds.ops_bus.grant_put_events_to(self.ingest_fn)
            ds.enrich_bucket.grant_read_write(self.ingest_fn)

        # Secrets Manager read
        self.ingest_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:*:*:secret:cx/{stage}/*"],
        ))
        self.delivery_fn.add_to_role_policy(iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue"],
            resources=[f"arn:aws:secretsmanager:*:*:secret:cx/{stage}/*"],
        ))

        # ── API Gateway ────────────────────────────────────────────────────────
        self.api = apigw.RestApi(
            self, "ChannelApi",
            rest_api_name=f"cx-{stage}-channels",
            deploy_options=apigw.StageOptions(
                stage_name=stage,
                throttling_rate_limit=100,
                throttling_burst_limit=200,
            ),
        )

        webhook = self.api.root.add_resource("webhook")

        # /webhook/telnyx  /webhook/telegram  /webhook/voice
        for path in ("telnyx", "telegram", "voice"):
            webhook.add_resource(path).add_method(
                "POST",
                apigw.LambdaIntegration(self.ingest_fn),
            )

        cdk.CfnOutput(self, "ChannelApiUrl", value=self.api.url)
        cdk.CfnOutput(self, "IngestFnName", value=self.ingest_fn.function_name)
        cdk.CfnOutput(self, "DeliveryFnName", value=self.delivery_fn.function_name)
