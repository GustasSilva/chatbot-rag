# scripts/

Os scripts executáveis do projeto, separados pelo papel que cumprem. Todos assumem o pacote
instalado (`pip install -e .`) e são chamados da raiz do repositório:

```bash
python scripts/produto/cobertura_nucleo.py
```

## `produto/`

O assistente do Manual do Aluno e as medições que o sustentam. É o que está em uso.

| Script | O que faz |
|---|---|
| `assistente_institucional.py` | Chat livre no terminal, o produto demonstrável. |
| `cobertura_nucleo.py` | Cobertura do núcleo de compilador sobre o gold-set institucional. |
| `institucional_acuracia.py` | Acurácia de resposta e de recuperação. |
| `institucional_guardrail.py` | Teste adversarial: taxa de recusa fora de escopo. |

## `goldsets/`

Constroem e validam os conjuntos de avaliação a partir dos corpora. Rodar antes de qualquer
medição, quando o corpus mudar.

| Script | Gold-set |
|---|---|
| `construir_goldset_institucional.py` | Manual do Aluno, 50 perguntas em linguagem de aluno. |
| `construir_goldset_manual.py` | Manual do Aluno, versão do Marco 1. |
| `construir_goldset_pcdt.py` | Quatro PCDTs do SUS. |

## `estudo/`

O estudo comparativo de estratégias de recuperação e a intervenção de decodificação restrita
por gramática. **Os dois viraram resultado preliminar no pivô de 13/08/2026**, quando o núcleo
do trabalho passou a ser o front-end de compilador sobre a entrada. Os scripts continuam aqui
porque produziram números que o texto cita, e precisam ser reexecutáveis.

| Script | O que mediu |
|---|---|
| `marco0_smoke.py` | Fumaça do pipeline RAG. |
| `marco1_manual.py` | Comparação de estratégias sobre o Manual do Aluno. |
| `marco2_pira.py` | Benchmark Pirá 2.0, com poder estatístico. |
| `marco3_pcdt.py` | PCDT do SUS com reranker. |
| `marco3_chatbot.py` | Chatbot de saúde citando fonte. |
| `marco3_guardrail.py` | Recusa em perguntas fora de escopo. |
| `marco_gramatica_smoke.py` | Fumaça da decodificação restrita. |
| `exp_gramatica.py` | Efeito da gramática de citação na atribuição de fonte. |
| `exp_json.py` | Efeito da gramática JSON na validade da saída estruturada. |
| `exp_fusao_reranker.py` | RRF contra união intercalada na entrada do reranker. |
| `exp_prompt_n14.py` | Âncora de atribuição no prompt. **Rejeitado.** |
| `diag_limiar_goldset.py` | Calibração do piso de score do reranker. |
| `diag_score_reranker.py` | Separação entre perguntas dentro e fora de escopo. |

---

O raciocínio por trás das decisões de projeto está em [`../docs/decisoes.md`](../docs/decisoes.md).
