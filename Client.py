import socket
import Shared
from Protocol import criar_handshake, parse_config, send_packet, recv_packet



def config_handshake():

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

    while True:
        try:
            size = int(input(f"Digite o size maximo do bloco (min. {Shared.MIN_MESSAGE_SIZE}): "))
            if size < Shared.MIN_MESSAGE_SIZE:
                print(f"size invalido! O size minimo permitido é {Shared.MIN_MESSAGE_SIZE}.")
                continue
            break
        except ValueError:
            print("Digite um numero inteiro")

    
    return mode, size


def main():
    modo, size = config_handshake()
    
    cliente_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print(f"\nConectando a {Shared.HOST}:{Shared.PORT}...")
    
    try:
        cliente_socket.connect((Shared.HOST, Shared.PORT))
        print("Conectado com sucesso!")

        proposal = criar_handshake(modo, size)
        print(f"Enviando proposal de handshake: {proposal}")
        send_packet(cliente_socket, proposal)
        
        response = recv_packet(cliente_socket)
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