# Assistente do Manual do Aluno

> Um assistente de perguntas e respostas em português cujo **núcleo é um front-end de
> compilador**. A pergunta do aluno passa por análise **léxica, sintática e semântica**, e a
> intenção reconhecida é respondida direto do documento, **sem modelo de linguagem no
> caminho**. A IA entra só onde a gramática não alcança, como plano B.

Desligar a IA não desliga o assistente: ele continua respondendo tudo o que a gramática
cobre, hoje **44 das 50 perguntas** do conjunto de avaliação. Essa é a tese do projeto, e é
verificável a qualquer momento pela procedência que acompanha cada resposta.

A escolha da estratégia de busca que sustenta esse núcleo não foi arbitrada: veio de um
**estudo comparativo medido** (densa, esparsa e híbrida, com teste estatístico pareado) que
está documentado mais abaixo.

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
| | `rag.recuperacao.densa` | Similaridade de cosseno sobre embeddings |
| | `rag.recuperacao.hibrida` | Fusão por RRF ou soma ponderada |
| | `rag.recuperacao.reranker` | Cross-encoder de segundo estágio |
| **Plano B** | `rag.ia.chatbot` · `generator` · `fabrica` | Chatbot RAG com guardrail e piso de score, sobre Ollama ou llama.cpp |
| | `rag.ia.gramatica_citacao` · `json_estruturado` | Autômato e gramática que restringem a saída do modelo |
| **Avaliação** | `rag.avaliacao.metricas` · `stats` · `goldset` | Recall@k, MRR, Wilcoxon pareado com Holm e tamanho de efeito |
| **Montagem** | `rag.pipeline` · `rag.config` · `rag.apresentacao` | Índice, parâmetros fixos e a formatação comum à tela e ao terminal |

O pacote `rag.compilador`, com exceção do controlador, **não importa nada além da biblioteca padrão**:
só `re`, `unicodedata`, `dataclasses`, `enum` e `collections.abc`. Nenhum gerador de parser,
nenhuma biblioteca de processamento de linguagem. É verificável por `grep`.

A recuperação do produto é **BM25 mais reranker**, e não a híbrida vencedora do estudo
comparativo. O motivo está em [`docs/decisoes.md`](docs/decisoes.md) §10: quem consulta o
Manual é a consulta canônica, já escrita nas palavras do documento, e nesse caminho o BM25
puro empata com a híbrida. O cross-encoder permanece porque o **piso de score** de −3,2, que é
o guardrail do plano B, depende do escore dele.

## Como rodar

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Linux/Mac:  source .venv/bin/activate
pip install -e ".[dev]"

pytest                                        # 98 testes, rápidos, sem baixar modelo
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

O estudo comparativo, que é reprodutível independentemente do produto:

```bash
python scripts/estudo/marco0_smoke.py                # baixa o e5 (~440 MB) na primeira vez
python scripts/goldsets/construir_goldset_manual.py  # reconstrói e valida o gold-set do Manual
python scripts/estudo/marco1_manual.py               # Marco 1, escreve outputs/marco1_*.csv
python scripts/estudo/marco2_pira.py                 # Marco 2, Pirá 2.0
python scripts/goldsets/construir_goldset_pcdt.py    # gold-set de saúde, pares leigo e técnico
python scripts/estudo/marco3_pcdt.py                 # Marco 3, PCDT com reranker
```

