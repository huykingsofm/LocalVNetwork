from hks_pynetwork.errors import HKSPyNetworkError


class InternalError(HKSPyNetworkError):
    "The exception is raised by failures in internal module."


class ChannelError(InternalError):
    "The exception is raised by failures in channel."


class ChannelSlotError(ChannelError):
    "The exception is raised when an error occurs due to slot."


class ChannelClosedError(ChannelError):
    "The exception is raised when the method is working after channel closing."

class ForwardNodeError(ChannelError):
    "The exception is raised by failures in forwarder."
