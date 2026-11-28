"""Kit runtime: callers keep their interpreter; no implicit environment setup."""


def ensure():
    """Retain the upstream hook without installing or switching Python."""
