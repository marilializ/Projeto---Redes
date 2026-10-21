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
├── Shared.py
├── README.md
├── Diario_ia.md
└── ...
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

## Protocolo proposto

### Framing

Cada mensagem é precedida por um cabeçalho de 4 bytes (inteiro sem sinal, big-endian) que indica o tamanho do conteúdo em bytes. O receptor lê primeiro esse cabeçalho e depois exatamente a quantidade de bytes indicada. Optou-se pelo prefixo de tamanho em vez de delimitadores porque o texto do usuário pode conter qualquer caractere, inclusive o próprio delimitador. As funções `send_packet()` e `recv_packet()`, em `Protocol.py`, são usadas para todas as mensagens, incluindo o handshake.

### Mensagens

Todas as mensagens seguem o formato de texto `TIPO|CAMPO=valor`:

- `HELLO|MODE=<modo>|MAX=<tamanho>`: proposta de handshake enviada pelo cliente;
- `CONFIG|WINDOW=<janela>`: resposta do servidor aceitando o handshake;
- `ERROR|<motivo>`: resposta do servidor recusando o handshake;
- `DATA|SEQ=<n>|CHK=<checksum>|<payload>`: pacote de dados, com payload de no máximo 4 caracteres, sempre no final;
- `ACK|SEQ=<n>`: confirmação positiva;
- `NAK|SEQ=<n>`: confirmação negativa (checksum inválido);
- `FIN|TOTAL=<n>`: fim da transmissão, com o total de pacotes;
- `FINACK`: confirmação do fim.

### Checksum

O checksum segue o modelo do checksum da Internet (RFC 1071): soma de palavras de 16 bits com retorno do carry e complemento de 1 no final. Ele é calculado sobre o número de sequência e o payload juntos, para que uma corrupção em qualquer um dos dois seja detectada. A implementação foi feita à mão, sem bibliotecas externas.

### Modos de operação

- `INDIVIDUAL`: stop-and-wait; o cliente envia um pacote e espera o ACK antes de enviar o próximo.
- `GBN`: o cliente envia até N pacotes sem esperar resposta; o ACK é cumulativo, há um único temporizador, e em timeout ou NAK todos os pacotes a partir do mais antigo não confirmado são reenviados.
- `SR`: o cliente envia até N pacotes sem esperar resposta; o ACK é individual, cada pacote tem seu próprio temporizador e só o pacote com problema é reenviado. O servidor guarda pacotes fora de ordem num buffer.

O tempo de espera para retransmissão é de 2 segundos (`TIMEOUT` em `Shared.py`).

## Simulação de erros e perdas

Como o TCP já oferece entrega confiável na camada de transporte, os erros e perdas serão simulados na aplicação, de forma determinística. Isso inclui:

- perda de pacote específico;
- alteração de payload;
- corrupção do checksum;
- duplicação de pacote;
- descarte de ACK/NAK para forçar retransmissão.

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
- Checkpoint 3 (Inserção de Erros e Perdas): a fazer.
