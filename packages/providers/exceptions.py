class ProviderError(Exception):
    """Base exception for all AI provider errors."""
    pass

class ProviderConnectionError(ProviderError):
    """Raised when the provider API is unreachable."""
    pass

class ProviderTimeoutError(ProviderError):
    """Raised when the provider takes too long to respond."""
    pass

class ProviderAuthenticationError(ProviderError):
    """Raised for invalid API keys."""
    pass