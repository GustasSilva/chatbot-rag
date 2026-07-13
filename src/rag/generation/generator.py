"""Interface do gerador de respostas (Q3 / Marco 3).

O núcleo científico (Q1/Q2) usa só métricas de recuperação e NÃO depende do LLM. A
geração entra apenas no artefato de demonstração (Marco 3), com um LLM fixo e temperatura
0 para reprodutibilidade (protocolo §3). O backend concreto (Claude API, local, ...) será
escolhido e implementado quando o Marco 3 chegar — por isso aqui há só o contrato.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..config import ConfigGeracao
from ..corpus.chunking import Chunk


@dataclass(frozen=True)
class RespostaGerada:
    texto: str
    fontes: list[int]  # ids dos chunks citados como fonte


class Gerador(ABC):
    """Gera a resposta final a partir da pergunta e dos chunks recuperados."""

    @abstractmethod
    def gerar(self, pergunta: str, contextos: list[Chunk]) -> RespostaGerada:
        raise NotImplementedError


class GeradorNaoConfigurado(Gerador):
    """Placeholder explícito: falha alto se alguém tentar gerar sem backend configurado."""

    def gerar(self, pergunta: str, contextos: list[Chunk]) -> RespostaGerada:
        raise NotImplementedError(
            "Nenhum gerador configurado. Defina geracao.backend no config.yaml "
            "(ex.: 'ollama') e use GeradorOllama."
        )


_SISTEMA = (
    "Você é um assistente que responde perguntas SOMENTE com base nos trechos fornecidos. "
    "Se a resposta não estiver nos trechos, responda exatamente: "
    "'Não encontrei essa informação nos documentos.' "
    "Cite a(s) fonte(s) usada(s) indicando o número do trecho entre colchetes, por exemplo [1]. "
    "Responda em português, de forma concisa e objetiva."
)
# Captura números de citação em [1], [1, 2], [1,2] etc. (vários dígitos por colchete).
_CITACAO = re.compile(r"\[([\d,\s]+)\]")


def extrair_fontes_citadas(texto: str, contextos: list[Chunk]) -> list[int]:
    """Mapeia os [n] citados na resposta de volta para os ids de chunk do contexto.

    Aceita ``[1]``, ``[1, 2]`` e ``[1,2]``; ignora números fora do intervalo dos trechos.
    """
    citados = {
        int(num)
        for grupo in _CITACAO.findall(texto)
        for num in re.findall(r"\d+", grupo)
    }
    return [contextos[n - 1].id for n in sorted(citados) if 1 <= n <= len(contextos)]


class GeradorOllama(Gerador):
    """Gerador local via Ollama (LLM fixo, temperatura 0 para reprodutibilidade).

    Monta um prompt com os trechos recuperados numerados (cada um rotulado com o documento
    de origem), instrui o modelo a responder só a partir deles e a citar a fonte pelo número.
    As fontes citadas são mapeadas de volta para os ids de chunk.
    """

    def __init__(
        self,
        modelo: str,
        host: str = "http://localhost:11434",
        temperatura: float = 0.0,
        timeout_s: int = 120,
    ) -> None:
        self.modelo = modelo
        self.host = host.rstrip("/")
        self.temperatura = temperatura
        self.timeout_s = timeout_s

    @classmethod
    def de_config(cls, cfg: ConfigGeracao, usar_fallback: bool = False) -> "GeradorOllama":
        modelo = cfg.modelo_fallback if usar_fallback else cfg.modelo
        if not modelo:
            raise ValueError("config.geracao sem modelo definido")
        return cls(modelo=modelo, host=cfg.host, temperatura=cfg.temperatura,
                   timeout_s=cfg.timeout_s)

    def gerar(self, pergunta: str, contextos: list[Chunk]) -> RespostaGerada:
        if not contextos:
            return RespostaGerada("Não encontrei essa informação nos documentos.", [])

        blocos = [
            f"[{i}] (fonte: {c.doc_id}) {c.texto}" for i, c in enumerate(contextos, start=1)
        ]
        conteudo = "Trechos:\n" + "\n\n".join(blocos) + f"\n\nPergunta: {pergunta}\nResposta:"
        resposta = self._chamar(_SISTEMA, conteudo)
        fontes = extrair_fontes_citadas(resposta, contextos)
        return RespostaGerada(texto=resposta.strip(), fontes=fontes)

    def _chamar(self, sistema: str, usuario: str) -> str:
        payload = {
            "model": self.modelo,
            "messages": [
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            "stream": False,
            "options": {"temperature": self.temperatura},
        }
        req = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as erro:
            raise RuntimeError(
                f"Falha ao chamar o Ollama em {self.host} (servidor no ar? modelo "
                f"'{self.modelo}' baixado?): {erro}"
            ) from erro
        return dados["message"]["content"]
