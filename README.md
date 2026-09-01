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
       |  compilador/base_conhecimento.py    consulta -> trecho do Manual   (BM25 + reranker)
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
| Reconheceu mas trouxe o trecho errado | 1 (é 0 sem o reranker) |
| Empates na gramática | **0/50** |
| Frase destacada exata | 30/44 = 68% |
| Recusa fora de escopo (31 adversariais) | **31/31 = 100%** |
| Robustez a paráfrase | 23/25 |
| Testes | **81**, todos passando |

Os números acima são do **caminho do produto**, BM25 mais reranker. Rodando só com BM25
(`COBERTURA_RAPIDA=1`), a recuperação sobe para 44/44, o falso positivo some e o destaque cai
para 26/44. O reranker fica **não por essa troca**, que é discutível, e sim porque é a única
fonte da medida que o guardrail consome; a comparação completa está adiante e em §24.

**Tempo de resposta:** não é reprodutível o bastante para entrar como número. Três medições
da mesma pergunta pelo núcleo deram 1,4 s, 3,1 s e 10,5 s, porque o custo é dominado pela
passagem do reranker e varia com a quantidade de candidatos. O plano B fica na casa dos 20 s.

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
símbolo repetido em dois elementos da mesma regra, que é a condição da prova (§3).

Quando mais de uma regra casa, o desempate é por **três critérios sucessivos** (§21):

1. **cobertura**: vence a regra que cobre mais símbolos *distintos* da pergunta, que é
   *maximal munch* contado em símbolos e não em elementos;
2. **compacidade**: empatando, vence a de menor dispersão, com os símbolos mais próximos
   entre si, o que impede combinar símbolos de perguntas diferentes;
3. **exigência**: empatando ainda, vence a que exige mais símbolos obrigatórios.

A ordem de declaração resolve o resto, então a mesma entrada dá sempre o mesmo resultado.
O critério antigo era só o terceiro, e ele deixava `como_trancar` nunca disparar: empatava
com `matricula_ingressante` em obrigatórios e perdia por vir depois na tabela.

### Mais de uma intenção na mesma pergunta

O símbolo inicial da gramática é `pergunta := regra+`, e não `regra` (§22). `analisar_todas`
reconhece a regra vencedora, **retira da sequência os símbolos que a satisfizeram junto com
as demais ocorrências deles**, e recomeça sobre o que restou, até o limite de três intenções:

```python
sintatico.analisar_todas(tokens, maximo=3)   # [Reconhecimento, ...]
sintatico.analisar(tokens)                   # só a principal, usada na medição de cobertura
```

Cada intenção vira uma consulta e uma resposta próprias, rotuladas, com as fontes reunidas
numa lista só.

Validações que falham alto na importação, e não em produção: símbolo fora do léxico (o
análogo do identificador não declarado), regra composta só de opcionais, símbolo repetido em
dois elementos da mesma regra, intenção sem ação correspondente e ação sem regra que a
acione. Há ainda duas no léxico, para variante ambígua e para palavra que esteja ao mesmo
tempo no vocabulário e na lista de ruído.

**As regras derivam dos títulos de seção do Manual, não das 50 perguntas.** Os títulos foram
extraídos do PDF pelos atributos de fonte, porque o documento não tem marcadores nem sumário.
Por isso a medição de cobertura não é *in sample* (§8).

## Arquitetura

Montar o assistente inteiro é uma chamada, e desligar a inteligência artificial é um argumento:

```python
from rag.pipeline import montar_assistente

dialogo = montar_assistente()                      # núcleo + plano B
dialogo = montar_assistente(com_plano_b=False)     # só o compilador, sem modelo nenhum

resposta = dialogo.responder("Quantas faltas posso ter?")
resposta.origem      # Origem.NUCLEO | Origem.PLANO_B | Origem.NAO_ENTENDIDA
```


