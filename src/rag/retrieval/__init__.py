"""As 3 estratégias de recuperação comparadas em Q1, mais o reranker de Q2.

- ``densa``:    similaridade vetorial (embedding da pergunta vs. dos chunks).
- ``esparsa``:  BM25 Okapi implementado do zero.
- ``hibrida``:  fusão das duas (RRF ou soma ponderada).
- ``reranker``: cross-encoder que reordena o top-k (segundo estágio, Q2).
"""
