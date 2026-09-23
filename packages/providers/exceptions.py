class ProviderError(Exception):
    """Base exception for all AI provider errors."""


class ProviderAPIError(ProviderError):
    """Raised when a provider accepts the connection but rejects a request."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class ProviderConnectionError(ProviderError):
    """Raised when the provider API is unreachable."""


class ProviderTimeoutError(ProviderError):
    """Raised when the provider takes too long to respond."""


class ProviderAuthenticationError(ProviderAPIError):
    """Raised for invalid API keys."""


class ProviderRateLimitError(ProviderAPIError):
    """Raised for quota, credit, or request-rate limits."""
