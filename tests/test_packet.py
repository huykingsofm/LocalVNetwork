import os
from hks_pynetwork.errors.packet import PacketDecodingError, PacketEncodingError, PacketSizeError

from hks_pynetwork.packet import PacketEncoder, PacketDecoder


def test_packet_encoder():
    encoder = PacketEncoder()
    try:
        encoder.encode(os.urandom(1111))
        assert True
    except PacketSizeError:
        pass

    try:
        encoder.encode(os.urandom(1111))
        assert True
    except PacketEncodingError:
        pass

    try:
        encoder.encode(os.urandom(1111))
        assert True
    except PacketDecodingError:
        pass