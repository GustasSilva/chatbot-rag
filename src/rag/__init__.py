"""Chatbot RAG em português — comparação de estratégias de recuperação.

Pacote organizado por responsabilidade:
- ``corpus``:    carregamento de documentos e chunking.
- ``embeddings``: modelo de embedding fixo (sentence-transformers / e5).
- ``retrieval``:  as 3 estratégias comparadas (densa, esparsa/BM25, híbrida) + reranker.
- ``evaluation``: métricas de recuperação (Recall@k, MRR) e testes estatísticos.
- ``generation``: interface do gerador de respostas (Q3, adiada para o Marco 3).
"""

__all__ = ["config"]
