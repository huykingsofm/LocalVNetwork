from os import name
import random
import threading

from hks_pylib.logger import LoggerGenerator
from hks_pylib.logger.logger_generator import InvisibleLoggerGenerator
from hks_pylib.logger.standard import StdLevels, StdUsers
from hkserror.hkserror import HTypeError
from hks_pynetwork.external import STCPSocket, STCPSocketClosedError

from hks_pynetwork.errors.internal import ChannelError, ChannelSlotError, ChannelClosedError, ForwardNodeError


class ChannelBuffer(object):
    def __init__(self):
        self._buffer = []
        self.__lock = threading.Lock()

    def push(self, source: str, message: bytes, obj: object = None):
        self.__lock.acquire()
        self._buffer.append({"source": source, "message": message, "obj": obj})
        self.__lock.release()

    def pop(self, source: str = None):
        self.__lock.acquire()
        if len(self._buffer) == 0:
            return None, None, None

        idx = 0
        if source is not None:
            for i, packet in enumerate(self._buffer):
                if packet["source"] == source:
                    idx = i
                    break

        packet = self._buffer[idx]
        del self._buffer[idx]

        self.__lock.release()
        return packet["source"], packet["message"], packet["obj"]

    def __len__(self):
        return len(self._buffer)


class LocalNode(object):
    nodes = []
    node_names = []
    MAX_NODES = 8
    lock = threading.Lock()

    def __init__(self,
            name: str = None,
            logger_generator: LoggerGenerator = InvisibleLoggerGenerator(),
            display: dict = {}
        ):
        if name is not None and not isinstance(name, str):
            raise HTypeError("name", name, str, None)

        if not isinstance(logger_generator, LoggerGenerator):
            raise HTypeError("logger_generator", logger_generator, LoggerGenerator)

        if not isinstance(display, dict):
            raise HTypeError("display", display, dict)

        if name is None:
            while name is None or name in LocalNode.node_names:
                name = str(random.randint(1000000, 9999999))

        if name in LocalNode.node_names:
            raise ChannelSlotError(f"Name {name} is in use.")

        if len(LocalNode.nodes) >= LocalNode.MAX_NODES:
            raise ChannelSlotError("No available slot in Local Node list.")

        LocalNode.lock.acquire()
        LocalNode.node_names.append(name)
        LocalNode.nodes.append(self)
        LocalNode.lock.release()

        self.name = name
        self._buffer = ChannelBuffer()
        self._closed = False
 
        self._buffer_available = threading.Event()
        self.__send_lock = threading.Lock()
        self.__recv_lock = threading.Lock()

        self._log = logger_generator.generate(
                name,
                display
            )

        self._log(StdUsers.DEV, StdLevels.INFO,
        "{} join to Local Nodes.".format(name))

    def send(self, destination_name: str, message: bytes, obj: object = None):
        if not isinstance(destination_name, str):
            raise HTypeError("destination_name", destination_name, str)

        if not isinstance(message, bytes):
            raise HTypeError("message", message, bytes)

        self.__send_lock.acquire()
        if isinstance(message, bytes) is False:
            raise Exception("Message must be a bytes object.")

        if self._closed:
            raise ChannelClosedError("Channel closed.")

        try:
            slot_of_destination = LocalNode.node_names.index(destination_name)
            destination_node: LocalNode = LocalNode.nodes[slot_of_destination]
        except ValueError:
            raise ChannelSlotError(f"Channel name {destination_name} doesn't exist.")

        destination_node._buffer.push(self.name, message, obj)
        destination_node._buffer_available.set()
        self.__send_lock.release()

    def recv(self, source: str = None):
        if source is not None and not isinstance(source, str):
            raise HTypeError("source", source, str, None)

        if source is not None and source not in LocalNode.node_names:
            raise ChannelError("{} has not existed in Local Nodes.".format(source))

        if self._closed:
            raise ChannelClosedError("Channel closed.")

        if len(self._buffer) == 0 and not self._closed:
            self._buffer_available.wait()
        self._buffer_available.clear()

        if self._closed:
            raise ChannelClosedError("Channel closed.")

        source, msg, obj = self._buffer.pop(source)
        return source, msg, obj

    def close(self):
        if not self._closed:
            self.__recv_lock.acquire()

            self._closed = True
            self._buffer_available.set()

            my_slot = LocalNode.node_names.index(self.name)
            del LocalNode.node_names[my_slot]
            del LocalNode.nodes[my_slot]
            del self._buffer

            name = self.name
            self.name = None
            self.__recv_lock.release()

            self._log(StdUsers.DEV, StdLevels.INFO,
            "{} leaves Local Nodes.".format(name))


