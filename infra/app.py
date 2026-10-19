"""CDK app entry point -- wires all stacks for 1145cx."""
from __future__ import annotations

import os

import aws_cdk as cdk
from stacks.data_stack import DataStack
from stacks.channel_stack import ChannelStack
from stacks.spine_stack import SpineStack

app = cdk.App()

stage = app.node.try_get_context("stage") or os.environ.get("STAGE", "sandbox")
account = os.environ.get("CDK_DEFAULT_ACCOUNT", "298713973957")
region = os.environ.get("CDK_DEFAULT_REGION", "us-east-1")
env = cdk.Environment(account=account, region=region)

prefix = f"Cx{stage.capitalize()}"

# ── Tier 0: Data (all tables, S3, EventBridge) ──────────────────────────────
data = DataStack(app, f"{prefix}Data", stage=stage, env=env)

# ── Tier 1: Channels (ingest + delivery + API GW) ───────────────────────────
channels = ChannelStack(
    app, f"{prefix}Channels",
    stage=stage,
    data_stack=data,
    env=env,
)
channels.add_dependency(data)

# ── Tier 1: Spine (Step Functions + turn/wait lambdas) ──────────────────────
spine = SpineStack(
    app, f"{prefix}Spine",
    stage=stage,
    data_stack=data,
    env=env,
)
spine.add_dependency(data)

# ── Wire spine ARN back into ingest ──────────────────────────────────────────
channels.ingest_fn.add_environment(
    "SPINE_STATE_MACHINE_ARN", spine.state_machine.state_machine_arn
)
spine.state_machine.grant_start_execution(channels.ingest_fn)

app.synth()
