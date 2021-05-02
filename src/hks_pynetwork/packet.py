import struct

from hkserror.hkserror import HTypeError

from hks_pynetwork.errors.packet import IncompletePacketError, PacketSizeError


MAX_HEADER_SIZE = 65535
MAX_PAYLOAD_SIZE = 4294967295
MAX_PACKET_SIZE = MAX_HEADER_SIZE + MAX_PAYLOAD_SIZE

MIN_HEADER_SIZE = 6


class PacketEncoder(object):
    def encode(self, payload: bytes):
        if not isinstance(payload, bytes):
            raise HTypeError("payload", payload, bytes)

        if len(payload) > MAX_PAYLOAD_SIZE:
            raise PacketSizeError("Payload size is too large "
            "(expected < {}).".format(MAX_PAYLOAD_SIZE))

        # PACKET = HEADER + PAYLOAD
        # HEADER = HEADER_SIZE(2 bytes) + PAYLOAD_SIZE(4 byte) + OPTIONAL_HEADER
        # ==> PACKET = HERDER_SIZE + PAYLOAD_SIZE + OPTIONAL_HEADER + PAYLOAD

        header_struct = ">HI"

        header_dummy = struct.pack(header_struct, 0, 0)
        header_size = len(header_dummy)

        header = struct.pack(header_struct, header_size, len(payload))

        return header + payload


class PacketDecoder(object):
    def get_header(self, packet: bytes):
        if not isinstance(packet, bytes):
            raise HTypeError("packet", packet, bytes)

        if len(packet) > MAX_PACKET_SIZE:
            raise PacketSizeError("Packet size is too large "
            "(expected < {}).".format(MAX_PACKET_SIZE))

        if len(packet) < MIN_HEADER_SIZE:
            raise IncompletePacketError("Incomplete header.")

        header_size, payload_size = struct.unpack(">HI", packet[:MIN_HEADER_SIZE])
        if header_size > MAX_HEADER_SIZE:
            raise PacketSizeError("Header size is too large "
            "(expected < {}).".format(MAX_HEADER_SIZE))

        if len(packet) < header_size:
            raise IncompletePacketError("Incomplete header.")

        header_dict = {}
        header_dict["header_size"] = header_size
        header_dict["payload_size"] = payload_size

        return header_dict

    def decode(self, packet: bytes):
        if not isinstance(packet, bytes):
            raise HTypeError("packet", packet, bytes)

        header = self.get_header(packet)

        header_size, payload_size = header["header_size"], header["payload_size"]
        
        if payload_size > MAX_PAYLOAD_SIZE:
            raise PacketSizeError("Payload size is too large "
            "(expected < {}).".format(MAX_PAYLOAD_SIZE))

        if len(packet) < header_size + payload_size:
            raise IncompletePacketError("Incomplete packet.")
 
        packet_dict = header
        packet_dict["payload"] = packet[header_size: header_size + payload_size]
        packet_dict["packet_size"] = header_size + payload_size

        return packet_dict
