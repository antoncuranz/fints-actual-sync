class FinTSConnectionError(Exception):
    pass


class FinTSAuthenticationError(Exception):
    pass


class ActualExportError(Exception):
    pass


class InvalidSessionState(Exception):
    pass


class TanSessionExpiredError(Exception):
    pass
