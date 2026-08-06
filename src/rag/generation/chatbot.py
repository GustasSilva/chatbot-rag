"""Chatbot RAG: liga a recuperação à geração (o artefato de demonstração, Q3).

Usa a melhor recuperação medida nos marcos anteriores (idealmente híbrida + reranker),
pega o top-k de trechos e pede ao gerador uma resposta em português citando a fonte.
"""
from __future__ import annotations

import random
import unicodedata
from dataclasses import dataclass

from ..corpus.chunking import Chunk
from ..retrieval.base import Recuperador
from .generator import RECUSA_PADRAO, Gerador, RespostaGerada, Turno


@dataclass(frozen=True)
class RespostaChatbot:
    pergunta: str
    resposta: RespostaGerada
    contextos: list[Chunk]  # trechos recuperados que alimentaram o gerador


# Saudação/conversa social: respondida com uma mensagem fixa e amigável, SEM passar pela
# recuperação. É deliberadamente conservador — só dispara quando a mensagem é SÓ saudação,
# nunca quando há uma pergunta de verdade (essas seguem para o pipeline, que responde ou
# recusa fora de escopo normalmente).
# Conjunto de respostas para não repetir a mesma frase quando o usuário saúda mais de uma vez.
RESPOSTAS_SAUDACAO = (
    "Olá! Sou o assistente (não-oficial) do Manual do Aluno da UNIP. Posso ajudar com dúvidas "
    "sobre a vida acadêmica — matrícula, faltas, provas, aproveitamento de estudos e afins. Em "
    "que posso ajudar?",
    "Oi! Este é o assistente (não-oficial) do Manual do Aluno da UNIP. Pergunte à vontade sobre "
    "matrícula, faltas, provas, trancamento e outros temas acadêmicos.",
    "Olá, tudo bem? Tiro dúvidas sobre o Manual do Aluno da UNIP — faltas, provas, rematrícula, "
    "aproveitamento de estudos e afins. O que você quer saber?",
    "Oi, que bom te ver! Sou o assistente (não-oficial) do Manual do Aluno. Sobre qual assunto "
    "da vida acadêmica você precisa de ajuda?",
)


def _resposta_saudacao() -> str:
    return random.choice(RESPOSTAS_SAUDACAO)
# Ordenadas por tamanho decrescente: remover as frases antes das palavras soltas.
_SAUDACOES = (
    "como voce esta", "como vc esta", "como vai voce", "como vai",
    "bom dia", "boa tarde", "boa noite",
    "tudo bem", "tudo bom", "tudo certo",
    "e ai", "ola", "oi", "opa", "hey", "ei", "salve", "beleza",
)
# Palavras de ligação que podem sobrar em torno de uma saudação sem torná-la uma pergunta.
_RUIDO = {"e", "ai", "voce", "vc", "entao", "assistente", "por", "favor", "bom", "boa"}


def _normalizar(texto: str) -> str:
    """Minúsculas, sem acentos, pontuação virando espaço."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto.lower()) if not unicodedata.combining(c)
    )
    return "".join(c if c.isalnum() or c.isspace() else " " for c in sem_acento)


def eh_saudacao(texto: str) -> bool:
    """True se a mensagem for APENAS saudação/social (sem pergunta substantiva)."""
    n = " " + " ".join(_normalizar(texto).split()) + " "
    achou = False
    for frase in _SAUDACOES:
        alvo = f" {frase} "
        if alvo in n:
            achou = True
            n = n.replace(alvo, " ")
    if not achou:  # nenhuma saudação reconhecida -> não é saudação
        return False
    resto = [t for t in n.split() if t not in _RUIDO]
    return not resto  # sobrou só saudação/ruído -> é saudação pura


class ChatbotRAG:
    """Liga recuperação e geração, com um piso de score opcional como guardrail.

    ``piso_score`` recusa a pergunta ANTES de chamar o LLM quando nem o melhor trecho
    recuperado tem confiança suficiente (score do 1º estágio abaixo do piso). É defesa em
    profundidade contra vazamento: perguntas fora do domínio puxam trechos lexicalmente
    vizinhos e um guardrail brando pode respondê-los; o piso barra esses casos e ainda
    economiza a latência do LLM. O valor é específico do recuperador — só faz sentido com
    o reranker (cross-encoder, logits) e é calibrado contra o gold-set do corpus.

    ``saudar`` liga a resposta amigável a saudações puras (produto de chat livre); desligado
    por padrão para a via científica não mudar de comportamento.
    """

    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        gerador: Gerador,
        top_k_contexto: int = 5,
        piso_score: float | None = None,
        saudar: bool = False,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {c.id: c for c in chunks}
        self._gerador = gerador
        self._top_k = top_k_contexto
        self._piso_score = piso_score
        self._saudar = saudar

    def responder(
        self, pergunta: str, historico: list[Turno] | None = None
    ) -> RespostaChatbot:
        if self._saudar and eh_saudacao(pergunta):
            return RespostaChatbot(pergunta, RespostaGerada(_resposta_saudacao(), []), [])

        # Multi-turn: reescreve a pergunta como autônoma para a recuperação funcionar em
        # follow-ups elípticos ("e as presenciais?"). Sem histórico, nada muda.
        consulta = self._gerador.reescrever_consulta(pergunta, historico) if historico else pergunta
        resultados = self._recuperador.buscar(consulta, self._top_k)
        if self._piso_score is not None and (
            not resultados or resultados[0].score < self._piso_score
        ):
            return RespostaChatbot(pergunta, RespostaGerada(RECUSA_PADRAO, []), [])
        contextos = [self._por_id[r.chunk_id] for r in resultados]
        resposta = self._gerador.gerar(pergunta, contextos, historico=historico)
        return RespostaChatbot(pergunta=pergunta, resposta=resposta, contextos=contextos)
