import time
from hks_pynetwork.external import STCPSocket
import time
import threading
import socket as sock
from hks_pylib.cipher import AES_CBC, NoCipher, XorCipher, AES_CTR, SimpleSSL
from hks_pylib.logger import StandardLoggerGenerator
KEY = b"0123456789abcdef"
IV = b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff"

def test_client():
    logger_generator = StandardLoggerGenerator("client.hks_network.log")
    socket = STCPSocket(
        XorCipher(b"1"), 
        buffer_size= 7, 
        logger_generator=logger_generator,
        display= {"dev": ["error", "debug", "info", "warning"], "user": ["warning", "info"]})
    socket.connect(("127.0.0.1", 1999))
    socket.send(b"00080056789abcdefgh")
    print(socket.recv())
    socket.send(b"0123456789abcd")
    print(socket.recv())
    time.sleep(3)
    socket.close()

test_client()