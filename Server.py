import socket
from Shared import HOST, PORT, DEFAULT_WINDOW_SIZE
from Protocol import parse_handshake, create_config, send_packet, recv_packet

def start_server():
    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )
    
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    print(f"servidor aguardando conexão em {HOST}:{PORT}...")
    client_socket, client_address = server_socket.accept()
    print(f"cliente conectado: {client_address}")

    try:
        message = recv_packet(client_socket)
        print(f"handshake recebido: {message}")

        try:
            mode, max_message_size = parse_handshake(message)
            print(f"modo: {mode}")
            print(f"tamanho máximo: {max_message_size}")
            response = create_config(DEFAULT_WINDOW_SIZE)
            send_packet(client_socket, response)
            print(f"configuração enviada: {response}")

        except ValueError as error:
            print(f"erro no handshake: {error}")
            send_packet(client_socket, f"ERROR|{error}")

    except ConnectionError as error:
        print(f"conexão perdida: {error}")

    finally:
        client_socket.close()
        server_socket.close()
        print("conexão encerrada.")


if __name__ == "__main__":
    start_server()