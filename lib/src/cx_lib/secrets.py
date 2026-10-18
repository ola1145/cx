"""Secrets Manager helper.

In tests, set env vars directly (e.g. CX_TELNYX_API_KEY=test) and
set SECRETS_BACKEND=env to skip Secrets Manager calls entirely.

Usage::

    from cx_lib.secrets import get_secret
    secret = get_secret("cx/sandbox/telnyx")   # returns dict
    api_key = secret["api_key"]
"""
from __future__ import annotations
import json
import os
from functools import lru_cache
from typing import Any

import boto3

__all__ = ["get_secret"]


@lru_cache(maxsize=32)
def get_secret(secret_name: str) -> dict[str, Any]:
    """Fetch and cache a secret from Secrets Manager.

    If SECRETS_BACKEND=env (test mode), looks for an env var named
    CX_SECRET_<UPPERCASED_NAME_WITH_SLASHES_AS_UNDERSCORES>.
    """
    if os.environ.get("SECRETS_BACKEND") == "env":
        env_key = "CX_SECRET_" + secret_name.upper().replace("/", "_").replace("-", "_")
        raw = os.environ.get(env_key, "{}")
        return json.loads(raw)  # type: ignore[return-value]

    client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    resp = client.get_secret_value(SecretId=secret_name)
    return json.loads(resp["SecretString"])  # type: ignore[return-value]
