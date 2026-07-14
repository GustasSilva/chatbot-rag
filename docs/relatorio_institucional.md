# Relatório — Assistente Institucional (produto sobre o Manual do Aluno)

Produto de chat livre sobre a vida acadêmica, construído sobre o Manual do Aluno. Usa a
configuração de recuperação validada cientificamente (**híbrida + reranker**) e um gerador
local (**Ollama / Llama 3.1 8B Q4**, temperatura 0) com **guardrail em perfil institucional**
(menos estrito que o de saúde — permite sintetizar a partir dos trechos, só recusa quando o
assunto não está no material). Saúde/Pirá permanecem como estudo científico (Q1/Q2), não
como chat aberto.

## Acurácia de resposta (50 perguntas, linguagem de aluno)

Gold-set: `data/goldsets/institucional.json` (50 perguntas). Harness: `scripts/institucional_acuracia.py`.

| métrica | resultado | como foi medida |
|---|---|---|
| Recuperação (chunk-fonte no top-5) | **49/50 = 98%** | objetiva/automática |
| Respondeu (não recusou) | 49/50 = 98% | objetiva |
| Citação do chunk exato (entre respondidas) | 41/49 = 84% | objetiva |
| **Conteúdo correto** | **46/50 = 92%** | revisão manual (não LLM-juiz) |

## Erros classificados (não misturar tipos)

**Recuperação (1):**
- `n04` "Como é a matrícula de quem acabou de entrar na faculdade?" — o chunk de *progressão
  tutelada* não entrou no top-5; a pergunta ambígua casou com outro trecho de matrícula.

**Geração (3):**
- `n14` "De quem é a responsabilidade de controlar as faltas?" — **resposta confidentemente
  errada**: disse "do professor" quando o correto é "do aluno". O chunk certo estava no
  contexto (recuperação OK), mas o modelo sintetizou de um trecho vizinho. É o erro mais
  relevante para o produto (errado com confiança, sem hesitar).
- `n07` "Onde encontro vaga de estágio não obrigatório?" — over-refusal: recusou mesmo com o
  trecho certo (Agentes de Integração) recuperado.
- `n17` "Faltar por serviço militar conta como falta?" — resposta confusa: lidera com "Sim,
  conta como falta" antes de chegar ao abono para serviço militar.

**Citação (≈5, conteúdo certo):** `m01, n02, n16, n20, n27` — resposta correta, mas citou um
chunk **vizinho** (que contém a mesma informação, por causa da sobreposição do chunking) em
vez do chunk-fonte exato. A métrica de citação exata é conservadora.

## Leitura

Recuperação quase perfeita (98%) e ~92% de acerto de conteúdo com um LLM local de 8B. Os
poucos erros são majoritariamente de **geração, não de recuperação** — o modelo ocasionalmente
sintetiza do trecho errado (`n14`) ou recusa demais (`n07`). Isso orienta os próximos passos:
guardrail adversarial ampliado (item 5) e, se necessário, ajuste de prompt/modelo para reduzir
erros do tipo `n14`.

## Enquadramento (produto × ciência)

- **Institucional (este relatório):** produto funcional, chat livre, métrica de acurácia de
  resposta + guardrail. Domínio de menor risco → levado a produto.
- **Saúde/Pirá:** estudo comparativo controlado (Q1: híbrida>densa e esparsa>densa; Q2:
  reranker vale), demonstração restrita — não vira chat aberto (risco maior).
