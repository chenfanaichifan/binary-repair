"""Typed, redaction-safe errors for the LLM gateway.

The gateway must never put a credential, bearer token or raw provider body in
an exception message, log line or structured error payload.  Callers classify
failures by stable ``code`` values instead of matching provider prose.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

__all__ = [
    "LLMGatewayError",
    "ConfigurationError",
    "CredentialError",
    "ProviderError",
    "AuthenticationError",
    "RateLimitError",
    "LLMTimeoutError",
    "ResponseError",
    "IdentityMismatchError",
    "UsageError",
    "RETRYABLE_CODES",
    "AUTH_CODES",
    "safe_text",
    "error_payload",
]

# Stable codes.  Provider-specific prose stays in ``details`` and is never
# interpreted by control flow.
CONFIG_ERROR = "configuration_error"
MISSING_CREDENTIAL = "missing_credential"
INVALID_CREDENTIAL = "invalid_credential"
AUTH_FAILED = "authentication_failed"
FORBIDDEN = "forbidden"
RATE_LIMITED = "rate_limited"
PROVIDER_ERROR = "provider_error"
PROVIDER_UNAVAILABLE = "provider_unavailable"
BAD_REQUEST = "bad_request"
TIMEOUT = "timeout"
NETWORK_ERROR = "network_error"
EMPTY_CONTENT = "empty_content"
MALFORMED_RESPONSE = "malformed_response"
MODEL_IDENTITY_MISMATCH = "model_identity_mismatch"
MODEL_NOT_FOUND = "model_not_found"
USAGE_INVALID = "usage_invalid"
UNKNOWN = "unknown_error"

RETRYABLE_CODES = frozenset({RATE_LIMITED, TIMEOUT, NETWORK_ERROR,
                             PROVIDER_UNAVAILABLE})
AUTH_CODES = frozenset({MISSING_CREDENTIAL, INVALID_CREDENTIAL,
                        AUTH_FAILED, FORBIDDEN})


def safe_text(value: Any, *, limit: int = 300) -> str:
    """Return a bounded printable string; never a secret.

    Callers must still avoid passing keys here.  This helper only removes
    control characters and bounds length so provider bodies cannot flood logs.
    """
    text = "" if value is None else str(value)
    text = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
    return text[:limit]


@dataclass
class LLMGatewayError(Exception):
    """Base typed error with a stable code and safe serialization."""

    code: str = UNKNOWN
    message: str = ""
    provider: str | None = None
    status: int | None = None
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message or self.code)
        self.message = safe_text(self.message or self.code)
        if not self.retryable:
            self.retryable = self.code in RETRYABLE_CODES
        self.details = {str(k): safe_text(v) for k, v in (self.details or {}).items()}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "provider": self.provider,
            "status": self.status,
            "retryable": self.retryable,
            "details": dict(self.details),
        }

    def __str__(self) -> str:
        suffix = f" ({self.provider})" if self.provider else ""
        return f"{self.code}: {self.message}{suffix}"


def error_payload(error: BaseException) -> dict[str, Any]:
    """Convert any gateway error to a stable redacted payload."""
    if isinstance(error, LLMGatewayError):
        return error.to_dict()
    return {
        "code": UNKNOWN,
        "message": safe_text(type(error).__name__),
        "provider": None,
        "status": None,
        "retryable": False,
        "details": {},
    }


class ConfigurationError(LLMGatewayError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(code=CONFIG_ERROR, message=message, **kwargs)


class CredentialError(LLMGatewayError):
    """Missing/invalid credential; never carries the credential value."""

    def __init__(self, message: str, *, code: str = MISSING_CREDENTIAL,
                 **kwargs: Any) -> None:
        super().__init__(code=code, message=message, **kwargs)


class ProviderError(LLMGatewayError):
    def __init__(self, message: str, *, code: str = PROVIDER_ERROR,
                 retryable: bool | None = None, **kwargs: Any) -> None:
        if retryable is not None:
            kwargs["retryable"] = retryable
        super().__init__(code=code, message=message, **kwargs)


class AuthenticationError(ProviderError):
    def __init__(self, message: str = "provider authentication failed", **kwargs: Any) -> None:
        super().__init__(message, code=AUTH_FAILED, retryable=False, **kwargs)


class RateLimitError(ProviderError):
    def __init__(self, message: str = "provider rate limit", **kwargs: Any) -> None:
        super().__init__(message, code=RATE_LIMITED, retryable=True, **kwargs)


class LLMTimeoutError(ProviderError):
    def __init__(self, message: str = "provider request timed out", **kwargs: Any) -> None:
        super().__init__(message, code=TIMEOUT, retryable=True, **kwargs)


class ResponseError(LLMGatewayError):
    def __init__(self, message: str, *, code: str = MALFORMED_RESPONSE,
                 **kwargs: Any) -> None:
        super().__init__(code=code, message=message, **kwargs)


class IdentityMismatchError(LLMGatewayError):
    def __init__(self, message: str, *, requested: str | None = None,
                 observed: str | None = None, **kwargs: Any) -> None:
        details = dict(kwargs.pop("details", {}) or {})
        details["requested"] = requested or ""
        details["observed"] = observed or ""
        super().__init__(code=MODEL_IDENTITY_MISMATCH, message=message,
                         details=details, **kwargs)


class UsageError(LLMGatewayError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(code=USAGE_INVALID, message=message, **kwargs)
