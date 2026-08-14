"""Base de conhecimento: executa a consulta do front-end contra o Manual e devolve o trecho.

É a costura entre as duas metades do sistema. O front-end de compilador decidiu **o que**
perguntar (``Consulta``); aqui se pergunta ao documento, reaproveitando a recuperação que já
existe e já foi medida nos marcos científicos — nada de busca nova, só uso.

**Este é o caminho que responde sem IA.** Da pergunta do aluno até o trecho do Manual não há
modelo de linguagem em lugar nenhum: léxico, gramática, parser, consulta canônica e recuperação.
A LLM só aparece no plano B, que é decisão do controlador, não daqui.

Depende do ``Recuperador`` **abstrato**, nunca de uma estratégia concreta: o produto injeta a
configuração que venceu a comparação (híbrida + reranker) e a via científica segue intocada.

Sem piso de score
-----------------
O ``ChatbotRAG`` precisa de um piso de score porque aceita pergunta livre: qualquer assunto entra,
inclusive fora do escopo, e o piso é o que barra. Aqui o portão é **a gramática**: só chega
consulta de intenção reconhecida, e a consulta canônica dessa intenção foi escrita por nós
apontando para um assunto que conferimos existir no Manual. Fora de escopo não chega até aqui —
não casa regra nenhuma e o controlador manda para o plano B.

Ainda assim a busca pode voltar vazia (corpus trocado, termo sem casamento). Nesse caso a
resposta vem com ``trechos`` vazio e ``encontrou`` falso; o que fazer é decisão do controlador.

A resposta traz o chunk inteiro (rastreabilidade) **e** um ``destaque``: a frase do chunk que
de fato responde. Sem isso a resposta começaria no meio do assunto anterior, porque o chunk é
uma janela de tamanho fixo, não um parágrafo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..corpus.chunking import Chunk
from ..retrieval.base import Recuperador
from ..retrieval.esparsa import tokenizar
from .semantico import Consulta

# Fim de frase: ponto/!/? seguido de espaço. Heurística simples de propósito — abreviação
# ("art. 178") não quebra porque o dígito vem colado, e o custo de um corte errado é um
# destaque um pouco maior, não uma resposta errada.
_FIM_DE_FRASE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class RespostaNucleo:
    """O que o núcleo respondeu: a consulta executada e os trechos do Manual que a respondem."""

    consulta: Consulta
    trechos: tuple[Chunk, ...]
    destaque: str  # a frase do 1º trecho que responde — o que se mostra ao aluno

    @property
    def encontrou(self) -> bool:
        return bool(self.trechos)


def destacar(texto: str, consulta: str) -> str:
    """A frase do trecho com maior sobreposição de termos com a consulta.

    O chunk tem ~180 tokens e quase sempre começa no meio de outro assunto: mostrá-lo inteiro
    ao aluno é ruim de ler e parece resposta errada. Esta é a versão sem IA de "extrair a
    resposta do trecho" — determinística e conferível, ao contrário da síntese do LLM.

    Usa o tokenizador do BM25 de propósito: o destaque é pontuado pela mesma noção de termo
    que escolheu o trecho, então destacar não pode discordar de recuperar.
    """
    frases = [frase for frase in _FIM_DE_FRASE.split(texto) if frase.strip()]
    if not frases:
        return texto.strip()
    termos = set(tokenizar(consulta))
    # max devolve a primeira em caso de empate: ordem do documento, resultado estável.
    return max(frases, key=lambda frase: len(termos & set(tokenizar(frase)))).strip()


class BaseConhecimento:
    """Liga a consulta canônica ao Manual, pela estratégia de recuperação que receber."""

    def __init__(
        self,
        recuperador: Recuperador,
        chunks: list[Chunk],
        top_k: int = 3,
    ) -> None:
        self._recuperador = recuperador
        self._por_id = {chunk.id: chunk for chunk in chunks}
        self._top_k = top_k

    def consultar(self, consulta: Consulta) -> RespostaNucleo:
        """Busca no Manual pelo texto canônico da consulta — nunca pela frase do aluno."""
        resultados = self._recuperador.buscar(consulta.texto, self._top_k)
        trechos = tuple(self._por_id[resultado.chunk_id] for resultado in resultados)
        destaque = destacar(trechos[0].texto, consulta.texto) if trechos else ""
        return RespostaNucleo(consulta, trechos, destaque)
