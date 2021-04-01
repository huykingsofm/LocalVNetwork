import random
import threading
from .lib.selective_print import StandardPrint
from .external import STCPSocket, STCPSocketClosed


class ChannelException(Exception): ...
class ChannelSlotError(ChannelException): ...
class ChannelFullSlots(ChannelSlotError): ...
class ChannelObjectExists(ChannelException): ...
class ChannelMessageFormatError(ChannelException): ...
class ChannelClosed(ChannelException): ...


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

    def __init__(self, name: str = None):
        if name is None:
            while name is None or name in LocalNode.node_names:
                name = str(random.randint(1000000, 9999999))

        if name in LocalNode.node_names:
            raise ChannelObjectExists(f"Name {name} is in use")

        if len(LocalNode.nodes) >= LocalNode.MAX_NODES:
            raise ChannelFullSlots("No available slot in Local Node list")

        LocalNode.node_names.append(name)
        LocalNode.nodes.append(self)
        self.name = name
        self._buffer = ChannelBuffer()
        self._closed = False
        self.__buffer_available = threading.Event()
        self.__send_lock = threading.Lock()
        self.__recv_lock = threading.Lock()

    def send(self, destination_name: str, message: bytes, obj: object = None):
        self.__send_lock.acquire()
        if isinstance(message, bytes) is False:
            raise Exception("Message must be a bytes object")

        if self._closed:
            raise ChannelClosed("Channel closed")

        try:
            slot_of_destination = LocalNode.node_names.index(destination_name)
            destination_node: LocalNode = LocalNode.nodes[slot_of_destination]
        except ValueError:
            raise ChannelSlotError(f"Channel name {destination_name} doesn't exist")

        destination_node._buffer.push(self.name, message, obj)
        destination_node.__buffer_available.set()
        self.__send_lock.release()

    def recv(self, source=None):
        self.__recv_lock.acquire()
        if self._closed:
            raise ChannelClosed("Channel closed")

        if len(self._buffer) == 0 and not self._closed:
            self.__buffer_available.wait()
        self.__buffer_available.clear()

        if self._closed:
            raise ChannelClosed("Channel closed")

        source, msg, obj = self._buffer.pop(source)
        self.__recv_lock.release()
        return source, msg, obj

    def close(self):
        self.__recv_lock.acquire()
        if not self._closed:
            self._closed = True
            self.__buffer_available.set()
            my_slot = LocalNode.node_names.index(self.name)
            del LocalNode.node_names[my_slot]
            del LocalNode.nodes[my_slot]
            self.name = None
            del self._buffer
        self.__recv_lock.release()


class ForwardNode(LocalNode):
    def __init__(
                    self,
                    node: LocalNode = None,
                    socket: STCPSocket = None,
                    name: str = None,
                    implicated_die: bool = False,
                    verbosities: tuple = {"user": ["error"], "dev": ["error"]}
                ):
        assert node is None or isinstance(node, LocalNode)
        assert socket is None or isinstance(socket, STCPSocket)
            
        self._node = node
        self._socket = socket
        super().__init__(name)

        self._implicated_die = implicated_die
        if verbosities is None:
            verbosities = socket.__print.verbosities

        self.__print = StandardPrint(f"ForwardNode {self.name}", verbosities)
        self._one_thread_stop = threading.Event()

    def set_node(self, node):
        assert node is None or isinstance(node, LocalNode)
        self._node = node
    
    def set_socket(self, socket):
        assert socket is None or isinstance(socket, STCPSocket)
        self._socket = socket

    def start(self):
        if not self._node or not self._socket:
            raise Exception("ForwardNode must be initilized with both node and socket")

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
            if self._node.__buffer_available.is_set() is False:
                self._node.__buffer_available.set()

        self.__print("user", "notification", "Stopped")

    def _wait_message_from_remote(self):
        while not self._closed:
            try:
                data = self._socket.recv()
            except STCPSocketClosed:
                break
            except Exception as e:
                self.__print("user", "error", "Unknown error")
                self.__print("dev", "error", repr(e))
                break
            if data:
                try:
                    super().send(self._node.name, data)
                except ChannelClosed:
                    self.__print("user", "notification", "Channel closed")
                    break

        self._one_thread_stop.set()
        self.__print("user", "notification", "Waiting from remote ended")

    def _wait_message_from_node(self):
        while not self._closed:
            try:
                _, message, _ = super().recv()
            except AttributeError:  # after close forwarder, it dont have buffer attribute --> error
                break
            except ChannelClosed:
                self.__print("user", "notification", "Channel closed")
                break
            except Exception as e:
                self.__print("user", "error", "Unknown error")
                self.__print("dev", "error", repr(e))
                break
            if message:
                self._socket.send(message)

        self._one_thread_stop.set()
        self.__print("user", "notification", "Waiting from node ended")

    def send(self, received_node_name, message):
        raise NotImplementedError

    def recv(self):
        raise NotImplementedError
