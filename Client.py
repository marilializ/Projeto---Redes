# Cliente: le modo e tamanho do usuario, faz o handshake, fatia a mensagem em
# pacotes de 4 caracteres e os envia no modo escolhido (INDIVIDUAL, GBN ou SR),
# retransmitindo em caso de NAK ou timeout. Termina com FIN/FINACK.

import socket
import Shared
import time
from Protocol import (
    criar_handshake, parse_config, send_packet, recv_packet,
    split_message, create_data, create_fin, parse_packet,
)
from Cipher import generate_key, to_hex


# Menu inicial: pergunta o modo de operacao e o tamanho maximo da mensagem,
# repetindo a pergunta ate receber um valor valido.
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


# Le a mensagem respeitando o tamanho maximo negociado no handshake
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


# Usada no modo INDIVIDUAL: espera a resposta para o pacote `seq` e devolve
# "ACK", "NAK" ou "TIMEOUT". Respostas de outros SEQs (ex.: ACK atrasado de um
# pacote anterior) sao ignoradas e a espera continua.
def wait_response(sock, seq):

    while True:
        try:
            pkt = parse_packet(recv_packet(sock))
        except socket.timeout:
            # o socket tem settimeout(TIMEOUT): este e o temporizador do pacote
            return "TIMEOUT"
        except ValueError as error:
            print(f"[CLIENTE] pacote invalido ignorado: {error}")
            continue

        if pkt["type"] in ("ACK", "NAK") and pkt["seq"] == seq:
            return pkt["type"]

        print(f"[CLIENTE] pacote inesperado ignorado: {pkt}")


def build_packet(seq, payload, key):
    # Unico ponto onde o cliente monta pacotes DATA (todos os modos passam aqui).
    packet = create_data(seq, payload, key)
    # PONTO DE INTEGRACAO: simulacao de erros.
    # A corrupcao deve ser aplicada AQUI, sobre `packet` ja cifrado e com
    # checksum calculado. Corromper antes de create_data so geraria texto
    # decifrado errado, sem falha de checksum (e sem NAK). Para manter o pacote
    # parseavel, troque um digito hex do payload por outro digito hex.
    return packet


def cipher_of(packet):
    # payload cifrado (hex) de um pacote DATA, so para log
    return packet.split("|", 3)[3]


# Modo INDIVIDUAL (stop-and-wait): envia um pacote e so passa para o proximo
# depois do ACK. NAK ou timeout reenviam o mesmo pacote.
def send_individual(sock, chunks, key):
    for seq, payload in enumerate(chunks):
        packet = build_packet(seq, payload, key)

        # repete ate o pacote ser confirmado
        while True:
            send_packet(sock, packet)
            print(f"[CLIENTE] -> DATA SEQ={seq} '{payload}' cifrado={cipher_of(packet)}")

            result = wait_response(sock, seq)
            if result == "ACK":
                print(f"[CLIENTE] <- ACK SEQ={seq}")
                break
            if result == "NAK":
                print(f"[CLIENTE] <- NAK SEQ={seq}, retransmitindo")
            else:
                print(f"[CLIENTE] timeout SEQ={seq}, retransmitindo")


