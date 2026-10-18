"""CxFunction: arm64 Lambda with X-Ray tracing, JSON logs and 90-day log retention."""
from __future__ import annotations
import pathlib
from typing import Any
import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_, aws_logs as logs, aws_iam as iam
from constructs import Construct


class CxFunction(Construct):
    def __init__(self, scope: Construct, id: str, *, package_name: str, handler: str,
                 env_vars: dict[str, str] | None = None,
                 timeout: cdk.Duration = cdk.Duration.seconds(29),
                 memory_size: int = 256, description: str = "") -> None:
        super().__init__(scope, id)
        build_path = pathlib.Path(__file__).parent.parent.parent / "build" / package_name
        code = (lambda_.Code.from_asset(str(build_path)) if build_path.exists()
                else lambda_.Code.from_inline("def handler(e, c): pass  # placeholder"))
        log_group = logs.LogGroup(self, "LogGroup",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=cdk.RemovalPolicy.DESTROY)
        self.function = lambda_.Function(self, "Fn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            architecture=lambda_.Architecture.ARM_64,
            handler=handler, code=code, timeout=timeout,
            memory_size=memory_size, tracing=lambda_.Tracing.ACTIVE,
            environment={"LOG_LEVEL": "INFO", **(env_vars or {})},
            log_group=log_group, description=description or id)
        self.function.add_to_role_policy(iam.PolicyStatement(
            actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
            resources=["*"]))

    @property
    def fn(self) -> lambda_.Function:
        return self.function
