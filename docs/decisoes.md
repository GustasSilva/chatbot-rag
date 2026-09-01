# Decisões de projeto do núcleo

Registro do raciocínio por trás do código de `src/rag/compilador/` e da configuração do produto. Os
módulos têm docstrings curtas e apontam para cá; o detalhe, as medições e as alternativas
rejeitadas ficam neste arquivo.

Todos os números vêm das 50 perguntas de `data/goldsets/institucional.json`, medidas por
`scripts/produto/cobertura_nucleo.py` e `scripts/produto/institucional_guardrail.py`.

---

## 1. Por que gramática de intenções, e não a frase inteira

Linguagem natural é ambígua e variada demais para uma gramática formal cobrir a sentença
completa. A gramática aqui reconhece o **padrão que importa** e ignora o resto: casa uma
sequência de símbolos e deixa passar as palavras entre eles.

O alfabeto não é o caractere, é o **símbolo canônico** produzido pela análise léxica (`FALTA`,
`TRANCAR`, `QUANTIDADE`). Cada regra é uma sequência desses símbolos e nomeia uma intenção.

## 2. Casamento por ilha continua regular

A regra não precisa cobrir a frase toda: casa como subsequência. Isso parece uma concessão
teórica, mas não é. `QUANTIDADE FALTA` é açúcar sintático para `Σ* QUANTIDADE Σ* FALTA Σ*`, que
é uma linguagem regular. As duas extensões seguem no regular:

- **adjacência** (`A+B`) é concatenação sem `Σ*` entre os elementos;
- **exclusão** (`!A`) é a diferença `L \ (Σ* A Σ*)`.

Linguagens regulares são fechadas para concatenação, complemento e interseção, então todo o
reconhecimento cabe num autômato finito: sem pilha, sem retrocesso.

## 3. Por que o reconhecimento guloso é exato

A fase sintática varre os tokens uma vez, da esquerda para a direita, pegando a primeira
ocorrência de cada elemento. Guloso assim normalmente é incompleto: em `X? X`, consumir o único
`X` no opcional faz o obrigatório falhar, e seria preciso retroceder.

A saída foi **restringir a classe de gramática em vez de complicar o algoritmo**:
`Gramatica.de_notacao` rejeita símbolo repetido em elementos diferentes da mesma regra. Com os
elementos disjuntos, o token que casa um elemento não serve a nenhum outro, então pegar a
ocorrência mais à esquerda nunca custa um casamento possível — ela deixa o maior sufixo para os
elementos seguintes. O mesmo argumento vale para o grupo de ordem livre (`A&B`), que consome o
mínimo ao pegar a primeira ocorrência de cada símbolo.

Por isso a cadeia adjacente é modelada como **um elemento** com vários símbolos, e não como
elementos separados: como par atômico, o argumento de troca continua valendo.

## 4. Adjacência e exclusão: os dois casos que as motivaram

Ambos medidos no gold-set, e em ambos a pergunta é clara para um leitor humano — o empate era
imprecisão da gramática, não ambiguidade da língua.

| Pergunta | Problema | Mecanismo |
|---|---|---|
| "consequência de **não trancar** a matrícula" | a regra do "não matricular" também casava, pulando `TRANCAR` para alcançar `MATRICULA` | adjacência: `CONSEQUENCIA NEGACAO+TRANCAR` prende o "não" ao que ele nega |
| "o que é o estágio **não** obrigatório" | a regra do estágio obrigatório casava junto, porque ignorava a negação | exclusão: `QUE ESTAGIO OBRIGATORIO !NEGACAO` se descarta |

Resultado: empates caíram de 2/50 para **0/50**. As 6 sobreposições restantes se resolvem todas
pelo critério de especificidade.

Adjacência é medida no fluxo de **símbolos**, não de palavras: em "não fizer a matrícula",
`NEGACAO` e `MATRICULA` são adjacentes porque "fizer" não é símbolo. Exigir palavras coladas
seria rígido demais para língua natural.

## 5. O peso do desempate conta símbolos, não elementos

Quando duas regras casam, vence a que exigiu mais símbolos obrigatórios — o mesmo *maximal
munch* que um analisador léxico usa para preferir a palavra-chave mais longa.

Contar **elementos** foi um erro que se pagou na medição: a cadeia adjacente
`NEGACAO+OBRIGATORIO` dá conta de dois símbolos da frase e pesava um só, e por isso uma regra
específica passou a perder de uma genérica. Passou a contar símbolos (`1 + len(extras)`).

Exclusão não conta: é condição de guarda, não pedaço da pergunta que a regra explicou.

## 6. Regra de um único símbolo obrigatório é superfície de vazamento

Reservada a termo inequívoco do documento ("jubilamento", "trote"). Palavra que uma pergunta
fora de escopo possa carregar exige um segundo símbolo, senão "quanto custa a mensalidade" e
"qual a senha do wi-fi" passam a ser respondidas em vez de recusadas.

O caso mais instrutivo: `limite_faltas` exigia só `QUANTIDADE FALTA`, e por isso respondia
*"quantas faltas eu já tenho?"* — pergunta sobre dado pessoal — com a regra geral dos 75%.
Passou a exigir um terceiro símbolo (`PODER|OBRIGATORIO|DISCIPLINA`), que separa a pergunta
sobre a **norma** da pergunta sobre o **aluno**. A formulação genérica que perde cobertura com
isso ("qual o limite de faltas?") cai no plano B, que a responde.

## 7. Consulta canônica: a frase do aluno não chega à busca

Cada intenção tem uma consulta fixa, escrita à mão **no vocabulário do Manual**. É o passo de
*lowering* de um compilador: a forma de superfície, cheia de variação, vira uma representação
interna única.

Duas consequências:

- **O núcleo responde sem IA**, de forma determinística: mesma pergunta, mesma consulta, mesmo
  trecho.
- **Fecha o buraco léxico medido no Marco 3**, onde a busca por palavra-chave desabava em
  pergunta de leigo (recall@5 0.17 contra 0.83 na técnica) porque a palavra do aluno não é a
  palavra do documento. A tradução acontece antes da busca, no léxico e nesta tabela, em vez de
  ser deixada para o recuperador adivinhar.

