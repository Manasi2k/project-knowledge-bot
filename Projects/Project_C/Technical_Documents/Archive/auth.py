"""Token verification for Project C (RS256 JWT)."""
import time
from dataclasses import dataclass

ALLOWED_ALGORITHMS = ("RS256",)
MAX_CLOCK_SKEW_SECONDS = 30


@dataclass
class Claims:
    sub: str
    tenant_id: str
    exp: int
    jti: str


class TokenError(Exception):
    """Raised when a token fails verification."""


def verify_token(claims: dict, header: dict, resource_tenant_id: str, deny_list: set) -> Claims:
    """Verify already-decoded token parts.

    Signature verification is done by the gateway; this function enforces
    the application rules: algorithm, expiry, revocation and tenant match.
    """
    if header.get("alg") not in ALLOWED_ALGORITHMS:
        raise TokenError("unsupported algorithm")
    if claims["exp"] + MAX_CLOCK_SKEW_SECONDS < time.time():
        raise TokenError("token_expired")
    if claims["jti"] in deny_list:
        raise TokenError("token_revoked")
    if claims["tenant_id"] != resource_tenant_id:
        raise TokenError("tenant_mismatch")
    return Claims(claims["sub"], claims["tenant_id"], claims["exp"], claims["jti"])