| Camada | Módulo | Papel |
|---|---|---|
| **Núcleo (compilador)** | `rag.compilador.lexico` | Tokeniza, normaliza a escrita e traduz variantes em símbolos. É a tabela de símbolos do reconhecedor: fixa, carregada antes da análise, e é contra ela que cada símbolo usado numa regra é validado |
| | `rag.compilador.gramatica` | A notação das regras e o compilador dela, com as validações |
| | `rag.compilador.sintatico` | Reconhece a intenção, ou devolve `None` e aciona o plano B |
| | `rag.compilador.semantico` | Traduz a intenção na consulta canônica e colhe os campos |
| | `rag.compilador.base_conhecimento` | Executa a consulta contra o Manual e destaca a frase que responde |
| | `rag.compilador.intencoes` | Só dados: léxico, gramática e ações, sem lógica |
| **Controlador** | `rag.compilador.dialogo` | Orquestra as fases e decide o plano B. Marca a origem de cada resposta |
| **Corpus** | `rag.corpus` | Carrega o PDF, normaliza e divide em trechos com sobreposição |
| **Recuperação** | `rag.recuperacao` | **BM25 Okapi do zero** com índice invertido, e o cross-encoder de segundo estágio |
| **Plano B** | `rag.ia` | Chatbot RAG com guardrail e piso de score, sobre Ollama. É o único que recebe o histórico da conversa |
| **Medição** | `rag.goldset` | Carrega o conjunto de perguntas de referência e resolve a relevância de cada trecho |
| **Montagem** | `rag.pipeline` | `montar_assistente(cfg)` monta o produto inteiro: é a única chamada que um ponto de entrada precisa fazer |
| **Parâmetros** | `rag.config` | Uma estrutura imutável com todos os valores fixos do trabalho |
| **Exibição** | `rag.apresentacao` | Saudação, recusa e o recorte dos trechos, igual na tela e no terminal |

O pacote `rag.compilador`, com exceção do controlador, **não importa nada além da biblioteca
padrão**: só `re`, `dataclasses`, `enum` e `collections.abc`. Nenhum gerador de parser, nenhuma
biblioteca de processamento de linguagem. É verificável por `grep`, inclusive contra `import`
escondido dentro de função:

```bash
grep -rhoE "^\s*(import|from) [a-z_.]+" src/rag/compilador/*.py | awk '{print $2}' | grep -v "^\." | sort -u
```

### O que cada camada de recuperação paga

A recuperação do produto é **BM25 mais reranker**, e as duas foram medidas separadamente
(§24, scripts em `scripts/estudo/`):

| | núcleo (44 reconhecidas) | plano B (top-5, 50 perguntas) | guardrail (31 adversariais) |
|---|---|---|---|
| **só BM25** | 44/44 · 0 falso positivo · destaque 26/44 | 45/50 | **2/31** |
| **BM25 + reranker** | 43/44 · 1 falso positivo · destaque 30/44 | **49/50** | **31/31** |

O reranker **não paga o próprio custo no núcleo**: ali a consulta já é canônica, escrita nas
palavras do documento, e casamento de palavra-chave basta. Ele paga nos outros dois: leva a
recuperação do plano B de 45 para 49, e é a **única** fonte da medida que o piso de −3,2
consome. Um piso sobre a pontuação do BM25 recusa 2 das 31 adversariais, porque as duas
populações se sobrepõem por inteiro (legítima mais fraca 4,45, adversarial mais forte 12,69).

A arquitetura que a medição recomenda é tirar o reranker do percurso do núcleo e mantê-lo no
plano B, o que são duas linhas em `pipeline.py`. **Não feito**, para não invalidar os números
já publicados no texto do TCC.

O próprio compilador serve de **primeiro estágio do guardrail**: recusar quando a pergunta não
dispara símbolo de assunto algum pega 20 das 31 adversariais, sem custo nas legítimas, e falha
exatamente na categoria ambígua ("horário da cantina" dispara `HORARIO`). Medido, **não
implementado**.

### O plano B e a conversa

O núcleo opera sempre sobre a mensagem isolada. O plano B é o único que recebe os últimos
quatro turnos, e quando há histórico ele faz **duas** chamadas ao modelo:

```python
consulta = gerador.reescrever_consulta(pergunta, historico)  # 1ª: pergunta autônoma -> busca
resultados = recuperador.buscar(consulta, top_k)
if resultados[0].score < piso_score:
    return RECUSA                                            # o modelo não é chamado
return gerador.gerar(pergunta, contextos, historico)         # 2ª: a redação
```

A primeira resolve referências elípticas ("e as presenciais?") para que a **recuperação**
funcione; quem vai para a geração é a pergunta original. `tests/test_dialogo.py` verifica que
o histórico não chega ao núcleo.

## Como rodar

**1. Ambiente**

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Linux/Mac:  source .venv/bin/activate
pip install -e ".[dev]"

