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

Reconstroem o conjunto de perguntas de referencia a partir do PDF. Rodar so quando o corpus ou
o chunking mudarem; o JSON versionado ja e o resultado validado.

| Script | O que faz |
|---|---|
| `construir_goldset_institucional.py` | Manual do Aluno, 50 perguntas em linguagem de aluno. |

## `estudo/`

Medicoes que sustentam decisoes de arquitetura, e nao o funcionamento do produto. Rodar so
quando a decisao for revisitada; os numeros ficam registrados no `docs/decisoes.md` §24,
porque `outputs/` nao e versionado.

| Script | O que responde |
|---|---|
| `piso_sem_reordenador.py` | O piso do guardrail funciona sobre a pontuacao do BM25? Nao: 2/31 contra 31/31. |
| `contribuicao_do_reordenador.py` | Quanto o reordenador melhora a recuperacao do caminho auxiliar, e se criterio lexico barra a categoria ambigua. |
| `guardrail_pelo_compilador.py` | O proprio front-end serve de primeiro estagio do guardrail? Pega 20/31 sem custo nas legitimas. |
