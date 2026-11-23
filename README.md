# Projeto de Redes com Python

## Descrição

Este projeto implementa uma aplicação cliente-servidor em Python utilizando sockets, com foco no desenvolvimento de um protocolo próprio de camada de aplicação para transporte confiável de dados. A ideia central é demonstrar, na prática, conceitos de redes de computadores como handshaking, controle de fluxo, integridade, sequência, confirmação de mensagens e simulação de erros em um canal imperfeito.

O sistema será estruturado para:

- conectar cliente e servidor via sockets;
- negociar parâmetros iniciais da comunicação;
- dividir uma mensagem de texto em pacotes menores;
- verificar integridade dos dados;
- controlar janela e retransmissão;
- simular perdas e corrupções de forma determinística.

## Objetivo

- Implementar comunicação via sockets em Python;
- criar uma arquitetura cliente-servidor;
- realizar handshake inicial entre cliente e servidor;
- aplicar conceitos de confiabilidade em camada de aplicação;
- suportar envio individual e em lote;
- validar a transmissão com checksum, ACK/NAK, sequência e temporizador.

## Handshake

No início da comunicação, o cliente e o servidor trocam informações para definir os parâmetros da sessão, como:

- modo de operação;
- tamanho máximo do texto a ser enviado;
- tamanho da janela de transmissão.

Essa etapa é essencial para garantir que ambas as partes utilizem as mesmas regras durante a troca de mensagens.

## Decisão de design do protocolo

O enunciado menciona duas dimensões principais da operação:

- envio individual ou em lote;
- confirmação da janela por Go-Back-N ou Repetição Seletiva.

Para simplificar a implementação, o projeto utiliza o campo `MODE` para indicar o modo de operação escolhido pelo cliente. Atualmente, o cliente pode selecionar entre envio `INDIVIDUAL`, `GBN` (Go-Back-N) e `SR` (Repetição Seletiva).

Durante o handshake, o servidor valida o modo solicitado e retorna os parâmetros sob sua responsabilidade, como o tamanho inicial da janela de recepção.

No modo `INDIVIDUAL`, o servidor responde com janela 1, já que o envio individual funciona como uma janela de tamanho 1 (stop-and-wait). Nos modos `GBN` e `SR`, a janela inicial é 5, definida pela constante `DEFAULT_WINDOW_SIZE` em `Shared.py`.

A forma de **confirmação** é um segundo eixo, independente do modo do cliente: o servidor define o `ACKMODE` (`SERVER_ACK_MODE` em `Shared.py`) e o anuncia no `CONFIG`.

- `INDIVIDUAL`: um ACK para cada pacote recebido;
- `GROUP`: uma confirmação por lote — ACK cumulativo no GBN e `ACKG` (lista de SEQs recebidos, como o SACK do TCP) no SR.

Mudança em relação ao CP2: no CP2 o campo `MODE` era o único eixo; no CP3 o grupo separou a estratégia de retransmissão do cliente (`MODE`) da granularidade de confirmação do servidor (`ACKMODE`), para atender ao requisito de o servidor aceitar as duas configurações.

## Tecnologias utilizadas

- Python 3
- Biblioteca `socket`
- Estrutura de protocolo próprio em camada de aplicação

## Estrutura do projeto

```text
Projeto---Redes/
├── Client.py
├── Server.py
├── Protocol.py
├── Cipher.py
├── Shared.py
└── README.md
```

## Funcionamento geral

O fluxo de funcionamento é:

```text
Cliente conecta ao servidor
Handshake inicial
Negociação de parâmetros
Fragmentação da mensagem em pacotes
Envio dos pacotes com checksum e sequência
Validação no servidor
Confirmação (ACK/NAK)
Encerramento (FIN/FINACK)
Reconstrução da mensagem original
```

## Requisitos do trabalho

A aplicação deve atender aos seguintes requisitos:

- comunicação via sockets;
- handshake inicial com troca de parâmetros;
- payload máximo de 4 caracteres por pacote;
- checksum para garantia de integridade;
- número de sequência;
- temporizador para retransmissão;
- ACK e NACK;
- suporte a janela de envio com paralelismo;
- simulação de erros e perdas em nível de aplicação;
- confirmação em modo individual ou por janela.

## Como executar

### Pré-requisitos

- Python 3 instalado
- ambiente local com acesso ao localhost ou IP configurado

### Passo a passo

1. Abra um terminal na pasta do projeto e inicie o servidor:

```bash
python3 Server.py
```

2. Em outro terminal, inicie o cliente:

```bash
python3 Client.py
```

No Windows, use `python` (ou `py`) no lugar de `python3`.

3. No cliente, escolha o modo de operação (1 para Individual, 2 para Go-Back-N, 3 para Repetição Seletiva), informe o tamanho máximo da mensagem (mínimo 30) e digite a mensagem a ser enviada.

