"""Stage layout — one Stage per environment."""
from __future__ import annotations
import pathlib
import sys
from typing import Any

import aws_cdk as cdk
import yaml
from constructs import Construct
from pydantic import BaseModel


class EnvConfig(BaseModel):
    env: str
    account: str
    region: str
    agent_model_id: str = "us.amazon.nova-lite-v1:0"
    agent_live_version: str = "PLACEHOLDER"
    agent_canary_version: str = "PLACEHOLDER"
    prompt_canary_share: float = 0.1
    speech_provider: str = "telnyx"
    embed_model_id: str = "amazon.titan-embed-text-v2:0"
    number_order_enabled: bool = False
    number_daily_cap: int = 5
    max_monthly_usd: float = 5.0
    max_upfront_usd: float = 2.0
    outbound_calls_enabled: bool = False
    twilio_enabled: bool = False
    twilio_bundle_approved: bool = False
    enrich_paid_sources: bool = False
    enrich_x_enabled: bool = False
    booking_scout_enabled: bool = False
    research_daily_cap: int = 10
    rate_limit_per_min: int = 20
    max_turns_per_session: int = 300
    trial_days: int = 14
    grace_days: int = 7
    release_after_days: int = 14
    langs: str = "en,es"
    api_domain: str = "api.1145.ai"
    app_domain: str = "app.1145.ai"
    terms_version: str = "v1"
    privacy_version: str = "v1"
    ai_notice_version: str = "v1"


def load_config(env_name: str) -> EnvConfig:
    config_path = pathlib.Path(__file__).parent / "config" / f"{env_name}.yaml"
    with open(config_path) as f:
        data = yaml.safe_load(f)
    return EnvConfig(**data)


class CxStage(cdk.Stage):
    def __init__(self, scope: Construct, id: str, *, env_name: str, **kwargs: Any) -> None:
        cfg = load_config(env_name)
        aws_env = cdk.Environment(account=cfg.account, region=cfg.region)
        super().__init__(scope, id, env=aws_env, **kwargs)
        self.cfg = cfg
        self._build_stacks()

    def _build_stacks(self) -> None:
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from ws9_data.infra.stack import DataStack  # noqa: PLC0415
        data = DataStack(
            self, "CX-Data",
            cfg=self.cfg,
            termination_protection=(self.cfg.env != "sandbox"),
        )
        # Workstream stacks: uncomment as each is implemented
        # from ws1_channels.infra.stack import ChannelStack
        # ChannelStack(self, "CX-Channels", cfg=self.cfg, data=data)
        # from ws2_spine.infra.stack import SpineStack
        # SpineStack(self, "CX-Spine", cfg=self.cfg, data=data)
        # (other workstreams follow the same pattern)
