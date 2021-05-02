import os
from hks_pylib.logger.standard import StdUsers
from hks_pylib.logger import Display
import random
import threading
from hks_pynetwork.external import STCPSocket
from hks_pylib.cryptography.ciphers.symmetrics import AES_CTR, AES_CBC
from hks_pylib.logger import StandardLoggerGenerator
 
logger_generator = StandardLoggerGenerator("tests/test_external.log")
KEY = os.urandom(32)
N_SAMPLE_DATA = random.randint(10, 20)
CLIENT_SAMPLE_DATA_LIST = [os.urandom(random.randint(100, 200)) for _ in range(N_SAMPLE_DATA)]
SERVER_SAMPLE_DATA_LIST = [os.urandom(random.randint(100, 200)) for _ in range(N_SAMPLE_DATA)]


def server():
    server = STCPSocket(
        cipher=AES_CTR(KEY),
        name="Server",
        buffer_size=1024,
        logger_generator=logger_generator,
        display={StdUsers.USER: Display.ALL, StdUsers.DEV: Display.ALL}
    )

    server.bind(("127.0.0.1", 9999))
    server.listen()
    socket, addr = server.accept()
    
    err = None
    for client_data, server_data in zip(CLIENT_SAMPLE_DATA_LIST, SERVER_SAMPLE_DATA_LIST):
        data = socket.recv()
        if data != client_data:
            err = "SERVER ERROR DATA NOT MATCH"
            break
        socket.send(server_data)

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
        display={StdUsers.USER: Display.ALL, StdUsers.DEV: Display.ALL}
    )
    client.connect(("127.0.0.1", 9999))

    err = None
    for client_data, server_data in zip(CLIENT_SAMPLE_DATA_LIST, SERVER_SAMPLE_DATA_LIST):
        client.send(client_data)
        data = client.recv()
        if data != server_data:
            err = "ERROR CLIENT DATA NOT MATCH"
            break

    client.close()
    if err:
        raise Exception(err)


def test_client_server():
    t1 = threading.Thread(target=server)
    t1.start()
    t2 = threading.Thread(target=client)
    t2.start()
    t1.join()
    t2.join()

if __name__ == "__main__":
    client()