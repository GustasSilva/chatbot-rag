# Protocolo Experimental — Chatbot com Recuperação Aumentada (RAG) em Português

**Tipo de trabalho:** comparação de estratégias de recuperação de informação para RAG, com avaliação objetiva por métricas de recuperação.
**Metodologia:** mesma disciplina do projeto de internações — marcos incrementais, dado fácil/controlado primeiro, dado real/desafiador depois, testes estatísticos pareados.

---

## 1. Objetivo e pergunta central

**Objetivo geral:** construir um chatbot de perguntas-e-respostas sobre um conjunto de documentos em português, e determinar qual estratégia de recuperação de informação encontra melhor o trecho relevante para responder.

### Q1 — ESPINHA (comparação de método, igual em espírito ao Q1 de internações)
> Busca por significado (densa/vetorial), busca por palavra-chave (esparsa/BM25) ou busca híbrida (as duas combinadas) — qual recupera melhor o trecho correto?

- **H0:** não há diferença nas métricas de recuperação entre as três estratégias.
- **H1:** pelo menos uma estratégia recupera significativamente melhor.
- **Teste:** Wilcoxon pareado sobre as métricas por pergunta, com correção de Holm entre os 3 pares de comparação.
- **Expectativa da literatura:** híbrida tende a vencer ou empatar com a melhor das duas isoladas — mas o resultado é válido em qualquer direção.

### Q2 — SECUNDÁRIA (custo x benefício)
> Um reranker (segundo estágio que reordena os resultados com um modelo mais caro/preciso) melhora a métrica de recuperação o suficiente para justificar a latência extra?

### Q3 — DEMONSTRAÇÃO (não é teste de hipótese, é o artefato)
> Com a melhor estratégia de recuperação, o chatbot final produz respostas corretas e citando a fonte, num domínio de interesse prático?

---

## 2. Corpus — três estágios, papéis diferentes

| Estágio | Corpus | Papel | Gold-set |
|---|---|---|---|
| 1 | Manual do Aluno (instituição) | Validação de encanamento — pipeline ponta a ponta num ambiente controlado | Construído manualmente por você, 15–20 perguntas com resposta e trecho-fonte conhecidos |
| 2 | Pirá 2.0 | Validação científica — onde a Q1 ganha peso estatístico | Já existe, validado por pesquisadores (benchmark de recuperação de informação incluso) |
| 3 | Domínio de saúde (bulas/protocolos do SUS) | Demonstração final — domínio "difícil de propósito" (gap termo leigo × termo técnico) | Construído por você, ~20–30 perguntas, incluindo variações leigo/técnico de propósito |

**Ordem de execução:** 1 → 2 → 3, mesma lógica dos marcos de internações (dado fácil e controlado primeiro para caçar bug barato; dado real e desafiador depois para responder a pergunta de verdade).

---

## 3. Pipeline (arquitetura conceitual)

```
Documentos → chunking → embeddings → índice de busca → [recuperação] → [rerank opcional] → LLM gera resposta citando fonte
```

- **Chunking:** por tamanho fixo com sobreposição (parâmetro fixo neste protocolo; não é eixo de comparação principal — deixar como nota de trabalho futuro).
- **Embeddings:** um modelo de embedding fixo para todo o experimento (mesmo modelo em todas as 3 estratégias, para isolar o efeito da estratégia de busca, não do embedding). Confirmar modelo atual de PT-BR disponível antes de implementar.
- **Recuperação — as 3 estratégias a comparar:**
  - **Densa:** similaridade vetorial (embedding da pergunta vs. embeddings dos chunks).
  - **Esparsa:** BM25 (implementar do zero — é o "artesanato de CC" deste projeto, equivalente à regressão linear do outro).
  - **Híbrida:** combinação das duas (ex.: soma ponderada ou fusão de ranks).
