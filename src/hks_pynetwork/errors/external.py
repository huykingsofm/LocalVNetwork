from hks_pynetwork.errors import HKSPyNetworkError


class ExternalError(HKSPyNetworkError):
    "The exception is raised by failures in external module."


class STCPSocketError(ExternalError):
    "The exception is raised by failures in STCPSocket."


class STCPSocketClosedError(STCPSocketError):
    "The exception is raised when a STCPSocket was closed."


class STCPSocketTimeoutError(STCPSocketError):
    "The exception is raised when a STCPSocket method stop due to timeout."