Os **campos** (nome de disciplina, número de dias) saem do que a regra não consumiu e **não
entram na consulta**: a regra de frequência do Manual não menciona "cálculo", e incluir isso só
atrapalharia o casamento.

Consulta canônica escrita com palavra que não é do documento erra o alvo. Três casos corrigidos
por esse princípio: "nota necessária no exame" virou "média final MF igual ou maior que 5,0";
"ausência na avaliação" virou "não compareça no dia e horário agendado"; "prazo de concessão"
virou "será concedido pelo prazo", porque o Manual escreve "concedido", não "concessão".

## 8. As regras vieram do Manual, não das perguntas

As 77 regras derivam dos **títulos de seção do documento**, extraídos do PDF pelos atributos de
fonte (o arquivo não tem sumário eletrônico, e regex de Title Case só devolvia a lista de
dirigentes do prefácio).

Isso é o que torna a medição defensável: escrever regra olhando as mesmas perguntas que depois
medem a cobertura daria um número in-sample, que nada diz sobre generalização.

## 9. O destaque: alternativas medidas e rejeitadas

Um trecho tem 180 palavras e quase sempre começa no meio do assunto anterior, então mostrá-lo
inteiro parece resposta errada. O destaque escolhe a frase com maior sobreposição de termos com
a consulta, usando o tokenizador do BM25 — assim destacar não pode discordar de recuperar.

Acerto = trecho-fonte do gold-set dentro da frase destacada, nas 44 que a gramática reconhece.
Os quatro critérios foram medidos **só com BM25**, para que a comparação entre eles corra em
condição idêntica. No caminho do produto, com o reranker, o critério em uso chega a 30/44 (§17).

| Critério | Só o 1º trecho | Varrendo os 3 |
|---|---|---|
| **sobreposição bruta (em uso)** | **26/44** | 24/44 |
| dividido pela raiz do tamanho | 25/44 | 20/44 |
| dividido pelo tamanho (precisão) | 19/44 | — |
| média harmônica tipo F1 | 20/44 | 16/44 |

Duas lições. Ampliar o espaço de busca sem melhorar a pontuação deixa frase longa do trecho
errado vencer por volume de termos. E normalizar por tamanho favorece fragmento curto, sendo que
o Manual é cheio de "Art. 5º -".

O caminho que sobra não é a fórmula, é a **evidência**: ponderar cada termo pelo IDF do índice,
o que exigiria dar à função acesso às estatísticas do corpus.

Diagnóstico das 18 falhas medidas nessa condição: em 12 a frase certa estava no 2º ou 3º trecho; em 6 o trecho do topo
estava certo e a frase escolhida não; em 0 a métrica foi injusta.

## 10. Recuperação do produto: BM25 + reranker

Difere da configuração vencedora do estudo comparativo (híbrida + reranker) por uma razão
medida: quem consulta o Manual passou a ser a consulta canônica, escrita nas palavras do próprio
documento, e nesse caminho BM25 puro e híbrida+reranker deram resultado **idêntico**. A
recuperação densa compensava a redação crua do aluno, que não chega mais até a busca.

O cross-encoder permanece porque o **piso de score** depende do escore dele, e o piso é o
guardrail do plano B — esse sim ainda recebe a pergunta como o aluno escreveu. Trocar a base do
piso de híbrida para BM25 não mexeu no guardrail: 31/31 nas adversariais, 0/50 de recusa
indevida, mesma folga de 0,28 até o piso de −3,2.

Densa, híbrida e união seguem no pacote, reproduzíveis: são a evidência que justificou a
escolha.

## 11. Por que a base de conhecimento não tem piso de score

O `ChatbotRAG` precisa de piso porque aceita pergunta livre. Na base de conhecimento o portão é
**a gramática**: só chega consulta de intenção reconhecida, e a consulta canônica dessa intenção
foi escrita apontando para um assunto que conferimos existir no Manual. Fora de escopo não
chega até lá — não casa regra nenhuma e o controlador manda para o plano B.

## 12. Limitações conhecidas do léxico

- **Uma palavra por vez.** Termos compostos não são casados como unidade: "aluno-atleta" vira
  `ALUNO ATLETA` (funciona, a gramática compõe), mas "prova on-line" vira `PROVA` mais duas
  palavras soltas. É o primeiro caso a pedir *maximal munch* sobre a sequência de palavras.
- **Sem tabela de entidades.** Nome de disciplina cai em `DESCONHECIDO`, de propósito: vira
  matéria-prima de campo. Quando a gramática precisar deles por tipo, entra um
  `TipoToken.ENTIDADE` com tabela própria.
- **Ordinais** ("1º") não são reconhecidos como número; a normalização os deixa como "1o".
- **Pontuação descartada**; a interrogação é inferida do símbolo interrogativo.

## 13. Robustez a paráfrase, medida

Cobertura no gold-set superestima robustez: o gold-set foi escrito num registro razoavelmente
canônico. Numa sonda de 5 assuntos × 5 formas de perguntar cada um, escritas sem olhar as
regras:

| | |
|---|---|
| antes dos consertos | 13/25 |
| depois | **23/25** |

Os consertos foram: operador de ordem livre (`&`), sinônimos que faltavam ("obrigado", "devolvi",
"suspensão") e uma regra específica demais na biblioteca, que exigia três símbolos enquanto a
genérica de punições capturava o resto **e respondia errado**.

As duas que ainda falham são conscientes: "qual o limite de ausências?" cai no plano B pelo
terceiro símbolo da seção 6, e "tenho que ir na formatura?" exigiria aceitar `QUE` como marcador
modal, o que deixaria a gramática frouxa.

## 14. O teste adversarial tem de passar pelo caminho do produto

`scripts/produto/institucional_guardrail.py` instanciava o `ChatbotRAG` diretamente. Com o núcleo
respondendo antes do modelo, o teste ficou cego: qualquer regra genérica demais passava sem ser
notada.