class ForwardNode(LocalNode):
    def __init__(
                    self,
                    node: LocalNode,
                    socket: STCPSocket,
                    name: str,
                    implicated_die: bool = False,
                    logger_generator: LoggerGenerator = InvisibleLoggerGenerator(),
                    display: tuple = {}
                ):
        if node is not None and not isinstance(node, LocalNode):
            raise HTypeError("node", node, LocalNode, None)

        if socket is not None and not isinstance(socket, STCPSocket):
            raise HTypeError("socket", socket, STCPSocket, None)

        if name is not None and not isinstance(name, str):
            raise HTypeError("name", name, str, None)

        if not isinstance(implicated_die, bool):
            raise HTypeError("implicated_die", implicated_die, bool)

        if not isinstance(logger_generator, LoggerGenerator):
            raise HTypeError("logger_generator", logger_generator, LoggerGenerator)

        if not isinstance(display, dict):
            raise HTypeError("display", display, dict)

        self._node = node
        self._socket = socket
        super().__init__(
                name=name,
                logger_generator=logger_generator,
                display=display
            )

        self._implicated_die = implicated_die
        if display is None:
            display = socket._log.display

        self._one_thread_stop = threading.Event()

    def set_node(self, node: LocalNode):
        if not isinstance(node, LocalNode):
            raise HTypeError("node", node, LocalNode)

        self._node = node

    def set_socket(self, socket: STCPSocket):
        if not isinstance(socket, STCPSocket):
            raise HTypeError("socket", socket, STCPSocket)

        self._socket = socket

    def start(self):
        self._log(StdUsers.DEV, StdLevels.INFO, "Start forwarding between local "
        "node and remote node.")
        if not self._node or not self._socket:
            raise ForwardNodeError("The node or the socket has been not provided yet.")

        t1 = threading.Thread(
                target=self._wait_message_from_node,
                name="WaitFromLocal of {}".format(self.name)
            )
        t1.setDaemon(True)
        t1.start()

        t2 = threading.Thread(
                target=self._wait_message_from_remote,
                name="WaitFromRemote of {}".format(self.name)
            )
        t2.setDaemon(True)
        t2.start()

        self._one_thread_stop.wait()
        self.close()

        if self._implicated_die:
            self._node.close()
            self._socket.close()
        else:
            if self._node._buffer_available.is_set() is False:
                self._node._buffer_available.set()

        self._log(StdUsers.DEV, StdLevels.INFO, "Stop completely.")

    def _wait_message_from_remote(self):
        while not self._closed:
            try:
                data = self._socket.recv()
            except STCPSocketClosedError:
                self._log(StdUsers.DEV, StdLevels.INFO, "Forwarding message from "
                "remote node closed normally (remote node closed).")
                break
            except Exception as e:
                self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message from "
                "remote node closed with an unknown error in data receiving.")

                self._log(StdUsers.DEV, StdLevels.ERROR, "Forwarding message from "
                "remote node closed with an unknown error in data receiving ({}).".format(e))
                break

            if data:
                try:
                    super().send(self._node.name, data)
                except ChannelClosedError:
                    self._log(StdUsers.DEV, StdLevels.INFO, "Forwarding message from "
                    "remote node closed normally (local node closed).")
                    break
                except Exception as e:
                    self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message from "
                    "remote node closed with an unknown error in data sending.")

                    self._log(StdUsers.DEV, StdLevels.ERROR, "Forwarding message from "
                    "remote node closed with an unknown error "
                    "in data sending ({}).".format(e))
                    break
        self._one_thread_stop.set()

    def _wait_message_from_node(self):
        while not self._closed:
            try:
                _, message, _ = super().recv()
            except AttributeError as e:  
                # (Old version) After closing forwarder,
                # it doesn't have buffer attribute.
                # It should be remove this exception in the future.
                self._log(StdUsers.DEV, StdLevels.WARNING,
                "AttributeError occurs when closing forward.")
                
                self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message "
                "from local node closed normally (forwarder self-closed).")
                
                self._log(StdUsers.DEV, StdLevels.INFO, "Forwarding message "
                "from local node closed normally (forwarder self-closed).")
                break
            except ChannelClosedError:
                self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message "
                "from local node closed normally (forwarder self-closed).")

                self._log(StdUsers.DEV, StdLevels.INFO, "Forwarding message "
                "from local node closed normally (forwarder self-closed).")
                break
            except Exception as e:
                self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message "
                "from local node closed with an unknown error in data receiving.")

                self._log(StdUsers.DEV, StdLevels.ERROR, "Forwarding message "
                "from local node closed with an unknown "
                "error ({}) in data receiving.".format(e))
                break

            if message:
                try:
                    self._socket.send(message)
                except STCPSocketClosedError:
                    self._log(StdUsers.DEV, StdLevels.INFO, "Forwarding message "
                    "from local node closed normally (remote node closed).")
                    break
                except Exception as e:
                    self._log(StdUsers.USER, StdLevels.INFO, "Forwarding message "
                    "from local node closed with an unknown error in data sending.")

                    self._log(StdUsers.DEV, StdLevels.ERROR, "Forwarding message "
                    "from local node closed with an unknown "
                    "error in data sending ({}).".format(e))
                    break

        self._one_thread_stop.set()

    def send(self, received_node_name, message):
        raise NotImplementedError("Forwarder doesn't have send() method.")

    def recv(self):
        raise NotImplementedError("Forwarder doesn't have recv() method.")
