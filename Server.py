import socket
import time
from Shared import HOST, PORT, DEFAULT_WINDOW_SIZE, WINDOW_SCHEDULE, SERVER_ACK_MODE, TIMEOUT
from Protocol import (
    parse_handshake, create_config, send_packet, recv_packet,
    parse_packet, verify_checksum, create_ack, create_nak, create_finack,
    create_window, create_ackg
)

def update_window_if_needed(sock, expected_seq, current_window):
    if expected_seq in WINDOW_SCHEDULE and WINDOW_SCHEDULE[expected_seq] != current_window:
        new_window = WINDOW_SCHEDULE[expected_seq]
        print(f"[SERVIDOR] mudando janela de {current_window} para {new_window}")
        send_packet(sock, create_window(new_window))
        return new_window
    return current_window

def handle_fin(sock, pkt, received_len, fallback_packet, timeout_limit=5):
    if pkt["total"] != received_len:
        print(f"[SERVIDOR] aviso: FIN indica {pkt['total']} pacotes, recebidos {received_len}. REJEITADO.")
        send_packet(sock, fallback_packet)
        return False
    else:
        print("[SERVIDOR] <- FIN -> FINACK")
        send_packet(sock, create_finack())
        
        print("[SERVIDOR] entrando em TIME-WAIT...")
        start_wait = time.time()
        while time.time() - start_wait < 3.0:
            try:
                msg = recv_packet(sock)
                p = parse_packet(msg)
                if p["type"] == "FIN":
                     send_packet(sock, create_finack())
            except socket.timeout:
                pass
            except:
                pass
        return True

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
    current_window = DEFAULT_WINDOW_SIZE
    sock.settimeout(TIMEOUT)

    while True:
        try:
            message = recv_packet(sock)
            pkt = parse_packet(message)
        except socket.timeout:
            if SERVER_ACK_MODE == "GROUP" and expected_seq > 0:
                print(f"[SERVIDOR] timeout de recepção -> enviando ACK cumulativo {expected_seq - 1}")
                send_packet(sock, create_ack(expected_seq - 1))
            continue
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
                
                current_window = update_window_if_needed(sock, expected_seq, current_window)

                if SERVER_ACK_MODE == "INDIVIDUAL":
                    print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' -> ACK {seq}")
                    send_packet(sock, create_ack(seq))
                else:
                    print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' recebido e loteado.")
                    if expected_seq % current_window == 0:
                         print(f"[SERVIDOR] lote de {current_window} pacotes fechado -> ACK {expected_seq - 1}")
                         send_packet(sock, create_ack(expected_seq - 1))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora de ordem (esperado {expected_seq}), descartado")
                if expected_seq > 0:
                    send_packet(sock, create_ack(expected_seq - 1))

        elif pkt["type"] == "FIN":
            if handle_fin(sock, pkt, len(received), create_nak(expected_seq)):
                return "".join(received)
        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")


def receive_sr(sock, initial_window):
    rcv_base = 0
    buffer = {}
    received = []
    current_window = initial_window
    sock.settimeout(TIMEOUT)

    while True:
        try:
            message = recv_packet(sock)
            pkt = parse_packet(message)
        except socket.timeout:
            if SERVER_ACK_MODE == "GROUP" and len(buffer) > 0:
                seqs = sorted(list(buffer.keys()))
                print(f"[SERVIDOR] timeout de recepção -> enviando ACKG para buffer {seqs}")
                send_packet(sock, create_ackg(seqs))
            continue
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq, payload = pkt["seq"], pkt["payload"]

            if not verify_checksum(seq, payload, pkt["chk"]):
                print(f"[SERVIDOR] checksum invalido SEQ={seq} -> NAK")
                send_packet(sock, create_nak(seq))
                continue

            if rcv_base <= seq < rcv_base + current_window:
                if SERVER_ACK_MODE == "INDIVIDUAL":
                     send_packet(sock, create_ack(seq))
                     
                if seq not in buffer:
                    buffer[seq] = payload
                    print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' guardado no buffer")
                else:
                    print(f"[SERVIDOR] <- DATA SEQ={seq} duplicado")

                pacotes_confirmados = sorted(list(buffer.keys()))

                while rcv_base in buffer:
                    received.append(buffer.pop(rcv_base))
                    print(f"[SERVIDOR] SEQ={rcv_base} entregue em ordem")
                    rcv_base += 1
                
                if SERVER_ACK_MODE == "GROUP":
                     send_packet(sock, create_ackg(pacotes_confirmados))

                current_window = update_window_if_needed(sock, rcv_base, current_window)

            elif rcv_base - current_window <= seq < rcv_base:
                print(f"[SERVIDOR] <- DATA SEQ={seq} ja entregue -> ACK {seq} de novo")
                if SERVER_ACK_MODE == "INDIVIDUAL":
                    send_packet(sock, create_ack(seq))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora da janela, ignorado")

        elif pkt["type"] == "FIN":
            fallback = create_ackg(sorted(list(buffer.keys()))) if buffer else create_nak(rcv_base)
            if handle_fin(sock, pkt, len(received), fallback):
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

            window_size = 1 if mode == "INDIVIDUAL" else DEFAULT_WINDOW_SIZE
            
            response = create_config(window_size, SERVER_ACK_MODE)
            
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