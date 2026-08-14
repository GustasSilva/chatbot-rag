# Relatório Final — um motor RAG, duas aplicações

Documento de fechamento. Amarra as duas metades do projeto e aponta para os relatórios
detalhados; os números-cabeçalho estão aqui para o texto se sustentar sozinho.

- **Ciência (Q1/Q2/Q3):** detalhes e tabelas completas no [`README.md`](../README.md).
- **Produto (assistente institucional):** detalhes em [`relatorio_institucional.md`](relatorio_institucional.md).

## 1. Resumo

Um único motor de RAG, **corpus-agnóstico** — recuperação **densa** (e5), **esparsa** (BM25
Okapi implementado do zero) e **híbrida** (RRF), **reranker** cross-encoder opcional e um
**gerador local** (Ollama / Llama 3.1 8B Q4, temperatura 0) com guardrail. Sobre esse mesmo
motor foram construídas **duas aplicações, separadas por risco**:

| | Produto | Ciência |
|---|---|---|
| Corpus | Manual do Aluno | Pirá 2.0 (227 q.) + 4 PCDTs do SUS (24 q.) |
| Uso | **chat livre** (input aberto) | **estudo comparativo controlado** |
| Entrega | assistente institucional funcional | resposta a Q1/Q2/Q3 |
| Por quê | domínio de **menor risco** | saúde tem **maior risco** → não vira chat aberto |

A separação é deliberada: a mesma engenharia serve tanto para um produto demonstrável quanto
para um experimento com teste estatístico — mas só o domínio de baixo risco (institucional)
é exposto como chat livre.

## 2. Ciência — o que ficou respondido

- **Q1 (qual estratégia recupera melhor).** No Pirá 2.0 (n=227, Wilcoxon pareado + Holm):
  **híbrida > densa** (efeito +0.71, grande, p_holm=0.0001) e **esparsa > densa** (efeito
  +0.35, médio, p_holm=0.025); **híbrida ≈ esparsa** (não significativo). Ou seja, o BM25
  "de artesanato" **supera o denso zero-shot** no domínio técnico — replica o achado do paper
  do Pirá. A direção **híbrida ≥ densa ≈ esparsa** se sustenta no corpus de saúde (n=24, sem
  poder para significância). **Gap leigo×técnico:** o BM25 **desaba** no vocabulário leigo
  (R@5 0.17 leigo × 0.83 técnico, p=0.008); a densa é a que menos sofre — a busca semântica
  atravessa parte do gap.
- **Q2 (o reranker justifica a latência).** Sim, no caso de uso de QA: o cross-encoder sobre
  a híbrida melhora sobretudo o topo do ranking (**MRR 0.411 → 0.581**, **R@1 0.29 → 0.50**),
  que é o que vira resposta. A 1ª fonte é a que importa.
- **Q3 (chatbot citando fonte).** O chatbot junta a melhor recuperação (híbrida + reranker) ao
  gerador local, responde em PT **citando o trecho `[n]`** e **recusa** quando a informação
  não está no contexto (guardrail; não alucina).

**Achado transversal (limitação real da híbrida).** A fusão RRF pode ficar **abaixo da densa
pura** quando um recuperador acerta forte e o outro falha: itens que ambos acham medianamente
diluem um acerto forte de um só (verificado no miss do diabetes do Q3 — a densa achava o
trecho no rank 2, a híbrida o perdia). Por isso **híbrida ≈ esparsa**, não híbrida > esparsa.

## 3. Produto — assistente institucional

Chat livre sobre o Manual do Aluno, perfil de guardrail **institucional** (mais brando que o de
saúde) e um **piso de score** de reranker.

Recuperação do produto: **BM25 + reranker** (`pipeline.montar_recuperador_produto`). Difere da
configuração vencedora do estudo comparativo (híbrida + reranker) por uma razão medida: quem
consulta o Manual passou a ser a **consulta canônica** montada pelo front-end de compilador,
escrita nas palavras do próprio documento — e nesse caminho BM25 puro e híbrida+reranker deram
resultado **idêntico** (`scripts/cobertura_nucleo.py`). A recuperação densa compensava a redação
crua do aluno, que não chega mais até a busca. O cross-encoder permanece porque o **piso de
score** depende do escore dele, e o piso é o guardrail do plano B — esse sim ainda recebe a
pergunta como o aluno escreveu.

