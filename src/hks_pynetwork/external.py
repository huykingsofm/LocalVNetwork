import copy
import time
import errno
import socket
import threading

from hks_pylib.logger import LoggerGenerator
from hks_pylib.cryptography.ciphers.cipherid import CipherID
from hks_pylib.cryptography.ciphers.hkscipher import HKSCipher
from hks_pylib.logger.logger_generator import InvisibleLoggerGenerator
from hks_pylib.logger.standard import StdLevels, StdUsers
from hkserror.hkserror import HFormatError, HTypeError

from hks_pynetwork.packet_buffer import PacketBuffer
from hks_pynetwork.secure_packet import SecurePacketEncoder, SecurePacketDecoder

from hks_pylib.errors.cryptography.ciphers import CipherParameterError
from hks_pylib.errors.cryptography.ciphers.symmetrics import UnAuthenticatedPacketError

from hks_pynetwork.errors.packet import IncompletePacketError
from hks_pynetwork.errors.secure_packet import CipherTypeMismatchError
from hks_pynetwork.errors.external import STCPSocketClosedError, STCPSocketTimeoutError


class STCPSocket(object):
    DEFAULT_TIME_OUT = 0.1
    DEFAULT_RELOAD_TIME = 0.1

    def __init__(
                    self,
                    cipher: HKSCipher,
                    name: str,
                    buffer_size: int,
                    logger_generator: LoggerGenerator = InvisibleLoggerGenerator(),
                    display: dict = {}
                ):
        if not isinstance(cipher, HKSCipher):
            raise HTypeError("cipher", cipher, HKSCipher)

        if not isinstance(buffer_size, int):
            raise HTypeError("buffer_size", int)

        if buffer_size <= 0:
            raise HFormatError("Parameter buffer_size expected an positive integer.")
        
        if not isinstance(logger_generator, LoggerGenerator):
            raise HTypeError("logger_generator", logger_generator, LoggerGenerator)

        if not isinstance(display, dict):
            raise HTypeError("display", display, dict)

        if not isinstance(name, str):
            raise HTypeError("name", name, str)

        self._name = name
        self._logger_generator = logger_generator
        self._display = display
        self._log = self._logger_generator.generate(name, self._display)

        self._log(StdUsers.DEV, StdLevels.DEBUG, "Initialized with "
        "cipher {}.".format(CipherID.cls2name(type(cipher))))

        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__cipher = cipher
        self.__cipher.reset()

        self.set_reload_time(STCPSocket.DEFAULT_RELOAD_TIME)
        self.set_recv_timeout(None)

        self.__packet_encoder = SecurePacketEncoder(self.__cipher)
        self.__packet_decoder = SecurePacketDecoder(self.__cipher)
        self.__buffer = None
        self.__buffer_size = buffer_size

        self.__buffer_available = threading.Event()
        self._stop_auto_recv = False
        self._prepare_close = False

        self._is_working = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._is_working:
            self.close()

    def _start_auto_recv(self):
        self._log(StdUsers.DEV, StdLevels.INFO, "Start the automatic received process.")
        while True:
            try:
                data = self._socket.recv(self.__buffer_size)
            except socket.error as e:
                if isinstance(e, socket.timeout) and not self._stop_auto_recv:
                    continue
 
                self._socket.close()
                if e.errno in (errno.ECONNRESET, errno.ECONNABORTED, errno.ECONNREFUSED):
                    self._log(StdUsers.DEV, StdLevels.INFO, "Automatic received "
                    "process closed normally ({}).".format(e))
                    break
                elif isinstance(e, socket.timeout):
                    self._log(StdUsers.DEV, StdLevels.INFO, "Automatic received "
                    "process closed normally (timeout and socket closed).")
                    break
                elif isinstance(e, OSError) and e.errno == 10038:
                    self._log(StdUsers.DEV, StdLevels.INFO, "Automatic received "
                    "process closed normally (remote socket closed).")
                    break
                else:
                    self._log(StdUsers.DEV, StdLevels.ERROR, "Automatic received "
                    "process closed with an unknown socket error ({}).".format(e))
                    raise e
            except Exception as e:
                self._socket.close()
                self._log(StdUsers.DEV, StdLevels.ERROR, "Automatic received process "
                "closed with an unknown error ({}).".format(e))
                break
            else:  # If there is no error
                # When be closed by the remote party,
                # socket will receive infinite empty packets
                if not data:
                    self._socket.close()
                    self._log(StdUsers.DEV, StdLevels.INFO, "Automatic received process "
                    "closed normally (remote socket closed).")
                    break
                self.__buffer.push(data)
                self.__buffer_available.set()

        self.__buffer_available.set()

    def set_reload_time(self, value: float):
        if not isinstance(value, (int, float)):
            raise HTypeError("value", value, float, int)

        if value < 0:
            raise HFormatError("Parameter value expected a non-negative number.")

        self._log(StdUsers.DEV, StdLevels.DEBUG, "Set reload "
        "time to {}.".format(value))
        self.__reload_time = value

    def set_recv_timeout(self, value: float):
        if value is not None and not isinstance(value, (int, float)):
            raise HTypeError("value", value, float, int, None)

        if value is not None and value < 0:
            raise HFormatError("Parameter value expected a non-negative number.")

        self._log(StdUsers.DEV, StdLevels.DEBUG, "Set received "
        "timeout to {}.".format(value))
        self.__recv_timeout = value

    def settimeout_raw(self, value: float):
        if value is not None and not isinstance(value, (int, float)):
            raise HTypeError("value", value, float, int, None)

        if value < 0:
            raise HFormatError("Parameter value expected a non-negative number.")

        self._log(StdUsers.DEV, StdLevels.DEBUG, "Set timeout "
        "to {}.".format(value))

        return self._socket.settimeout(value)

    def recv(self) -> bytes:
        data = b''
        if self.__recv_timeout is not None:
            start_recv_time = time.time()

        while not data:
            if self.isclosed() and len(self.__buffer) == 0:
                raise STCPSocketClosedError("Connection closed.")

            try:
                data = self.__buffer.pop()
            except IncompletePacketError as e:
                # Not enough length of packet, waiting more data
                continue
            except (UnAuthenticatedPacketError,
                    CipherParameterError,
                    CipherTypeMismatchError) as e:
                self._log(StdUsers.USER, StdLevels.WARNING, "Detect an abnormal packet.")
                self._log(StdUsers.DEV, StdLevels.WARNING, "Detect an abnormal packet "
                "({}).".format(e))
                break
            except Exception as e:
                self._log(StdUsers.USER, StdLevels.INFO, "Unknown error.")
                self._log(StdUsers.DEV, StdLevels.ERROR, "Unknown error "
                "({}).".format(e))
                break
            finally:
                if not data:
                    if self.__recv_timeout is not None and\
                        time.time() - start_recv_time > self.__recv_timeout:
                        if self.__recv_timeout != 0:
                            raise STCPSocketTimeoutError("Receiving exceeds timeout.")
                        else:
                            raise STCPSocketTimeoutError("Method recv() can not return "
                            "the value immediately.")

                    time.sleep(self.__reload_time)

                    if self.__recv_timeout is None and len(self.__buffer) == 0\
                        and not self.isclosed():
                        self.__buffer_available.wait()

        self.__buffer_available.clear()
        return data

    def send(self, data: bytes) -> int:
        if not isinstance(data, bytes):
            raise HTypeError("data", data, bytes)

        self.__cipher.reset()
        packet = self.__packet_encoder.encode(data)
        return self._socket.send(packet)

    def sendall(self, data: bytes) -> int:
        if not isinstance(data, bytes):
            raise HTypeError("data", data, bytes)

        self.__cipher.reset()
        packet = self.__packet_encoder.encode(data)
        return self._socket.sendall(packet)

    def bind(self, address):
        return self._socket.bind(address)

    def listen(self, __backlog: int = 0):
        self._socket.listen(__backlog)
        self._is_working = True

        self._log(StdUsers.USER, StdLevels.INFO, "Server start listening.")
        self._log(StdUsers.DEV, StdLevels.INFO, "Server start listening.")

    def accept(self):
        socket, addr = self._socket.accept()
        socket.settimeout(STCPSocket.DEFAULT_TIME_OUT)  # timeout for non-blocking socket

        self._log(StdUsers.USER, StdLevels.INFO, "Server accepted {}.".format(addr))
        self._log(StdUsers.DEV, StdLevels.INFO, "Server accepted {}.".format(addr))

        socket = self._fromsocket(socket, addr, start_serve=True)
        socket._is_working = True
        
        return socket, addr

    def connect(self, address):
        self._socket.connect(address)
        self._is_working = True

        self._log(StdUsers.USER, StdLevels.INFO, "Connect to "
        "server {} successfully.".format(address))
    
        self._log(StdUsers.DEV, StdLevels.INFO, "Connect to "
        "server {} successfully.".format(address))
    
        self._log(StdUsers.DEV, StdLevels.DEBUG, "Transform "
        "to STCP Socket {}.".format(address))

        self._log = self._logger_generator.generate(
                f"STCP Socket {address}", self._display)

        self.settimeout_raw(STCPSocket.DEFAULT_TIME_OUT)

        self._stop_auto_recv = False
        auto_recv = threading.Thread(
                target=self._start_auto_recv,
                name="AutoRecv of {}".format(self._name)
            )
        auto_recv.start()

        self.__buffer = PacketBuffer(
                decoder=self.__packet_decoder,
                name="Packet Buffer of {}".format(address),
                logger_generator=self._logger_generator,
                display=self._display
            )

    def close(self):
        if self.__buffer is not None:  # not STCP Listener
            self.__buffer_available.set()
            self._stop_auto_recv = True

        if not self.isclosed():
            self._socket.close()
            self._is_working = False
            self._log(StdUsers.DEV, StdLevels.INFO, "Closed.")

    def isclosed(self):
        "This method returns the raw socket._closed"
        return self._socket._closed

    def isworking(self):
        return self._is_working and not self.isclosed()

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
                name="PacketBuffer of {}".format(address),
                logger_generator=self._logger_generator,
                display=self._display
            )

        if start_serve:
            new_socket._stop_auto_recv = False
            auto_recv = threading.Thread(
                    target=new_socket._start_auto_recv,
                    name="AutoRecv of {}".format(new_socket._name)
                )
            auto_recv.start()

        return new_socket
