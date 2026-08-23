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

Acerto = trecho-fonte do gold-set dentro da frase destacada, nas 44 que a gramática reconhece:

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

Diagnóstico das 18 falhas: em 12 a frase certa estava no 2º ou 3º trecho; em 6 o trecho do topo
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