pytest                                        # 81 testes, rápidos, sem baixar modelo
```

Para **reproduzir as medições**, e não só usar o projeto, instale o ambiente exato em que elas
foram feitas — o piso de score do guardrail é calibrado contra os escores destas versões:

```bash
pip install torch==2.13.0 --index-url https://download.pytorch.org/whl/cpu   # build só CPU
pip install -r requirements.txt
pip install -e . --no-deps
```

**2. O corpus.** O Manual do Aluno **não vem no repositório** (`data/raw/` está no `.gitignore`).
Sem ele, tudo abaixo falha com `FileNotFoundError`. Coloque o PDF em:

```
data/raw/manual_aluno_unip_2026.pdf
```

O nome do arquivo é o padrão de `rag.config.Config.caminho_manual`; para usar outro, mude lá.

**3. O produto**

```bash
python servidor.py                                  # tela em http://localhost:8000, sem dependência extra
python scripts/produto/assistente_institucional.py  # a mesma conversa no terminal
```

O plano B exige [Ollama](https://ollama.com) no ar, com `ollama pull llama3.1:8b`. **Sem ele o
núcleo responde normalmente**, e o que a gramática não reconhece devolve a mensagem de não
entendimento: é a demonstração de que o assistente funciona com a IA desligada.

Na primeira execução o cross-encoder (470 MB) é baixado do HuggingFace. Depois disso ele sai do
cache local, e a partida não depende mais de rede.

**4. As medições**

```bash
python scripts/produto/cobertura_nucleo.py            # quanto o núcleo responde sem IA
python scripts/produto/institucional_guardrail.py     # guardrail adversarial, 31 perguntas fora de escopo
python scripts/produto/institucional_acuracia.py      # acurácia de resposta, 50 perguntas (exige Ollama)
```

A cobertura tem um modo rápido, que pula o cross-encoder e roda em segundos:

```bash
COBERTURA_RAPIDA=1 python scripts/produto/cobertura_nucleo.py     # bash
$env:COBERTURA_RAPIDA=1; python scripts/produto/cobertura_nucleo.py   # PowerShell
```

Para reconstruir o conjunto de perguntas de referência a partir do PDF (só é preciso quando o
corpus muda; o JSON pronto está versionado em `data/goldsets/`):

```bash
python scripts/goldsets/construir_goldset_institucional.py
```

## Decisões de design

- **BM25 do zero** (`recuperacao.py`): índice invertido, IDF Okapi e normalização por
  tamanho, sem nenhuma biblioteca de busca pronta.
- **Consulta canônica**: a frase do aluno nunca chega ao recuperador. A variação de escrita
  morre na análise léxica e a intenção é traduzida numa consulta escrita nas palavras do
  documento.
- **A base de conhecimento não tem piso de score**, e é deliberado: ali o portão é a
  gramática. Pergunta fora de escopo não casa regra e nunca chega à busca (§11).
- **Regra de um símbolo obrigatório só para termo inequívoco** do documento. Palavra que uma
  pergunta fora de escopo possa carregar exige um segundo símbolo, senão vira superfície de
  vazamento (§6).
- **Chunking fixo** em 180 tokens com 45 de sobreposição: mudar aqui invalidaria todas as
  medições já feitas, porque move a fronteira dos trechos.
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

A assimetria e proposital: **o nucleo e uma pasta com sete arquivos; a IA inteira e um arquivo
so.** A forma do diretorio ja diz onde esta a intervencao.

```
src/rag/compilador/    O NUCLEO, sem modelo e sem peso treinado
    lexico.py            fase 1: tokeniza, normaliza e canoniza sinonimos
    gramatica.py         fase 2: a notacao das regras de intencao e a compilacao dela
    sintatico.py         fase 2: casa os simbolos com as regras
    semantico.py         fase 3: preenche campos e monta a consulta canonica
    intencoes.py         os dados: 77 regras, vocabulario e acoes do Manual
    base_conhecimento.py executa a consulta no Manual e destaca a frase que responde
    dialogo.py           o controlador: decide entre nucleo e plano B

src/rag/ia.py          A INTELIGENCIA ARTIFICIAL, em papel secundario:
                       o gerador sobre Ollama e o chatbot RAG com o piso de score
src/rag/recuperacao.py BM25 do zero e o reranker; infraestrutura usada pelos dois
src/rag/corpus.py      o texto de onde as respostas saem: PDF, normalizacao e trechos
src/rag/goldset.py     carga do conjunto de perguntas de referencia
src/rag/config.py      todos os parametros fixos, numa dataclass congelada
src/rag/pipeline.py    montar_assistente(): do PDF ao assistente pronto
src/rag/apresentacao.py  saudacao, recusa e o recorte dos trechos citados

servidor.py            servidor da biblioteca padrao que serve web/index.html
web/index.html         a tela do produto: HTML, CSS e JS num arquivo so

scripts/produto/       o assistente e as medicoes em uso (4)
scripts/goldsets/      construcao do conjunto de referencia (1)
scripts/estudo/        medicoes que sustentam decisoes de arquitetura (3)
scripts/LEIA-ME.md     o que cada script faz

tests/                 81 testes
docs/decisoes.md       o porque de cada decisao do nucleo, com as medicoes
data/goldsets/         o conjunto de referencia validado (JSON)
data/raw/              corpora brutos, fora do git
outputs/               metricas (CSV), regeneraveis
```
