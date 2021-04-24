from hks_pynetwork.errors import HKSPyNetworkError


class InternalError(HKSPyNetworkError):
    "Exception is raised by failures in internal module."


class ChannelSlotError(InternalError):
    "Exception is raised when an error occurs due to slot."


class ChannelClosedError(InternalError):
    "Exception is raised when the method is working after channel closing."
