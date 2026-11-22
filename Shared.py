# Constantes compartilhadas por cliente e servidor. Mudar um valor aqui muda
# o comportamento dos dois lados ao mesmo tempo.

# Endereco do servidor (localhost, os dois processos rodam na mesma maquina)
HOST = "127.0.0.1"
PORT = 9999

# Valores padrao da sessao. DEFAULT_MAX_MESSAGE_SIZE ainda nao e usado no
# codigo (o tamanho maximo vem do usuario no cliente). DEFAULT_WINDOW_SIZE e a
# janela inicial que o servidor anuncia no CONFIG nos modos GBN e SR.
DEFAULT_MAX_MESSAGE_SIZE = 30
DEFAULT_WINDOW_SIZE = 5

# Menor tamanho maximo de mensagem aceito no handshake (validado nos dois lados)
MIN_MESSAGE_SIZE = 30

# Modos de operacao aceitos no campo MODE do HELLO:
#   INDIVIDUAL = stop-and-wait (janela 1)
#   GBN        = Go-Back-N
#   SR         = Repeticao Seletiva
VALID_MODES = {
    "INDIVIDUAL",
    "GBN",
    "SR"
}

# Requisito: carga util de no maximo 4 caracteres por pacote
PAYLOAD_SIZE = 4

# Requisito: temporizador. Segundos sem confirmacao ate o cliente retransmitir.
TIMEOUT = 2.0

# Mudancas de janela feitas pelo servidor durante a transmissao (GBN e SR).
# Formato {seq: nova_janela}: quando o servidor passa a esperar o SEQ da chave,
# ele muda a propria janela e avisa o cliente com um pacote WINDOW.
# Ex.: {4: 2} -> ao esperar o SEQ 4, a janela passa a ser 2.
WINDOW_SCHEDULE = {0: 5, 4: 2, 8: 4}

# Como o servidor confirma os pacotes nos modos GBN e SR:
#   "INDIVIDUAL" -> um ACK para cada pacote recebido
#   "GROUP"      -> confirmacoes em lote (ACK cumulativo no GBN, ACKG no SR)
SERVER_ACK_MODE = "GROUP"

# Simulador de erros e perdas (lado cliente, deterministico).
# Cada lista guarda os SEQs que vao sofrer aquele erro. O erro acontece so na
# PRIMEIRA tentativa de cada SEQ; a retransmissao passa limpa (senao o
# protocolo entraria em loop infinito). Ex.: "corrupt": [2] corrompe o SEQ 2
# uma unica vez. Listas vazias = canal sem erros.
ERROR_PLAN = {
    "corrupt":   [],   # troca um digito hex do payload -> checksum falha -> NAK
    "drop_data": [],   # DATA nao e enviado -> estoura o temporizador do cliente
    "duplicate": [],   # DATA enviado duas vezes -> servidor descarta a copia
    "drop_ack":  [],   # ACK/ACKG recebido e descartado -> forca retransmissao
}
