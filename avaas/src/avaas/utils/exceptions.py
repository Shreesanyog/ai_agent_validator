class AvaasError(Exception):
    """Base class for all AVaaS-specific exceptions."""


class AgentNotFoundError(AvaasError):
    pass


class RunNotFoundError(AvaasError):
    pass


class NoBaselineFoundError(AvaasError):
    pass
