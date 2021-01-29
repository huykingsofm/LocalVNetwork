import re
import time
import errno
import threading
import random
from .CustomPrint import StandardPrint
from .PacketBuffer import PacketBuffer
from .SecureTCP import STCPSocket, STCPSocketClosed, RELOAD_TIME

class ChannelException(Exception): ...
class ChannelSlotError(ChannelException): ...
class ChannelFullSlots(ChannelSlotError): ...
class ChannelObjectExists(ChannelException): ...
class ChannelMessageFormatError(ChannelException): ...
class ChannelClosed(ChannelException): ...

class AnythingBuffer(object):
    def __init__(self):
        self.__buffer__ = []

    def push(self, source, message, obj = None):
        self.__buffer__.append({"source": source, "message": message, "obj": obj})

    def pop(self, source = None):
        if len(self.__buffer__) == 0:
            return None, None, None

        idx = 0
        if source != None:
            for i, packet in enumerate(self.__buffer__):
                if packet["source"] == source:
                    idx = i
                    break

        packet = self.__buffer__[idx]
        del self.__buffer__[idx]

        return packet["source"], packet["message"], packet["obj"]

    def __len__(self):
        return len(self.__buffer__)

MAX_NODES = 8
class LocalNode(object):
    nodes = []
    node_names = []
    def __init__(self, name = None):
        if name == None:
            while name == None or name in LocalNode.node_names:
                name = str(random.randint(1000000, 9999999))

        if name in LocalNode.node_names:
            raise ChannelObjectExists(f"Name {name} inuse")

        if len(LocalNode.nodes) >= MAX_NODES:
            raise ChannelFullSlots("No available slot in Local Node")

        LocalNode.node_names.append(name)
        LocalNode.nodes.append(self)
        self.name = name
        self.__buffer__ = AnythingBuffer()
        self.__process__ = threading.Event()
        self._closed = False

    def send(self, destination_name: str, message: bytes, obj = None):
        if isinstance(message, bytes) == False:
            raise Exception("Message must be a bytes object")

        if self._closed:
            raise ChannelClosed("Channel closed")
        
        try:
            slot_of_destination = LocalNode.node_names.index(destination_name)
            destination_node: LocalNode = LocalNode.nodes[slot_of_destination]
        except:
            raise ChannelSlotError(f"No username is {destination_name}")
            
        destination_node.__buffer__.push(self.name, message, obj)
        destination_node.__process__.set()

    def recv(self, source = None):
        if self._closed:
            raise ChannelClosed("Channel closed")
        
        if len(self.__buffer__) == 0 and not self._closed:
            self.__process__.wait()
        self.__process__.clear()
        
        if self._closed:
            raise ChannelClosed("Channel closed")
        
        return self.__buffer__.pop(source)

    def close(self):
        if not self._closed:
            self._closed = True
            self.__process__.set()
            my_slot = LocalNode.node_names.index(self.name)
            del LocalNode.node_names[my_slot]
            del LocalNode.nodes[my_slot]
            self.name = None
            del self.__buffer__

class ForwardNode(LocalNode):
    def __init__(self, 
        node: LocalNode, 
        socket: STCPSocket, 
        name = None, 
        implicated_die = False,
        reload_time = RELOAD_TIME,
        verbosities: tuple = {"user": ["error"], "dev": ["error"]}
    ):
        self.node = node
        self.remote_client = socket
        super().__init__(name)
    
        self.implicated_die = implicated_die
        if verbosities == None:
            verbosities = socket.__print__.verbosities
    
        self.__print__ = StandardPrint(f"ForwardNode {self.name}", verbosities)
        self.forward_process = threading.Event()

    def start(self):
        t1 = threading.Thread(target= self._wait_message_from_node)
        t1.setDaemon(True)
        t1.start()

        t2 = threading.Thread(target= self._wait_message_from_remote)
        t2.setDaemon(True)
        t2.start()

        self.forward_process.wait()
        self.close()
        if self.implicated_die:
            self.node.close()
            self.remote_client.close()
        else:
            if self.node.__process__.is_set() == False:
                self.node.__process__.set()

        self.__print__("user", "notification", "Stopped")

    def _wait_message_from_remote(self):
        while not self._closed:
            try:
                data = self.remote_client.recv()
            except STCPSocketClosed:
                break
            except Exception as e:
                self.__print__("user", "error", "Unknown error")
                self.__print__("dev", "error", repr(e))
                break
            if data:
                super().send(self.node.name, data)    
        
        self.forward_process.set()
        self.__print__("user", "notification", "Waiting from remote ended")

    def _wait_message_from_node(self):
        while not self._closed:
            try:
                _, message, _ = super().recv()
            except AttributeError as e: # after close forwarder, it dont have buffer attribute --> error
                break
            except Exception as e:
                self.__print__("user", "error", "Unknown error")
                self.__print__("dev", "error", repr(e))
                break
            if message:
                self.remote_client.send(message)

        self.forward_process.set()
        self.__print__("user", "notification", "Waiting from node ended")

    def send(self, received_node_name, message):
        raise NotImplementedError

    def recv(self):
        raise NotImplementedError