from hks_pynetwork.errors import HKSPyNetworkError


class SecurePacketError(HKSPyNetworkError):
    "The exception is raised by failures in secure_packet module."


class CipherTypeMismatchError(SecurePacketError):
    """The exception is raised when type of cipher of
    decoded packet is diffrent from intial cipher."""
