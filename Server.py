# Servidor: aceita um cliente, valida o handshake, responde com CONFIG e recebe
# os pacotes no modo pedido (INDIVIDUAL, GBN ou SR). Verifica o checksum de
# cada pacote, decifra, confirma com ACK/NAK/ACKG e remonta a mensagem.
# Atende uma unica transmissao e encerra.

import socket
import time
from Shared import HOST, PORT, DEFAULT_WINDOW_SIZE, WINDOW_SCHEDULE, SERVER_ACK_MODE, TIMEOUT
from Protocol import (
    parse_handshake, create_config, send_packet, recv_packet,
    parse_packet, verify_checksum, create_ack, create_nak, create_finack,
    create_window, create_ackg
)
from Cipher import decrypt_payload, to_hex


def open_data(sock, pkt, key):
    # Ordem encrypt-then-MAC: 1) checksum sobre o payload cifrado (hex);
    # 2) so se estiver integro, decifra. Pacote corrompido recebe NAK sem
    # ser decifrado. Retorna o texto claro, ou None se mandou NAK.
    seq, cipher_hex = pkt["seq"], pkt["payload"]

    if not verify_checksum(seq, cipher_hex, pkt["chk"]):
        print(f"[SERVIDOR] checksum invalido SEQ={seq} -> NAK")
        send_packet(sock, create_nak(seq))
        return None

    try:
        text = decrypt_payload(cipher_hex, key)
    except ValueError as error:
        print(f"[SERVIDOR] falha ao decifrar SEQ={seq} ({error}) -> NAK")
        send_packet(sock, create_nak(seq))
        return None

    print(f"[SERVIDOR] SEQ={seq} cifrado={cipher_hex} -> decifrado '{text}'")
    return text

# Aplica WINDOW_SCHEDULE: se o proximo SEQ esperado tem uma mudanca de janela
# agendada, troca a janela do servidor e avisa o cliente com WINDOW.
# E chamada depois de receber um pacote, entao a chave 0 nunca dispara; ela
# so documenta a janela inicial.
def update_window_if_needed(sock, expected_seq, current_window):
    if expected_seq in WINDOW_SCHEDULE and WINDOW_SCHEDULE[expected_seq] != current_window:
        new_window = WINDOW_SCHEDULE[expected_seq]
        print(f"[SERVIDOR] mudando janela de {current_window} para {new_window}")
        send_packet(sock, create_window(new_window))
        return new_window
    return current_window

# Trata o FIN nos modos GBN e SR. Devolve True se a sessao pode terminar.
# - Se o TOTAL do FIN nao bate com o que foi entregue, ainda faltam pacotes:
#   recusa o FIN e manda `fallback_packet` (NAK/ACKG) para o cliente
#   retransmitir o que falta.
# - Se bate, manda FINACK e entra em TIME-WAIT (como no TCP): fica 3s
#   respondendo a FINs repetidos, caso o FINACK tenha se perdido.
# O parametro timeout_limit nao e usado; o TIME-WAIT esta fixo em 3s.
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
            # captura qualquer erro, inclusive ConnectionError quando o cliente
            # fecha a conexao; nesse caso o laco continua ate completar os 3s
            except:
                pass
        return True

# Modo INDIVIDUAL (stop-and-wait): aceita so o SEQ esperado e confirma cada
# pacote com ACK. Nao usa timeout no servidor: quem retransmite e o cliente.
def receive_individual(sock, key):
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
            seq = pkt["seq"]
            payload = open_data(sock, pkt, key)
            if payload is None:
                continue

            if seq == expected_seq:
                received.append(payload)
                expected_seq += 1
                print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' -> ACK")
                send_packet(sock, create_ack(seq))
            elif seq < expected_seq:
                # duplicado: o ACK anterior se perdeu e o cliente retransmitiu.
                # Confirma de novo, mas nao entrega o pacote outra vez.
                print(f"[SERVIDOR] <- DATA SEQ={seq} duplicado -> ACK")
                send_packet(sock, create_ack(seq))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora de ordem, descartado")

        elif pkt["type"] == "FIN":
            # diferente de handle_fin: aqui o FIN e aceito mesmo se o TOTAL
            # nao bater (so registra o aviso) e nao ha TIME-WAIT
            if pkt["total"] != len(received):
                print(f"[SERVIDOR] aviso: FIN indica {pkt['total']} pacotes, recebidos {len(received)}")
            print("[SERVIDOR] <- FIN -> FINACK")
            send_packet(sock, create_finack())
            return "".join(received)

        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")


# Modo Go-Back-N: o receptor nao tem buffer. Aceita so o SEQ esperado e
# descarta qualquer pacote fora de ordem.
# No modo GROUP o ACK e cumulativo e enviado quando um lote fecha
# (expected_seq multiplo da janela atual, contado desde o SEQ 0) ou quando
# o servidor fica TIMEOUT segundos sem receber nada.
def receive_gbn(sock, key):
    expected_seq = 0
    received = []
    current_window = DEFAULT_WINDOW_SIZE
    sock.settimeout(TIMEOUT)

    while True:
        try:
            message = recv_packet(sock)
            pkt = parse_packet(message)
        except socket.timeout:
            # silencio no canal: confirma o que ja chegou em ordem, para o
            # cliente nao ficar esperando um lote que nao vai fechar
            # (ex.: ultimo lote menor que a janela)
            if SERVER_ACK_MODE == "GROUP" and expected_seq > 0:
                print(f"[SERVIDOR] timeout de recepção -> enviando ACK cumulativo {expected_seq - 1}")
                send_packet(sock, create_ack(expected_seq - 1))
            continue
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq = pkt["seq"]
            payload = open_data(sock, pkt, key)
            if payload is None:
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
                # fora de ordem ou duplicado: descarta e repete o ACK do ultimo
                # pacote recebido em ordem, para o cliente saber de onde voltar
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora de ordem (esperado {expected_seq}), descartado")
                if expected_seq > 0:
                    send_packet(sock, create_ack(expected_seq - 1))

        elif pkt["type"] == "FIN":
            # se faltar pacote, o NAK do SEQ esperado faz o cliente voltar nele
            if handle_fin(sock, pkt, len(received), create_nak(expected_seq)):
                return "".join(received)
        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")


