"""Recuperação de trechos do corpus, a infraestrutura que núcleo e plano B compartilham.

- ``esparsa``:  BM25 escrito do zero, índice invertido e IDF Okapi. É o que o núcleo usa.
- ``reranker``: reordenação por cross-encoder. O piso de score do guardrail é calculado
                sobre o escore dele.
- ``base``:     o contrato comum aos recuperadores.
"""
