import socket
from Shared import HOST, PORT, DEFAULT_WINDOW_SIZE
from Protocol import parse_handshake, create_config


def start_server():
    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f"servidor aguardando conexão em {HOST}:{PORT}...")
    client_socket, client_address = server_socket.accept()
    print(f"cliente conectado: {client_address}")

    try:
        data = client_socket.recv(1024)
        if not data:
            print("cliente encerrou a conexão.")
            return
        message = data.decode()
        print(f"handshake recebido: {message}")

        try:
            mode, max_message_size = parse_handshake(message)
            print(f"modo: {mode}")
            print(f"tamanho máximo: {max_message_size}")
            response = create_config(DEFAULT_WINDOW_SIZE)
            client_socket.sendall(response.encode())
            print(f"configuração enviada: {response}")

        except ValueError as error:
            print(f"erro no handshake: {error}")
            client_socket.sendall(
                f"ERROR|{error}".encode()
            )

    finally:
        client_socket.close()
        server_socket.close()
        print("conexão encerrada.")


if __name__ == "__main__":
    start_server()