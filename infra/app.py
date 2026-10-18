#!/usr/bin/env python3
"""CDK app entry — one stage per environment."""
from __future__ import annotations
import pathlib
import sys

import aws_cdk as cdk

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from stages import CxStage  # noqa: E402

app = cdk.App()
env_name: str = app.node.try_get_context("env") or "sandbox"
CxStage(app, f"CX-{env_name.capitalize()}", env_name=env_name)
app.synth()