Corrigido para rodar pelo `Dialogo`. Uma resposta de origem `NUCLEO` numa pergunta adversarial é
contada como vazamento por definição, independente do que o texto diga. A correção encontrou
imediatamente o vazamento descrito na seção 6.

## 15. Erro que reaparece nos dois caminhos

*"De quem é a responsabilidade de controlar as faltas?"* O Manual tem duas frases vizinhas: o
professor lança a frequência, o aluno controla as próprias faltas. O modelo de linguagem
sintetizava do trecho errado e respondia "professor"; o núcleo destaca do trecho errado e
responde a mesma coisa.

Mecanismos diferentes, mesma armadilha: é **granularidade do documento**, não defeito da técnica
de geração.

## 16. O plano B não é reprodutível na prática

A mesma pergunta sobre serviço militar produziu **três redações diferentes em três execuções**,
com temperatura zero — duas corretas e uma começando por "Sim" onde a resposta é "não". O núcleo
é reprodutível por construção.

Nas 6 perguntas que a gramática não cobre, o plano B recupera o trecho certo em 6/6 e acerta o
conteúdo em 5/6, com 0 recusas indevidas.

Um defeito observado ao vivo: em resposta longa e em lista, o modelo citou na numeração do
próprio Manual ("Art. 13") em vez do formato `[n]`, e o painel de fontes ficou sem nenhuma marca.
O experimento anterior concluiu que o baseline citava `[n]` em ~100% dos casos, mas mediu apenas
respostas curtas do gold-set: a conclusão não estava errada, estava incompleta.

## 17. Estado atual

| Medida | Valor |
|---|---|
| Reconhecidas pelo núcleo | 44/50 |
| Trecho certo recuperado | 43/44 |
| Intenção errada | 0 |
| Frase destacada exata | 30/44 |
| Empates na gramática | 0/50 |
| Recusa fora de escopo | 31/31 |
| Robustez a paráfrase | 23/25 |
| Tempo de resposta | ~1,2 s (núcleo) · ~19 s (plano B) |
| Testes | 98 |

Medido pelo **caminho do produto** (BM25 mais reranker), como manda o §14. Com
`COBERTURA_RAPIDA=1`, que usa só BM25, sai 44/44 de recuperação e 26/44 de destaque: o
reranker troca um acerto de recuperação (a pergunta `n20`) por quatro de destaque.

---

## 18. O que saiu do código na limpeza de 28/08/2026

A limpeza cortou 5 subpacotes para 1 e 30% de prosa para 21%. O que era **justificativa** saiu
do código e ficou aqui; o que era **código sem consumidor** foi removido. Registro do que sumiu,
para não se tentar de novo:

- **Perfil de guardrail "estrito".** Havia dois *system prompts*, um estrito (herdado do corpus
  de saúde) e um institucional. O produto sempre usou o institucional; o estrito não tinha
  chamador. Ficou um prompt só, em ``rag.ia._SISTEMA``.
- **`modelo_fallback` / `usar_fallback`.** Um segundo modelo (3B) previsto para o caso de a
  latência do 8B atrapalhar a demonstração. Nunca foi acionado em lugar nenhum do código.
- **`construir_relevancia_por_documento`.** Relevância em nível de documento, exigida pelo
  benchmark Pirá. O Pirá saiu do projeto no pivô; a função só era usada pelo próprio teste.
- **`rag.ia.fabrica`.** Uma função de repasse para desacoplar do backend concreto. Com um único
  backend, dois dos quatro chamadores já a ignoravam e chamavam ``GeradorOllama.de_config``
  direto. Agora todos chamam.
- **Reescrita "ancorada" da consulta multi-turn.** Uma variante do prompt de reescrita, com
  âncora de atribuição para corrigir o erro n14, foi implementada e medida: **não corrigiu o
  n14 e piorou o over-refusal** (recusas de 1 para 5, nas 50 perguntas). Rejeitada. O prompt em
  uso é o simples, em ``rag.ia._SISTEMA_REESCRITA``.
- **Três normalizadores de acento** (no léxico, no BM25 e no detector de saudação) viraram um,
  ``rag.corpus.sem_acentos``. Eram idênticos e podiam divergir sem ninguém perceber.

O campo ``ItemGold.tipo`` foi **mantido** mesmo sem uso: é ``None`` nos 68 itens dos dois
gold-sets, mas a chave existe no JSON, e tirá-la obrigaria a reescrever o instrumento de
medição para economizar uma linha.

`Campo` e `Consulta.campos`, na fase semântica, também foram **mantidos** sem consumidor no
produto: são o atributo sintetizado da tradução dirigida por sintaxe, e é o que separa a fase
semântica de uma tabela de consulta.

---

## 19. Segunda passada de simplificação (29/08/2026)

Três redundâncias que a passada anterior não tinha atacado:

- **O `config.yaml` foi embora.** Eram 106 linhas (76 de `config.py` mais 30 de YAML), seis
  dataclasses e a dependência `pyyaml`, para carregar doze valores. Uma varredura dos acessos
  a `cfg.*` mostrou que `seed` e `recuperacao.top_k` **não eram lidos por ninguém**, e que os
  seis chamadores de `carregar_config()` nunca passaram caminho customizado. Hoje é uma
  dataclass congelada de campos planos, em `rag.config`. O argumento de reprodutibilidade não
  se perde: a estrutura continua sendo o único lugar onde os parâmetros vivem, e agora o
  interpretador confere nome e tipo de cada um.
- **`RespostaChatbot` foi removida.** Era embalagem pura: o controlador desembrulhava
  `resposta.resposta.texto` e `resposta.contextos` na linha seguinte. `RespostaGerada` passou a
  carregar os trechos, e as respostas do sistema caíram de quatro tipos para três
  (`RespostaGerada`, `RespostaNucleo`, `RespostaDialogo`), cada uma de uma camada distinta.
