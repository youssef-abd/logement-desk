class Blocked(Exception):
    """A source answered 403/429 or a challenge page."""


class DriftError(Exception):
    """A source returned data but required fields are missing."""


class EmptyResult(Exception):
    """A source answered but returned no listings at all (usually a challenge page or a wrong zone id)."""
