"""Role constants for Context Sphere v3."""

from __future__ import annotations

ROLE_PM = "pm"
ROLE_WORKER = "worker"
ROLE_REVIEWER = "reviewer"

ROLES = (ROLE_PM, ROLE_WORKER, ROLE_REVIEWER)


def validate_role(role: str) -> str:
    """Return a normalized role or raise on unsupported names."""
    normalized = role.strip().lower()
    if normalized not in ROLES:
        raise ValueError(f"unsupported role {role!r}; expected one of {ROLES}")
    return normalized
