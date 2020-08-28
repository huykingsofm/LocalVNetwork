from LocalVNetwork.SecureTCP import STCPSocket

if __name__ == "__main__":
    remote_socket = STCPSocket()
    remote_socket.connect(("127.0.0.1", 9999))
    while True:
        data = input(">>> ")
        remote_socket.send(data.encode())
        data = remote_socket.recv()
        print(data)