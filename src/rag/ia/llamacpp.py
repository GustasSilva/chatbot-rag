"""Gerador local via ``llama-cpp-python`` com decodificação restrita por gramática.

É a **intervenção de compiladores** do trabalho: em vez de apenas *pedir* no prompt que o
modelo cite a fonte (o que o Ollama faz, e que às vezes falha), aqui a saída é *restringida*
na própria decodificação por um autômato (ver ``gramatica.py``). Implementa o mesmo contrato
``Gerador`` do backend Ollama, então pluga no ``ChatbotRAG`` sem tocar em nada da recuperação.

Instalação (com CUDA já presente na máquina):

    set CMAKE_ARGS=-DGGML_CUDA=on
    pip install llama-cpp-python

e aponte ``geracao.caminho_modelo_gguf`` (no ``config.yaml``) para o GGUF do Llama 3.1 8B Q4.
A ``llama_cpp`` é importada de forma preguiçosa: este módulo pode ser importado (e o autômato,
testado) sem a lib instalada.
"""
from __future__ import annotations

from ..corpus.chunking import Chunk
from .generator import (
    PERFIS_SISTEMA,
    RECUSA_PADRAO,
    Gerador,
    RespostaGerada,
    Turno,
    extrair_fontes_citadas,
)
from .gramatica_citacao import AutomatoCitacao, RestritorCitacao, token_eh_especial
from .json_estruturado import SISTEMA_JSON, construir_gbnf, validar