# Modo Go-Back-N: ate `window_size` pacotes enviados sem confirmacao.
#   base       = SEQ mais antigo ainda nao confirmado
#   next_seq   = proximo SEQ a enviar
#   [base, next_seq) = pacotes enviados aguardando ACK
# Ha um unico temporizador, do pacote `base`. ACK e cumulativo (ACK n confirma
# tudo ate n). Em timeout ou NAK, volta para `base` e reenvia toda a janela.
def send_gbn(sock, chunks, window_size, key):
    total = len(chunks)
    base = 0
    next_seq = 0
    timer_start = None

    while base < total:
        # 1) preenche a janela: envia enquanto houver espaco e pacotes
        while next_seq < base + window_size and next_seq < total:
            packet = build_packet(next_seq, chunks[next_seq], key)
            send_packet(sock, packet)
            print(f"[CLIENTE] -> DATA SEQ={next_seq} '{chunks[next_seq]}' cifrado={cipher_of(packet)}   "
                  f"janela=[{base}..{base + window_size - 1}]")
            # o temporizador e do pacote mais antigo: so liga se este for a base
            if base == next_seq:
                timer_start = time.monotonic()
            next_seq += 1

        # 2) espera resposta so pelo tempo que falta para o temporizador estourar
        remaining = Shared.TIMEOUT - (time.monotonic() - timer_start)
        try:
            if remaining <= 0:
                # o temporizador ja estourou antes mesmo de esperar
                raise socket.timeout
            sock.settimeout(remaining)
            pkt = parse_packet(recv_packet(sock))
        except socket.timeout:
            # Go-Back-N: next_seq = base faz o passo 1 reenviar a janela inteira
            print(f"[CLIENTE] timeout! voltando para SEQ={base} e reenviando a janela")
            next_seq = base
            continue
        except ValueError as error:
            print(f"[CLIENTE] pacote invalido ignorado: {error}")
            continue

        # 3) trata a resposta
        if pkt["type"] == "ACK" and pkt["seq"] >= base:
            # cumulativo: tudo ate pkt["seq"] foi recebido, a janela desliza
            print(f"[CLIENTE] <- ACK SEQ={pkt['seq']} (cumulativo)")
            base = pkt["seq"] + 1
            # ainda ha pacotes pendentes: reinicia o temporizador para a nova base
            if base < next_seq:
                timer_start = time.monotonic()
        elif pkt["type"] == "NAK" and pkt["seq"] >= base:
            print(f"[CLIENTE] <- NAK SEQ={pkt['seq']}, voltando para SEQ={base}")
            next_seq = base
        else:
            # ACK/NAK de pacote ja confirmado (seq < base). Pacotes WINDOW
            # tambem caem aqui: o GBN nao trata mudanca de janela no cliente.
            print(f"[CLIENTE] {pkt['type']} SEQ={pkt.get('seq')} antigo, ignorado")

