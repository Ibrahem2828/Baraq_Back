class AIServiceError(Exception):
    """Base exception for AI service integration failures."""


class AIServiceDisabledError(AIServiceError):
    """Raised when the AI service integration is disabled."""


class AIServiceTimeoutError(AIServiceError):
    """Raised when the AI service request times out."""


class AIServiceBadResponseError(AIServiceError):
    """Raised when the AI service returns an invalid response."""


class AIServiceAuthenticationError(AIServiceError):
    """Raised when the AI service rejects authentication."""
