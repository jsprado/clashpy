"""User-facing operational errors raised by clashpy components."""


class ClashpyError(RuntimeError):
    """Base class for expected runtime failures."""


class NewsSourceError(ClashpyError):
    """Raised when a news source cannot retrieve data."""


class CacheDataError(ClashpyError):
    """Raised when cached data cannot be decoded."""


class ProviderError(ClashpyError):
    """Raised when an LLM provider call fails."""


class NoNewsDataError(ClashpyError):
    """Raised when news retrieval succeeds but returns no usable data."""
