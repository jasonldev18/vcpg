class NotFound(Exception):
    pass


class Conflict(Exception):
    """The request is valid but not allowed in the current state."""
