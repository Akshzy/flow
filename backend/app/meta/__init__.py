"""Meta integration package (narrow adapter boundary).

Meta-specific logic is isolated in this package; the rest of Floww consumes
normalized connection state (see ``app.meta.adapter``).
"""

from app.meta.adapter import (
    META_AUTHORIZATION_IMPLEMENTED,
    MetaAuthorizationNotConfiguredError,
    MetaConnectionService,
    normalize_identifier,
)

__all__ = [
    "META_AUTHORIZATION_IMPLEMENTED",
    "MetaAuthorizationNotConfiguredError",
    "MetaConnectionService",
    "normalize_identifier",
]
