from Shared import VALID_MODES, MIN_MESSAGE_SIZE


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