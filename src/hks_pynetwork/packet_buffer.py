import threading

from hks_pylib.logger import LoggerGenerator
from hks_pynetwork.secure_packet import PacketDecoder

from hks_pynetwork.errors.packet import IncompletePacketError
from hks_pynetwork.errors.secure_packet import CipherTypeMismatchError


class PacketBuffer():
    def __init__(
                    self,
                    decoder: PacketDecoder,
                    name: str,
                    logger_generator: LoggerGenerator,
                    display: dict
                ) -> None:
        assert isinstance(decoder, PacketDecoder)

        self._buffer = []

        self._packet_decoder = decoder

        self.__print = logger_generator.generate(name, display)
        
        self._current_packet = b""
        self._current_packet_size = 0
        self._expected_current_packet_size = 0
        
        self._push_lock = threading.Lock()

    def push(self, packet: bytes, append_to_end: bool = True):
        self._push_lock.acquire()

        if append_to_end:
            self._buffer.append(packet)
        else:
            self._buffer.insert(0, packet)

        self._push_lock.release()

    def pop(self):
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
                packet_dict = self._packet_decoder.get_header(self._current_packet)
                self._expected_current_packet_size =\
                    packet_dict["payload_size"] + packet_dict["header_size"]
            except IncompletePacketError:
                return b""
            except Exception as e:
                self.__print("dev", "error", "Unknown error occurs "
                "when decode a packet ({}).".format(repr(e)))
                raise e

        if self._current_packet_size < self._expected_current_packet_size:
            return b""

        try:
            packet_dict = self._packet_decoder.decode(self._current_packet)
        except CipherTypeMismatchError as e:
            raise e
        finally:
            if  self._current_packet_size > self._expected_current_packet_size:
                apart_of_next_packet = self._current_packet[
                        self._expected_current_packet_size :
                    ]
                self.push(apart_of_next_packet, append_to_end=False)
 
            self._current_packet = b""
            self._current_packet_size = 0
            self._expected_current_packet_size = 0

        return packet_dict["payload"]

    def __len__(self):
        return len(self._buffer)
