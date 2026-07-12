# Chatbot RAG em Português — Comparação de Estratégias de Recuperação

> Construir um assistente de perguntas-e-respostas em português e determinar — com
> métricas objetivas de recuperação e teste estatístico — qual estratégia de busca
> (**densa**, **esparsa** ou **híbrida**) melhor sustenta a geração de respostas
> corretas, validando o achado em corpora de dificuldade crescente.

Projeto experimental seguindo `docs/protocolo_rag_chatbot.md`. Metodologia por **marcos
incrementais**: dado fácil e controlado primeiro (para caçar bug barato), dado real e
desafiador depois (para responder a pergunta de verdade), com testes estatísticos pareados.

## Perguntas de pesquisa

- **Q1 (espinha)** — Busca por significado (densa/vetorial), por palavra-chave
  (esparsa/BM25) ou híbrida: qual recupera melhor o trecho correto? *(Wilcoxon pareado +
  Holm sobre Recall@k e MRR.)*
- **Q2 (secundária)** — Um reranker (cross-encoder) melhora a recuperação o suficiente
  para justificar a latência extra?
- **Q3 (demonstração)** — Com a melhor estratégia, o chatbot final responde certo e
  citando a fonte, num domínio de interesse prático?

## Arquitetura

```
Documentos → chunking → embeddings → índice → [recuperação] → [rerank opcional] → LLM cita fonte
```

Só a **estratégia de recuperação** varia entre as comparações; chunking, embedding e (no
futuro) o LLM ficam **fixos**, para isolar o efeito da busca e não confundi-lo com o da
geração (protocolo §7).

| Camada | Módulo | Papel |
|---|---|---|
| Corpus | `rag.corpus.loaders` / `chunking` | Carrega PDF/texto, normaliza, divide em chunks com sobreposição |
| Embedding | `rag.embeddings` | Modelo fixo `multilingual-e5-base` (prefixos `query:`/`passage:`) |
| Recuperação | `rag.retrieval.densa` | Similaridade de cosseno (vetorial) |
| | `rag.retrieval.esparsa` | **BM25 Okapi implementado do zero** |
| | `rag.retrieval.hibrida` | Fusão RRF ou soma ponderada |
| | `rag.retrieval.reranker` | Cross-encoder de 2º estágio (Q2) |
| Avaliação | `rag.evaluation.metrics` | Recall@k, MRR (por pergunta) |
| | `rag.evaluation.stats` | Wilcoxon pareado + Holm + tamanho de efeito |
| | `rag.evaluation.goldset` | Perguntas com trecho-fonte; resolução de relevância |
| Geração | `rag.generation.generator` | Interface do LLM (Q3, **adiada** ao Marco 3) |
| Fábrica | `rag.pipeline` | Amarra corpus → índice → 3 recuperadores compartilhando chunks/embedding |

## Marcos

