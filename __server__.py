from LocalVNetwork import LocalNode, ForwardNode, STCPSocket
import threading

if __name__ == "__main__":
    server_socket = STCPSocket()
    server_socket.bind(("127.0.0.1", 9999))
    server_socket.listen()

    client_socket, _ = server_socket.accept()

    server_node = LocalNode()
    print(f"server {server_node.name}")
    
    forwarder = ForwardNode(server_node, client_socket, verbosities = ("error", "warning"))
    print(f"forwarder {forwarder.name}")
    
    t = threading.Thread(target= forwarder.serve)
    t.start()

    while True:
        try:
            print(server_node.recv())
        except:
            break