Dados do Pirá, baixados do repositório oficial
([C4AI/Pira](https://github.com/C4AI/Pira), CC BY 4.0) para `data/raw/pira/`, fora do git:

```bash
for f in train validation test; do \
  gh api "repos/C4AI/Pira/contents/Data/$f.csv" -H "Accept: application/vnd.github.raw" \
    > "data/raw/pira/$f.csv"; done
```

Os PCDTs vêm da CONITEC para `data/raw/pcdt/`; as URLs oficiais estão no cabeçalho de
`scripts/goldsets/construir_goldset_pcdt.py`.

## O estudo comparativo que sustenta a recuperação

Antes do núcleo existir, o projeto mediu qual estratégia de busca recupera melhor o trecho
correto: **densa** (vetorial), **esparsa** (BM25) ou **híbrida**. A metodologia é de marcos
incrementais, seguindo [`docs/protocolo_rag_chatbot.md`](docs/protocolo_rag_chatbot.md): dado
fácil e controlado primeiro, para caçar bug barato, e dado real e difícil depois, para
responder a pergunta de verdade, sempre com teste estatístico pareado.

| Marco | Corpus | Portão | Resultado |
|---|---|---|---|
| **0** Smoke test | Texto curto, 5 perguntas triviais | as 3 recuperam o trecho óbvio | passou |
| **1** Manual do Aluno | Manual UNIP 2026, 18 perguntas | ≥1 estratégia com recall@5 > 70% | passou, e satura em 100% |
| **2** Pirá 2.0 | 757 abstracts científicos, 227 perguntas | BM25 na faixa da literatura | passou, e **Q1 discrimina** |
| **3** Saúde | 4 PCDTs do SUS, 1330 trechos, 24 perguntas | gap leigo e técnico, mais o reranker | direção sustentada |

**Marco 1.** As três chegam a recall@5 de 100%, então o corpus **satura e não discrimina**. O
marco cumpre o papel de validar o encanamento, não o de responder à pergunta de pesquisa. A
híbrida lidera em MRR (0,917 contra 0,903 da esparsa e 0,880 da densa), mas nada sobrevive a
Holm com n=18.

**Marco 2 (Pirá 2.0).** Com n=227 o teste tem poder real.

| estratégia | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| densa (e5) | 0.52 | 0.71 | 0.78 | 0.87 | 0.642 |
| esparsa (BM25) | 0.56 | 0.83 | 0.86 | 0.90 | 0.698 |
| **híbrida** | 0.52 | 0.81 | **0.89** | **0.93** | 0.680 |

Portão: BM25 com recall@10 de 0,90, batendo o valor do paper e confirmando que o corpus e a
tokenização estão corretos. Em recall@5, **híbrida > densa** com efeito +0,71 e p_holm=0,0001,
e **esparsa > densa** com efeito +0,35 e p_holm=0,025. **Híbrida e esparsa empatam
estatisticamente** (p=0,178). O achado replica o do paper: no Pirá o BM25 supera o denso zero
shot, porque o domínio técnico favorece o casamento léxico e o e5 trunca abstracts longos.

**Marco 3 (saúde).** Corpus difícil de propósito, com 24 perguntas em **pares de vocabulário
leigo e técnico** apontando para o mesmo trecho. Com n=24 valem direção e tamanho de efeito.

| estratégia | R@5 leigo | R@5 técnico | p pareado |
|---|---|---|---|
| densa | 0.33 | 0.67 | 0.125 |
| esparsa (BM25) | **0.17** | **0.83** | **0.008** |
| híbrida | 0.42 | 0.83 | 0.062 |

Todas pioram no vocabulário leigo, mas o **BM25 desaba** (0,17 contra 0,83, significativo),
que é dependência léxica pura. A **densa é a que menos sofre**, porque a busca semântica
atravessa parte da distância entre o termo do aluno e o termo do documento. É exatamente o
fenômeno que o corpus foi desenhado para expor, e é a razão de o produto **não** entregar a
frase crua do usuário à busca.

O **reranker** (cross-encoder sobre a híbrida) leva o R@1 de 0,29 para 0,50 e o MRR de 0,411
para 0,581, com efeito +0,58. O ganho se concentra no topo do ranking, que é o que importa
quando a primeira fonte é a que vira resposta.

Uma limitação registrada: a fusão por RRF pode ficar **abaixo da densa pura** quando um
recuperador acerta forte e o outro falha, porque a média de ranks dilui o acerto isolado. O
caso foi diagnosticado em detalhe e um experimento de fusão alternativa está em
`scripts/estudo/exp_fusao_reranker.py`, mantido para reprodução e sem efeito no produto.

## A intervenção anterior: gramática na decodificação

Antes do pivô para a entrada, a contribuição de Ciência da Computação atacava a **saída** do
modelo de linguagem. Os dois módulos continuam no repositório, testados isoladamente:

- **`ia/gramatica_citacao.py`** define a gramática regular do formato de citação `[n]` e o
  **autômato finito determinístico que a reconhece, escrito à mão**. O número é casado por um
  autômato de prefixos, o que elimina becos sem saída por construção. `RestritorCitacao` é um
  *logits processor*: a cada passo avança o autômato e põe `-inf` no logit de todo token que
  levaria a uma cadeia inválida.
- **`ia/json_estruturado.py`** sobe um nível na hierarquia. Um objeto JSON é **livre
  de contexto**, porque o aninhamento exige pilha. O esquema é autorado à mão em GBNF, com
  `fonte ::= "1" | ... | "K"`, o que torna **impossível por construção** um índice de fonte
  fora da faixa. A alternância explícita foi escrita justamente porque o JSON Schema do motor
  garante apenas que o valor é inteiro, e não que ele está dentro do intervalo de trechos
  efetivamente presentes no contexto.

Os experimentos são `scripts/estudo/exp_gramatica.py` e `scripts/estudo/exp_json.py`, e exigem
`llama-cpp-python` com um GGUF apontado por `GGUF_MODEL`. Nenhum dos dois está no caminho do
produto hoje.

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
- **Pareamento explícito no Wilcoxon** (`avaliacao.execucao.series_pareadas`), alinhando os vetores
  pela mesma ordem de perguntas.
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
    generator.py         a interface do gerador
    llamacpp.py          o modelo local
    fabrica.py           escolhe a implementacao pelo config
    chatbot.py           monta a resposta a partir dos trechos recuperados
    gramatica_citacao.py gramatica e automato que restringem a SAIDA do modelo
    json_estruturado.py  saida estruturada validada

src/rag/recuperacao/   infraestrutura usada pelos dois
    esparsa.py           BM25 escrito do zero (o que o nucleo usa)
    densa.py             busca vetorial
    hibrida.py           fusao das duas por RRF
    reranker.py          reordenacao por cross-encoder
    embeddings.py        o modelo de embedding
    base.py, uniao.py    contrato comum e a fusao alternativa do estudo

src/rag/corpus/        o texto de onde as respostas saem: PDF, normalizacao e trechos
src/rag/avaliacao/     metricas, gold-sets e estatistica (nao entra no produto)
src/rag/dados/         leitura dos conjuntos externos do estudo
src/rag/config.py      o config.yaml tipado
src/rag/pipeline.py    monta indice e recuperadores
src/rag/apresentacao.py  formata a resposta para exibicao

servidor.py            servidor da biblioteca padrao que serve web/index.html
web/index.html         a tela do produto: HTML, CSS e JS num arquivo so
config.yaml            parametros fixos do experimento

scripts/produto/       o assistente e as medicoes em uso (4)
scripts/goldsets/      construcao dos conjuntos de avaliacao (3)
scripts/estudo/        o comparativo de recuperacao e a decodificacao restrita (13)
scripts/LEIA-ME.md     o que cada script faz

tests/                 98 testes
docs/decisoes.md       o porque de cada decisao do nucleo, com as medicoes
docs/protocolo_rag_chatbot.md   o protocolo experimental
data/goldsets/         gold-sets validados (JSON)
data/raw/              corpora brutos, fora do git
outputs/               metricas (CSV), regeneraveis
```

A decodificacao restrita, em `ia/gramatica_citacao.py`, tambem e tecnica de compilador, mas
aplicada a **saida** do modelo. Foi a intervencao anterior ao pivo de 13/08/2026 e hoje vale
como resultado preliminar; o nucleo atual atua sobre a **entrada**.