4. O servidor mostra cada pacote recebido e, no final, a mensagem reconstruída. O cliente mostra cada confirmação recebida.

O servidor encerra ao final de cada transmissão, então é preciso iniciá-lo novamente antes de cada teste.

Para testar com erros, configure o `ERROR_PLAN` antes de iniciar (ver [Simulação de erros e perdas](#simulação-de-erros-e-perdas)).

## Protocolo proposto

### Framing

Cada mensagem é precedida por um cabeçalho de 4 bytes (inteiro sem sinal, big-endian) que indica o tamanho do conteúdo em bytes. O receptor lê primeiro esse cabeçalho e depois exatamente a quantidade de bytes indicada. Optou-se pelo prefixo de tamanho em vez de delimitadores porque o texto do usuário pode conter qualquer caractere, inclusive o próprio delimitador. As funções `send_packet()` e `recv_packet()`, em `Protocol.py`, são usadas para todas as mensagens, incluindo o handshake.

### Mensagens

Todas as mensagens seguem o formato de texto `TIPO|CAMPO=valor`:

- `HELLO|MODE=<modo>|MAX=<tamanho>|KEY=<chave em hex>`: proposta de handshake enviada pelo cliente, com a chave de sessão;
- `CONFIG|WINDOW=<janela>|ACKMODE=<INDIVIDUAL ou GROUP>`: resposta do servidor aceitando o handshake;
- `ERROR|<motivo>`: resposta do servidor recusando o handshake;
- `DATA|SEQ=<n>|CHK=<checksum>|<payload cifrado em hex>`: pacote de dados, com até 4 caracteres de texto, cifrados e representados em hexadecimal, sempre no final;
- `ACK|SEQ=<n>`: confirmação positiva;
- `NAK|SEQ=<n>`: confirmação negativa (checksum inválido);
- `ACKG|SEQS=<n1>,<n2>,...`: confirmação em lote do SR em modo `GROUP`, com a lista de SEQs recebidos;
- `WINDOW|SIZE=<n>`: o servidor muda o tamanho da janela durante a transmissão (de 1 a 5);
- `FIN|TOTAL=<n>`: fim da transmissão, com o total de pacotes;
- `FINACK`: confirmação do fim.

### Checksum

O checksum segue o modelo do checksum da Internet (RFC 1071): soma de palavras de 16 bits com retorno do carry e complemento de 1 no final. Ele é calculado sobre o número de sequência e o payload **já cifrado** juntos, para que uma corrupção em qualquer um dos dois seja detectada. A implementação foi feita à mão, sem bibliotecas externas.

### Criptografia (Ponto Extra 2)

O payload de cada pacote DATA é cifrado com uma cifra simétrica XOR com chave repetida, implementada à mão em `Cipher.py`, sem bibliotecas de criptografia:

```text
cifrado[i] = claro[i] XOR chave[i mod tamanho_da_chave]
```

- **Simétrica e auto-inversa:** como `(m XOR k) XOR k = m`, a mesma função cifra e decifra, com a mesma chave.
- **Chave de sessão:** o cliente sorteia uma chave de 8 bytes a cada conexão e a envia no campo `KEY` do `HELLO`. Não há chave fixa no código; duas execuções com o mesmo texto geram pacotes diferentes.
- **Hexadecimal:** depois do XOR o payload vira bytes arbitrários, que não formam UTF-8 válido para o envio. Por isso ele viaja em hexadecimal (conversão também feita à mão). O texto é cifrado sobre seus bytes UTF-8: um caractere ASCII ocupa 2 dígitos hex, e um acentuado, 4. Por exemplo, `"test"` vira 8 dígitos e `"ação"` vira 12. A carga útil da aplicação continua sendo de 4 caracteres.
- **Ordem das operações (encrypt-then-MAC):** o cliente cifra primeiro e calcula o checksum sobre o payload cifrado. O servidor verifica o checksum antes de decifrar; pacote corrompido recebe NAK sem ser decifrado.
- **Simulação de erros:** a corrupção deliberada de pacotes acontece depois da cifragem (em `build_packet()`, no `Client.py`), para que seja detectada pelo checksum e gere NAK.

Limitações conhecidas: a chave viaja em claro no handshake, então quem captura o `HELLO` consegue decifrar a sessão; e o XOR com chave repetida é vulnerável a texto conhecido (`claro XOR cifrado` revela a chave). A cifra cumpre o objetivo didático do ponto extra, mas não oferece segurança real.

### Modos de operação

- `INDIVIDUAL`: stop-and-wait; o cliente envia um pacote e espera o ACK antes de enviar o próximo.
- `GBN`: o cliente envia até N pacotes sem esperar resposta; o ACK é cumulativo, há um único temporizador, e em timeout ou NAK todos os pacotes a partir do mais antigo não confirmado são reenviados.
- `SR`: o cliente envia até N pacotes sem esperar resposta; cada pacote tem seu próprio temporizador e só o pacote com problema é reenviado. O servidor guarda pacotes fora de ordem num buffer e reconfirma qualquer pacote já entregue que chegue de novo (sinal de que a confirmação anterior se perdeu).

### Janela dinâmica

A janela vai de 1 a 5, é definida pelo servidor e começa em 5. Durante a transmissão, o servidor a altera conforme `WINDOW_SCHEDULE` em `Shared.py` (padrão `{0: 5, 4: 2, 8: 4}`: cai para 2 ao esperar o SEQ 4 e sobe para 4 ao esperar o SEQ 8) e avisa o cliente com `WINDOW`. Pacotes já enviados acima do novo limite não são cancelados: a janela nova vale para os próximos envios.

### Temporizadores e encerramento

- Cliente: 2 s sem confirmação → retransmite (`TIMEOUT`).
- Servidor: 1 s sem receber nada → confirma o lote incompleto em modo `GROUP` (`SERVER_TIMEOUT`). É menor que o do cliente para a confirmação chegar antes da retransmissão.
- `FIN` com total diferente do recebido é recusado (NAK ou ACKG do que falta); após 5 recusas o servidor aborta com "entrega incompleta". Depois do `FINACK`, o servidor fica 3 s em TIME-WAIT respondendo a `FIN` repetido. O cliente desiste após 5 `FIN` sem resposta.

## Simulação de erros e perdas

Como o TCP já oferece entrega confiável na camada de transporte, os erros e perdas são simulados na aplicação, no lado cliente, de forma determinística: cada erro é ligado a um número de sequência, nunca sorteado, então o mesmo plano sempre gera o mesmo resultado.

### Como configurar

Edite `ERROR_PLAN` no final de `Shared.py`, colocando em cada lista os SEQs que devem sofrer aquele erro:

```python
ERROR_PLAN = {
    "corrupt":   [1],   # altera o payload depois do checksum
    "drop_data": [],    # o pacote DATA não é enviado
    "duplicate": [],    # o pacote DATA é enviado duas vezes
    "drop_ack":  [],    # a confirmação (ACK/ACKG) é descartada ao chegar no cliente
}
```

Listas vazias = canal sem erros. Para escolher a forma de confirmação, altere `SERVER_ACK_MODE` (`"INDIVIDUAL"` ou `"GROUP"`). Depois, rode servidor e cliente normalmente. O cliente imprime o plano em uso, e cada erro aparece no log com o prefixo `[SIMULADOR]`.

Cada erro acontece **só na primeira tentativa** daquele SEQ; a retransmissão sai limpa, senão o pacote nunca chegaria.

### O que cada erro provoca

| Erro | INDIVIDUAL | GBN | SR |
| --- | --- | --- | --- |
| `corrupt` | checksum inválido → NAK → reenvia o pacote | NAK → reenvia a janela desde o mais antigo não confirmado | NAK → reenvia só aquele pacote |
| `drop_data` | timeout → reenvia o pacote | servidor descarta os seguintes; timeout → reenvia a janela | servidor guarda os seguintes no buffer; timeout → reenvia só o que faltou |
| `duplicate` | servidor reconfirma sem duplicar o texto | servidor descarta a cópia | servidor reconhece como já recebido |
| `drop_ack` | timeout → reenvia; servidor reconfirma | um ACK cumulativo posterior cobre o perdido | timeout → reenvia; servidor reconfirma o já entregue |

Exemplo para demonstração: mensagem `transporte confiavel com GBN e SR!!!` (36 caracteres, 9 pacotes) com tamanho máximo 40, que também mostra a janela mudando duas vezes nos modos GBN e SR.

## Processo de construção e uso de IA

A Inteligência Artificial foi utilizada como apoio didático ao longo do projeto, especialmente para:

- compreender os conceitos de transporte confiável;
- comparar GBN e Repetição Seletiva;
- revisar trechos de código e depuração;
- discutir checksum, temporizador e fluxo de mensagens;
- desenhar o formato dos pacotes e o framing.

A IA foi utilizada como ferramenta de apoio, mas todas as decisões técnicas foram validadas pelo grupo antes de sua implementação.

O registro detalhado do uso de IA em cada etapa está no relatório de cada checkpoint.

## Status do projeto

- Checkpoint 1 (Handshake e Sockets): concluído.
- Checkpoint 2 (Protocolo Sem Erros): concluído. Os três modos (Individual, GBN e SR) funcionam no canal sem erros, com checksum, número de sequência, ACK/NAK, temporizador e janela já implementados.
- Checkpoint 3 (Inserção de Erros e Perdas): concluído. Simulador de erros determinístico (corrupção, perda de dados, duplicação e perda de confirmação), confirmação individual ou em grupo, janela dinâmica de 1 a 5, criptografia XOR (ponto extra) e checksum feito à mão (ponto extra).
