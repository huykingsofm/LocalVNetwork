from os import stat
import struct

MAX_LENGTH = 65535 + 4294967295


class PacketException(Exception): ...
class CannotExtractPacket(PacketException): ...


class PacketEncoder(object):
    @staticmethod
    def pack(payload: bytes):
        if isinstance(payload, bytes) is False:
            raise Exception("Payload must be a byte object")

        # PACKET = HEADER + PAYLOAD
        # HEADER = HEADER_SIZE(2 bytes) + PAYLOAD_SIZE(4 byte) + OPTIONAL_HEADER
        # ==> PACKET = HERDER_SIZE + PAYLOAD_SIZE + OPTIONAL_HEADER + PAYLOAD

        # header struct except for header_size
        header_struct = ">HI"
        header_dummy = struct.pack(header_struct, 0, 0)
        header_size = len(header_dummy)
        header = struct.pack(header_struct, header_size, len(payload))

        return header + payload


class PacketDecoder(object):
    @staticmethod
    def _decode_header(packet: bytes):
        if isinstance(packet, bytes) is False:
            raise Exception("Packet must be a bytes object")

        header_size, payload_size = struct.unpack(">HI", packet[:6])
        if len(packet) < header_size:
            raise CannotExtractPacket("Incomplete header")

        header_dict = {}
        header_dict["header_size"] = header_size
        header_dict["payload_size"] = payload_size

        return header_dict

    @staticmethod
    def unpack(packet: bytes):
        if isinstance(packet, bytes) is False:
            raise Exception("Packet must be a bytes object")

        try:
            header = PacketDecoder._decode_header(packet)
        except Exception as e:
            raise e

        header_size, payload_size = header["header_size"], header["payload_size"]
        if len(packet) < header_size + payload_size:
            raise CannotExtractPacket("Incomplete packet")

        packet_dict = header
        packet_dict["payload"] = packet[header_size: header_size + payload_size]
        packet_dict["packet_size"] = header_size + payload_size

        return packet_dict