- **Config plugável:** o núcleo é corpus-agnóstico — o produto trocou só o corpus, sem mudar
  código do motor.
- **Acurácia de resposta** (50 perguntas em linguagem de aluno, revisão manual):
  **recuperação 98%**, **conteúdo 92%**, citação exata 84%. Erros majoritariamente de
  **geração, não de recuperação** (o 8B às vezes sintetiza do trecho vizinho). Uma instrução
  anti-repetição (perfil institucional **v2**) zerou o over-refusal (2%→0%) ao custo da citação
  exata (84%→80%) — A/B completo no relatório institucional.
- **Guardrail adversarial** (31 perguntas fora de escopo): só com o prompt, 27/31 recusam; o
  único **vazamento real** (pergunta médica puxando um trecho institucional vizinho) foi
  fechado com um **piso de score de reranker (−3.2)** → recusa vai a **31/31 = 100%**. O piso
  foi *calibrado* para não recusar nenhuma das 50 do gold-set (**0/50 in-sample**, folga fina
  de 0.28 — ver ressalva no relatório institucional). **0/5 injeções** de prompt extraíram
  conteúdo fabricado. (No perfil **v2** o guardrail é **30/31**: um caso — *"quando é minha
  próxima prova?"* — recusa o dado pessoal mas pivota para o Calendário público, **sem fabricar**.)
- **Interface:** **tela web** (`streamlit run app.py`, com os trechos-fonte numerados `[n]` e o
  citado marcado) ou **REPL** (`python scripts/assistente_institucional.py`) — ambas com
  **disclaimer** (assistente não-oficial), citação do trecho do Manual e recusa fora de escopo.
  Mostra os **trechos consultados em toda resposta** (mesmo quando o modelo não cita `[n]`, para
  a evidência nunca ficar oculta) e **responde saudações** de forma amigável, sem afrouxar a
  recusa a perguntas específicas fora de escopo (detector conservador, `chatbot.eh_saudacao`).
  Mantém **contexto da conversa** (multi-turn): reescreve follow-ups elípticos (*"e as
  presenciais?"*) numa pergunta autônoma antes de recuperar. Validado: guardrail e acurácia de
  turno único **inalterados** (30/31; recuperação 98%) e **0 vazamentos** em follow-ups
  adversariais (*"e o tratamento para asma?"* após uma pergunta legítima segue recusando).

## 4. Limitações e questões abertas

- **Erro de geração tipo `n14`** (produto): o 8B ocasionalmente responde **errado com
  confiança** sintetizando do trecho vizinho. Mitigável por prompt/modelo — em aberto.
- **Experimento de fusão** (estudo preliminar) — **fechado e fora do escopo do produto**.
  Testado rerankear a **união intercalada** densa+esparsa (sem média de ranks) em vez de
  RRF→rerank, com a mesma verba de candidatos. A união ficou consistentemente ≥ RRF (recall@5
  saúde 0.71→0.75, Pirá 0.91→0.93) **mas sem significância** (p>0.05), e recuperou o
  **"miss do diabetes"**. A questão deixou de existir no produto: com o front-end de compilador
  não há mais fusão nenhuma no caminho (a recuperação é BM25 + reranker, ver §3), então RRF
  versus união virou pergunta sobre a configuração do estudo comparativo, não sobre o sistema
  entregue. Fica registrado como resultado; `RecuperadorUniao` e `scripts/exp_fusao_reranker.py`
  seguem reproduzíveis para quem quiser reexaminar o estudo.
- **Piso de score** é específico do corpus + reranker (calibrado no Manual); outro corpus
  exige recalibrar (o mecanismo é geral, o valor não).
- **Escopo do produto:** Manual-only — os demais documentos institucionais não estavam
  disponíveis localmente. O motor aceita mais corpora sem mudança de código.

## 5. Reprodutibilidade

Parâmetros fixos em `config.yaml` (embedding, chunking, temperatura 0, piso de score). Como
rodar cada marco e o produto: seção "Como rodar" do `README.md`. Métricas regeneráveis em
`outputs/*.csv`; gold-sets versionados em `data/goldsets/`; corpora brutos fora do git (fontes
oficiais no README e nos scripts de construção dos gold-sets).
