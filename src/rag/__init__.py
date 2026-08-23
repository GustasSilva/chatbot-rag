"""Assistente de perguntas e respostas em português cujo núcleo é um front-end de compilador.

Quem entende a pergunta é o pacote ``compilador``. O modelo de linguagem, em ``ia``, é plano B:
só entra quando a gramática não reconhece a pergunta.

Os pacotes estão separados pelo que cada um é, e a fronteira que mais importa é a primeira:

**O núcleo, sem aprendizado de máquina**

- ``compilador``: análise léxica, sintática e semântica sobre a pergunta do aluno, mais a
  consulta à base de conhecimento e o controlador de diálogo. Puro Python, sem modelo, sem
  peso treinado. É a intervenção de Ciência da Computação do trabalho.

**A inteligência artificial, em papel secundário**

- ``ia``: o modelo de linguagem e o que o cerca, incluindo a decodificação restrita por
  gramática. Essa restrição também é técnica de compilador, mas aplicada à **saída** do
  modelo, e não à entrada do aluno. Foi a intervenção anterior ao pivô de 13/08/2026 e hoje
  vale como resultado preliminar.

**A infraestrutura que os dois usam**

- ``recuperacao``: BM25 escrito do zero, recuperação densa, híbrida, reranker e o modelo de
  embeddings. O núcleo usa a parte esparsa; o plano B usa a pilha completa.
- ``corpus``: carregamento de PDF, normalização e divisão em trechos.
- ``avaliacao``: métricas, gold-sets e testes estatísticos. Não entra no produto.
- ``dados``: leitura dos conjuntos externos usados no estudo comparativo.

**Transversais**, na raiz do pacote: ``config`` (o ``config.yaml`` tipado), ``pipeline``
(monta índice e recuperadores) e ``apresentacao`` (formata a resposta para exibição).

O raciocínio por trás de cada decisão está em ``docs/decisoes.md``.
"""

__all__ = ["config"]
