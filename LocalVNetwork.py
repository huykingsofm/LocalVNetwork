import re
import time
import threading
import random
from CustomPrint import StandardPrint
from PacketBuffer import PacketBuffer
from SecureTCP import STCPSocket
from DefinedError import InvalidArgument

class ChannelException(Exception): ...
class ChannelSlotError(ChannelException): ...
class ChannelFullSlots(ChannelSlotError): ...
class ChannelObjectExists(ChannelException): ...
class ChannelMessageFormatError(ChannelException): ...
class ChannelClosed(ChannelException): ...

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
        self.buffer = PacketBuffer(decoder= None)
        self.process = threading.Event()
        self._closed = False

    def send(self, received_node_name, message):
        if isinstance(message, bytes) == False:
            raise InvalidArgument("Message must be a bytes object")

        if self._closed:
            raise ChannelClosed("Channel closed")
        
        try:
            slot_of_received_node_name = LocalNode.node_names.index(received_node_name)
            received_node = LocalNode.nodes[slot_of_received_node_name]
        except:
            raise ChannelSlotError(f"No username is {received_node_name}")
            
        message = "from {}:".format(self.name).encode() + message
        received_node.buffer.push(message)
        received_node.process.set()

    def recv(self, reload_time = 0.3):
        if self._closed:
            raise ChannelClosed("Channel closed")
        
        n_try = 3
        from_user = None
        message = None
        while n_try > 0:
            if len(self.buffer) == 0 and not self._closed:
                self.process.wait()

            message = self.buffer.pop()
            if message:
                match = re.match(r"^from (\w+):(.+)", message.decode())
                if match == None:
                    raise ChannelMessageFormatError("Message format is wrong")

                from_user = match.group(1)
                message = match.group(2)
                break
            else:
                n_try -= 1
                time.sleep(reload_time)

        self.process.clear()
        if message == None and self._closed and n_try == 0:
            raise ChannelClosed("Channel closed")

        return from_user, message.encode()

    def close(self):
        if not self._closed:
            self.process.set()
            self._closed = True
            my_slot = LocalNode.node_names.index(self.name)
            del LocalNode.node_names[my_slot]
            del LocalNode.nodes[my_slot]
            self.name = None
            del self.buffer

class ForwardNode(LocalNode):
    def __init__(self, node: LocalNode, socket: STCPSocket, name = None, verbosities: tuple = ("error", )):
        self.node = node
        self.remote_client = socket
        super().__init__(name)
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
        if self.node.process.is_set() == False:
            self.node.process.set()

        self.__print__(f"Stopped", "notification")

    def _wait_message_from_remote(self):
        while not self._closed:
            try:
                data = self.remote_client.recv()
            except Exception as e:
                self.__print__(repr(e), "warning")
                break
            if data:
                super().send(self.node.name, data)    
        
        self.forward_process.set()
        self.__print__("Waiting from remote ended", "notification")

    def _wait_message_from_node(self):
        while not self._closed:
            try:
                _, data = super().recv()
            except Exception as e:
                self.__print__(repr(e), "warning")
                break
            if data:
                self.remote_client.send(data)

        self.forward_process.set()
        self.__print__("Waiting from node ended", "notification")

    def send(self, received_node_name, message):
        raise NotImplementedError

    def recv(self):
        raise NotImplementedError
    
if __name__ == "__main__":
    # Test your code
    pass