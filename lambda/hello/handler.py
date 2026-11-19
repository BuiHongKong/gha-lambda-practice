"""Minimal Lambda handler for GitHub Actions practice."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def handler(event: dict[str, Any] | None, context: Any) -> dict[str, Any]:
    """Return a small JSON payload so deploy/invoke checks are easy to verify."""
    event = event or {}
    return {
        "statusCode": 200,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(
            {
                "ok": True,
                "service": "gha-lambda-practice",
                "message": "hello from lambda",
                "region": os.environ.get("AWS_REGION", "unknown"),
                "function": getattr(context, "function_name", "local"),
                "received": event,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        ),
    }
