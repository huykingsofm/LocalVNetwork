from LocalVNetwork.LocalVNetwork import LocalNode, ForwardNode, STCPSocket
import threading

if __name__ == "__main__":
    server_socket = STCPSocket(verbosities= ("error", "warning", "notification"))
    server_socket.bind(("127.0.0.1", 9999))
    server_socket.listen()

    client_socket, _ = server_socket.accept()

    server_node = LocalNode()
    print(f"server {server_node.name}")
    
    forwarder = ForwardNode(server_node, client_socket, verbosities = ("error", "warning", "notification"))
    print(f"forwarder {forwarder.name}")
    
    t = threading.Thread(target= forwarder.start)
    t.start()

    while True:
        try:
            print(server_node.recv())
            data = input(">>> ").encode()
            server_node.send(forwarder.name, data)
        except Exception as e:
            print("Last: " + repr(e))
            break