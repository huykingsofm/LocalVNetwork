import copy
import time
import errno
import socket
import threading

from hks_pylib.logger import LoggerGenerator
from hks_pynetwork.packet_buffer import PacketBuffer
from hks_pylib.cipher import AllCipher, _Cipher
from hks_pynetwork.secure_packet import SecurePacketEncoder, SecurePacketDecoder

# Exception
from hks_pylib.cipher import DecryptFailed
from hks_pynetwork.packet import CannotExtractPacket
from hks_pynetwork.secure_packet import CipherTypeMismatch


class STCPSocketException(Exception): ...
class STCPSocketClosed(STCPSocketException): ...
class STCPSocketTimeout(STCPSocketException): ...


class STCPSocket(object):
    DEFAULT_TIME_OUT = 0.1

    def __init__(
                    self,
                    cipher: _Cipher,
                    buffer_size: int = 1024,
                    reload_time: float = 0.001,
                    logger_generator: LoggerGenerator = ...,
                    display: dict = ...,
                    name: str="STCP Socket Listener",
                ):
        assert isinstance(cipher, _Cipher)
        assert isinstance(buffer_size, int)
        assert isinstance(reload_time, float)
        assert isinstance(logger_generator, LoggerGenerator)
        assert isinstance(display, dict)
        assert isinstance(name, str)

        self._logger_generator = logger_generator
        self._display = display
        self.__print = self._logger_generator.generate(name, self._display)

        self.__print("dev", "debug", "Initialized with cipher {}".format(AllCipher.cls2name(type(cipher))))
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__cipher = cipher
        self.__cipher.reset_params()
        self.set_reload_time(reload_time)
        self.__recv_timeout = None

        self.__packet_encoder = SecurePacketEncoder(self.__cipher)
        self.__packet_decoder = SecurePacketDecoder(self.__cipher)
        self.__buffer = None
        self.__buffer_size = buffer_size

        self.__buffer_available = threading.Event()
        self._stop_auto_recv = False


    def __enter__(self):
        return self

    def __exit__(self, *args):
        return self._socket.__exit__(args)

    def _start_auto_recv(self):
        self.__print("dev", "info", "Start automatically receiving...")
        while not self.isclosed():
            try:
                data = self._socket.recv(self.__buffer_size)
            except socket.error as e:
                if isinstance(e, socket.timeout) and not self._stop_auto_recv:
                    continue

                # self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                if e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.ECONNREFUSED):
                    self.__print("dev", "info", "Automatically receiving closes normally ({})".format(repr(e)))
                    break
                elif isinstance(e, socket.timeout):
                    self.__print("dev", "info", "Automatically receiving closes normally (timeout and socket closed)")
                    break
                else:
                    self.__print("dev", "error", "Connection stops suddenly ({})".format(repr(e)))
                    raise e
            except Exception as e:
                # self._socket.shutdown(socket.SHUT_RDWR)
                self._socket.close()
                self.__print("dev", "error", "Unknown error in automatically receiving ({})".format(repr(e)))
                raise e
            else:
                if not data:  # when be closed, socket will receive infinite empty packet
                    self._socket.close()
                    self.__print("dev", "info", "Automatically receiving closes normally (remote socket closed)")
                    break
                self.__buffer.push(data)
                self.__buffer_available.set()
        self.__buffer_available.set()
        self.__print("dev", "info", "Stop automatically receiving...")

    def set_reload_time(self, value: float):
        self.__print("dev", "debug", "Set reload time to {}".format(value))
        self.__reload_time = value

    def set_recv_timeout(self, value: float):
        self.__print("dev", "debug", "Set receive timeout to {}".format(value))
        self.__recv_timeout = value

    def settimeout(self, value: float):
        self.__print("dev", "debug", "Set timeout to {}".format(value))
        return self._socket.settimeout(value)

    def setreloadtime(self, reloadtime: float):
        self.__reload_time = reloadtime

    def recv(self) -> bytes:
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
                continue
            except CipherTypeMismatch as e:
                # Cipher's type mismatch
                self.__print("user", "warning", "Detect an abnormal packet")
                self.__print("dev", "warning", "Detect an abnormal packet ({})".format(repr(e)))
                break
            except DecryptFailed as e:
                # Cannot decrypt the packet: authentication failed, wrong parameters, ...
                self.__print("user", "warning", "Detect an abnormal packet")
                self.__print("dev", "warning", "Detect an abnormal packet ({})".format(repr(e)))
                break
            except Exception as e:
                self.__print("user", "info", "Unknown error in recv() method")
                self.__print("dev", "error", "Unknown error in recv() method ({})".format(repr(e)))
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
        return self._socket.send(packet)

    def sendall(self, data) -> int:
        self.__cipher.reset_params()
        packet = self.__packet_encoder(data)
        return self._socket.sendall(packet)

    def bind(self, address):
        return self._socket.bind(address)

    def listen(self, __backlog: int = 0):
        self.__print("user", "info", "Server listen...")
        self.__print("dev", "info", "Server listen...")
        return self._socket.listen(__backlog)

    def accept(self):
        socket, addr = self._socket.accept()
        socket.settimeout(STCPSocket.DEFAULT_TIME_OUT)  # timeout for non-blocking socket
        self.__print("user", "info", "Server accept {}".format(addr))
        self.__print("dev", "info", "Server accept {}".format(addr))
        socket = self._fromsocket(socket, addr, start_serve=True)
        return socket, addr

    def connect(self, address):
        ret = self._socket.connect(address)
        self.__print("user", "info", "Connect to server {} successfully".format(address))
        self.__print("dev", "info", "Connect to server {} successfully".format(address))
        self.__print("dev", "debug", "Transform to STCP Socket {}".format(address))

        self.__print = self._logger_generator.generate(f"STCP Socket {address}", self._display)
        self.settimeout(STCPSocket.DEFAULT_TIME_OUT)  # timeout for non-blocking socket
        
        self._stop_auto_recv = False
        server = threading.Thread(target=self._start_auto_recv)
        server.setDaemon(False)
        server.start()

        self.__buffer = PacketBuffer(
            decoder=self.__packet_decoder,
            identifier=address,
            logger_generator=self._logger_generator,
            display=self._display
        )
        return ret

    def close(self):
        if self.__buffer is None:  # STCP Listener
            self._socket.close()
        else:
            self.__buffer_available.set()
            self._stop_auto_recv = True
        self.__print("dev", "info", "Closed")

    def isclosed(self):
        return self._socket._closed

    def _fromsocket(self, socket: socket.socket, address, start_serve=True):
        cipher = copy.copy(self.__cipher)
        new_socket = STCPSocket(
            cipher=cipher, 
            buffer_size=self.__buffer_size,
            logger_generator=self._logger_generator,
            display=self._display,
            name=f"STCP Socket {address}"
        )
        new_socket._socket = socket
        new_socket.__buffer = PacketBuffer(
            decoder=new_socket.__packet_decoder,
            identifier=address,
            logger_generator=self._logger_generator,
            display=self._display
        )
        if start_serve:
            new_socket._stop_auto_recv = False
            server = threading.Thread(target=new_socket._start_auto_recv)
            server.setDaemon(False)
            server.start()
        return new_socket
