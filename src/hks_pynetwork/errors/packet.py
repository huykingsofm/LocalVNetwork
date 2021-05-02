from hks_pynetwork.errors import HKSPyNetworkError


class PacketError(HKSPyNetworkError):
    "The exception is raised by failures in packet module."


class PacketEncodingError(PacketError):
    "The exception raised by some errors in packet encoding."


class PacketDecodingError(PacketError):
    "The exception is raised by some errors in packet decoding."


class PacketSizeError(PacketDecodingError, PacketEncodingError):
    "The exception raised by the invalid size of packet elements"


class IncompletePacketError(PacketDecodingError):
    "The exception is raised when the incomplete packet is extracted."
