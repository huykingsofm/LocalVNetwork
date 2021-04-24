from hks_pynetwork.errors import HKSPyNetworkError


class PacketError(HKSPyNetworkError):
    "Exception is raised by failures in packet module."


class PacketSizeError(PacketError):
    "Exception raised by the invalid size of packet elements"
    

class CannotExtractPacketError(PacketError):
    "Exception is raised by some errors in packet extracting."


class IncompletePacketError(CannotExtractPacketError):
    "Exception is raised when the incomplete packet is extracted."
