"""Connectors package — compliance-first source abstraction.

Importing the package registers every built-in connector implementation via
the ``@register`` decorator (so the API, worker, and seed all share one
registry)."""

from app.connectors.base import (  # noqa: F401
    ComplianceError, ConnectorBase, RawRecord, get_connector_cls, register,
)
from app.connectors import dev_feed  # noqa: E402,F401  (side effect: registration)
