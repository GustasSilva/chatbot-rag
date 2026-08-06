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


# Frase de recusa canônica: emitida no caminho sem contexto e pelo piso de score do
# reranker (chatbot). Também é o que o prompt manda o LLM responder quando o assunto não
# está nos trechos — mantê-la única evita divergência entre os pontos de recusa.
RECUSA_PADRAO = "Não encontrei essa informação nos documentos."


@dataclass(frozen=True)
class RespostaGerada:
    texto: str
    fontes: list[int]  # ids dos chunks citados como fonte


# Histórico de conversa: turnos anteriores como (pergunta do usuário, resposta dada).
Turno = tuple[str, str]


class Gerador(ABC):
    """Gera a resposta final a partir da pergunta e dos chunks recuperados."""

    @abstractmethod
    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        raise NotImplementedError

    def reescrever_consulta(self, pergunta: str, historico: list[Turno]) -> str:
        """Reescreve a pergunta como autônoma usando o histórico (para a recuperação).

        Default: devolve a pergunta sem mudança — geradores sem LLM (ou sem suporte a
        conversa) não reescrevem. ``GeradorOllama`` sobrescreve com a reescrita via LLM.
        """
        return pergunta


class GeradorNaoConfigurado(Gerador):
    """Placeholder explícito: falha alto se alguém tentar gerar sem backend configurado."""

    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        raise NotImplementedError(
            "Nenhum gerador configurado. Defina geracao.backend no config.yaml "
            "(ex.: 'ollama') e use GeradorOllama."
        )


# Dois perfis de guardrail. O ESTRITO (saúde/demonstração científica) recusa a menos que a
# resposta esteja literalmente nos trechos — prioriza não errar em domínio de risco. O
# INSTITUCIONAL (produto sobre o Manual, menor risco) é mais brando: permite sintetizar a
# partir dos trechos e só recusa quando o assunto realmente não é tratado — evita o
# over-refusal (recusar mesmo com o trecho certo recuperado).
_SISTEMA_ESTRITO = (
    "Você é um assistente que responde perguntas SOMENTE com base nos trechos fornecidos. "
    "Se a resposta não estiver nos trechos, responda exatamente: "
    "'Não encontrei essa informação nos documentos.' "
    "Cite a(s) fonte(s) usada(s) indicando o número do trecho entre colchetes, por exemplo [1]. "
    "Responda em português, de forma concisa e objetiva."
)
_SISTEMA_INSTITUCIONAL = (
    "Você é um assistente sobre o Manual do Aluno. Responda com base nos trechos fornecidos, "
    "podendo sintetizar e inferir a partir do que eles dizem — desde que a resposta se apoie "
    "neles. Não invente dados (datas, números, prazos) que não estejam nos trechos. "
    "Só responda 'Não encontrei essa informação nos documentos.' se os trechos realmente não "
    "tratarem do assunto perguntado. "
    "Combine os trechos em UMA resposta única e coesa; não escreva um parágrafo por trecho nem "
    "repita a mesma informação. "
    "Cite a(s) fonte(s) usada(s) indicando o número do trecho entre colchetes, por exemplo [1]. "
    "Responda em português, de forma clara e objetiva."
)
PERFIS_SISTEMA = {"estrito": _SISTEMA_ESTRITO, "institucional": _SISTEMA_INSTITUCIONAL}

# Reescrita de pergunta para conversa multi-turn: condensa histórico + pergunta numa
# pergunta autônoma, para a RECUPERAÇÃO funcionar em follow-ups elípticos ("e as presenciais?").
_SISTEMA_REESCRITA = (
    "Dada a conversa e a última pergunta do usuário, reescreva essa pergunta como uma pergunta "
    "AUTÔNOMA e completa em português, resolvendo referências (ex.: 'e as presenciais?', 'isso', "
    "'ele') com base no histórico. Responda APENAS com a pergunta reescrita, sem explicações. "
    "Se a pergunta já for autônoma, repita-a sem mudanças."
)
# Nota: uma variante "ancorada" (âncora de atribuição p/ o erro n14) foi testada e REJEITADA —
# não corrigiu n14 e regrediu o over-refusal (recusas 1→5 nas 50). Ver scripts/exp_prompt_n14.py.

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
        perfil: str = "estrito",
    ) -> None:
        if perfil not in PERFIS_SISTEMA:
            raise ValueError(f"perfil de guardrail desconhecido: {perfil}")
        self.modelo = modelo
        self.host = host.rstrip("/")
        self.temperatura = temperatura
        self.timeout_s = timeout_s
        self.perfil = perfil
        self._sistema = PERFIS_SISTEMA[perfil]

    @classmethod
    def de_config(
        cls, cfg: ConfigGeracao, usar_fallback: bool = False, perfil: str | None = None
    ) -> "GeradorOllama":
        modelo = cfg.modelo_fallback if usar_fallback else cfg.modelo
        if not modelo:
            raise ValueError("config.geracao sem modelo definido")
        return cls(modelo=modelo, host=cfg.host, temperatura=cfg.temperatura,
                   timeout_s=cfg.timeout_s, perfil=perfil or cfg.perfil_guardrail)

    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        if not contextos:
            return RespostaGerada(RECUSA_PADRAO, [])

        blocos = [
            f"[{i}] (fonte: {c.doc_id}) {c.texto}" for i, c in enumerate(contextos, start=1)
        ]
        conteudo = "Trechos:\n" + "\n\n".join(blocos) + f"\n\nPergunta: {pergunta}\nResposta:"
        # Sem histórico: mensagens = [system, user] — idêntico ao comportamento de turno único.
        mensagens = [{"role": "system", "content": self._sistema}]
        mensagens += self._mensagens_historico(historico)
        mensagens.append({"role": "user", "content": conteudo})
        resposta = self._chamar(mensagens)
        fontes = extrair_fontes_citadas(resposta, contextos)
        return RespostaGerada(texto=resposta.strip(), fontes=fontes)

    def reescrever_consulta(self, pergunta: str, historico: list[Turno]) -> str:
        if not historico:
            return pergunta
        mensagens = [{"role": "system", "content": _SISTEMA_REESCRITA}]
        mensagens += self._mensagens_historico(historico)
        mensagens.append({"role": "user", "content": f"Pergunta a reescrever: {pergunta}"})
        return self._chamar(mensagens).strip() or pergunta

    @staticmethod
    def _mensagens_historico(historico: list[Turno] | None) -> list[dict]:
        """Converte os turnos anteriores em mensagens user/assistant para o chat do Ollama."""
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