- **`pipeline.montar_assistente`.** A montagem estava copiada em três pontos de entrada, e o
  caminho do PDF em seis. Agora `montar_assistente(cfg, com_plano_b=..., saudar=...)` monta o
  produto inteiro, e as medições usam os degraus (`indexar_manual`, `montar_esparsa`,
  `montar_plano_b`) quando precisam de uma variação.

A frase de recusa estava escrita em três lugares (a constante, o *system prompt* e o
reconhecedor da tela). Agora é uma constante só, em `rag.apresentacao.RECUSA`, que o prompt
interpola. O reconhecimento continua casando só o começo da frase, porque o modelo às vezes
acrescenta ao final, e o prefixo tem nome próprio (`_INICIO_RECUSA`) ao lado dela.

Verificado depois da mudança: 75 testes passando, cobertura do núcleo em **44/50** com 26/44 de
destaque pelo caminho rápido (os mesmos números do §17), e o caminho do produto respondendo em
**1,4 s** com e sem acento.

---

## 20. Comportamentos levantados em 29/08/2026, medidos e ainda não decididos

Nada aqui foi alterado no código. São **três comportamentos do sistema que ninguém tinha
medido**, levantados numa conversa de orientação. Ficam registrados para virarem decisão, num
sentido ou no outro, depois de discutidos.

### 20.1 Duas perguntas num único input: responde uma, descarta a outra em silêncio

`AnalisadorSintatico.analisar` devolve **um** `Reconhecimento`, nunca uma lista. Quando a
entrada contém mais de uma pergunta, várias regras casam e vence a de mais símbolos
obrigatórios; as demais são descartadas **sem qualquer sinal para o aluno**.

Medido:

```
"Quantas faltas posso ter e como faço o trancamento da matrícula?"
   símbolos : QUANTIDADE FALTA PODER COMO TRANCAR MATRICULA
   venceu   : limite_faltas (3 obrigatórios)
   perderam : como_trancar (2), prazo_trancamento (2), matricula_ingressante (2)
   consulta : "frequência obrigatória em cada disciplina, aulas dadas"
```

Três propriedades observadas:

- **A ordem não importa.** Inverter as duas perguntas dá o mesmo vencedor, porque o desempate
  é por peso da regra, não por posição na frase.
- **A pontuação não separa.** Em "o que é jubilamento? e o trote é permitido?" o `?` é
  descartado como separador no analisador léxico, e as duas perguntas viram um fluxo único de
  símbolos. Ambas as regras têm um símbolo obrigatório, então vence **a primeira declarada** em
  `REGRAS`, e a outra some.
- A regra vencedora pode não ser a primeira pergunta da frase, o que torna o comportamento
  difícil de prever para quem usa.

O caminho mais barato para tratar isso seria **segmentar a entrada antes da fase 2** e rodar o
analisador por segmento, sem tocar no reconhecedor. Não foi feito: muda a arquitetura e
invalida a medição de cobertura de 44/50, que é sobre uma pergunta por vez.

### 20.2 O plano B recebe a frase crua: o front-end é descartado

Quando a gramática não reconhece, o controlador entrega ao plano B **exatamente o que o aluno
digitou**:

```python
# compilador/dialogo.py
return self._recorrer_ao_plano_b(pergunta, historico)   # a frase crua
# ia.py
consulta = pergunta                                      # busca com a frase crua
```

Tokens, símbolos canônicos e normalização de escrita **não chegam ao plano B**. A normalização
existe só do lado do compilador.

É o que explica o A/B do acento: sem acento o núcleo responde igual, e a mesma pergunta pelo
plano B é recusada pelo piso de score. **A assimetria é o resultado, não um defeito** — mas é
consequência de uma decisão que nunca foi escrita como tal.

Duas leituras possíveis, ambas defensáveis, e é isso que precisa ser decidido:

- **manter**: as duas vias ficam independentes, e é isso que permite medir uma contra a outra
  sem contaminação;
- **enriquecer**: usar os símbolos reconhecidos para melhorar a consulta do plano B, o que
  provavelmente subiria a recuperação nas seis perguntas que hoje escapam do núcleo, ao custo
  de as duas vias deixarem de ser comparáveis.

### 20.3 O que a LLM recebe

Ela **nunca vê o PDF**. Cada chamada leva:

| | |
|---|---|
| system prompt | 632 caracteres, fixo |
| contexto | 5 trechos (`top_k_contexto`), de 180 tokens cada |
| total | ~900 palavras, de um corpus de 173 trechos |

Algo em torno de **3% do Manual por pergunta**, escolhido pelo BM25 com o cross-encoder por
cima. O restante do documento não existe para o modelo.

### 20.4 Os campos da fase semântica seguem sem consumidor

Já registrado no §18, e volta aqui porque foi apontado de fora: `Campo` e `Consulta.campos`
colhem o dado solto da pergunta (`{"disciplina": "Cálculo"}`) e **nada no produto lê esse
valor**. São ~20 linhas que sustentam chamar a fase de tradução dirigida por sintaxe em vez de
tabela de consulta.

A escolha é binária: **usar** o campo (exibindo ao aluno, ou filtrando o trecho) ou **cortar** e
assumir que a fase é um mapeamento intenção → consulta. Manter inerte é o que faz a fase
parecer mais complexa do que é.

---

## 21. Desempate por maximal munch (29/08/2026)

### O bug que estava em produção

`como_trancar` **nunca respondia**. Aparecia na lista de "nunca disparam" da medição de
cobertura, e o motivo não era falta de vocabulário:

```
"como faço o trancamento da matrícula?"
   símbolos : COMO TRANCAR MATRICULA
   casaram  : matricula_ingressante (peso 2)  |  como_trancar (peso 2)
   venceu   : matricula_ingressante   -- declarada na posição 13
   perdeu   : como_trancar            -- declarada na posição 15

   resposta dada    : "aluno ingressante matriculado automaticamente no regime de
                       progressão tutelada"
   resposta correta : "como solicitar o trancamento de matrícula"
```

O aluno perguntava como trancar e recebia a regra de matrícula automática de ingressantes.
Resposta errada, entregue com confiança e marcada "sem IA".

