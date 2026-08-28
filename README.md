# Assistente do Manual do Aluno

> Um assistente de perguntas e respostas em português cujo **núcleo é um front-end de
> compilador**. A pergunta do aluno passa por análise **léxica, sintática e semântica**, e a
> intenção reconhecida é respondida direto do documento, **sem modelo de linguagem no
> caminho**. A IA entra só onde a gramática não alcança, como plano B.

Desligar a IA não desliga o assistente: ele continua respondendo tudo o que a gramática
cobre, hoje **44 das 50 perguntas** do conjunto de avaliação. Essa é a tese do projeto, e é
verificável a qualquer momento pela procedência que acompanha cada resposta.

## A ideia

Um compilador não entende o programa inteiro por adivinhação. Ele reconhece uma linguagem
descrita por uma gramática, e o que não pertence a essa linguagem é rejeitado de forma
explícita. Aqui a mesma máquina é apontada para a pergunta do aluno: a gramática não descreve
o português, descreve as **formas de pergunta** que o Manual do Aluno é capaz de responder.

Disso saem três propriedades que um chatbot baseado só em modelo de linguagem não tem:

- **A resposta é o texto do documento**, não uma redação sobre ele. Não há o que alucinar.
- **O que não é reconhecido é reconhecidamente não reconhecido.** O `None` do analisador
  sintático é o sinal de plano B, não um palpite.
- **A cobertura é auditável.** Cada resposta carrega a origem, então dá para medir quanto o
  núcleo responde sozinho em vez de estimar.

## O caminho de uma pergunta

```
"Quantas faltas posso ter em Cálculo?"
       |
       |  compilador/lexico.py          texto  ->  tokens tipados
       v
  [QUANTIDADE] [FALTA] [PODER]   ("ter", "em" = ruído · "Cálculo" = desconhecido)
       |
       |  compilador/sintatico.py       tokens ->  intenção          (segundo compilador/gramatica.py)
       v
  intenção = limite_faltas
       |
       |  compilador/semantico.py       intenção -> consulta canônica
       v
  "frequência obrigatória em cada disciplina, aulas dadas"  + {disciplina: Cálculo}
       |
       |  compilador/base_conhecimento.py    consulta -> trecho do Manual   (BM25)
       v
  3 trechos + a frase que responde
       |
       |  compilador/dialogo.py         respondeu? senão, plano B
       v
  resposta com origem NÚCLEO
```

Repare no terceiro passo: **nenhuma palavra do aluno chega à busca**. Quem consulta o Manual
é uma consulta canônica escrita no vocabulário do próprio documento, o que é o *lowering* de
um compilador. É esse mecanismo que faz o casamento léxico acontecer entre duas frases do
mesmo texto, e não entre a gíria do aluno e o juridiquês do regimento.

## Cobertura do núcleo

Medido em 50 perguntas escritas em linguagem de aluno (`scripts/produto/cobertura_nucleo.py`), sobre
o Manual do Aluno UNIP 2026 dividido em 173 trechos.

| Medida | Valor |
|---|---|
| Perguntas reconhecidas pelo núcleo | **44/50 = 88%** |
| Trecho correto entre os recuperados | **43/44 = 98%** |
| Intenção errada (falso positivo) | **0** |
| Empates na gramática | **0/50** |
| Frase destacada exata | 30/44 = 68% |
| Recusa fora de escopo (31 adversariais) | **31/31 = 100%** |
| Robustez a paráfrase | 23/25 |
| Tempo de resposta | **~1,2 s** pelo núcleo · ~19 s pelo plano B |
| Testes | **98**, todos passando |

Os números acima são do **caminho do produto**, BM25 mais reranker. Rodando só com BM25
(`COBERTURA_RAPIDA=1`), a recuperação sobe para 44/44 e o destaque cai para 26/44: o reranker
troca um acerto de recuperação por quatro de destaque. A troca compensa e por isso ele fica,
mas a tabela precisa ser a do caminho que o aluno usa, e não a do modo rápido.

Duas observações honestas sobre a tabela. A **frase destacada** é o ponto fraco conhecido: o
trecho certo é recuperado em 98% dos casos, mas a sentença exata que responde é acertada em
68%. Quatro critérios alternativos foram implementados e medidos, e todos ficaram piores; a
tabela está em [`docs/decisoes.md`](docs/decisoes.md) §9. E o **teste adversarial** roda pelo
`Dialogo`, ou seja, pelo mesmo caminho do produto: uma resposta de origem `NUCLEO` numa
pergunta adversarial conta como vazamento por definição, independente do texto. Quando o
teste ainda instanciava o plano B direto, ele era cego para o núcleo e deixou passar um
vazamento real ([`docs/decisoes.md`](docs/decisoes.md) §14).

O **plano B** tem medição própria, das mesmas 50 perguntas: recupera o trecho certo em 98% e
responde com o conteúdo correto em 92%, com os erros concentrados na geração e não na
recuperação. O A/B do prompt, a ressalva de que o piso de score foi calibrado nas mesmas 50
perguntas e a visão consolidada de produto e estudo estão em
[`docs/relatorio_institucional.md`](docs/relatorio_institucional.md) e
[`docs/relatorio_final.md`](docs/relatorio_final.md).

