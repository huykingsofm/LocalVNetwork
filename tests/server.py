from hks_pynetwork.external import STCPSocket
from hks_pynetwork.external import STCPSocketClosed
from hks_pylib.cipher import XorCipher, AES_CBC, AES_CTR, SimpleSSL
import socket as sock
import time
import select
from hks_pylib.logger import StandardLoggerGenerator

KEY = b"0123456789abcdef"
IV = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff"

def test_server():
    logger_generator = StandardLoggerGenerator("server.hks_network.log")
    socket = STCPSocket(
            XorCipher(b"1"),
            buffer_size= 5,
            logger_generator=logger_generator,
            display={"user": ["info", "warning"], "dev": ["info", "warning", "error", "debug"]}
        )
    socket.bind(("127.0.0.1", 1999))
    socket.listen()
    client, _ = socket.accept()
    #client.settimeout(0)
    while True:
        data = client.recv()
        client.send(b"huykingsofm")
        print(data)

test_server()