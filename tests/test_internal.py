import os
import random
import threading

from hks_pynetwork.internal import LocalNode, ForwardNode
from hks_pylib.logger import StandardLoggerGenerator
from hks_pynetwork.external import STCPSocket
from hks_pylib.cryptography.ciphers.symmetrics import AES_CTR, AES_CBC

logger_generator = StandardLoggerGenerator("tests/test_internal.log")
KEY = os.urandom(32)
N_SAMPLE_DATA = random.randint(10, 20)
NODE1_SAMPLE_DATA_LIST = [os.urandom(random.randint(100, 200)) for _ in range(N_SAMPLE_DATA)]
NODE2_SAMPLE_DATA_LIST = [os.urandom(random.randint(100, 200)) for _ in range(N_SAMPLE_DATA)]


def node1():
    node = LocalNode(
        name="NODE1",
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )

    err = None
    for node1_data, node2_data in zip(NODE1_SAMPLE_DATA_LIST, NODE2_SAMPLE_DATA_LIST):
        node.send("NODE2", node1_data)
        source, data, obj = node.recv()
        if source != "NODE2":
            err = "ERROR NODE1 SOURCE NOT MATCH"
        if data != node2_data:
            err = "ERROR NODE1 DATA NOT MATCH"
    node.close()
    if err:
        raise Exception(err)

def node2():
    node = LocalNode(
        name="NODE2",
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )

    err = None
    for node1_data, node2_data in zip(NODE1_SAMPLE_DATA_LIST, NODE2_SAMPLE_DATA_LIST):
        source, data, obj = node.recv()
        node.send("NODE1", node2_data)
        if source != "NODE1":
            err = "ERROR NODE2 SOURCE NOT MATCH"
        if data != node1_data:
            err = "ERROR NODE2 DATA NOT MATCH"
    node.close()
    if err:
        raise Exception(err)

def test_local_node():
    t1 = threading.Thread(target=node2)
    t1.start()
    t2 = threading.Thread(target=node1)
    t2.start()
    t1.join()
    t2.join()

def server():
    server = STCPSocket(
        cipher=AES_CTR(KEY),
        name="Server",
        buffer_size=1024,
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )

    server.bind(("127.0.0.1", 19999))
    server.listen()
    socket, addr = server.accept()
    
    err = None
    for node1_data, node2_data in zip(NODE1_SAMPLE_DATA_LIST, NODE2_SAMPLE_DATA_LIST):
        data = socket.recv()
        if data != node2_data:
            err = "SERVER ERROR DATA NOT MATCH"
            break
        socket.send(node1_data)

    socket.close()
    if err:
        raise Exception(err)

    socket.close()

def client():
    client = STCPSocket(
        cipher=AES_CTR(KEY),
        name="Client",
        buffer_size=1024,
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )
    client.connect(("127.0.0.1", 19999))
    
    node = LocalNode(
        "CLIENT",
        logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )
    forwarder = ForwardNode(
        node=node,
        socket=client,
        name="Forwarder of client",
        implicated_die=True,
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )
    threading.Thread(target=forwarder.start).start()

    err = None
    for node1_data, node2_data in zip(NODE1_SAMPLE_DATA_LIST, NODE2_SAMPLE_DATA_LIST):
        node.send(forwarder.name, node2_data)
        source, data, obj = node.recv()
        if source != forwarder.name:
            err = "ERROR CLIENT SOURCE NOT MATCH"
            break
        if data != node1_data:
            err = "ERROR CLIENT DATA NOT MATCH"
            break

    node.close()
    if err:
        raise Exception(err)


def test_forwardnode():
    t1 = threading.Thread(target=server)
    t1.start()
    t2 = threading.Thread(target=client)
    t2.start()
    t1.join()
    t2.join()