## A gramática de intenções

O alfabeto não é o caractere: é o **símbolo canônico** que a análise léxica produz. Hoje são
**89 símbolos** (12 marcadores e 77 assuntos) cobertos por **268 variantes de escrita**, mais
110 palavras tratadas como ruído. Sobre esse alfabeto há **77 regras**, cada uma nomeando uma
intenção.

As regras não são codificadas à mão em Python. Elas são **escritas numa notação e
compiladas**, o que faz do projeto um compilador dentro de um compilador:

```python
"limite_faltas":            "QUANTIDADE&FALTA&PODER|OBRIGATORIO|DISCIPLINA"
"prazo_trancamento":        "QUANTIDADE|PRAZO TRANCAR MATRICULA?"
"consequencia_sem_trancar": "CONSEQUENCIA NEGACAO+TRANCAR"
"estagio_obrigatorio":      "QUE ESTAGIO OBRIGATORIO !NEGACAO"
```

| Operador | Significado | Formalmente |
|---|---|---|
| espaço | sequência, e a ordem importa | concatenação com `Σ*` entre os símbolos |
| `?` | elemento opcional | união com a cadeia vazia |
| `\|` | símbolos equivalentes na posição | união |
| `+` | adjacência, o símbolo logo em seguida | concatenação **sem** `Σ*` |
| `&` | os dois presentes, em qualquer ordem | união das permutações |
| `!` | exclusão, a regra cai se o símbolo aparecer | diferença `L \ (Σ* s Σ*)` |

A regra casa como **subsequência**, ignorando o que sobra na frase. Isso é açúcar sintático:
`QUANTIDADE FALTA` denota `Σ* QUANTIDADE Σ* FALTA Σ*`, que **continua sendo linguagem
regular** sobre o alfabeto de símbolos, sem exigir pilha. Adjacência e exclusão também fecham
no regular. O argumento completo está em [`docs/decisoes.md`](docs/decisoes.md) §2 e §4.

O reconhecimento é **guloso**, uma varredura da esquerda para a direita por regra, e é
**exato** porque a classe de gramáticas foi restringida: `Gramatica.de_notacao` rejeita
símbolo repetido em dois elementos da mesma regra, que é a condição da prova (§3). Quando
mais de uma regra casa, vence a de mais símbolos obrigatórios, o que é *maximal munch*
contado em símbolos e não em elementos (§5).

Três validações falham alto na importação, e não em produção: símbolo fora do léxico (o
análogo do identificador não declarado), regra composta só de opcionais, e intenção sem ação
correspondente na tabela semântica.

**As regras derivam dos títulos de seção do Manual, não das 50 perguntas.** Os títulos foram
extraídos do PDF pelos atributos de fonte, porque o documento não tem marcadores nem sumário.
Por isso a medição de cobertura não é *in sample* (§8).

## Arquitetura

| Camada | Módulo | Papel |
|---|---|---|
| **Núcleo (compilador)** | `rag.compilador.lexico` | Tokeniza, normaliza a escrita e traduz variantes em símbolos. É a tabela de símbolos do reconhecedor: fixa, carregada antes da análise, e é contra ela que cada símbolo usado numa regra é validado |
| | `rag.compilador.gramatica` | A notação das regras e o compilador dela, com as validações |
| | `rag.compilador.sintatico` | Reconhece a intenção, ou devolve `None` e aciona o plano B |
| | `rag.compilador.semantico` | Traduz a intenção na consulta canônica e colhe os campos |
| | `rag.compilador.base_conhecimento` | Executa a consulta contra o Manual e destaca a frase que responde |
| | `rag.compilador.intencoes` | Só dados: léxico, gramática e ações, sem lógica |
| **Controlador** | `rag.compilador.dialogo` | Orquestra as fases e decide o plano B. Marca a origem de cada resposta |
| **Corpus** | `rag.corpus.loaders` · `chunking` | Carrega o PDF, normaliza e divide em trechos com sobreposição |
| **Recuperação** | `rag.recuperacao.esparsa` | **BM25 Okapi do zero**, com índice invertido |
| | `rag.recuperacao.reranker` | Cross-encoder de segundo estágio |
| **Plano B** | `rag.ia.chatbot` · `generator` · `fabrica` | Chatbot RAG com guardrail e piso de score, sobre Ollama |
| **Medição** | `rag.avaliacao.goldset` | Carrega o conjunto de perguntas de referência e resolve a relevância de cada trecho |
| **Montagem** | `rag.pipeline` · `rag.config` · `rag.apresentacao` | Índice, parâmetros fixos e a formatação comum à tela e ao terminal |

O pacote `rag.compilador`, com exceção do controlador, **não importa nada além da biblioteca padrão**:
só `re`, `unicodedata`, `dataclasses`, `enum` e `collections.abc`. Nenhum gerador de parser,
nenhuma biblioteca de processamento de linguagem. É verificável por `grep`.