class GeradorLlamaCpp(Gerador):
    """Gera com o GGUF em processo, com a saída restringida por gramática (a intervenção).

    Dois modos:

    - ``modo="citacao"`` (Estágio 1): restringe o formato de citação ``[n]`` por um AFD feito à
      mão (``restringir_citacao`` liga/desliga; ``exigir_citacao`` obriga ao menos uma citação).
      É o usado pelo experimento ``exp_gramatica``.
    - ``modo="json"`` (Estágio 2): força a saída ao objeto ``{"resposta": ..., "fontes": [...]}``
      por uma gramática livre de contexto (GBNF), com os índices restritos a ``1..K``. ``gerar``
      devolve um ``RespostaGerada`` normal (texto = ``resposta``, fontes = ids de chunk), então é
      **drop-in** no ``ChatbotRAG`` do produto.

    Em ambos, o caminho de recusa não passa pela gramática (contexto vazio devolve a recusa direto).
    """

    def __init__(
        self,
        caminho_modelo: str,
        *,
        perfil: str = "institucional",
        temperatura: float = 0.0,
        n_ctx: int = 4096,
        n_gpu_layers: int = -1,  # -1 = todas as camadas na GPU (usa a CUDA já instalada)
        max_tokens: int = 512,
        modo: str = "citacao",  # "citacao" (Estágio 1, AFD [n]) | "json" (Estágio 2, GBNF)
        restringir_citacao: bool = True,
        exigir_citacao: bool = True,
        verbose: bool = False,
    ) -> None:
        if perfil not in PERFIS_SISTEMA:
            raise ValueError(f"perfil de guardrail desconhecido: {perfil}")
        if modo not in {"citacao", "json"}:
            raise ValueError(f"modo desconhecido: {modo} (use 'citacao' ou 'json')")
        try:
            from llama_cpp import Llama
        except ImportError as erro:  # pragma: no cover - depende de build externo
            raise RuntimeError(
                "llama-cpp-python não está instalado. Instale com CUDA "
                "(CMAKE_ARGS=-DGGML_CUDA=on pip install llama-cpp-python) para usar este backend."
            ) from erro

        self._sistema = PERFIS_SISTEMA[perfil]
        self.temperatura = temperatura
        self.max_tokens = max_tokens
        self.modo = modo
        self.restringir_citacao = restringir_citacao
        self.exigir_citacao = exigir_citacao
        self._llm = Llama(
            model_path=caminho_modelo, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers, verbose=verbose
        )
        self._vocab, self._ids_especiais, self._ids_parada = self._mapear_vocabulario()
        # Último restritor usado (expõe contadores passos/intervencoes para o experimento).
        self.ultimo_restritor: RestritorCitacao | None = None

    @classmethod
    def de_config(cls, cfg, perfil: str | None = None) -> "GeradorLlamaCpp":
        """Constrói a partir de ``config.geracao`` (campos do llama-cpp são opcionais no YAML)."""
        caminho = getattr(cfg, "caminho_modelo_gguf", None)
        if not caminho:
            raise ValueError("config.geracao.caminho_modelo_gguf não definido")
        return cls(
            caminho_modelo=caminho,
            perfil=perfil or cfg.perfil_guardrail,
            temperatura=cfg.temperatura,
            n_ctx=getattr(cfg, "n_ctx", 4096),
            n_gpu_layers=getattr(cfg, "n_gpu_layers", -1),
            restringir_citacao=getattr(cfg, "restringir_citacao", True),
        )

    # Tokens de fim de geração a bloquear enquanto não houver citação. O Llama 3 tem dois; os
    # demais cobrem outras famílias de modelo. token_eos() é somado a este conjunto.
    _ALVOS_PARADA = frozenset({"<|eot_id|>", "<|end_of_text|>", "</s>", "<|endoftext|>"})

    def _mapear_vocabulario(self) -> tuple[dict[int, str], set[int], set[int]]:
        """Pré-computa (id -> texto), os ids "especiais" (``[``/``]``/dígito) e os de parada.

        Feito uma única vez: o ``RestritorCitacao`` só varre os especiais no caminho quente. Os
        tokens de parada têm texto normal vazio, então são detectados via ``detokenize(special=True)``.
        """
        vocab: dict[int, str] = {}
        especiais: set[int] = set()
        ids_parada: set[int] = {self._llm.token_eos()}
        for tid in range(self._llm.n_vocab()):
            texto = self._llm.detokenize([tid]).decode("utf-8", "ignore")
            vocab[tid] = texto
            if token_eh_especial(texto):
                especiais.add(tid)
            elif not texto:  # candidatos a token de controle (texto normal vazio)
                especial = self._llm.detokenize([tid], special=True).decode("utf-8", "ignore")
                if especial in self._ALVOS_PARADA:
                    ids_parada.add(tid)
        return vocab, especiais, ids_parada

    def gerar(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None = None
    ) -> RespostaGerada:
        if not contextos:
            return RespostaGerada(RECUSA_PADRAO, [])
        if self.modo == "json":
            return self._gerar_estruturado(pergunta, contextos, historico)
        return self._gerar_citacao(pergunta, contextos, historico)

    def _gerar_estruturado(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None
    ) -> RespostaGerada:
        """Modo JSON: gera o objeto restrito por gramática e o converte em ``RespostaGerada``.

        Mapeia os índices ``1..K`` do campo ``fontes`` para os ids de chunk do contexto. A gramática
        garante um JSON válido no esquema; o ``if not ok`` é apenas defensivo.
        """
        raw = self.gerar_json(pergunta, contextos, historico=historico, usar_gramatica=True)
        ok, dados, _ = validar(raw, len(contextos))
        if not ok:
            return RespostaGerada(texto=raw, fontes=[])
        fontes = [contextos[n - 1].id for n in dados["fontes"] if 1 <= n <= len(contextos)]
        return RespostaGerada(texto=dados["resposta"], fontes=fontes)

    def _gerar_citacao(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None
    ) -> RespostaGerada:
        mensagens = self._montar_mensagens(pergunta, contextos, historico)
        processadores = None
        if self.restringir_citacao:
            from llama_cpp import LogitsProcessorList

            automato = AutomatoCitacao(
                num_fontes=len(contextos), exigir_citacao=self.exigir_citacao
            )
            restritor = RestritorCitacao(
                automato, self._vocab, self._ids_especiais, self._ids_parada
            )
            self.ultimo_restritor = restritor
            processadores = LogitsProcessorList([restritor])

        saida = self._llm.create_chat_completion(
            messages=mensagens,
            temperature=self.temperatura,
            max_tokens=self.max_tokens,
            logits_processor=processadores,
        )
        texto = saida["choices"][0]["message"]["content"].strip()
        fontes = extrair_fontes_citadas(texto, contextos)
        return RespostaGerada(texto=texto, fontes=fontes)

    def gerar_json(
        self,
        pergunta: str,
        contextos: list[Chunk],
        historico: list[Turno] | None = None,
        usar_gramatica: bool = True,
    ) -> str:
        """Gera a resposta como JSON estruturado (Estágio 2) e devolve o texto bruto.

        ``usar_gramatica=True`` força o esquema via o motor de gramática da llama.cpp (JSON válido
        por construção); ``False`` é o baseline (mesmo prompt, sem restrição) — a única diferença
        entre os dois, para a comparação ser justa. A validação fica a cargo de quem chama
        (``json_estruturado.validar``), sobre a string crua.
        """
        blocos = [
            f"[{i}] (fonte: {c.doc_id}) {c.texto}" for i, c in enumerate(contextos, start=1)
        ]
        conteudo = "Trechos:\n" + "\n\n".join(blocos) + f"\n\nPergunta: {pergunta}\nResponda em JSON:"
        mensagens = [{"role": "system", "content": SISTEMA_JSON}]
        for pergunta_ant, resposta_ant in historico or []:
            mensagens.append({"role": "user", "content": pergunta_ant})
            mensagens.append({"role": "assistant", "content": resposta_ant})
        mensagens.append({"role": "user", "content": conteudo})
        extra = {}
        if usar_gramatica:
            from llama_cpp import LlamaGrammar

            extra["grammar"] = LlamaGrammar.from_string(
                construir_gbnf(len(contextos)), verbose=False
            )
        saida = self._llm.create_chat_completion(
            messages=mensagens, temperature=self.temperatura, max_tokens=self.max_tokens, **extra
        )
        return saida["choices"][0]["message"]["content"].strip()

    def _montar_mensagens(
        self, pergunta: str, contextos: list[Chunk], historico: list[Turno] | None
    ) -> list[dict]:
        """Monta [system, ...histórico, user] no mesmo formato do backend Ollama."""
        blocos = [
            f"[{i}] (fonte: {c.doc_id}) {c.texto}" for i, c in enumerate(contextos, start=1)
        ]
        conteudo = "Trechos:\n" + "\n\n".join(blocos) + f"\n\nPergunta: {pergunta}\nResposta:"
        mensagens = [{"role": "system", "content": self._sistema}]
        for pergunta_ant, resposta_ant in historico or []:
            mensagens.append({"role": "user", "content": pergunta_ant})
            mensagens.append({"role": "assistant", "content": resposta_ant})
        mensagens.append({"role": "user", "content": conteudo})
        return mensagens
