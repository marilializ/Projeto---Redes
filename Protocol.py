from Shared import VALID_MODES, MIN_MESSAGE_SIZE
import struct
from Shared import VALID_MODES, MIN_MESSAGE_SIZE, PAYLOAD_SIZE


def criar_handshake(mode, max_message_size):
    if mode not in VALID_MODES:
        raise ValueError("modo de operação invalido.")
    if max_message_size < MIN_MESSAGE_SIZE:
        raise ValueError(
            f"o tamanho maximo deve ser de pelo menos {MIN_MESSAGE_SIZE} caracteres."
        )
    return f"HELLO|MODE={mode}|MAX={max_message_size}"


def parse_handshake(message):
    parts = message.split("|")
    if len(parts) != 3:
        raise ValueError("handshake invalido.")

    if parts[0] != "HELLO":
        raise ValueError("mensagem não é um HELLO.")

    mode = parts[1].split("=")[1]
    max_message_size = int(parts[2].split("=")[1])

    if mode not in VALID_MODES:
        raise ValueError("modo de operação inválido.")

    if max_message_size < MIN_MESSAGE_SIZE:
        raise ValueError(
            f"o tamanho maximo deve ser de pelo menos {MIN_MESSAGE_SIZE} caracteres."
        )
    return mode, max_message_size


def create_config(window_size):
    return f"CONFIG|WINDOW={window_size}"


def parse_config(message):
    parts = message.split("|")
    if len(parts) != 2:
        raise ValueError("configuração invalida.")

    if parts[0] != "CONFIG":
        raise ValueError("mensagem não é uma CONFIG.")

    window_size = int(parts[1].split("=")[1])
    return window_size

HEADER_SIZE = 4


def send_packet(sock, message):
    data = message.encode("utf-8")
    header = struct.pack("!I", len(data))
    sock.sendall(header + data)


def _recv_exact(sock, n):
    buffer = b""
    while len(buffer) < n:
        chunk = sock.recv(n - len(buffer))
        if not chunk:
            raise ConnectionError("conexão encerrada pelo outro lado.")
        buffer += chunk
    return buffer


def recv_packet(sock):
    header = _recv_exact(sock, HEADER_SIZE)
    (length,) = struct.unpack("!I", header)
    data = _recv_exact(sock, length)
    return data.decode("utf-8")

def calc_checksum(seq, payload):
    data = f"{seq}|{payload}".encode("utf-8")
    if len(data) % 2 == 1:
        data += b"\x00"

    total = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        total += word
        total = (total & 0xFFFF) + (total >> 16)

    return ~total & 0xFFFF

def verify_checksum(seq, payload, checksum):
    return calc_checksum(seq, payload) == checksum

def split_message(text):
    return [text[i:i + PAYLOAD_SIZE] for i in range(0, len(text), PAYLOAD_SIZE)]

def create_data(seq, payload):
    if len(payload) > PAYLOAD_SIZE:
        raise ValueError(f"payload maior que {PAYLOAD_SIZE} caracteres.")
    checksum = calc_checksum(seq, payload)
    return f"DATA|SEQ={seq}|CHK={checksum}|{payload}"


def create_ack(seq):
    return f"ACK|SEQ={seq}"


def create_nak(seq):
    return f"NAK|SEQ={seq}"


def create_fin(total_packets):
    return f"FIN|TOTAL={total_packets}"


def create_finack():
    return "FINACK"

def _get_field(part, name):
    key, _, value = part.partition("=")
    if key != name:
        raise ValueError(f"campo {name} esperado, recebido '{part}'.")
    return int(value)

def parse_packet(message):
    kind = message.split("|", 1)[0]

    if kind == "DATA":
        parts = message.split("|", 3)
        if len(parts) != 4:
            raise ValueError("pacote DATA mal formado.")
        return {
            "type": "DATA",
            "seq": _get_field(parts[1], "SEQ"),
            "chk": _get_field(parts[2], "CHK"),
            "payload": parts[3],
        }

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