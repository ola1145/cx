"""TenantStack: TS-1 through TS-8 (provisioning, tenant config, dashboard seed)."""
from __future__ import annotations
from typing import Any
import aws_cdk as cdk
from constructs import Construct


class TenantStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, cfg: Any, data: Any, **kwargs: Any) -> None:
        super().__init__(scope, id, **kwargs)
        # TODO: implement TS-1 through TS-8 (provisioning, tenant config, dashboard seed)
        cdk.CfnOutput(self, "Status", value="stub")
