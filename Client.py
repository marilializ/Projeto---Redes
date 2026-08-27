import socket
import Shared
from Protocol import criar_handshake, parse_config


def send_message(message, connection):
    connection.sendall((message + "\n").encode())

def receive_message(connection):
    return connection.recv(1024).decode().strip()

def config_handshake():

    size = Shared.DEFAULT_MAX_MESSAGE_SIZE

    print("\n--- Configuracao Inicial da Conexao ---")
    print("[ 1 ] Envio Individual")
    print("[ 2 ] Go-Back-N (GBN)")
    print("[ 3 ] Repeticao Seletiva (SR)")
    
    while True:
        try:
            choice = int(input("Escolha o modo de operacao (1, 2 ou 3): "))
            if choice == 1:
                mode = "INDIVIDUAL"
            elif choice == 2:
                mode = "GBN"
            elif choice == 3:
                mode = "SR"
            else:
                print("Opcao invalida")
                continue
            break
        except ValueError:
            print("Digite um numero inteiro")

    
    return mode, size


def main():
    modo, tamanho = config_handshake()
    
    cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"\nConectando a {Shared.HOST}:{Shared.PORT}...")
    
    try:
        cliente_socket.connect((Shared.HOST, Shared.PORT))
        print("Conectado com sucesso!")

        proposal = criar_handshake(modo, tamanho)
        print(f"Enviando proposal de handshake: {proposal}")
        send_message(proposal, cliente_socket)
        
        response = receive_message(cliente_socket)
        print(f"Resposta do servidor: {response}")
        
        try:
            window_size = parse_config(response)
            print(f"Janela definida pelo servidor: {window_size}")
            print("\nHandshake concluido! Prontos para transmitir.")
        except ValueError as error:
            print(f"\nFalha no handshake: {error}")
            
    except Exception as e:
        print(f"Erro: {e}")
    finally:
        cliente_socket.close()


if __name__ == "__main__":
    main()