| Marco | Corpus | Portão | Status |
|---|---|---|---|
| **0 — Smoke test** | Texto curtíssimo, 5 perguntas triviais | 3 estratégias recuperam o trecho óbvio | ✅ **passou** |
| **1 — Manual do Aluno** | Manual UNIP 2026 (18 perguntas) | ≥1 estratégia com recall@5 > 70% | ✅ **passou** (todas 100%, satura) |
| **2 — Pirá 2.0** | Benchmark científico ([C4AI/USP](https://github.com/C4AI/Pira), CC BY 4.0) | BM25 na faixa da literatura | ✅ **passou** (Q1 discrimina) |
| **3 — Saúde + Reranker** | 4 PCDTs do SUS ([CONITEC](https://www.gov.br/conitec), CC BY) | Q1 se sustenta + Q2 + gap leigo×técnico | ✅ **Q1/Q2 feitos** (Q3 adiado) |

### Resultado do Marco 1

| estratégia | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| densa | 0.78 | 1.00 | 1.00 | 1.00 | 0.880 |
| esparsa (BM25) | 0.83 | 0.94 | 1.00 | 1.00 | 0.903 |
| **híbrida** | 0.83 | 1.00 | 1.00 | 1.00 | **0.917** |

**Leitura honesta do Marco 1 — o corpus satura.** As três estratégias chegam a
**Recall@5 = 100%** (e Recall@3 ≈ 100%): o teto foi atingido. Isso significa que o Marco 1
**não discrimina** as estratégias — a métrica-espinha está saturada e não há variância
pareada suficiente para o Wilcoxon separar densa/esparsa/híbrida (todas as comparações em
Recall@5 são empate; nada sobrevive a Holm). O Marco 1 cumpre exatamente o papel que o
protocolo lhe dá: **validação de encanamento** (o pipeline ponta a ponta funciona, o
gold-set é sólido, a recuperação é forte num ambiente controlado) — e **não** uma resposta
a Q1. A discriminação entre estratégias e o peso estatístico de Q1 dependem de um corpus
mais difícil, com perguntas onde as estratégias divergem: é o papel do **Marco 2 (Pirá 2.0)**.
O único sinal (fraco, não significativo) que sobra é a ordem de MRR — a híbrida lidera —,
coerente com a expectativa da literatura, mas a rigor indistinguível aqui.

### Resultado do Marco 2 (Pirá 2.0)

Corpus = 757 abstracts em PT (cada um um documento); queries = split de test (227
perguntas); gold = o abstract da pergunta. Aqui as perguntas divergem e **n=227**, então o
Wilcoxon+Holm tem poder real.

| estratégia | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| densa (e5) | 0.52 | 0.71 | 0.78 | 0.87 | 0.642 |
| esparsa (BM25) | 0.56 | 0.83 | 0.86 | 0.90 | 0.698 |
| **híbrida** | 0.52 | 0.81 | **0.89** | **0.93** | 0.680 |

**Portão:** BM25 recall@10 = **0.90**, batendo o paper (BM25 > 90% para k≥6) — confirma que
o corpus e a tokenização estão corretos.

**Q1 — direção, tamanho de efeito (rank-biserial pareado) e p_holm:**

| métrica | comparação | efeito | magnitude | p_holm | significativo |
|---|---|---|---|---|---|
| recall@5 | híbrida > densa | +0.71 | grande | 0.0001 | ✅ |
| recall@5 | esparsa > densa | +0.35 | médio | 0.025 | ✅ |
| recall@5 | híbrida > esparsa | +0.26 | pequeno-médio | 0.178 | ❌ |
| MRR | híbrida > densa | +0.25 | pequeno-médio | 0.115 | ❌ |
| MRR | esparsa > densa | +0.22 | pequeno | 0.115 | ❌ |
| MRR | esparsa > híbrida | −0.13 | pequeno | 0.348 | ❌ |

Efeito calculado sobre os pares discordantes (`n_efetivo`); em recall@5 muitos pares
empatam. **Leitura de fechamento:** o efeito robusto é **híbrida > densa (grande)**;
**esparsa > densa (médio)** também se sustenta — **replica o achado do paper de que o BM25
supera o denso no Pirá** (domínio técnico favorece o casamento léxico, e o e5 zero-shot
trunca abstracts >512 subtokens). Já **híbrida ≈ esparsa** (efeito pequeno, não
significativo): não dá para afirmar que a híbrida bate o BM25 aqui. Conclusão precisa:
**híbrida > densa e esparsa > densa; híbrida e esparsa empatam estatisticamente.**

### Resultado do Marco 3 (Saúde — 4 PCDTs do SUS)

Corpus difícil "de propósito": 4 protocolos clínicos (asma, hipertensão, diabetes t2, dor
crônica; 1330 chunks) e um gold-set de 24 perguntas em **pares leigo×técnico** (12+12) — a
mesma pergunta em vocabulário popular vs. clínico, apontando para o mesmo trecho. n é
pequeno, então valem direção e tamanho de efeito (o protocolo prevê isso no corpus difícil).

**Q1 — geral:** híbrida R@5=0.62 / MRR=0.411; densa 0.50 / 0.392; esparsa 0.50 / 0.356. A
híbrida lidera (efeito +0.60 vs ambas), mas nada é significativo a n=24. Direção: **híbrida
≥ densa ≈ esparsa** — o padrão do Marco 2 se sustenta em direção, sem poder para provar.

**Gap leigo×técnico (o cerne do Marco 3):**

| estratégia | R@5 leigo | R@5 técnico | p (pareado por fato) |
|---|---|---|---|
| densa | 0.33 | 0.67 | 0.125 |
| esparsa (BM25) | **0.17** | **0.83** | **0.008** |
| híbrida | 0.42 | 0.83 | 0.062 |

Todas recuperam pior no leigo (efeito +1.00: por fato, o técnico sempre ≥ leigo). Mas o
**BM25 desaba no vocabulário leigo** (0.17 vs 0.83, significativo) — pura dependência léxica.
A **densa é a que menos sofre no leigo** entre as puras (0.33 > 0.17): a busca semântica
atravessa parte do gap termo-leigo × termo-técnico. É exatamente o fenômeno que o corpus foi
desenhado para expor.

**Q2 — reranker (cross-encoder sobre a híbrida):**

| | R@1 | R@3 | R@5 | R@10 | MRR |
|---|---|---|---|---|---|
| híbrida | 0.29 | 0.46 | 0.62 | 0.67 | 0.411 |
| + reranker | **0.50** | **0.62** | **0.71** | **0.75** | **0.581** |

Ganho grande, sobretudo no topo do ranking (R@1 +0.21, MRR +0.17, efeito +0.58) — o que mais
importa para um chatbot de QA, onde a 1ª fonte é a que vai para a resposta. Sugere que a
latência extra do reranker **se justifica** neste caso de uso (p=0.09 a n=24; direção clara).

**Q3 (chatbot gerando resposta citando fonte):** adiado — depende do backend do gerador.

## Como rodar

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate     |  Linux/Mac:  source .venv/bin/activate
pip install -e ".[dev]"

pytest                                   # 15 testes de núcleo (rápidos, sem baixar modelo)
python scripts/marco0_smoke.py           # Marco 0 — baixa o e5 (~440 MB) na 1ª vez
python scripts/construir_goldset_manual.py   # (re)constrói e valida o gold-set do manual
python scripts/marco1_manual.py          # Marco 1 — avaliação + Q1; escreve outputs/marco1_*.csv
python scripts/marco2_pira.py            # Marco 2 — Pirá; escreve outputs/marco2_*.csv
python scripts/construir_goldset_pcdt.py # gold-set de saúde (pares leigo×técnico)
python scripts/marco3_pcdt.py            # Marco 3 — PCDT + reranker; baixa o cross-encoder na 1ª vez
```

Dados do Pirá (Marco 2) — baixados do repositório oficial ([C4AI/Pira](https://github.com/C4AI/Pira),
CC BY 4.0) para `data/raw/pira/` (fora do git):

```bash
# via GitHub CLI (branch main):
for f in train validation test; do \
  gh api "repos/C4AI/Pira/contents/Data/$f.csv" -H "Accept: application/vnd.github.raw" \
    > "data/raw/pira/$f.csv"; done
```

PCDTs (Marco 3) — baixados da CONITEC/gov.br para `data/raw/pcdt/` (`asma.pdf`,
`hipertensao.pdf`, `diabetes_t2.pdf`, `dor_cronica.pdf`). URLs oficiais no cabeçalho de
`scripts/construir_goldset_pcdt.py`.

## Decisões de design

- **BM25 do zero** (`retrieval/esparsa.py`): índice invertido + IDF Okapi + normalização
  por tamanho — nenhuma lib de busca pronta (é o "artesanato de CC" do projeto).
- **Embedding fixo** (`multilingual-e5-base`): o mesmo nas 3 estratégias, para medir a
  busca e não o embedding.
- **Fusão por RRF** como padrão da híbrida: usa só a ordem, então é imune à diferença de
  escala entre score de cosseno e BM25.
- **Relevância por sobreposição de offsets**: o trecho-fonte é um substring exato do
  corpus limpo; um chunk conta como relevante se cobre boa parte do trecho — robusto à
  fronteira do chunking (que tem sobreposição).
- **Normalização de PDF** (`corpus/loaders.normalizar_pdf`): remove hífens suaves e refaz
  palavras quebradas na quebra de linha (257 casos no manual) — melhora sobretudo o BM25.
- **Pareamento cuidadoso no Wilcoxon** (`avaliacao.series_pareadas`): vetores alinhados
  pela mesma ordem de perguntas — evita o erro clássico de desalinhar pares.
- **Gerador adiado**: o núcleo científico (Q1/Q2) não usa LLM; a interface existe, o
  backend concreto será escolhido no Marco 3.

## Estrutura

```
config.yaml            parâmetros fixos do experimento
src/rag/               pacote (corpus, embeddings, retrieval, evaluation, generation, pipeline)
scripts/               marco0_smoke, construir_goldset_manual, marco1_manual
tests/                 testes de núcleo (pytest)
data/raw/              corpora brutos (PDF) — fora do git
data/goldsets/         gold-sets validados (JSON)
outputs/               métricas e testes (CSV) — regeneráveis
docs/                  protocolo experimental
```
