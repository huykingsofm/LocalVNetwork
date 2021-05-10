import threading

from hks_pylib.logger import LoggerGenerator
from hks_pylib.logger.logger_generator import InvisibleLoggerGenerator
from hks_pylib.logger.standard import StdLevels, StdUsers
from hkserror.hkserror import HTypeError
from hks_pynetwork.secure_packet import PacketDecoder

from hks_pynetwork.errors.packet import IncompletePacketError, PacketSizeError
from hks_pynetwork.errors.secure_packet import CipherTypeMismatchError


class PacketBuffer():
    def __init__(
                    self,
                    decoder: PacketDecoder,
                    name: str,
                    logger_generator: LoggerGenerator = InvisibleLoggerGenerator(),
                    display: dict = {}
                ) -> None:
        if not isinstance(decoder, PacketDecoder):
            raise HTypeError("decoder", decoder, PacketDecoder)

        if name is not None and not isinstance(name, str):
            raise HTypeError("name", name, str, None)

        self._buffer = []

        self._packet_decoder = decoder

        self.__print = logger_generator.generate(name, display)
        
        self._current_packet = b""
        self._current_packet_size = 0
        self._expected_current_packet_size = 0
        
        self._push_lock = threading.Lock()

    def push(self, packet: bytes, append_to_end: bool = True):
        if not isinstance(packet, bytes):
            raise HTypeError("packet", packet, bytes)

        if not isinstance(append_to_end, bool):
            raise HTypeError("append_to_end", append_to_end, bool)

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
            except PacketSizeError:
                self.__print(StdUsers.DEV, StdLevels.WARNING, "Detect an "
                "abnormal packet (invalid size).")

                self._current_packet = b""
                self._current_packet_size = 0
                self._expected_current_packet_size = 0
                return b""

        if self._current_packet_size < self._expected_current_packet_size:
            return b""

        try:
            packet_dict = self._packet_decoder.decode(self._current_packet)
        except CipherTypeMismatchError as e:
            self.__print(StdUsers.DEV, StdLevels.WARNING, "Detect an "
            "abnormal packet ({}).".format(e))
            return b""
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
