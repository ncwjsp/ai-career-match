"""Stable domain errors; HTTP mapping belongs to the route owner."""


class NlpError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)
