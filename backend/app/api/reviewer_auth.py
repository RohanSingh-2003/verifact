"""Reviewer authentication and role enforcement for blinded human annotation.

This module implements a lightweight, token-based authentication system for
the human annotation workflow. Each reviewer role (reviewer1, reviewer2,
adjudicator) is assigned a unique secret token configured in environment
variables. The token is validated via the ``Authorization: Bearer <token>``
HTTP header.

Security properties:
- Reviewer identity is derived from a server-side secret, not from a
  client-supplied ``reviewer_id`` field.
- Each token maps to exactly one role (reviewer1, reviewer2, or adjudicator).
- Tokens are never logged, returned in responses, or stored in the database.

Configuration (in ``backend/.env``):
    REVIEWER1_TOKEN=<secret>
    REVIEWER2_TOKEN=<secret>
    ADJUDICATOR_TOKEN=<secret>
"""

from __future__ import annotations

import hmac
import logging
from enum import Enum
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings

logger = logging.getLogger("verifact.api.reviewer_auth")


class ReviewerRole(str, Enum):
    """Authenticated reviewer roles for the annotation workflow."""

    REVIEWER1 = "reviewer1"
    REVIEWER2 = "reviewer2"
    ADJUDICATOR = "adjudicator"


def _get_reviewer_tokens() -> dict[str, ReviewerRole]:
    """Build a mapping from configured tokens to reviewer roles.

    Only tokens that are non-empty and not placeholder values are included.
    """
    settings = get_settings()
    token_map: dict[str, ReviewerRole] = {}

    r1 = getattr(settings, "reviewer1_token", "").strip()
    r2 = getattr(settings, "reviewer2_token", "").strip()
    adj = getattr(settings, "adjudicator_token", "").strip()

    if r1 and not r1.startswith("replace-with-"):
        token_map[r1] = ReviewerRole.REVIEWER1
    if r2 and not r2.startswith("replace-with-"):
        token_map[r2] = ReviewerRole.REVIEWER2
    if adj and not adj.startswith("replace-with-"):
        token_map[adj] = ReviewerRole.ADJUDICATOR

    return token_map


def _constant_time_lookup(token: str, token_map: dict[str, ReviewerRole]) -> ReviewerRole | None:
    """Look up a token in the map using constant-time comparison to prevent timing attacks."""
    for stored_token, role in token_map.items():
        if hmac.compare_digest(token.encode("utf-8"), stored_token.encode("utf-8")):
            return role
    return None


def authenticate_reviewer(
    authorization: Annotated[str | None, Header()] = None,
) -> ReviewerRole:
    """FastAPI dependency that authenticates a reviewer via Bearer token.

    Returns the authenticated ``ReviewerRole``.

    Raises:
        HTTPException(401): If no token is provided or the token is invalid.
        HTTPException(503): If reviewer tokens are not configured.
    """
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_map = _get_reviewer_tokens()
    if not token_map:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Reviewer tokens are not configured. Set REVIEWER1_TOKEN, REVIEWER2_TOKEN, and ADJUDICATOR_TOKEN in backend/.env.",
        )

    role = _constant_time_lookup(token, token_map)
    if role is None:
        logger.warning("Failed reviewer authentication attempt (invalid token).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid reviewer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return role


def require_reviewer(
    role: ReviewerRole = Depends(authenticate_reviewer),
) -> ReviewerRole:
    """Dependency that requires the caller to be reviewer1 or reviewer2 (not adjudicator)."""
    if role not in (ReviewerRole.REVIEWER1, ReviewerRole.REVIEWER2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only reviewer1 or reviewer2 can access this endpoint.",
        )
    return role


def require_adjudicator(
    role: ReviewerRole = Depends(authenticate_reviewer),
) -> ReviewerRole:
    """Dependency that requires the caller to be the adjudicator."""
    if role != ReviewerRole.ADJUDICATOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the adjudicator can access this endpoint.",
        )
    return role


def get_optional_reviewer_role(
    authorization: Annotated[str | None, Header()] = None,
) -> ReviewerRole | None:
    """Extract reviewer role from Bearer token if present, returning None if absent.

    Raises:
        HTTPException(401): If authorization header format is malformed or token is invalid.
    """
    if authorization is None:
        return None

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Empty bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_map = _get_reviewer_tokens()
    if not token_map:
        return None

    role = _constant_time_lookup(token, token_map)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return role


def require_non_reviewer(
    role: ReviewerRole | None = Depends(get_optional_reviewer_role),
) -> ReviewerRole | None:
    """Dependency for routes that allow public access but strictly forbid Reviewer 1 and Reviewer 2.

    Returns the role (None for anonymous, or ReviewerRole.ADJUDICATOR for adjudicator).
    Raises:
        HTTPException(403): If the caller is authenticated as reviewer1 or reviewer2.
    """
    if role in (ReviewerRole.REVIEWER1, ReviewerRole.REVIEWER2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer identities are restricted from accessing unblinded evaluation results and detector scores.",
        )
    return role


def block_reviewer_access(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Block reviewer identities from accessing unrestricted annotation data.

    When reviewer tokens are configured:
    - Reviewer1 and Reviewer2 tokens are rejected with 403 Forbidden.
    - Missing or invalid tokens are rejected with 401 Unauthorized.
    - Adjudicator token is permitted.
    When tokens are not configured in production, fails closed with 503.
    In unconfigured local dev/test environments, permits access for backwards compatibility.
    """
    settings = get_settings()
    token_map = _get_reviewer_tokens()
    if not token_map:
        if settings.environment == "production":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Reviewer authorization tokens are required in production.",
            )
        return

    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required to access unrestricted annotation data.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format. Use: Authorization: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    role = _constant_time_lookup(token, token_map)
    if role in (ReviewerRole.REVIEWER1, ReviewerRole.REVIEWER2):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Reviewer identities cannot access unrestricted annotation data.",
        )
    if role != ReviewerRole.ADJUDICATOR:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token for unrestricted annotation data.",
            headers={"WWW-Authenticate": "Bearer"},
        )



