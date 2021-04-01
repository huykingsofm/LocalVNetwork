import copy
import time
import errno
import socket
import threading

from .lib.cipher import NoCipher
from .packet_buffer import PacketBuffer
from .lib.selective_print import StandardPrint
from .secure_packet import SecurePacketEncoder, SecurePacketDecoder

# Exception
from .lib.cipher import DecryptFailed
from .packet import CannotExtractPacket
from .secure_packet import CipherTypeMismatch


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
        self.__reload_time = DEFAULT_RELOAD_TIME
        self.__recv_timeout = None

        self.__packet_encoder = SecurePacketEncoder(self.__cipher)
        self.__packet_decoder = SecurePacketDecoder(self.__cipher)
        self.__buffer = None
        self.__buffer_size = buffer_size

        self.__buffer_available = threading.Event()
        self._stop_auto_recv = False

        self.__print = StandardPrint("STCP Socket", verbosities)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self._socket.__exit__(args)

    def _start_auto_recv(self):
        self.__print("user", "notification", "Start serve socket...")
        while not self.isclosed():
            try:
                data = self._socket.recv(self.__buffer_size)
            except socket.error as e:
                if isinstance(e, socket.timeout) and not self._stop_auto_recv:
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
                self.__buffer.push(data)
                self.__buffer_available.set()
        self.__buffer_available.set()
        self.__print("user", "notification", "Stop serve socket...")

    def set_recv_timeout(self, value: float):
        self.__recv_timeout = value

    def settimeout(self, value: float):
        return self._socket.settimeout(value)

    def setreloadtime(self, reloadtime: float):
        self.__reload_time = reloadtime

    def recv(self, bufsize: int, flags: int = ...) -> bytes:
        data = b''
        if self.__recv_timeout is not None:
            start_recv_time = time.time()

        while not data:
            if self.isclosed() and len(self.__buffer) == 0:
                raise STCPSocketClosed("Connection closed")

            try:
                data = self.__buffer.pop()
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
                    if self.__recv_timeout is not None and time.time() - start_recv_time > self.__recv_timeout:
                        if self.__recv_timeout != 0:
                            raise STCPSocketTimeout("Receiving exceeds timeout")
                        else:
                            raise STCPSocketTimeout("Method recv() can not return the value immediately")
                    time.sleep(self.__reload_time)

                    if self.__recv_timeout is None and len(self.__buffer) == 0 and not self.isclosed():
                        self.__buffer_available.wait()

        self.__buffer_available.clear()
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

    def listen(self, __backlog: int = ...):
        self.__print("user", "notification", "Server listen...")
        return self._socket.listen(__backlog)

    def accept(self):
        socket, addr = self._socket.accept()
        socket.settimeout(DEFAULT_TIME_OUT)  # timeout for non-blocking socket
        self.__print("user", "notification", "Server accept {}".format(addr))
        socket = self._fromsocket(socket, addr, start_serve=True)
        return socket, addr

    def connect(self, address):
        ret = self._socket.connect(address)

        self._socket.settimeout(DEFAULT_TIME_OUT)  # timeout for non-blocking socket

        self._stop_auto_recv = False
        server = threading.Thread(target=self._start_auto_recv)
        server.setDaemon(False)
        server.start()

        self.__buffer = PacketBuffer(self.__packet_decoder, address, {"dev": {"error"}})
        self.__print.prefix = f"STCP Socket {address}"
        return ret

    def close(self):
        self.__buffer_available.set()
        self._stop_auto_recv = True

    def isclosed(self):
        return self._socket._closed

    def _fromsocket(self, socket: socket.socket, address, start_serve=True):
        cipher = copy.copy(self.__cipher)
        dtp = STCPSocket(cipher, self.__buffer_size, self.__print._verbosities)
        dtp._socket = socket
        dtp.__print.prefix = f"STCP Socket {address}"
        dtp.__buffer = PacketBuffer(dtp.__packet_decoder, address, {"dev": {"error"}})
        if start_serve:
            dtp._stop_auto_recv = False
            server = threading.Thread(target=dtp._start_auto_recv)
            server.setDaemon(False)
            server.start()
        return dtp
