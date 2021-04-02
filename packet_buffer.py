import struct
import threading

from .secure_packet import CipherTypeMismatch
from .packet import CannotExtractPacket, PacketDecoder
from .lib.logger.logger import LoggerGenerator

class PacketBufferException(Exception): ...
class PacketBufferOverflow(PacketBufferException): ...


class PacketBuffer():
    def __init__(
                    self,
                    decoder: PacketDecoder,
                    identifier=None,
                    logger_generator: LoggerGenerator = ...,
                    display: dict = ...
                ) -> None:
        self._buffer = []
        self._packet_decoder = decoder
        prefix = "PacketBuffer"
        if identifier is not None:
            prefix = f"PacketBuffer {identifier}"
        self.__print = logger_generator.generate(prefix, display)
        self._current_packet = b""
        self._current_packet_size = 0
        self._expected_current_packet_size = 0
        self._push_lock = threading.Lock()

    def push(self, packet: bytes, append_to_end=True):
        self._push_lock.acquire()
        if append_to_end:
            self._buffer.append(packet)
        else:
            self._buffer.insert(0, packet)
        self._push_lock.release()

    def pop(self):
        try:
            if len(self._buffer) == 0:
                return b""

            self._current_packet_size += len(self._buffer[0])
            self._current_packet += self._buffer[0]
            del self._buffer[0]

            if self._packet_decoder is None:
                ret = self._current_packet
                self._current_packet = b""
                self._current_packet_size = 0
                self._expected_current_packet_size = 0
                return ret

            if self._expected_current_packet_size == 0:
                try:
                    packet_dict = self._packet_decoder._decode_header(self._current_packet)
                    self._expected_current_packet_size = packet_dict["payload_size"] + packet_dict["header_size"]
                except CannotExtractPacket:
                    return b""
                except struct.error:
                    return b""
                except Exception as e:
                    self.__print("dev", "warning", "Something error when decode a packet ({})".format(repr(e)))
                    return b""

            if self._current_packet_size < self._expected_current_packet_size:
                return b""

            # if self._current_packet == b"":
            #     self._current_packet_size = 0
            #     self._expected_current_packet_size = 0
            #     return b""

            try:
                packet_dict = self._packet_decoder(self._current_packet)
            except CipherTypeMismatch as e:
                raise e
            finally:
                if self._expected_current_packet_size < self._current_packet_size:
                    apart_of_next_packet = self._current_packet[self._expected_current_packet_size:]
                    self.push(apart_of_next_packet, append_to_end=False)

                self._current_packet = b""
                self._current_packet_size = 0
                self._expected_current_packet_size = 0
            return packet_dict["payload"]
        except Exception as e:
            # self.__print("dev", "error", "An error occurs when calling pop() ({})".format(repr(e)))
            raise e

    def __len__(self):
        return len(self._buffer)
