class Blocked(Exception):
    """A source answered 403/429 or a challenge page."""


class DriftError(Exception):
    """A source returned data but required fields are missing."""
