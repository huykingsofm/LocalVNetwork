from hks_pynetwork.errors import HKSPyNetworkError


class ExternalError(HKSPyNetworkError):
    "Exception is raised by failures in external module."


class STCPSocketClosedError(ExternalError):
    "Exception is raised when a STCPSocket was closed."


class STCPSocketTimeoutError(ExternalError):
    "Exception is raised when a STCPSocket method stop due to timeout."
