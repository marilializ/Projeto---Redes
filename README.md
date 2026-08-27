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

O fluxo de funcionamento previsto é:

```text
Cliente conecta ao servidor
Handshake inicial
Negociação de parâmetros
Fragmentação da mensagem em pacotes
Envio dos pacotes com checksum e sequência
Validação no servidor
Confirmação (ACK/NAK)
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

1. Abra um terminal na pasta do projeto.
2. Inicie o servidor:

```bash
python3 Server.py
```

3. Em outro terminal, inicie o cliente:

```bash
python3 Client.py
```

4. Realize a comunicação conforme o fluxo do programa.

## Protocolo proposto

A lógica do protocolo será baseada em pacotes de aplicação com metadados, incluindo:

- `FLAG`: tipo da mensagem;
- `SEQ`: número de sequência;
- `ACK`: confirmação recebida;
- `CHECKSUM`: controle de integridade;
- `PAYLOAD`: conteúdo do pacote, limitado a 4 caracteres.

Como o TCP fornece um fluxo contínuo de bytes e não preserva, por si só, os limites entre mensagens da aplicação, o protocolo deverá definir uma estratégia de framing.

A estratégia definitiva de framing será definida durante a evolução do protocolo para os próximos checkpoints. Entre as alternativas consideradas estão o uso de delimitadores e o uso de prefixo indicando o tamanho da mensagem.

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
- modelar a máquina de estados do protocolo;
- revisar trechos de código e depuração;
- discutir checksum, temporizador e fluxo de mensagens.

A IA foi utilizada como ferramenta de apoio, mas todas as decisões técnicas foram validadas pelo grupo antes de sua implementação.

## Status do projeto

Este README serve como base para a documentação do trabalho e deve evoluir junto com a implementação do código. As seções de uso, execução e protocolo podem ser ajustadas conforme o desenvolvimento avançar.
