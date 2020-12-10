from . import SecurePacket
from . import Packet
from . import Cipher
from .CustomPrint import StandardPrint

class PacketBufferException(Exception): ...
class PacketBufferOverflow(PacketBufferException): ...

class PacketBuffer():
    def __init__(self, decoder, identifier = None, verbosities: tuple = ("error", )):
        self.buffer = []
        self.packet_decoder = decoder
        prefix = "PacketBuffer"
        if identifier != None:
            prefix = f"PacketBuffer {identifier}"
        self.__print__ = StandardPrint(prefix, verbosities)
        self.current_packet = b""
        self.current_packet_size = 0
        self.expected_current_packet_size = 0

    def push(self, packet:bytes):
        self.__print__("Push the message: {}".format(packet), "notification")
        self.buffer.append(packet)

    def pop(self):
        try:
            if len(self.buffer) == 0:
                return b""
            
            self.current_packet_size += len(self.buffer[0])
            self.current_packet += self.buffer[0]
            del self.buffer[0]

            if self.expected_current_packet_size == 0 and self.packet_decoder:
                packet_dict = self.packet_decoder._decode_header(self.current_packet)
                self.expected_current_packet_size = packet_dict["payload_size"] + packet_dict["header_size"]

            if self.current_packet_size < self.expected_current_packet_size:
                return b""
            
            if self.packet_decoder == None:
                ret = self.current_packet
                self.current_packet = b""
                self.current_packet_size = 0
                self.expected_current_packet_size = 0
                return ret

            if self.current_packet == b"":
                return b""
                
            packet_tuple = self.packet_decoder(self.current_packet)
            packet_size = packet_tuple["packet_size"]
            
            if packet_size < len(self.current_packet):
                raise PacketBufferOverflow("Received packet's length is larger than the expected size of packet")

            self.current_packet = b""
            return packet_tuple["payload"]
        except Exception as e:
            raise e

    def __len__(self):
        return len(self.buffer)