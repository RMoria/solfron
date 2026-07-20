"""Exceptions for pysolfron."""


class SolfronError(Exception):
    """Base exception."""


class SolfronConnectionError(SolfronError):
    """Unable to connect."""


class InvalidResponseError(SolfronError):
    """Unexpected inverter response."""


class DiscoveryError(SolfronError):
    """Unable to locate inverter."""
