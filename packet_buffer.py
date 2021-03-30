import threading
from hks_network.packet import CannotExtractPacket 
from hks_network.lib.CustomPrint import StandardPrint


class PacketBufferException(Exception): ...
class PacketBufferOverflow(PacketBufferException): ...


class PacketBuffer():
    def __init__(self, decoder, identifier=None, verbosities: tuple = ("error", )):
        self.buffer = []
        self.packet_decoder = decoder
        prefix = "PacketBuffer"
        if identifier is not None:
            prefix = f"PacketBuffer {identifier}"
        self.__print__ = StandardPrint(prefix, verbosities)
        self.current_packet = b""
        self.current_packet_size = 0
        self.expected_current_packet_size = 0
        self._push_lock = threading.Lock()

    def push(self, packet: bytes, append_to_end=True):
        self._push_lock.acquire()
        self.__print__("dev", "notification", "Push {} bytes to buffer".format(len(packet)))
        if append_to_end:
            self.buffer.append(packet)
        else:
            self.buffer.insert(0, packet)
        self._push_lock.release()

    def pop(self):
        try:
            if len(self.buffer) == 0:
                return b""

            self.current_packet_size += len(self.buffer[0])
            self.current_packet += self.buffer[0]
            del self.buffer[0]

            if self.packet_decoder is None:
                ret = self.current_packet
                self.current_packet = b""
                self.current_packet_size = 0
                self.expected_current_packet_size = 0
                return ret

            if self.expected_current_packet_size == 0:
                try:
                    packet_dict = self.packet_decoder._decode_header(self.current_packet)
                    self.expected_current_packet_size = packet_dict["payload_size"] + packet_dict["header_size"]
                except Exception:
                    return b""

            if self.current_packet_size < self.expected_current_packet_size:
                raise CannotExtractPacket("Incomplete packet")

            if self.current_packet == b"":
                self.current_packet_size = 0
                self.expected_current_packet_size = 0
                return b""

            packet_tuple = self.packet_decoder(self.current_packet)

            if self.expected_current_packet_size < len(self.current_packet):
                apart_of_next_packet = self.current_packet[self.expected_current_packet_size:]
                self.push(apart_of_next_packet, append_to_end=False)

            self.current_packet = b""
            self.current_packet_size = 0
            self.expected_current_packet_size = 0
            return packet_tuple["payload"]
        except Exception as e:
            raise e

    def __len__(self):
        return len(self.buffer)