**Causa.** `como_trancar := COMO TRANCAR MATRICULA?` tem o terceiro símbolo **opcional**, então
conta dois obrigatórios, exatamente como `matricula_ingressante := COMO MATRICULA`. Empate. E o
desempate usava `>` e não `>=`, ficando a primeira declarada.

**Por que a medição não pegou.** O gold-set tem três perguntas sobre trancamento (`m03` "o que
é", `m04` "por quanto tempo", `m18` "consequência de não trancar") e **nenhuma "como trancar"**.
O buraco estava fora do conjunto medido. Os 44/50 e os zero falsos positivos continuavam
corretos.

**Como apareceu.** Não foi por inspeção: surgiu ao prototipar o reconhecimento múltiplo (§20.1).
O algoritmo de consumo iterado só funcionava com desempate por consumo, e ao trocar o critério o
caso de pergunta única passou a acertar. O trabalho sobre multi-pergunta encontrou um bug de
pergunta única.

### A correção

O desempate passa a ser **maximal munch**: vence a regra que consome mais símbolos da pergunta;
só no empate entra o número de obrigatórios; persistindo, a primeira declarada. É a regra
clássica do analisador léxico ("pegue o casamento mais longo"), aplicada no nível da regra.

```python
chave = (len(indices), regra.obrigatorios)     # antes: regra.obrigatorios
if melhor is None or chave > melhor[0]:
```

Junto veio uma segunda correção, sem a qual a primeira não mede o que promete: `_casar` passa a
reportar **todas** as posições consumidas por um elemento, e não só a primeira. Com os
operadores `&` e `+` um elemento cobre mais de uma posição, e o contador de consumo precisa
saber disso. O filtro por `conjuntos` evita levar junto uma palavra-chave que caia no meio do
intervalo sem pertencer ao elemento. Efeito colateral bem-vindo: `casados` e `sobra` passam a
ser uma partição de fato, o que antes não eram.

### O que foi verificado

| | antes | depois |
|---|---|---|
| testes | 75 | 75 |
| regras que perdem para outra na própria entrada canônica | 1/77 | **0/77** |
| cobertura, modo rápido | 44/50 · 44/44 · 26/44 · 0 FP | idêntico |
| cobertura, caminho do produto | 44/50 · 43/44 · 30/44 | idêntico |
| perguntas do gold-set que mudaram de intenção | — | **0 de 50** |
| adversariais reconhecidas pelo núcleo | 0/31 | 0/31 |

O **0 de 50** é o que sustenta os números publicados: nenhuma pergunta medida trocou de
intenção, então a cobertura continua valendo pela mesma causa, e não por compensação entre
acertos e erros. E como nenhuma das 31 adversariais é reconhecida pelo núcleo em nenhum dos dois
critérios, todas seguem para o plano B e o 31/31 depende só do piso de score, que não foi
tocado.

### O que isto não resolve

O reconhecimento continua devolvendo **uma** intenção. O comportamento de multi-pergunta do
§20.1 permanece: duas perguntas num input, uma resposta, sem aviso. O munch é pré-requisito da
mudança `pergunta := regra+`, não a mudança em si.

---

## 22. `pergunta := regra+` — reconhecimento múltiplo (29/08/2026)

Fecha o comportamento levantado no §20.1: duas perguntas num input, uma resposta, sem aviso.

### A mudança de gramática

O símbolo inicial deixa de ser uma regra e passa a ser uma sequência delas. `analisar_todas`
casa a regra que melhor cobre a pergunta, retira da frase os símbolos que ela usou e repete no
que sobrou, até nada mais casar ou até o teto (`Config.max_intencoes`, 3 por padrão). É o que um
compilador faz com uma sequência de comandos, e não exige heurística de segmentação nem tabela
nova: reaproveita o casamento de ilha como está.

`analisar` continua existindo e devolve a intenção principal, com semântica idêntica à anterior.
Foi verificado nas 50 perguntas do gold-set que ele coincide sempre com `analisar_todas[0]`.

O controlador consulta cada intenção no Manual e compõe a resposta **na ordem em que o aluno
perguntou**, não na ordem de reconhecimento. Basta uma intenção encontrar trecho para o núcleo
responder; só cai no plano B quando nenhuma encontra.

### Dois problemas que só apareceram na execução

**1. Símbolo repetido virava pergunta nova.** Em `n30`, "Para colar grau preciso estar regular
no ENADE", tanto "colar" quanto "grau" produzem `COLACAO`. A primeira regra consumia um, o outro
sobrava e alimentava `colacao_obrigatoria`, uma segunda intenção que ninguém perguntou.

Consumir um símbolo passou a **levar junto as outras ocorrências dele**. Aqui um símbolo nomeia
um assunto, não uma posição: "colar grau" é uma menção dita duas vezes.

**2. Símbolos de perguntas diferentes se costuravam.** Com três perguntas num input, o `QUE` de
"o que é jubilamento" casou com o `TRANCAR` de "como trancar a matrícula", produzindo
`definicao_trancamento` em vez de `como_trancar`. Regra nenhuma foi violada: o casamento de ilha
pula o que está no meio, e "no meio" passou a incluir outra pergunta.

### O desempate final, e por que é esse

Quatro combinações foram medidas antes de escolher:

| critério | espúrios em 50 | intenção principal | 3 perguntas |
|---|---|---|---|
| posições consumidas | 0 | 0 mudou | errado |
| posições + dispersão | 0 | **1 mudou** | certo |
| símbolos distintos | 0 | 0 mudou | errado |
| **distintos + dispersão** | **0** | **0 mudou** | **certo** |

Só a combinação passa em tudo, e cada metade resolve uma coisa:

- **símbolos distintos**, e não posições, remove a inflação do `COLACAO` duplicado — sem isso,
  quem alcança as duas ocorrências parece cobrir mais da pergunta do que cobre;
- **menor dispersão** entre a primeira e a última posição usada desempata a favor do casamento
  mais compacto, que é o que impede uma regra de costurar perguntas diferentes.

Sozinha, a dispersão trocava a intenção do `n30` para a errada. É a razão de as duas entrarem
juntas. A ordem completa do desempate está em `AnalisadorSintatico._melhor_regra`: distintos,
dispersão, obrigatórios, e persistindo o empate a primeira declarada.

### O que foi verificado

| | |
|---|---|
| testes | **81** (75 + 6 novos) |
| perguntas simples que produzem 2+ intenções | **0 de 50** |
| `analisar` vs `analisar_todas[0]` | **0 divergências em 50** |
| adversariais reconhecidas pelo núcleo | 0/31 |
| 77 regras contra a própria entrada canônica | 0 perdem |
| cobertura, caminho do produto | **44/50 · 43/44 · 30/44**, idêntico |

Ponta a ponta:

```
"como faço o trancamento da matrícula e quantas faltas posso ter?"
   origem=NUCLEO  intencoes=['como_trancar', 'limite_faltas']
   trechos=6  fontes=[57, 92]
```

### O que mudou fora do núcleo

`RespostaDialogo.intencao` virou `intencoes: tuple[str, ...]`, e acompanharam o JSON do
`servidor.py`, a tela (junta com " + "), o relatório do guardrail e os testes. `Config` ganhou
`max_intencoes`. O `janela` da apresentação passou a centrar no destaque certo quando a resposta
reúne mais de um.

### Cada resposta é rotulada pela intenção que a produziu

Com mais de uma intenção, o controlador prefixa cada resposta com `[intencao]`. Duas respostas
seguidas não dizem sozinhas qual delas responde o quê, e o rótulo tem o efeito colateral de
mostrar, na tela, qual regra disparou.

Com **uma** intenção o texto sai limpo, exatamente como sempre saiu: nada muda para a pergunta
simples, que é o caso das cinquenta do gold-set. Quem exibe tira o rótulo antes de procurar o
destaque dentro do trecho (`apresentacao._SEM_ROTULO`), senão a janela da fonte deixaria de
centrar na frase que respondeu.

### Limitação que fica

**1. A costura entre perguntas foi reduzida, não eliminada.** Uma frase longa o bastante, com
símbolos compatíveis espalhados, ainda pode produzir uma intenção que ninguém pediu. A saída
definitiva seria segmentar a entrada antes da fase 2, o que foi deliberadamente evitado: exige
heurística de separação (conjunção, pontuação) que erra em "faltas em Cálculo **e** Física".

**2. Quando só uma das perguntas é reconhecida, o núcleo responde essa e não avisa do resto.**

```
"quantas faltas posso ter e qual o tratamento para asma?"
   reconhecidas: ['limite_faltas']     sobrou: ['QUAL']
```

E **não há sinal confiável para detectar isso**. O candidato óbvio seria "sobrou símbolo sem
consumir", mas a medição desqualifica o critério: **39 das 50 perguntas do gold-set deixam
símbolo sem consumir**, e todas são perguntas simples respondidas corretamente.

```
m01  "Qual o percentual mínimo de frequência..."   sobrou: QUAL, DISCIPLINA
m04  "Por quanto tempo o trancamento..."           sobrou: PODER
m13  "Qual a penalidade por atraso na devolução..." sobrou: QUAL, BIBLIOTECA
```

A sobra de `['QUAL']` na pergunta com asma é indistinguível da sobra de `m01`. Pior: em
"quantas faltas e me conta uma piada" **não sobra nada**, porque "piada" e "conta" não estão no
léxico e nem chegam a virar símbolo.

Fica registrado como limitação conhecida: **o núcleo responde o que reconhece e não tem como
saber que metade da pergunta ficou sem resposta.** Encaminhar o resíduo ao plano B foi
descartado justamente por falta desse sinal — dispararia em 39 das 50 perguntas simples.

**3. O gold-set continua sendo de perguntas simples.** Medir a capacidade nova exige itens
multi-pergunta e uma métrica própria, ao lado da cobertura atual e não no lugar dela.

---

## 23. A decodificação restrita: o que foi, e por que está registrada aqui

**Não está em uso.** O código foi removido em `ed509a1` (28/08/2026), na redução do projeto ao
produto. Esta seção guarda a explicação, para o capítulo de projeto não depender de arqueologia
no histórico do Git.

### O que era

A intervenção do trabalho **até o pivô de 13/08/2026**: gramática e autômato aplicados à
**saída** do modelo, e não à entrada do aluno. Hoje vale como resultado preliminar.

A diferença com o que roda hoje é de garantia. O gerador atual **pede** a citação no prompt
("cite a fonte entre colchetes, por exemplo [1]"), e o modelo obedece na maioria das vezes. Na
decodificação restrita, a cada token gerado um autômato dizia quais tokens mantinham a saída
dentro da linguagem, e os demais tinham o logit posto em `-inf`. Citar fora do formato não era
improvável: era **impossível**, porque o caminho não existia no autômato.

Ela implementava o mesmo contrato `Gerador` do backend Ollama, então plugava no `ChatbotRAG`
sem tocar em nada da recuperação.

### Como funcionava, na cadeia clássica gramática → autômato → tradução

Da docstring de `gramatica_citacao.py`, preservada literalmente:

- **Gramática (regular).** A resposta é texto livre no qual toda ocorrência de `[` abre uma
  citação bem-formada `[n]`, com `n` inteiro em `1..K` (`K` = nº de trechos no contexto), e a
  geração só pode terminar depois de ao menos uma citação válida.
- **Autômato (AFD).** Reconhece essa linguagem com um autômato finito determinístico. O número
  é casado por um *autômato de prefixos* sobre o conjunto finito `{"1", ..., "K"}`, o que
  elimina becos sem saída por construção: todo prefixo válido alcança um número válido.
- **Tradução (máscara).** Na decodificação, o AFD diz, a cada passo, quais caracteres — logo,
  quais *tokens* — mantêm a saída dentro da linguagem; os demais têm o logit posto em `-inf`.

O autômato era **puro Python**, independente da LLM e da `llama_cpp`, e por isso testável
isoladamente (99 linhas de teste em `tests/test_gramatica_citacao.py`).

### O degrau seguinte, também implementado: subir de classe na hierarquia

`json_estruturado.py` trocava a gramática **regular** por uma **livre de contexto**:

> Enquanto a citação `[n]` é uma linguagem regular reconhecida por um AFD feito à mão, um objeto
> JSON é livre de contexto: o aninhamento de `{}`/`[]` exige uma **pilha** — um autômato de
> pilha — para casar aberturas e fechamentos.

O formato forçado era `{"resposta": "<texto>", "fontes": [<n>, ...]}`, com ao menos um `n`. Aqui
o autômato de pilha não era escrito à mão: autorava-se o **esquema**, e o motor de gramática da
`llama.cpp` o realizava.

Isso dá ao trabalho um exemplo próprio de **dois níveis distintos da hierarquia de Chomsky
aplicados ao mesmo problema**, com a razão da diferença explícita: o que exige memória de pilha
e o que não exige.

### O benefício

A limitação que o produto tem hoje, e que está registrada no README:

> o plano B às vezes cita um índice diferente do da fonte real, e a tela reporta isso fielmente

É exatamente a classe de falha que a decodificação restrita eliminava **por construção**.
Garantia de formato, não probabilidade de formato.

E o enquadramento vale para o capítulo: **gramática e autômato foram aplicados aos dois lados do
modelo** — hoje sobre a entrada do aluno (`rag.compilador`), antes sobre a saída do gerador. O
modelo de linguagem não é uma peça acoplada ao fim de um sistema; ele foi cercado dos dois
lados por técnica de compilador, e o trabalho escolheu um dos lados como núcleo.

### O que NÃO se preservou, e é preciso saber

O `LINHA-DO-TEMPO.md` do TCC registra a técnica como "implementada, **medida** e integrada". O
experimento existia (`scripts/estudo/exp_gramatica.py`) e media as coisas certas:

- taxa de **citação bem-formada** com e sem restrição, sobre as mesmas 50 perguntas e os mesmos
  contextos recuperados;
- **quantas vezes a máscara bloqueou o token de maior logit do modelo** — a prova de que o
  autômato de fato interveio na decodificação, e não apenas acompanhou.

Mas o script **só imprimia na tela; nunca gravou arquivo**. Não há saída dele em `outputs/`, e
os números não estão em nenhum relatório. **Para citar resultado numérico da decodificação
restrita no TCC, será preciso reexecutar**, o que exige `llama-cpp-python` e o GGUF do modelo.

Sem isso, o que se pode afirmar com honestidade é a técnica, o desenho do experimento e o que
ele media — não a magnitude do ganho.

### Onde está o código

No histórico, em `ed509a1^`:

```
git show ed509a1^:src/rag/ia/gramatica_citacao.py    # 227 linhas, o autômato
git show ed509a1^:src/rag/ia/llamacpp.py             # 229 linhas, o gerador
git show ed509a1^:src/rag/ia/json_estruturado.py     #  77 linhas, o nível livre de contexto
git show ed509a1^:scripts/estudo/exp_gramatica.py    # 106 linhas, o experimento
git show ed509a1^:tests/test_gramatica_citacao.py    #  99 linhas
```

---

## 24. BM25 e reordenador: o que cada um paga (01/09/2026)

A pergunta que motivou estas medições: o cross-encoder é componente pronto de 117,6 milhões
de parâmetros, e num TCC cuja contribuição é o front-end de compilador ele precisa justificar
a própria presença. Mediu-se, então, **onde cada camada de recuperação paga o próprio custo**,
em vez de decidir por preferência.

Scripts em `scripts/estudo/`; as saídas vão para `outputs/`, que não é versionado, e por isso
os números ficam registrados aqui.

### 24.1 As três medições

**Núcleo** (sobre as 44 perguntas que a gramática reconhece, `cobertura_nucleo.py`):

| | só BM25 | BM25 + reordenador |
|---|---|---|
| chunk-gold entre os 3 trechos | **44/44** | 43/44 |
| falso positivo (trecho errado) | **0** | 1 |
| trecho-fonte no destaque | 26/44 | **30/44** |

**Caminho auxiliar** (recuperação top-5 sobre as 50 perguntas, `quanto_o_reordenador_faz.py`):

| | acerto |
|---|---|
| só BM25 | 45/50 |
| BM25 + reordenador | **49/50** |

**Guardrail** (31 adversariais, `piso_sem_reordenador.py`):

| | recusadas |
|---|---|
| piso sobre a medida do reordenador (−3,2) | **31/31** |
| piso sobre a pontuação do BM25 | **2/31** |

As duas populações de pontuação do BM25 **se sobrepõem por inteiro**: a legítima mais fraca
vale 4,45 e a adversarial mais forte vale 12,69. Não existe corte. O melhor compromisso
possível (7,88) ainda perde 7 legítimas e deixa vazar 10 adversariais.

### 24.2 A leitura

O reordenador **não paga o próprio custo no núcleo**: piora a recuperação em uma pergunta,
introduz o falso positivo que é o modo de falha perigoso, e ganha 4 no destaque. A razão é
que o núcleo lhe entrega uma consulta canônica já escrita no vocabulário do documento, e
casamento de palavra-chave basta para isso.

Ele **paga com folga nas outras duas**: leva a recuperação do caminho auxiliar de 45 para 49,
e é a única fonte da medida que o guardrail consome. O caminho auxiliar recebe a pergunta
crua do aluno, que é o caso difícil.

**Decisão: manter.** A arquitetura que as medições recomendam é tirá-lo do percurso do núcleo
e mantê-lo no caminho auxiliar, o que são duas linhas em `pipeline.py`. Não foi feito porque
implicaria refazer os números já escritos no Capítulo 3, e o ganho líquido é pequeno.

### 24.3 O compilador como primeiro estágio do guardrail

Testou-se se o próprio front-end serve de detector de escopo, pelo critério mais simples:
**a pergunta dispara algum símbolo de ASSUNTO do Manual?**

| categoria adversarial | n | pega |
|---|---|---|
| outro domínio, saúde | 4 | 4 |
| outro domínio, geral | 5 | 5 |
| brincadeiras/casual | 5 | 5 |
| injeção / subversão | 5 | 4 |
| dados pessoais | 4 | 1 |
| **ambíguas** | 8 | **1** |
| | 31 | **20** |

Custo nas legítimas: **zero**. As 6 perguntas do gold-set que a gramática não reconhece
disparam todas ao menos um assunto (ressalva: n=6, base pequena).

Isso desenha um guardrail de dois estágios, com o primeiro sendo componente próprio:

1. **compilador**: sem assunto do Manual, recusa. 20/31.
2. **cross-encoder**: o resíduo, 11 casos, dos quais 8 são a categoria ambígua.

**Não implementado ainda.** É barato e reduz o papel do componente pronto, que é a posição
mais defensável dele.

### 24.4 Critério léxico para a categoria ambígua: medido e rejeitado

Hipótese: barrar a pergunta que contenha palavra ausente de todo o Manual. "Cantina",
"wi-fi" e "estacionamento" não ocorrem no documento.

Do lado adversarial funciona: **26/31 barradas**, incluindo 6 das 8 ambíguas.

Do lado legítimo destrói: **35 das 50 perguntas do gold-set seriam recusadas por engano**.
O aluno escreve "percentual", "solicita", "peço", "acontece", "posso", e o Manual escreve
de outro modo. Sem lematização, cada variação morfológica vira palavra estrangeira.

O critério falha pela mesma razão que motiva o trabalho inteiro: a distância entre a língua
do aluno e a do documento. O compilador resolve isso para os 89 símbolos mapeados, por 268
grafias; para vocabulário arbitrário não há mapeamento.

### 24.5 O que isso dá ao texto

A Seção 3.4 do Capítulo 3 afirma que o reordenador permanece porque o guardrail consome a
medida dele. Falta o número. Uma frase converte a afirmação em medição:

> Retirá-lo levaria a recuperação do caminho auxiliar de 49/50 para 45/50 e a recusa de
> perguntas fora de escopo de 31/31 para 2/31, porque a pontuação do BM25 não separa
> pergunta legítima de adversarial.

---

## 25. O reordenador sai do núcleo (01/09/2026)

Aplicada a separação que a §24 recomendava. `montar_assistente` passa a montar o BM25 uma vez,
entregá-lo à `BaseConhecimento`, e a envolvê-lo no cross-encoder **só** para o plano B.

```python
esparsa = montar_esparsa(indice, cfg)
base = BaseConhecimento(esparsa, indice.chunks, cfg.top_k_nucleo)
plano_b = montar_plano_b(montar_reordenado(indice, cfg, base=esparsa), ...)
```

`montar_recuperador_produto` virou apelido de `montar_reordenado`, que aceita a base pronta e
não reindexa. Em `cobertura_nucleo.py`, a variável de ambiente trocou de sentido: o padrão
agora **é** o produto, e `COBERTURA_REORDENADOR=1` monta a variante para comparação.

### O que mudou no núcleo

| | antes | depois |
|---|---|---|
| reconhecidas | 44/50 | 44/50 |
| chunk-gold entre os três | 43/44 | **44/44** |
| falso positivo | 1 | **0** |
| trecho-fonte no destaque | 30/44 | 26/44 |

A troca é deliberada: elimina uma falha de **correção**, aquela em que o sistema reconhece a
intenção e responde com confiança a partir do trecho errado, ao custo de quatro falhas de
**apresentação**, em que o trecho certo é exibido com a frase errada em destaque. Num trabalho
cuja tese é que a resposta é o texto do documento, verificável pelo aluno, a direção certa é
essa.

### Duas tentativas de recuperar o destaque, ambas falhas

**Ponderar os termos por IDF.** Era ideia pendente desde a §9: o critério em uso conta
sobreposição bruta, então "de" e "em" pesam o mesmo que "frequência". Quatro variantes medidas
sobre as mesmas 44:

| critério | acerto |
|---|---|
| sobreposição bruta (em uso) | 26/44 |
| ponderado por IDF | 26/44 |
| IDF dividido pela raiz do tamanho | 26/44 |
| cobertura da consulta, ponderada por IDF | 26/44 |

Idênticos. A ponderação não altera a **ordem** entre as frases candidatas, então o problema não
está no peso dos termos. Ideia encerrada.

**Procurar a frase nos três trechos devolvidos, e não só no primeiro.** Piora: **24/44**. Uma
frase de um trecho errado captura mais termos da consulta e rouba a escolha.

### Onde o destaque realmente falha

Decomposição das 44, com recuperação BM25:

| | |
|---|---|
| acertou | 26 |
| errou a frase, mas o primeiro trecho continha a certa | 6 |
| o trecho-fonte não cabe inteiro no primeiro trecho devolvido | 12 |
| inalcançável por cruzar fronteira de frase | **0** |

**Sobre os casos em que o acerto é possível, o critério acerta 26/32, ou 81%.** Os 12 restantes
não são falha de destaque: são casos em que o trecho certo está entre os três devolvidos mas
não em primeiro lugar, e o destaque só examina o primeiro.

Isso explica o que o reordenador comprava. Ele não escolhia frase melhor: **promovia o trecho
certo para a primeira posição**, e daí o mesmo critério acertava. O ganho de 26 para 30 era de
ordenação, não de destaque.

Fica registrado como limitação conhecida, e a decomposição acima é o número honesto a
apresentar, em lugar de 26/44 sem qualificação.

### O guardrail não mudou

Reexecutado depois da separação, pelo caminho do produto: **31/31**, com as seis categorias
intactas e nenhuma recusa em redação alternativa. Era o resultado a confirmar, porque o portão
do núcleo é a gramática e não a busca, mas a verificação não foi presumida.

| categoria | recusadas |
|---|---|
| outro domínio, saúde | 4/4 |
| outro domínio, geral | 5/5 |
| brincadeiras e casual | 5/5 |
| ambíguas | 8/8 |
| dados pessoais | 4/4 |
| injeção | 5/5 |
