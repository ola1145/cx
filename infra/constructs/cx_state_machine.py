"""CxStateMachine: Step Functions state machine from an ASL JSON file."""
from __future__ import annotations
import pathlib
from typing import Any
import aws_cdk as cdk
from aws_cdk import aws_stepfunctions as sfn, aws_logs as logs
from constructs import Construct


class CxStateMachine(Construct):
    def __init__(self, scope: Construct, id: str, *,
                 definition_file: str | pathlib.Path,
                 substitutions: dict[str, str] | None = None,
                 timeout: cdk.Duration | None = None) -> None:
        super().__init__(scope, id)
        log_group = logs.LogGroup(self, "LogGroup",
            retention=logs.RetentionDays.THREE_MONTHS,
            removal_policy=cdk.RemovalPolicy.DESTROY)
        self.state_machine = sfn.StateMachine(self, "SM",
            definition_body=sfn.DefinitionBody.from_file(
                str(definition_file), input_type=sfn.InputType.TEXT,
                substitutions=substitutions or {}),
            state_machine_type=sfn.StateMachineType.STANDARD,
            tracing_enabled=True,
            logs=sfn.LogOptions(destination=log_group, level=sfn.LogLevel.ALL,
                                include_execution_data=True),
            timeout=timeout)