# Modo Repeticao Seletiva: o receptor aceita pacotes fora de ordem dentro da
# janela e os guarda no buffer ate poder entrega-los em ordem.
#   rcv_base = proximo SEQ a ser entregue em ordem
#   buffer   = {seq: texto} dos pacotes recebidos e ainda nao entregues
#   janela de recepcao = [rcv_base, rcv_base + current_window)
def receive_sr(sock, initial_window, key):
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
            # silencio no canal: reconfirma o que esta no buffer (pacotes ja
            # entregues nao entram nesta lista)
            if SERVER_ACK_MODE == "GROUP" and len(buffer) > 0:
                seqs = sorted(list(buffer.keys()))
                print(f"[SERVIDOR] timeout de recepção -> enviando ACKG para buffer {seqs}")
                send_packet(sock, create_ackg(seqs))
            continue
        except ValueError as error:
            print(f"[SERVIDOR] pacote invalido descartado: {error}")
            continue

        if pkt["type"] == "DATA":
            seq = pkt["seq"]
            payload = open_data(sock, pkt, key)
            if payload is None:
                continue

            # dentro da janela de recepcao: guarda e entrega o que estiver em ordem
            if rcv_base <= seq < rcv_base + current_window:
                if SERVER_ACK_MODE == "INDIVIDUAL":
                     send_packet(sock, create_ack(seq))
                     
                if seq not in buffer:
                    buffer[seq] = payload
                    print(f"[SERVIDOR] <- DATA SEQ={seq} '{payload}' guardado no buffer")
                else:
                    print(f"[SERVIDOR] <- DATA SEQ={seq} duplicado")

                # lista tirada ANTES da entrega abaixo, para o ACKG incluir
                # tambem os pacotes que vao sair do buffer agora
                pacotes_confirmados = sorted(list(buffer.keys()))

                # entrega em ordem: enquanto o proximo SEQ esperado estiver no
                # buffer, passa para a mensagem e avanca a janela
                while rcv_base in buffer:
                    received.append(buffer.pop(rcv_base))
                    print(f"[SERVIDOR] SEQ={rcv_base} entregue em ordem")
                    rcv_base += 1
                
                if SERVER_ACK_MODE == "GROUP":
                     send_packet(sock, create_ackg(pacotes_confirmados))

                current_window = update_window_if_needed(sock, rcv_base, current_window)

            # ate uma janela atras de rcv_base: pacote ja entregue, retransmitido
            # porque a confirmacao se perdeu. So o modo INDIVIDUAL reconfirma;
            # no modo GROUP nenhuma confirmacao e reenviada aqui.
            elif rcv_base - current_window <= seq < rcv_base:
                print(f"[SERVIDOR] <- DATA SEQ={seq} ja entregue -> ACK {seq} de novo")
                if SERVER_ACK_MODE == "INDIVIDUAL":
                    send_packet(sock, create_ack(seq))
            else:
                print(f"[SERVIDOR] <- DATA SEQ={seq} fora da janela, ignorado")

        elif pkt["type"] == "FIN":
            # se faltar pacote: ACKG do que esta no buffer, ou NAK de rcv_base
            fallback = create_ackg(sorted(list(buffer.keys()))) if buffer else create_nak(rcv_base)
            if handle_fin(sock, pkt, len(received), fallback):
                return "".join(received)
        else:
            print(f"[SERVIDOR] pacote inesperado ignorado: {pkt}")

# Ponto de entrada: abre o socket, atende um cliente e encerra
def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # SO_REUSEADDR permite reiniciar o servidor logo em seguida na mesma porta
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
            mode, max_message_size, key = parse_handshake(message)
            print(f"modo: {mode}")
            print(f"tamanho máximo: {max_message_size}")
            print(f"chave de sessao: {to_hex(key)}")

            # stop-and-wait equivale a uma janela de tamanho 1
            window_size = 1 if mode == "INDIVIDUAL" else DEFAULT_WINDOW_SIZE
            
            response = create_config(window_size, SERVER_ACK_MODE)
            
            send_packet(client_socket, response)
            print(f"configuração enviada: {response}\n")

        # HELLO invalido: responde ERROR com o motivo e encerra
        except ValueError as error:
            print(f"erro no handshake: {error}")
            send_packet(client_socket, f"ERROR|{error}")
            return

        if mode == "INDIVIDUAL":
            text = receive_individual(client_socket, key)
        elif mode == "GBN":
            text = receive_gbn(client_socket, key)
        elif mode == "SR":
            text = receive_sr(client_socket, window_size, key)
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