import socket
from Shared import HOST, PORT, DEFAULT_WINDOW_SIZE
from Protocol import (
    parse_handshake, create_config, send_packet, recv_packet,
    parse_packet, verify_checksum, create_ack, create_nak, create_finack,
)


def receive_individual(sock):
    expected_seq = 0
    received = []

    while True:
        message = recv_packet(sock)

        try:
            pkt = parse_packet(message)
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq, payload = pkt["seq"], pkt["payload"]

            if not verify_checksum(seq, payload, pkt["chk"]):
                print(f"[SERVIDOR] checksum invalido SEQ={seq} -> NAK")
                send_packet(sock, create_nak(seq))
                continue

            if seq == expected_seq:
                received.append(payload)
                expected_seq += 1
                print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' -> ACK")
                send_packet(sock, create_ack(seq))
            elif seq < expected_seq:
                # duplicado (o ACK anterior se perdeu): confirma de novo
                print(f"[SERVIDOR] <- DATA SEQ={seq} duplicado -> ACK")
                send_packet(sock, create_ack(seq))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora de ordem, descartado")

        elif pkt["type"] == "FIN":
            if pkt["total"] != len(received):
                print(f"[SERVIDOR] aviso: FIN indica {pkt['total']} pacotes, recebidos {len(received)}")
            print("[SERVIDOR] <- FIN -> FINACK")
            send_packet(sock, create_finack())
            return "".join(received)

        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")

def receive_gbn(sock):
    expected_seq = 0
    received = []

    while True:
        message = recv_packet(sock)

        try:
            pkt = parse_packet(message)
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq, payload = pkt["seq"], pkt["payload"]

            if not verify_checksum(seq, payload, pkt["chk"]):
                print(f"[SERVIDOR] checksum invalido SEQ={seq} -> NAK")
                send_packet(sock, create_nak(seq))
                continue

            if seq == expected_seq:
                received.append(payload)
                expected_seq += 1
                print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' -> ACK {seq}")
                send_packet(sock, create_ack(seq))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora de ordem (esperado {expected_seq}), descartado")
                if expected_seq > 0:
                    send_packet(sock, create_ack(expected_seq - 1))

        elif pkt["type"] == "FIN":
            if pkt["total"] != len(received):
                print(f"[SERVIDOR] aviso: FIN indica {pkt['total']} pacotes, recebidos {len(received)}")
            print("[SERVIDOR] <- FIN -> FINACK")
            send_packet(sock, create_finack())
            return "".join(received)

        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")

def receive_sr(sock, window_size):
    rcv_base = 0
    buffer = {}
    received = []

    while True:
        message = recv_packet(sock)

        try:
            pkt = parse_packet(message)
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq, payload = pkt["seq"], pkt["payload"]

            if not verify_checksum(seq, payload, pkt["chk"]):
                print(f"[SERVIDOR] checksum invalido SEQ={seq} -> NAK")
                send_packet(sock, create_nak(seq))
                continue

            if rcv_base <= seq < rcv_base + window_size:
                send_packet(sock, create_ack(seq))
                if seq not in buffer:
                    buffer[seq] = payload
                    print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' guardado no buffer -> ACK {seq}")
                else:
                    print(f"[SERVIDOR] <- DATA SEQ={seq} duplicado -> ACK {seq}")

                while rcv_base in buffer:
                    received.append(buffer.pop(rcv_base))
                    print(f"[SERVIDOR] SEQ={rcv_base} entregue em ordem")
                    rcv_base += 1

            elif rcv_base - window_size <= seq < rcv_base:
                print(f"[SERVIDOR] <- DATA SEQ={seq} ja entregue -> ACK {seq} de novo")
                send_packet(sock, create_ack(seq))

            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora da janela, ignorado")

        elif pkt["type"] == "FIN":
            if pkt["total"] != len(received):
                print(f"[SERVIDOR] aviso: FIN indica {pkt['total']} pacotes, recebidos {len(received)}")
            print("[SERVIDOR] <- FIN -> FINACK")
            send_packet(sock, create_finack())
            return "".join(received)

        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")


def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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

            # envio individual = janela de tamanho 1
            window_size = 1 if mode == "INDIVIDUAL" else DEFAULT_WINDOW_SIZE
            response = create_config(window_size)
            send_packet(client_socket, response)
            print(f"configuração enviada: {response}\n")

        except ValueError as error:
            print(f"erro no handshake: {error}")
            send_packet(client_socket, f"ERROR|{error}")
            return

        if mode == "INDIVIDUAL":
            text = receive_individual(client_socket)
        elif mode == "GBN":
            text = receive_gbn(client_socket)
        elif mode == "SR":
            text = receive_sr(client_socket, window_size)
        else:
            print(f"modo {mode} desconhecido.")
            return

        print(f"\n[SERVIDOR] mensagem reconstruida: '{text}'")


    except ConnectionError as error:
        print(f"conexão perdida: {error}")

    finally:
        client_socket.close()
        server_socket.close()
        print("conexão encerrada.")


if __name__ == "__main__":
    start_server()