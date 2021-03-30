import copy
import time
import errno
import socket
import threading

from hks_network.lib.cipher import NoCipher
from hks_network.packet_buffer import PacketBuffer
from hks_network.lib.CustomPrint import StandardPrint
from hks_network.secure_packet import SecurePacketEncoder, SecurePacketDecoder

# Exception
from hks_network.lib.cipher import DecryptFailed
from hks_network.packet import CannotExtractPacket
from hks_network.secure_packet import CipherTypeMismatch


DEFAULT_RELOAD_TIME = 0.000001
DEFAULT_TIME_OUT = 0.1


class STCPSocketException(Exception): ...
class STCPSocketClosed(STCPSocketException): ...
class STCPSocketTimeout(STCPSocketException): ...


class STCPSocket(object):
    def __init__(
                    self,
                    cipher=NoCipher(),
                    buffer_size=1024,
                    verbosities={"dev": {"error", }, "user": {"error"}}
                ):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__cipher = cipher
        self.__cipher.reset_params()
        self._reload_time = DEFAULT_RELOAD_TIME
        self._timeout = None

        self.__packet_encoder = SecurePacketEncoder(self.__cipher)
        self.__packet_decoder = SecurePacketDecoder(self.__cipher)
        self._buffer = None
        self._buffer_size = buffer_size

        self._buffer_available = threading.Event()
        self._stop_recv = False

        self.__print = StandardPrint("STCP Socket", verbosities)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self._socket.__exit__(args)

    def _start_auto_recv(self):
        self.__print("user", "notification", "Start serve socket...")
        while not self.isclosed():
            try:
                data = self._socket.recv(self._buffer_size)
            except socket.error as e:
                if isinstance(e, socket.timeout) and not self._stop_recv:
                    continue

                # self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                if e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.ECONNREFUSED):
                    break
                elif isinstance(e, socket.timeout):
                    break
                else:
                    self.__print("user", "error", "Connection stopped suddenly")
                    self.__print("dev", "error", repr(e))
                    raise e
            except Exception as e:
                # self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                self.__print("user", "error", "Unknown error")
                self.__print("dev", "error", repr(e))
                raise e
            else:
                if not data:  # when be closed, socket will receive infinite empty packet
                    # self._socket.shutdown(socket.SHUT_RDWR)
                    self._socket.close()
                    break
                self._buffer.push(data)
                self._buffer_available.set()
        self._buffer_available.set()
        self.__print("user", "notification", "Stop serve socket...")

    def settimeout(self, value: float):
        self._timeout = value

    def setreloadtime(self, reloadtime: float):
        self._reload_time = reloadtime

    def recv(self, bufsize: int, flags: int = ...) -> bytes:
        data = b''
        if self._timeout is not None:
            start_recv_time = time.time()

        while not data:
            if self.isclosed() and len(self._buffer) == 0:
                raise STCPSocketClosed("Connection closed")

            try:
                data = self._buffer.pop()
            except CannotExtractPacket as e:
                # Not enough length of packet
                self.__print("dev", "warning", repr(e))
                continue
            except CipherTypeMismatch as e:
                # Cipher's type mismatch
                self.__print("dev", "warning", repr(e))
                break
            except DecryptFailed as e:
                # Cannot decrypt the packet: authentication failed, wrong parameters, ...
                self.__print("dev", "warning", repr(e))
                break
            except Exception as e:
                self.__print("user", "error", "Unknown error")
                self.__print("dev", "error", repr(e))
                break
            finally:
                if not data:
                    if self._timeout is not None and time.time() - start_recv_time > self._timeout:
                        if self._timeout != 0:
                            raise STCPSocketTimeout("Receiving exceeds timeout")
                        else:
                            raise STCPSocketTimeout("Method recv() can not return the value immediately")
                    time.sleep(self._reload_time)

                    if self._timeout is None and len(self._buffer) == 0 and not self.isclosed():
                        self._buffer_available.wait()

        self._buffer_available.clear()
        return data

    def send(self, data) -> int:
        self.__cipher.reset_params()
        packet = self.__packet_encoder(data)
        self.__print("dev", "notification", "Sent {} bytes".format(len(packet)))
        return self._socket.send(packet)

    def sendall(self, data) -> int:
        self.__cipher.reset_params()
        packet = self.__packet_encoder(data)
        self.__print("dev", "notification", "Sent {} bytes".format(len(packet)))
        return self._socket.sendall(packet)

    def bind(self, address):
        return self._socket.bind(address)

    def listen(self):
        self.__print("user", "notification", "Server listen...")
        return self._socket.listen()

    def accept(self):
        socket, addr = self._socket.accept()
        socket.settimeout(DEFAULT_TIME_OUT)  # timeout for non-blocking socket
        self.__print("user", "notification", "Server accept {}".format(addr))
        socket = self._fromsocket(socket, addr, start_serve=True)
        return socket, addr

    def connect(self, address):
        ret = self._socket.connect(address)

        self._socket.settimeout(DEFAULT_TIME_OUT)  # timeout for non-blocking socket

        self._stop_recv = False
        server = threading.Thread(target=self._start_auto_recv)
        server.setDaemon(False)
        server.start()

        self._buffer = PacketBuffer(self.__packet_decoder, address, {"dev": {"error"}})
        self.__print.prefix = f"STCP Socket {address}"
        return ret

    def close(self):
        self._buffer_available.set()
        self._stop_recv = True

    def isclosed(self):
        return self._socket._closed

    def _fromsocket(self, socket: socket.socket, address, start_serve=True):
        cipher = copy.copy(self.__cipher)
        dtp = STCPSocket(cipher, self._buffer_size, self.__print.__verbosities__)
        dtp._socket = socket
        dtp.__print.prefix = f"STCP Socket {address}"
        dtp._buffer = PacketBuffer(dtp.__packet_decoder, address, {"dev": {"error"}})
        if start_serve:
            dtp._stop_recv = False
            server = threading.Thread(target=dtp._start_auto_recv)
            server.setDaemon(False)
            server.start()
        return dtp
