import os

# ---------------------------------------------------------------------------
# Cifra simetrica XOR com chave repetida (implementada a mao).
#
# Para cada byte i da mensagem:
#     cifrado[i] = claro[i] ^ chave[i % len(chave)]
#
# A chave e "repetida" ao longo da mensagem: se a chave tem 8 bytes, o byte 8
# da mensagem volta a usar chave[0], o byte 9 usa chave[1], e assim por diante.
#
# A operacao e AUTO-INVERSA, porque para qualquer bit: (m ^ k) ^ k = m ^ 0 = m.
# Logo a mesma funcao serve para cifrar e decifrar, com a mesma chave
# (por isso e uma cifra SIMETRICA).
#
# Limitacoes (conhecidas e assumidas no projeto academico):
#   - a chave viaja em claro no HELLO; quem captura o handshake decifra tudo;
#   - com um trecho de texto conhecido, claro ^ cifrado revela a chave.
# ---------------------------------------------------------------------------

KEY_SIZE = 8  # bytes de chave de sessao (16 digitos hex no HELLO)

HEX_DIGITS = "0123456789abcdef"


def generate_key():
    # os.urandom so sorteia a chave; nao participa da cifra.
    return os.urandom(KEY_SIZE)


def xor_cipher(data, key):
    if not key:
        raise ValueError("chave vazia.")
    out = bytearray(len(data))
    for i in range(len(data)):
        out[i] = data[i] ^ key[i % len(key)]
    return bytes(out)


def to_hex(data):
    # Cada byte (0..255) vira dois digitos hex: o nibble alto (byte >> 4)
    # e o nibble baixo (byte & 0x0F). Ex.: 0xA7 -> "a" + "7".
    digits = []
    for byte in data:
        digits.append(HEX_DIGITS[byte >> 4])
        digits.append(HEX_DIGITS[byte & 0x0F])
    return "".join(digits)


def from_hex(text):
    # Caminho inverso: cada par de digitos vira um byte (alto << 4 | baixo).
    text = text.lower()
    if len(text) % 2 != 0:
        raise ValueError("hex com numero impar de digitos.")
    out = bytearray(len(text) // 2)
    for i in range(0, len(text), 2):
        high = HEX_DIGITS.find(text[i])
        low = HEX_DIGITS.find(text[i + 1])
        if high < 0 or low < 0:
            raise ValueError(f"digito hex invalido em '{text[i:i + 2]}'.")
        out[i // 2] = (high << 4) | low
    return bytes(out)


def encrypt_payload(text, key):
    # texto -> bytes utf-8 -> XOR -> hex. O hex e obrigatorio: os bytes cifrados
    # sao arbitrarios e nao formam utf-8 valido para send_packet/recv_packet.
    # Caracteres ASCII ocupam 1 byte (2 digitos hex); acentuados ocupam 2 bytes
    # (4 digitos). Ex.: "ação" = 4 caracteres, 6 bytes, 12 digitos hex.
    return to_hex(xor_cipher(text.encode("utf-8"), key))


def decrypt_payload(hex_text, key):
    # Caminho inverso: hex -> bytes -> XOR (mesma funcao) -> texto utf-8.
    return xor_cipher(from_hex(hex_text), key).decode("utf-8")
