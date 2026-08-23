"""Recuperacao de trechos do corpus, a infraestrutura que nucleo e plano B compartilham.

- ``esparsa``:  BM25 escrito do zero, indice invertido e IDF Okapi. **E o que o nucleo usa.**
- ``densa``:    similaridade vetorial entre a pergunta e os trechos.
- ``hibrida``:  fusao das duas por RRF.
- ``reranker``: reordenacao por cross-encoder, usada pelo plano B.
- ``embeddings``: o modelo de embedding que a densa e a hibrida carregam.
- ``base``:     o contrato comum a todos os recuperadores.
- ``uniao``:    fusao alternativa, medida no estudo e sem efeito no produto.
"""
