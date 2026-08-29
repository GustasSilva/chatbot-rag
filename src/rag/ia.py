"""O plano B do assistente: recuperação alimentando um modelo de linguagem local.

Só entra quando o pacote ``compilador`` não reconhece a pergunta. Traz o contrato ``Gerador``,
o backend Ollama (modelo fixo, temperatura 0, para o comportamento ser reprodutível) e o
``ChatbotRAG``, que liga a recuperação à geração.

O **piso de score** do reranker é o guardrail: recusa a pergunta fora de escopo antes de gastar
uma chamada ao modelo (``docs/decisoes.md`` §11).
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .apresentacao import RECUSA, eh_saudacao, resposta_saudacao
from .config import Config
from .corpus import Chunk
from .recuperacao import Recuperador

# Turnos anteriores da conversa: (pergunta, resposta).
Turno = tuple[str, str]

_SISTEMA = (
    "Você é um assistente sobre o Manual do Aluno. Responda com base nos trechos fornecidos, "
    "podendo sintetizar e inferir a partir do que eles dizem — desde que a resposta se apoie "
    "neles. Não invente dados (datas, números, prazos) que não estejam nos trechos. "
    f"Só responda '{RECUSA}' se os trechos realmente não "
    "tratarem do assunto perguntado. "
    "Combine os trechos em UMA resposta única e coesa; não escreva um parágrafo por trecho nem "
    "repita a mesma informação. "
    "Cite a(s) fonte(s) usada(s) indicando o número do trecho entre colchetes, por exemplo [1]. "
    "Responda em português, de forma clara e objetiva."
)

# Condensa histórico + pergunta numa pergunta autônoma, para a RECUPERAÇÃO funcionar em
# follow-ups elípticos ("e as presenciais?").
_SISTEMA_REESCRITA = (
    "Dada a conversa e a última pergunta do usuário, reescreva essa pergunta como uma pergunta "
    "AUTÔNOMA e completa em português, resolvendo referências (ex.: 'e as presenciais?', 'isso', "
    "'ele') com base no histórico. Responda APENAS com a pergunta reescrita, sem explicações. "
    "Se a pergunta já for autônoma, repita-a sem mudanças."
)

# Números de citação em [1], [1, 2], [1,2].
_CITACAO = re.compile(r"\[([\d,\s]+)\]")


@dataclass(frozen=True)
class RespostaGerada:
    """A resposta do plano B: o texto, quem a embasou e tudo que foi consultado."""

    texto: str
    fontes: list[int]                                   # ids dos chunks citados
    trechos: list[Chunk] = field(default_factory=list)  # tudo que foi recuperado


def extrair_fontes_citadas(texto: str, contextos: list[Chunk]) -> list[int]:
    """Mapeia os ``[n]`` citados na resposta de volta para os ids de chunk do contexto."""
    citados = {
        int(num)
        for grupo in _CITACAO.findall(texto)
        for num in re.findall(r"\d+", grupo)
    }
    return [contextos[n - 1].id for n in sorted(citados) if 1 <= n <= len(contextos)]


class Gerador(ABC):
    """Gera a resposta final a partir da pergunta e dos chunks recuperados."""

    @abstractmethod
    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        raise NotImplementedError

    def reescrever_consulta(self, pergunta: str, historico: list[Turno]) -> str:
        """Reescreve a pergunta como autônoma. Sem LLM, devolve a pergunta como veio."""
        return pergunta


class GeradorOllama(Gerador):
    """Gerador local via Ollama, com os trechos numerados no prompt e a fonte citada por número."""

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
    def de_config(cls, cfg: Config) -> "GeradorOllama":
        return cls(cfg.modelo_llm, cfg.host_ollama, cfg.temperatura, cfg.timeout_s)

    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        if not contextos:
            return RespostaGerada(RECUSA, [])

        blocos = [
            f"[{i}] (fonte: {c.doc_id}) {c.texto}" for i, c in enumerate(contextos, start=1)
        ]
        conteudo = "Trechos:\n" + "\n\n".join(blocos) + f"\n\nPergunta: {pergunta}\nResposta:"
        mensagens = [{"role": "system", "content": _SISTEMA}]
        mensagens += self._mensagens_historico(historico)
        mensagens.append({"role": "user", "content": conteudo})
        resposta = self._chamar(mensagens)
        fontes = extrair_fontes_citadas(resposta, contextos)
        return RespostaGerada(resposta.strip(), fontes, contextos)

    def reescrever_consulta(self, pergunta: str, historico: list[Turno]) -> str:
        if not historico:
            return pergunta
        mensagens = [{"role": "system", "content": _SISTEMA_REESCRITA}]
        mensagens += self._mensagens_historico(historico)
        mensagens.append({"role": "user", "content": f"Pergunta a reescrever: {pergunta}"})
        return self._chamar(mensagens).strip() or pergunta

    @staticmethod
    def _mensagens_historico(historico: list[Turno] | None) -> list[dict]:
        mensagens: list[dict] = []
        for pergunta_ant, resposta_ant in historico or []:
            mensagens.append({"role": "user", "content": pergunta_ant})
            mensagens.append({"role": "assistant", "content": resposta_ant})
        return mensagens

    def _chamar(self, mensagens: list[dict]) -> str:
        payload = {
            "model": self.modelo,
            "messages": mensagens,
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


class ChatbotRAG:
    """Recuperação e geração, com o piso de score do reranker como guardrail.

    ``saudar`` liga a resposta amigável a saudações puras; desligado por padrão, para a medição
    não mudar de comportamento.
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
    ) -> RespostaGerada:
        if self._saudar and eh_saudacao(pergunta):
            return RespostaGerada(resposta_saudacao(), [])

        consulta = self._gerador.reescrever_consulta(pergunta, historico) if historico else pergunta
        resultados = self._recuperador.buscar(consulta, self._top_k)
        if self._piso_score is not None and (
            not resultados or resultados[0].score < self._piso_score
        ):
            return RespostaGerada(RECUSA, [])
        contextos = [self._por_id[r.chunk_id] for r in resultados]
        return self._gerador.gerar(pergunta, contextos, historico=historico)