# Modo Repeticao Seletiva: ate `window_size` pacotes sem confirmacao, mas cada
# pacote tem o proprio temporizador e so o pacote com problema e reenviado.
#   base   = SEQ mais antigo ainda nao confirmado
#   acked  = SEQs ja confirmados (podem estar fora de ordem)
#   timers = {seq: instante do ultimo envio} dos pacotes aguardando confirmacao
# A janela so desliza quando `base` e confirmado.
def send_sr(sock, chunks, window_size, key):
    total = len(chunks)
    base = 0
    next_seq = 0
    acked = set()
    timers = {}

    while base < total:
        # 1) preenche a janela, ligando um temporizador para cada pacote
        while next_seq < base + window_size and next_seq < total:
            packet = build_packet(next_seq, chunks[next_seq], key)
            send_packet(sock, packet)
            print(f"[CLIENTE] -> DATA SEQ={next_seq} '{chunks[next_seq]}' cifrado={cipher_of(packet)}   "
                  f"janela=[{base}..{base + window_size - 1}]")
            timers[next_seq] = time.monotonic()
            next_seq += 1

        # 2) reenvia apenas os pacotes cujo temporizador estourou
        now = time.monotonic()
        expired = [s for s, t in timers.items() if now - t >= Shared.TIMEOUT]
        for s in expired:
            send_packet(sock, build_packet(s, chunks[s], key))
            print(f"[CLIENTE] timeout SEQ={s}, retransmitindo apenas ele")
            timers[s] = time.monotonic()

        # 3) espera resposta ate o proximo temporizador a estourar (o mais
        #    antigo); o minimo de 0.01s evita settimeout(0), que nao bloqueia
        oldest = min(timers.values()) if timers else time.monotonic()
        remaining = Shared.TIMEOUT - (time.monotonic() - oldest)
        try:
            sock.settimeout(max(remaining, 0.01))
            pkt = parse_packet(recv_packet(sock))
        except socket.timeout:
            # volta ao passo 2, que reenvia o que expirou
            continue
        except ValueError as error:
            print(f"[CLIENTE] pacote invalido ignorado: {error}")
            continue

        # 4) trata a resposta
        # Servidor mudou a janela (WINDOW_SCHEDULE): vale a partir do passo 1
        if pkt["type"] == "WINDOW":
            window_size = pkt["size"]
            print(f"[CLIENTE] <- WINDOW SIZE={window_size} (Atualizando janela do cliente)")
            continue

        # Confirmacao em lote (modo GROUP): marca cada SEQ como confirmado,
        # desliga seu temporizador e desliza a base sobre os confirmados
        if pkt["type"] == "ACKG":
            seqs = pkt.get("seqs", [])
            print(f"[CLIENTE] <- ACKG SEQS={seqs} (Lote de confirmacao)")
            for s in seqs:
                if s in timers:
                    acked.add(s)
                    del timers[s]
            while base in acked:
                base += 1
            continue

        # ACK/NAK individuais. `seq in timers` garante que o pacote ainda
        # aguarda confirmacao; respostas repetidas caem no else.
        seq = pkt.get("seq")
        if pkt["type"] == "ACK" and seq in timers:
            print(f"[CLIENTE] <- ACK SEQ={seq} (individual)")
            acked.add(seq)
            del timers[seq]
            while base in acked:
                base += 1
        elif pkt["type"] == "NAK" and seq in timers:
            print(f"[CLIENTE] <- NAK SEQ={seq}, retransmitindo apenas ele")
            send_packet(sock, build_packet(seq, chunks[seq], key))
            timers[seq] = time.monotonic()
        else:
            if pkt["type"] not in ("WINDOW", "ACKG"):
                print(f"[CLIENTE] {pkt['type']} SEQ={seq} ja confirmado, ignorado")



# Encerramento: envia FIN com o total de pacotes e repete ate receber FINACK
# (o FIN ou o FINACK tambem podem se perder).
def close_session(sock, total):
    sock.settimeout(Shared.TIMEOUT)
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

        # Handshake: envia HELLO (modo, tamanho, chave) e espera o CONFIG
        key = generate_key()
        print(f"Chave de sessao gerada: {to_hex(key)}")
        proposal = criar_handshake(modo, size, key)
        print(f"Enviando proposal de handshake: {proposal}")
        send_packet(cliente_socket, proposal)

        response = recv_packet(cliente_socket)
        print(f"Resposta do servidor: {response}")

        # ack_mode nao e usado pelo cliente: ele trata o que chegar (ACK,
        # NAK, ACKG ou WINDOW), qualquer que seja o modo do servidor
        try:
            window_size, ack_mode = parse_config(response)
        except ValueError as error:
            print(f"\nFalha no handshake: {error}")
            return

        print(f"Janela definida pelo servidor: {window_size}")
        print("\nHandshake concluido! Prontos para transmitir.")

        text = read_message(size)
        chunks = split_message(text)
        print(f"\nMensagem dividida em {len(chunks)} pacotes: {chunks}\n")

        # a partir daqui toda espera por resposta tem limite (temporizador)
        cliente_socket.settimeout(Shared.TIMEOUT)

        if modo == "INDIVIDUAL":
            send_individual(cliente_socket, chunks, key)
        elif modo == "GBN":
            send_gbn(cliente_socket, chunks, window_size, key)
        elif modo == "SR":
            send_sr(cliente_socket, chunks, window_size, key)
        else:
            print(f"Modo {modo} desconhecido.")
            return

        close_session(cliente_socket, len(chunks))
        print("\nTransmissao concluida!")

    except Exception as e:
        print(f"Erro: {e}")
    finally:
        cliente_socket.close()


if __name__ == "__main__":
    main()