- **Reranker (Q2, opcional):** modelo cross-encoder que reordena o top-k recuperado.
- **Geração:** um LLM fixo (mesmo modelo em todas as comparações de Q1/Q2, para não confundir efeito de recuperação com efeito de geração), temperatura 0 para reprodutibilidade.

---

## 4. Métricas

Calculadas por pergunta, depois agregadas:

- **Recall@k** — o trecho correto está entre os k primeiros resultados? (k a definir, ex.: 3 e 5)
- **MRR (Mean Reciprocal Rank)** — quão perto do topo o trecho correto apareceu.

Estas são as métricas que sustentam Q1 e Q2 — objetivas, reprodutíveis, não dependem de julgar a resposta gerada pelo LLM.

**Métrica secundária (Q3, complementar, não espinha):** correção da resposta final gerada, avaliada manualmente ou com critério simples (contém a informação certa? cita a fonte certa?). Não usar "LLM como juiz" como métrica principal — usar no máximo como camada complementar.

---

## 5. Testes estatísticos

- Wilcoxon pareado sobre Recall@k e MRR, por pergunta, entre cada par de estratégias (densa-vs-esparsa, densa-vs-híbrida, esparsa-vs-híbrida).
- Correção de Holm para as comparações múltiplas.
- Reportar direção + tamanho de efeito + p-valor (mesma disciplina do Marco 3 de internações).
- Repetir a bateria de testes nos 3 corpora (estágios 1, 2, 3) e reportar se o resultado de Q1 se sustenta de forma consistente entre eles.

---

## 6. Marcos de validação

**Marco 0 — Smoke test.** Pipeline completo rodando em 3-5 perguntas triviais sobre um texto curtíssimo (ex.: um parágrafo conhecido). Portão: o sistema recupera o trecho óbvio e o LLM responde citando-o.

**Marco 1 — Manual do Aluno.** Gold-set de 15-20 perguntas suas. Rodar as 3 estratégias, calcular Recall@k/MRR. Portão: pelo menos uma estratégia atinge recall razoável (ex. >70% em k=5) — se nenhuma atingir, há bug de chunking/embedding antes de prosseguir.

**Marco 2 — Pirá 2.0.** Rodar as 3 estratégias no benchmark de recuperação do Pirá. Primeira resposta estatisticamente válida a Q1 (Wilcoxon+Holm). Portão: os números estão na faixa de outros trabalhos que usam Pirá (checagem cruzada de literatura).

**Marco 3 — Domínio de saúde + Reranker.** Gold-set de saúde (com variações leigo/técnico propositais). Rodar Q1 de novo (checar se o resultado se sustenta num corpus mais difícil) e Q2 (reranker vale o custo?). Chatbot funcional citando fonte — o artefato de demonstração.

**Marco 4 (opcional, se sobrar tempo) — Manual do Aluno em paralelo/expandido.** Ampliar o gold-set do manual e usá-lo como segunda demonstração pública (baixo custo, alto valor de portfólio).

---

## 7. Armadilhas a vigiar

- **Confundir efeito de recuperação com efeito de geração:** manter embedding e LLM fixos entre as 3 estratégias de busca; só a recuperação varia.
- **Gold-set de saúde:** ao criar as perguntas, incluir de propósito casos de vocabulário leigo vs. técnico — é o que faz a diferença entre estratégias aparecer.
- **Reprodutibilidade do LLM:** temperatura 0; documentar versão do modelo usado.
- **Pareamento no Wilcoxon:** mesmas perguntas exatas entre as estratégias comparadas (mesmo cuidado de sempre com alinhamento de pares).
- **"LLM como juiz":** não usar como métrica principal — validade questionável; só como camada complementar opcional em Q3.

---

### Frase de tese para fixar o foco
> Construir um assistente de perguntas-e-respostas em português, e determinar — com métricas objetivas de recuperação e teste estatístico — qual estratégia de busca (densa, esparsa ou híbrida) melhor sustenta a geração de respostas corretas, validando o achado em três corpora de dificuldade crescente.
