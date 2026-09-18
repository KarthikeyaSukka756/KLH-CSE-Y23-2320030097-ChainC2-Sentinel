# ChainC2 Sentinel — Synthetic C2 Payload Model & Validator
"""Safe representation and validation of synthetic C2 configuration data.

Safety Guarantees:
- Only predefined, harmless configuration parameters are supported.
- Only the specific safe action 'BEACON' is permitted.
- Targets must strictly point to 127.0.0.1 or localhost.
- Rejects any external IPs, domains, shell commands, or arbitrary actions.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.utils.identifiers import generate_event_id

SAFE_PERMITTED_COMMANDS = {"BEACON"}
SAFE_PERMITTED_HOSTS = {"127.0.0.1", "localhost"}


class SyntheticC2Payload(BaseModel):
    """Structured inert configuration stored on C2DataStore for Scenario B."""

    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(
        default="synthetic_c2",
        description="Scenario identifier",
    )
    command: str = Field(
        default="BEACON",
        description="Harmless synthetic action. Only 'BEACON' is permitted.",
    )
    target: str = Field(
        ...,
        description="Destination URL for the beacon. Must be 127.0.0.1 or localhost.",
    )
    request_id: str = Field(
        default_factory=generate_event_id,
        description="Synthetic request identifier",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional safe metadata for the synthetic test",
    )

    @field_validator("command")
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Enforce that only safe predefined commands can be represented."""
        normalized = v.strip().upper()
        if normalized not in SAFE_PERMITTED_COMMANDS:
            raise ValueError(
                f"Security rejection: Command '{v}' is not permitted. "
                f"Only predefined safe actions {SAFE_PERMITTED_COMMANDS} are allowed. "
                f"Arbitrary command execution is strictly forbidden."
            )
        return normalized

    @field_validator("target")
    @classmethod
    def validate_target(cls, v: str) -> str:
        """Enforce that targets strictly resolve to local loopback addresses."""
        parsed = urlparse(v)
        if parsed.scheme not in ("http",):
            raise ValueError(
                f"Security rejection: Target scheme '{parsed.scheme}' is invalid. "
                f"Only local 'http' protocol is allowed."
            )
        hostname = (parsed.hostname or "").lower()
        if hostname not in SAFE_PERMITTED_HOSTS:
            raise ValueError(
                f"Security rejection: Target host '{hostname}' is not permitted. "
                f"Targets must strictly point to {SAFE_PERMITTED_HOSTS}. "
                f"External or public network communication is forbidden."
            )
        return v

    def to_blockchain_string(self) -> str:
        """Serialize payload into a JSON string suitable for C2DataStore."""
        return json.dumps(self.model_dump())

    @classmethod
    def from_raw(cls, raw: str | dict[str, Any]) -> SyntheticC2Payload:
        """Parse and validate synthetic configuration from raw string or dict."""
        if isinstance(raw, dict):
            return cls(**raw)

        cleaned = raw.strip()
        # Strip optional human-readable prefix if present
        if cleaned.startswith("SYNTHETIC_C2:"):
            cleaned = cleaned[len("SYNTHETIC_C2:"):].strip()

        data = json.loads(cleaned)
        return cls(**data)
