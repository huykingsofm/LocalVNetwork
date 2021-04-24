import random
import threading
from hks_pylib.logger import LoggerGenerator
from hks_pynetwork.external import STCPSocket, STCPSocketClosedError

from hks_pynetwork.errors.internal import ChannelSlotError, ChannelClosedError


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
            logger_generator: LoggerGenerator = ...,
            display: dict = ...
        ):
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
        self._print = logger_generator.generate(
            name,
            display
        )
        self._print("dev", "info", "The node join to Local Node.")

    def send(self, destination_name: str, message: bytes, obj: object = None):
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

    def recv(self, source=None):
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
            self.name = None
            self.__recv_lock.release()
            self._print("dev", "info", "The node leaves from Local Node.")


class ForwardNode(LocalNode):
    def __init__(
                    self,
                    node: LocalNode,
                    socket: STCPSocket,
                    name: str,
                    implicated_die: bool = False,
                    logger_generator: LoggerGenerator = ...,
                    display: tuple = ...
                ):
        assert node is None or isinstance(node, LocalNode)
        assert socket is None or isinstance(socket, STCPSocket)
            
        self._node = node
        self._socket = socket
        super().__init__(
            name=name,
            logger_generator=logger_generator,
            display=display
        )

        self._implicated_die = implicated_die
        if display is None:
            display = socket._print.display

        self.__print = logger_generator.generate(f"{self.name}", display)
        self._one_thread_stop = threading.Event()

    def set_node(self, node: LocalNode):
        assert isinstance(node, LocalNode)
        self._node = node
    
    def set_socket(self, socket: STCPSocket):
        assert isinstance(socket, STCPSocket)
        self._socket = socket

    def start(self):
        self.__print("dev", "info", "Start forward between local "
        "node and remote node.")
        assert self._node and self._socket

        t1 = threading.Thread(target=self._wait_message_from_node)
        t1.setDaemon(True)
        t1.start()

        t2 = threading.Thread(target=self._wait_message_from_remote)
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

        self.__print("dev", "info", "Stop completely.")

    def _wait_message_from_remote(self):
        while not self._closed:
            try:
                data = self._socket.recv()
            except STCPSocketClosedError:
                self.__print("dev", "info", "Waiting message from remote "
                    "close because STCP Socket closed.")
                break
            except Exception as e:
                self.__print("user", "info", "Unknown error in waiting "
                    "message from remote client.")
                self.__print("dev", "error", 
                    "Unknown error in waiting message from remote "
                    "client ({}).".format(repr(e))
                )
                break
            if data:
                try:
                    super().send(self._node.name, data)
                except ChannelClosedError:
                    self.__print("dev", "info", "Waiting message from remote "
                    "close because channel closed.")
                    break
                except Exception as e:
                    self.__print("user", "info", "Unknown error in sending "
                        "data to node.")
                    self.__print("dev", "error", "Unknown error in sending "
                        "data to node ({}).".format(repr(e)))
                    break
        self._one_thread_stop.set()

    def _wait_message_from_node(self):
        while not self._closed:
            try:
                _, message, _ = super().recv()
            except AttributeError as e:  
                # after close forwarder, it dont have buffer attribute
                self.__print("dev", "warning", "{} in waiting message "
                    "from local node.".format(e))
                self.__print("user", "info", "Waiting message from local "
                    "node close because channel closed.")
                break
            except ChannelClosedError:
                self.__print("user", "info", "Waiting message from local "
                    "node close because channel closed.")
                self.__print("dev", "info", "Waiting message from local "
                    "node close because channel closed.")
                break
            except Exception as e:
                self.__print("user", "info", "Unknown error in waiting "
                    "message from local node.")
                self.__print("dev", "error", "Unknown error in waiting "
                    "message from local node ({}).".format(repr(e)))
                break
            if message:
                try:
                    self._socket.send(message)
                except STCPSocketClosedError:
                    self.__print("dev", "info", " Waiting message from local node "
                    "close because STCP Socket closed.")
                    break

        self._one_thread_stop.set()

    def send(self, received_node_name, message):
        raise NotImplementedError("Forwarder doesn't have send() method.")

    def recv(self):
        raise NotImplementedError("Forwarder doesn't have recv() method.")
