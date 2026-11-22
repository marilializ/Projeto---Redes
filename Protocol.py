# Protocolo de aplicacao usado por cliente e servidor: formato das mensagens,
# framing sobre o socket TCP, checksum e parse dos pacotes.
#
# Todas as mensagens sao texto no formato TIPO|CAMPO=valor:
#   HELLO|MODE=<modo>|MAX=<tamanho>|KEY=<hex>  cliente -> servidor (handshake)
#   CONFIG|WINDOW=<janela>|ACKMODE=<modo>      servidor -> cliente (aceita)
#   ERROR|<motivo>                             servidor -> cliente (recusa)
#   DATA|SEQ=<n>|CHK=<checksum>|<payload hex>  cliente -> servidor (dados)
#   ACK|SEQ=<n>                                confirmacao positiva
#   NAK|SEQ=<n>                                confirmacao negativa
#   ACKG|SEQS=<n1>,<n2>,...                    confirmacao em lote (SR, modo GROUP)
#   WINDOW|SIZE=<n>                            servidor muda a janela
#   FIN|TOTAL=<n>                              fim da transmissao
#   FINACK                                     confirmacao do fim

import struct
from Shared import VALID_MODES, MIN_MESSAGE_SIZE, PAYLOAD_SIZE, MIN_WINDOW, MAX_WINDOW
from Cipher import to_hex, from_hex, encrypt_payload


# --- Handshake ---------------------------------------------------------------

# Monta a proposta do cliente. Valida antes de enviar para nao mandar um
# HELLO que o servidor vai recusar.
def criar_handshake(mode, max_message_size, key):
    if mode not in VALID_MODES:
        raise ValueError("modo de operação invalido.")
    if max_message_size < MIN_MESSAGE_SIZE:
        raise ValueError(
            f"o tamanho maximo deve ser de pelo menos {MIN_MESSAGE_SIZE} caracteres."
        )
    # chave de sessao negociada no handshake, em hex
    return f"HELLO|MODE={mode}|MAX={max_message_size}|KEY={to_hex(key)}"


# Lado do servidor: valida o HELLO e devolve (modo, tamanho maximo, chave).
# Qualquer problema vira ValueError, e o servidor responde com ERROR.
def parse_handshake(message):
    parts = message.split("|")
    if len(parts) != 4:
        raise ValueError("handshake invalido.")

    if parts[0] != "HELLO":
        raise ValueError("mensagem não é um HELLO.")

    mode = parts[1].split("=")[1]
    max_message_size = int(parts[2].split("=")[1])

    field, _, key_hex = parts[3].partition("=")
    if field != "KEY" or not key_hex:
        raise ValueError("chave de sessao ausente no HELLO.")
    key = from_hex(key_hex)

    if mode not in VALID_MODES:
        raise ValueError("modo de operação inválido.")

    if max_message_size < MIN_MESSAGE_SIZE:
        raise ValueError(
            f"o tamanho maximo deve ser de pelo menos {MIN_MESSAGE_SIZE} caracteres."
        )
    return mode, max_message_size, key


# Resposta do servidor ao HELLO: janela inicial e como ele vai confirmar
# os pacotes (ver SERVER_ACK_MODE em Shared.py).
def create_config(window_size, ack_mode):
    return f"CONFIG|WINDOW={window_size}|ACKMODE={ack_mode}"


# Lado do cliente: le o CONFIG. Se o servidor respondeu ERROR em vez de
# CONFIG, gera ValueError e o cliente aborta.
def parse_config(message):
    parts = message.split("|")
    if len(parts) != 3 or parts[0] != "CONFIG":
        raise ValueError("configuração invalida.")

    window_size = int(parts[1].split("=")[1])
    ack_mode = parts[2].split("=")[1]
    return window_size, ack_mode

# Tamanho em bytes do cabecalho de framing (ver send_packet)
HEADER_SIZE = 4

# Servidor avisando o cliente que a janela mudou (ver WINDOW_SCHEDULE)
def create_window(size):
    if not MIN_WINDOW <= size <= MAX_WINDOW:
        raise ValueError(f"janela {size} fora do intervalo {MIN_WINDOW}..{MAX_WINDOW}.")
    return f"WINDOW|SIZE={size}"

# Confirmacao em lote do SR: lista de SEQs recebidos, ex. "ACKG|SEQS=0,1,3"
def create_ackg(seqs_list):
    seqs_str = ",".join(map(str, seqs_list))
    return f"ACKG|SEQS={seqs_str}"


# --- Framing -----------------------------------------------------------------
# O TCP entrega um fluxo continuo de bytes, sem fronteira entre mensagens:
# dois send() podem chegar num unico recv(), ou uma mensagem pode chegar
# partida. Por isso cada mensagem leva na frente um cabecalho de 4 bytes com o
# seu tamanho ("!I" = inteiro sem sinal de 32 bits, big-endian / ordem de rede).
# Usamos prefixo de tamanho em vez de delimitador porque o texto pode conter
# qualquer caractere.

def send_packet(sock, message):
    data = message.encode("utf-8")
    header = struct.pack("!I", len(data))
    sock.sendall(header + data)


# Le exatamente n bytes. O laco e necessario porque recv(n) pode devolver
# MENOS que n bytes; ele so garante "ate n". recv vazio = conexao fechada.
def _recv_exact(sock, n):
    buffer = b""
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            raise ConnectionError("conexão encerrada pelo outro lado.")
        buffer += chunk
    return buffer


