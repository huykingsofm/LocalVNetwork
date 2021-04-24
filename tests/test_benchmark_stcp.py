import os
import time
import threading
from hks_pynetwork.external import STCPSocket
from hks_pylib.cryptography.ciphers.symmetrics import AES_CTR, AES_CBC
from hks_pylib.logger import StandardLoggerGenerator
 
logger_generator = StandardLoggerGenerator("tests/test_benchmark_stcp.log")
KEY = os.urandom(32)

SIZE_OF_DATA = 10**7

DATA = os.urandom(SIZE_OF_DATA)


def server():
    server = STCPSocket(
        cipher=AES_CTR(KEY),
        name="Server",
        buffer_size=10**6,
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )

    server.bind(("127.0.0.1", 9999))
    server.listen()
    socket, addr = server.accept()
    start = time.time()
    socket.recv()
    socket.send(DATA)
    end = time.time()
    print(end - start)

    socket.close()

def client():
    client = STCPSocket(
        cipher=AES_CTR(KEY),
        name="Client",
        buffer_size=10**6,
        logger_generator=logger_generator,
        display={"user": ["warning", "info"], "dev": ["info", "warning", "error", "debug"]}
    )
    client.connect(("127.0.0.1", 9999))

    start = time.time()
    client.send(DATA)
    data = client.recv()
    end = time.time()
    print(end - start)

    client.close()


def test_client_server():
    t1 = threading.Thread(target=server)
    t1.start()
    t2 = threading.Thread(target=client)
    t2.start()
    t1.join()
    t2.join()

if __name__ == "__main__":
    client()