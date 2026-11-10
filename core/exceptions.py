"""Shared domain failures; HTTP mapping belongs to the API layer."""
class LocalModelError(RuntimeError):
    """Local model transport or output failure."""


class SessionNotFound(LookupError):
    """Session missing or expired."""


class SessionCapacity(RuntimeError):
    """Bounded session storage is full."""


class DocumentNotFound(LookupError):
    """No published upload matches the supplied ID."""


class InvalidDocument(ValueError):
    """Unsupported or unreadable uploaded document."""


class AgentExecutionError(RuntimeError):
    """Non-model failure during agent execution."""
