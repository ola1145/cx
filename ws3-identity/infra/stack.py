"""IdentityStack: ID-1 through ID-8 (Cognito, phone verify, sign-in links)."""
from __future__ import annotations
from typing import Any
import aws_cdk as cdk
from constructs import Construct


class IdentityStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, cfg: Any, data: Any, **kwargs: Any) -> None:
        super().__init__(scope, id, **kwargs)
        # TODO: implement ID-1 through ID-8 (Cognito, phone verify, sign-in links)
        cdk.CfnOutput(self, "Status", value="stub")