# Le o cabecalho (tamanho) e depois exatamente aquele numero de bytes
def recv_packet(sock):
    header = _recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    data = _recv_exact(sock, length)
    return data.decode("utf-8")


# --- Checksum ----------------------------------------------------------------
# Requisito: checksum. Checksum da Internet (RFC 1071), feito a mao.
# Cobre o SEQ junto com o payload: se a corrupcao alterar o numero de
# sequencia, o pacote tambem e rejeitado (e nao entregue na posicao errada).

def calc_checksum(seq, payload):
    data = f"{seq}|{payload}".encode("utf-8")
    # 1) a soma e feita em palavras de 16 bits; se o numero de bytes for
    #    impar, completa com um byte zero
    if len(data) % 2 == 1:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        # 2) junta dois bytes numa palavra de 16 bits (alto << 8 + baixo)
        word = (data[i] << 8) + data[i + 1]
        total += word
        # 3) "end-around carry": o que passar de 16 bits volta somado no final
        total = (total & 0xFFFF) + (total >> 16)

    # 4) complemento de 1 da soma, limitado a 16 bits
    return ~total & 0xFFFF

# O receptor recalcula sobre o que recebeu e compara com o CHK do pacote
def verify_checksum(seq, payload, checksum):
    return calc_checksum(seq, payload) == checksum


# --- Pacotes de dados e controle --------------------------------------------

# Fatia o texto em pedacos de PAYLOAD_SIZE caracteres; o ultimo pode ser menor.
# Ex.: "abcdefghij" -> ["abcd", "efgh", "ij"]
def split_message(text):
    return [text[i:i + PAYLOAD_SIZE] for i in range(0, len(text), PAYLOAD_SIZE)]

def create_data(seq, payload, key):
    # o limite de 4 caracteres vale para o texto claro (carga util da aplicacao)
    if len(payload) > PAYLOAD_SIZE:
        raise ValueError(f"payload maior que {PAYLOAD_SIZE} caracteres.")
    # encrypt-then-MAC: cifra primeiro, checksum sobre o payload cifrado (hex)
    cipher_hex = encrypt_payload(payload, key)
    checksum = calc_checksum(seq, cipher_hex)
    return f"DATA|SEQ={seq}|CHK={checksum}|{cipher_hex}"


def create_ack(seq):
    return f"ACK|SEQ={seq}"


# Enviado pelo servidor quando o checksum de um DATA nao confere
def create_nak(seq):
    return f"NAK|SEQ={seq}"


# TOTAL permite ao servidor conferir se recebeu todos os pacotes
def create_fin(total_packets):
    return f"FIN|TOTAL={total_packets}"


def create_finack():
    return "FINACK"


# --- Parse -------------------------------------------------------------------

# Le um campo "NOME=valor" inteiro, conferindo se o nome e o esperado
def _get_field(part, name):
    key, _, value = part.partition("=")
    if key != name:
        raise ValueError(f"campo {name} esperado, recebido '{part}'.")
    return int(value)

# Converte uma mensagem recebida num dicionario {"type": ..., campos...}.
# Mensagem mal formada vira ValueError; quem chama descarta o pacote.
def parse_packet(message):
    kind = message.split("|", 1)[0]

    if kind == "DATA":
        # maxsplit=3: o payload e sempre o ultimo campo, entao fica inteiro
        # mesmo que contenha "|"
        parts = message.split("|", 3)
        if len(parts) != 4:
            raise ValueError("pacote DATA mal formado.")
        return {
            "type": "DATA",
            "seq": _get_field(parts[1], "SEQ"),
            "chk": _get_field(parts[2], "CHK"),
            "payload": parts[3],
        }

    if kind == "WINDOW":
        parts = message.split("|")
        if len(parts) != 2:
            raise ValueError("pacote WINDOW mal formado.")
        size = _get_field(parts[1], "SIZE")
        # janela fora de 1..5 e pacote invalido: o cliente descarta
        if not MIN_WINDOW <= size <= MAX_WINDOW:
            raise ValueError(f"janela {size} fora do intervalo {MIN_WINDOW}..{MAX_WINDOW}.")
        return {"type": "WINDOW", "size": size}

    if kind == "ACKG":
        parts = message.split("|")
        if len(parts) != 2:
            raise ValueError("pacote ACKG mal formado.")
        _, _, value = parts[1].partition("=")
        # "0,1,3" -> [0, 1, 3]; lista vazia se nao houver SEQs
        seqs = [int(x) for x in value.split(",")] if value else []
        return {"type": "ACKG", "seqs": seqs}

    if kind in ("ACK", "NAK"):
        parts = message.split("|")
        if len(parts) != 2:
            raise ValueError(f"pacote {kind} mal formado.")
        return {"type": kind, "seq": _get_field(parts[1], "SEQ")}

    if kind == "FIN":
        parts = message.split("|")
        if len(parts) != 2:
            raise ValueError("pacote FIN mal formado.")
        return {"type": "FIN", "total": _get_field(parts[1], "TOTAL")}

    if kind == "FINACK":
        return {"type": "FINACK"}

    raise ValueError(f"tipo de pacote desconhecido: {kind}")
