"""LegalStack: LG-1 through LG-8 (consent ledger, greeting rule)."""
from __future__ import annotations
from typing import Any
import aws_cdk as cdk
from constructs import Construct


class LegalStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, cfg: Any, data: Any, **kwargs: Any) -> None:
        super().__init__(scope, id, **kwargs)
        # TODO: implement LG-1 through LG-8 (consent ledger, greeting rule)
        cdk.CfnOutput(self, "Status", value="stub")
