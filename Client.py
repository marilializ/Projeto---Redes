import socket
import Shared
from Protocol import (
    criar_handshake, parse_config, send_packet, recv_packet,
    split_message, create_data, create_fin, parse_packet,
)


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
            size = int(input(f"Digite o tamanho maximo da mensagem (min. {Shared.MIN_MESSAGE_SIZE}): "))
            if size < Shared.MIN_MESSAGE_SIZE:
                print(f"Tamanho invalido! O minimo permitido e {Shared.MIN_MESSAGE_SIZE}.")
                continue
            break
        except ValueError:
            print("Digite um numero inteiro")

    return mode, size


def read_message(max_size):
    while True:
        text = input(f"\nDigite a mensagem a enviar (max. {max_size} caracteres): ")
        if not text:
            print("A mensagem nao pode ser vazia.")
            continue
        if len(text) > max_size:
            print(f"Mensagem muito longa ({len(text)} caracteres).")
            continue
        return text


def wait_response(sock, seq):
    # Espera ACK/NAK do pacote 'seq'. Retorna "ACK", "NAK" ou "TIMEOUT".
    while True:
        try:
            pkt = parse_packet(recv_packet(sock))
        except socket.timeout:
            return "TIMEOUT"
        except ValueError as error:
            print(f"[CLIENTE] pacote invalido ignorado: {error}")
            continue

        if pkt["type"] in ("ACK", "NAK") and pkt["seq"] == seq:
            return pkt["type"]

        print(f"[CLIENTE] pacote inesperado ignorado: {pkt}")


def send_individual(sock, chunks):
    for seq, payload in enumerate(chunks):
        packet = create_data(seq, payload)

        while True:
            send_packet(sock, packet)
            print(f"[CLIENTE] -> DATA SEQ={seq} '{payload}'")

            result = wait_response(sock, seq)
            if result == "ACK":
                print(f"[CLIENTE] <- ACK SEQ={seq}")
                break
            if result == "NAK":
                print(f"[CLIENTE] <- NAK SEQ={seq}, retransmitindo")
            else:
                print(f"[CLIENTE] timeout SEQ={seq}, retransmitindo")


def close_session(sock, total):
    fin = create_fin(total)
    while True:
        send_packet(sock, fin)
        print(f"[CLIENTE] -> FIN TOTAL={total}")
        try:
            pkt = parse_packet(recv_packet(sock))
        except socket.timeout:
            print("[CLIENTE] timeout no FIN, retransmitindo")
            continue
        except ValueError:
            continue

        if pkt["type"] == "FINACK":
            print("[CLIENTE] <- FINACK")
            return


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
        except ValueError as error:
            print(f"\nFalha no handshake: {error}")
            return

        print(f"Janela definida pelo servidor: {window_size}")
        print("\nHandshake concluido! Prontos para transmitir.")

        text = read_message(size)
        chunks = split_message(text)
        print(f"\nMensagem dividida em {len(chunks)} pacotes: {chunks}\n")

        # A partir daqui o temporizador fica ativo
        cliente_socket.settimeout(Shared.TIMEOUT)

        if modo == "INDIVIDUAL":
            send_individual(cliente_socket, chunks)
        else:
            print(f"Modo {modo} ainda nao implementado.")
            return

        close_session(cliente_socket, len(chunks))
        print("\nTransmissao concluida!")

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        cliente_socket.close()


if __name__ == "__main__":
    main()