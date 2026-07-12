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
| 3 — Saúde + Reranker | Bulas/protocolos SUS (gap leigo×técnico) | Q1 se sustenta + Q2 + chatbot citando fonte | ⬜ pendente |

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

**Q1 (agora com discriminação):**
- **híbrida > densa** em recall@5 (p_holm = 0.0001, efeito +0.71) — forte e significativo.
- **esparsa (BM25) > densa** em recall@5 (p_holm = 0.025) — **replica o achado do paper de que
  o BM25 supera o denso no Pirá**. Domínio técnico/científico favorece o casamento léxico, e
  o e5 zero-shot ainda trunca abstracts longos (>512 subtokens).
- híbrida ≥ esparsa (numérico, não significativo em recall@5; p_holm = 0.18).
- Em MRR nenhuma diferença sobrevive a Holm (efeitos menores).

Leitura: no corpus difícil, **híbrida ≥ esparsa > densa** — a híbrida entrega o melhor
recall e o BM25 é surpreendentemente forte, coerente com a literatura do Pirá.

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
```

Dados do Pirá (Marco 2) — baixados do repositório oficial ([C4AI/Pira](https://github.com/C4AI/Pira),
CC BY 4.0) para `data/raw/pira/` (fora do git):

```bash
# via GitHub CLI (branch main):
for f in train validation test; do \
  gh api "repos/C4AI/Pira/contents/Data/$f.csv" -H "Accept: application/vnd.github.raw" \
    > "data/raw/pira/$f.csv"; done
```

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
