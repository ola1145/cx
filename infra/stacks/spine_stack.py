"""SpineStack -- Step Functions state machine + WS2 Lambdas."""
from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
import aws_cdk.aws_iam as iam
import aws_cdk.aws_lambda as lambda_
import aws_cdk.aws_logs as logs
import aws_cdk.aws_stepfunctions as sfn
import aws_cdk.aws_stepfunctions_tasks as tasks
from constructs import Construct


class SpineStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        stage: str = "sandbox",
        data_stack: object = None,
        **kwargs: object,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        ds = data_stack

        common_env = {
            "STAGE": stage,
            "SESSIONS_TABLE": f"cx-{stage}-sessions",
            "INBOX_TABLE": f"cx-{stage}-inbox",
            "TURNS_TABLE": f"cx-{stage}-turns",
            "TENANTS_TABLE": f"cx-{stage}-tenants",
            "IDENTITIES_TABLE": f"cx-{stage}-identities",
            "CONSENTS_TABLE": f"cx-{stage}-consents",
            "OPS_BUS": f"1145cx-{stage}-ops",
        }

        # ── Turn Lambda ──────────────────────────────────────────────────────
        self.turn_fn = lambda_.Function(
            self, "TurnFn",
            function_name=f"cx-{stage}-ws2-turn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="cx_ws2_spine.turn_lambda.handler",
            code=lambda_.Code.from_asset("ws2-spine/src"),
            environment={
                **common_env,
                "BEDROCK_MODEL_ID": "amazon.nova-lite-v1:0",
                "AGENT_GRAPH_MODULE": "cx_ws2_spine.agent.graph",
            },
            timeout=cdk.Duration.seconds(60),
            memory_size=1024,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # ── Wait Lambda ──────────────────────────────────────────────────────
        self.wait_fn = lambda_.Function(
            self, "WaitFn",
            function_name=f"cx-{stage}-ws2-wait",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="cx_ws2_spine.wait_lambda.handler",
            code=lambda_.Code.from_asset("ws2-spine/src"),
            environment=common_env,
            timeout=cdk.Duration.seconds(29),
            memory_size=256,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # ── IAM grants ─────────────────────────────────────────────────────────
        if ds:
            for fn in (self.turn_fn, self.wait_fn):
                ds.sessions.grant_read_write_data(fn)
                ds.inbox.grant_read_write_data(fn)
                ds.turns.grant_read_write_data(fn)
                ds.tenants.grant_read_data(fn)
                ds.identities.grant_read_data(fn)
                ds.consents.grant_read_data(fn)
                ds.ops_bus.grant_put_events_to(fn)

        self.turn_fn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
            ],
            resources=["*"],
        ))

        # ── State Machine from ASL ────────────────────────────────────────────
        asl_path = Path(__file__).parent.parent.parent / "ws2-spine" / "statemachine" / "onboarding_spine.asl.json"
        if asl_path.exists():
            definition_body = sfn.DefinitionBody.from_string(asl_path.read_text())
        else:
            # Minimal inline definition (real ASL lives in ws2-spine/statemachine/)
            definition_body = sfn.DefinitionBody.from_string(json.dumps({
                "Comment": "1145cx onboarding spine",
                "StartAt": "Turn",
                "States": {
                    "Turn": {
                        "Type": "Task",
                        "Resource": "arn:aws:states:::lambda:invoke",
                        "Parameters": {
                            "FunctionName.$": f"$$.Execution.Input.turn_fn_arn",
                            "Payload.$": "$",
                        },
                        "End": True,
                    }
                },
            }))

        spine_role = iam.Role(
            self, "SpineRole",
            assumed_by=iam.ServicePrincipal("states.amazonaws.com"),
        )
        self.turn_fn.grant_invoke(spine_role)
        self.wait_fn.grant_invoke(spine_role)

        self.state_machine = sfn.StateMachine(
            self, "OnboardingSpine",
            state_machine_name=f"cx-{stage}-onboarding-spine",
            state_machine_type=sfn.StateMachineType.STANDARD,
            definition_body=definition_body,
            role=spine_role,
            timeout=cdk.Duration.hours(72),
            logs=sfn.LogOptions(
                destination=logs.LogGroup(
                    self, "SpineLogs",
                    log_group_name=f"/cx/{stage}/spine",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=cdk.RemovalPolicy.DESTROY,
                ),
                level=sfn.LogLevel.ALL,
                include_execution_data=True,
            ),
        )

        # Let wait Lambda invoke its own task-token callbacks
        self.wait_fn.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)
        self.state_machine.grant_task_response(self.wait_fn)

        cdk.CfnOutput(self, "StateMachineArn", value=self.state_machine.state_machine_arn)
        cdk.CfnOutput(self, "TurnFnName", value=self.turn_fn.function_name)