A recuperação do produto é **BM25 mais reranker**. Quem consulta o Manual é a consulta
canônica, já escrita nas palavras do documento, e nesse caminho o BM25 basta: a medição que
levou a essa escolha está em [`docs/decisoes.md`](docs/decisoes.md) §10. O cross-encoder
permanece porque o **piso de score** de −3,2, que é o guardrail do plano B, depende do
escore dele.

## Como rodar

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Linux/Mac:  source .venv/bin/activate
pip install -e ".[dev]"

pytest                                        # 77 testes, rápidos, sem baixar modelo
```

O produto, sobre o Manual do Aluno:

```bash
python servidor.py                                  # tela em http://localhost:8000, sem dependência extra
python scripts/produto/assistente_institucional.py  # a mesma conversa no terminal
```

As medições:

```bash
python scripts/produto/cobertura_nucleo.py                     # quanto o núcleo responde sem IA
COBERTURA_RAPIDA=1 python scripts/produto/cobertura_nucleo.py  # só BM25, sem carregar o cross-encoder
python scripts/produto/institucional_acuracia.py               # acurácia de resposta, 50 perguntas
python scripts/produto/institucional_guardrail.py              # guardrail adversarial, 31 perguntas fora de escopo
```

O plano B exige [Ollama](https://ollama.com) com `ollama pull llama3.1:8b`. Sem ele, o núcleo
responde normalmente e o que não é reconhecido devolve a mensagem de não entendimento, que é
justamente a demonstração de que o assistente funciona com a IA desligada.

## Decisões de design

- **BM25 do zero** (`recuperacao/esparsa.py`): índice invertido, IDF Okapi e normalização por
  tamanho, sem nenhuma biblioteca de busca pronta.
- **Consulta canônica**: a frase do aluno nunca chega ao recuperador. A variação de escrita
  morre na análise léxica e a intenção é traduzida numa consulta escrita nas palavras do
  documento.
- **A base de conhecimento não tem piso de score**, e é deliberado: ali o portão é a
  gramática. Pergunta fora de escopo não casa regra e nunca chega à busca (§11).
- **Regra de um símbolo obrigatório só para termo inequívoco** do documento. Palavra que uma
  pergunta fora de escopo possa carregar exige um segundo símbolo, senão vira superfície de
  vazamento (§6).
- **Embedding fixo** (`multilingual-e5-base`) e chunking fixo em 180 tokens com 45 de
  sobreposição, para que a comparação medisse a busca e não o pré-processamento.
- **Relevância por sobreposição de offsets**: o trecho-fonte é substring exato do corpus
  limpo, o que é robusto à fronteira dos trechos.
- **Duas limitações conhecidas e não corrigidas**, por decisão registrada: o plano B às vezes
  cita um índice diferente do da fonte real, e a tela reporta isso fielmente; e cabeçalhos de
  página do PDF aparecem dentro dos trechos, porque limpá-los mudaria as fronteiras e
  invalidaria todas as medições.

## Estrutura

O corte que mais importa separa **o que entende a pergunta** do **que gera texto**. O primeiro
é compilador e não usa aprendizado de máquina; o segundo é o plano B. `corpus` e `recuperacao`
não pertencem a nenhum dos dois: são a infraestrutura que ambos leem.

```
src/rag/compilador/    O NUCLEO, sem modelo e sem peso treinado
    lexico.py            fase 1: tokeniza, normaliza e canoniza sinonimos
    gramatica.py         fase 2: a notacao das regras de intencao
    sintatico.py         fase 2: casa os simbolos com as regras
    semantico.py         fase 3: preenche campos e monta a consulta
    intencoes.py         os dados: 77 regras, vocabulario e acoes do Manual
    base_conhecimento.py executa a consulta no Manual
    dialogo.py           o controlador: decide entre nucleo e plano B

src/rag/ia/            A INTELIGENCIA ARTIFICIAL, em papel secundario
    generator.py         a interface do gerador e o backend Ollama
    fabrica.py           monta o gerador a partir do config
    chatbot.py           monta a resposta a partir dos trechos recuperados

src/rag/recuperacao/   infraestrutura usada pelos dois
    esparsa.py           BM25 escrito do zero (o que o nucleo usa)
    reranker.py          reordenacao por cross-encoder; sustenta o piso de score
    base.py              o contrato comum

src/rag/corpus/        o texto de onde as respostas saem: PDF, normalizacao e trechos
src/rag/avaliacao/     carga do conjunto de perguntas de referencia
src/rag/config.py      o config.yaml tipado
src/rag/pipeline.py    monta indice e recuperador
src/rag/apresentacao.py  formata a resposta para exibicao

servidor.py            servidor da biblioteca padrao que serve web/index.html
web/index.html         a tela do produto: HTML, CSS e JS num arquivo so
config.yaml            parametros fixos

scripts/produto/       o assistente e as medicoes em uso (4)
scripts/goldsets/      construcao do conjunto de referencia (1)
scripts/LEIA-ME.md     o que cada script faz

tests/                 77 testes
docs/decisoes.md       o porque de cada decisao do nucleo, com as medicoes
data/goldsets/         o conjunto de referencia validado (JSON)
data/raw/              corpora brutos, fora do git
outputs/               metricas (CSV), regeneraveis
```
