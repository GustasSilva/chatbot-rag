"""Gramática regular do formato de citação ``[n]`` e o autômato que a reconhece.

Parte da decodificação restrita, hoje resultado preliminar do trabalho (ver ``llamacpp.py``). É
**puro Python** (o autômato) + numpy (só a máscara), independente da LLM e da ``llama_cpp`` —
por isso é testável isoladamente (ver ``tests/test_gramatica_citacao.py``).

A ideia, na cadeia clássica *gramática → autômato → tradução*:

- **Gramática (regular).** A resposta é texto livre no qual toda ocorrência de ``[`` abre uma
  citação bem-formada ``[n]``, com ``n`` inteiro em ``1..K`` (``K`` = nº de trechos no
  contexto), e a geração só pode terminar depois de ao menos uma citação válida.
- **Autômato (AFD).** Reconhecemos essa linguagem com um autômato finito determinístico. O
  número é casado por um *autômato de prefixos* sobre o conjunto finito ``{"1", ..., "K"}``,
  o que elimina becos sem saída por construção (todo prefixo válido alcança um número válido).
- **Tradução (máscara).** Na decodificação, o AFD diz, a cada passo, quais caracteres — logo,
  quais *tokens* — mantêm a saída dentro da linguagem; os demais têm o logit posto em ``-inf``.

O passo seguinte, **já implementado** em ``json_estruturado.py``, troca a gramática regular
por uma **livre de contexto** (saída JSON), que exige **pilha**, um autômato de pilha, para
casar colchetes e chaves aninhados.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import numpy as np


class Modo(Enum):
    TEXTO = auto()   # fora de citação, acumulando texto livre
    NUMERO = auto()  # depois de '[', casando os dígitos do número da citação


@dataclass(frozen=True)
class Estado:
    modo: Modo
    numero: str        # dígitos já lidos dentro do colchete atual ("" fora de citação)
    viu_citacao: bool  # já fechou ao menos uma citação válida?


DIGITOS = frozenset("0123456789")
ABRE = "["
FECHA = "]"
# Chars que a gramática trata de forma especial; todo o resto é "texto neutro" (sempre
# permitido em TEXTO, sempre inválido dentro de um número).
ESPECIAIS = frozenset("[]0123456789")


def token_eh_especial(texto: str) -> bool:
    """True se o texto do token contém algum caractere que a gramática trata (``[``, ``]``, dígito)."""
    return any(c in ESPECIAIS for c in texto)


class AutomatoCitacao:
    """AFD: reconhece "texto com citações ``[n]`` bem-formadas (``n`` em ``1..K``), >= 1 citação".

    ``num_fontes`` = ``K``, o nº de trechos disponíveis no contexto — uma citação ``[n]`` só é
    válida se ``1 <= n <= K``. ``exigir_citacao`` controla se a geração é obrigada a citar antes
    de terminar (desligue no caminho de recusa, que legitimamente não cita).
    """

    def __init__(self, num_fontes: int, exigir_citacao: bool = True) -> None:
        if num_fontes < 1:
            raise ValueError("num_fontes deve ser >= 1")
        self.num_fontes = num_fontes
        self.exigir_citacao = exigir_citacao
        # Números válidos e todos os seus prefixos não-vazios. O autômato de prefixos garante
        # que, uma vez dentro de um número, sempre há continuação até um número válido.
        self._validos = frozenset(str(i) for i in range(1, num_fontes + 1))
        self._prefixos = frozenset(
            v[:i] for v in self._validos for i in range(1, len(v) + 1)
        )

    def inicial(self) -> Estado:
        return Estado(Modo.TEXTO, "", False)

    def transicao(self, estado: Estado, ch: str) -> Estado | None:
        """Aplica um caractere. Devolve o novo estado, ou ``None`` se o caractere é inválido aqui."""
        if estado.modo is Modo.TEXTO:
            if ch == ABRE:
                return Estado(Modo.NUMERO, "", estado.viu_citacao)
            if ch == FECHA:
                return None  # ']' solto, sem '[' aberto -> malformado
            return estado  # qualquer outro caractere: texto livre, estado inalterado
        # modo NUMERO
        if ch in DIGITOS:
            candidato = estado.numero + ch
            if candidato in self._prefixos:
                return Estado(Modo.NUMERO, candidato, estado.viu_citacao)
            return None  # dígito que não leva a nenhum número válido (ex.: '9' com K=3)
        if ch == FECHA:
            if estado.numero in self._validos:
                return Estado(Modo.TEXTO, "", True)  # citação válida fechada
            return None  # ']' cedo demais ("[" sem dígito) ou número incompleto
        return None  # dentro do número só valem dígitos ou ']'

    def aceita_fim(self, estado: Estado) -> bool:
        """A geração só pode terminar em texto (não no meio de citação) e após >= 1 citação."""
        return estado.modo is Modo.TEXTO and (estado.viu_citacao or not self.exigir_citacao)

    def rodar(self, estado: Estado, texto: str) -> Estado | None:
        """Aplica uma cadeia inteira; devolve ``None`` assim que algum caractere for rejeitado."""
        atual: Estado | None = estado
        for ch in texto:
            atual = self.transicao(atual, ch)
            if atual is None:
                return None
        return atual


def tokens_permitidos(
    automato: AutomatoCitacao,
    estado: Estado,
    vocab_texto: dict[int, str],
    ids_parada: set[int],
) -> set[int]:
    """Implementação de referência (simples e O(vocab)): ids cujo texto mantém a saída válida.

    Usada nos testes como padrão-ouro contra o qual a máscara otimizada do ``RestritorCitacao``
    é comparada. Os tokens de parada (``ids_parada``: fim de geração — ``<|eot_id|>``,
    ``<|end_of_text|>`` etc.) são permitidos sse o autômato aceita o fim em ``estado``.
    """
    permitidos: set[int] = set()
    pode_parar = automato.aceita_fim(estado)
    for tid, texto in vocab_texto.items():
        if tid in ids_parada:
            if pode_parar:
                permitidos.add(tid)
            continue
        if texto and automato.rodar(estado, texto) is not None:
            permitidos.add(tid)
    return permitidos


class RestritorCitacao:
    """``logits_processor`` da llama-cpp: mascara os logits para manter a saída na gramática.

    Mantém o estado do AFD ao longo da geração (avança um token por passo). A cada chamada,
    os tokens que levariam o autômato a um estado inválido têm o logit posto em ``-inf`` (prob.
    zero após o softmax). Otimização: em ``TEXTO``, os tokens *neutros* são sempre válidos, então
    só precisamos checar os *especiais*; dentro de um número, ocorre o inverso. O resultado é
    idêntico ao de ``tokens_permitidos`` (verificado em teste), mas sem varrer o vocabulário todo.

    Recebe ``vocab_texto`` (id -> texto do token), ``ids_especiais`` (subconjunto cujo texto
    contém ``[``, ``]`` ou dígito) e ``ids_parada`` (tokens de fim de geração — o Llama 3 tem
    mais de um: ``<|eot_id|>`` e ``<|end_of_text|>``), todos pré-computados uma vez pelo gerador.
    Os tokens de parada só são liberados quando o autômato aceita o fim (ou seja, após citar).
    """

    def __init__(
        self,
        automato: AutomatoCitacao,
        vocab_texto: dict[int, str],
        ids_especiais: set[int],
        ids_parada: set[int],
    ) -> None:
        self._automato = automato
        self._vocab = vocab_texto
        self._especiais = ids_especiais
        self._ids_parada = ids_parada
        self._estado = automato.inicial()
        self._prompt_len: int | None = None
        self._consumidos = 0  # tokens gerados já aplicados ao autômato
        # Instrumentação (para o experimento): mede o quanto a restrição de fato atua.
        self.passos = 0        # nº de posições geradas (chamadas de máscara)
        self.intervencoes = 0  # nº de vezes que a máscara bloqueou o token de maior logit

    def __call__(self, input_ids, scores):
        self._avancar(input_ids)
        return self._mascarar(scores)

    def _avancar(self, input_ids) -> None:
        """Atualiza o estado do AFD com os tokens gerados desde a última chamada."""
        if self._prompt_len is None:
            self._prompt_len = len(input_ids)  # 1ª chamada: só o prompt, nada gerado ainda
        gerados = input_ids[self._prompt_len:]
        while self._consumidos < len(gerados):
            tid = int(gerados[self._consumidos])
            proximo = self._automato.rodar(self._estado, self._vocab.get(tid, ""))
            if proximo is not None:  # se None, a máscara anterior falhou — preserva o estado
                self._estado = proximo
            self._consumidos += 1

    def _mascarar(self, scores):
        estado = self._estado
        escolha_livre = int(np.argmax(scores))  # o que o modelo escolheria sem a restrição
        if estado.modo is Modo.TEXTO:
            pode_parar = self._automato.aceita_fim(estado)
            # Lever de citação forçada: se o modelo tenta PARAR sem ter citado, a máscara não
            # só barra a parada — ela restringe a saída aos tokens que ABREM ou COMPLETAM uma
            # citação, empurrando o modelo para um [n] em vez de deixá-lo divagar até o limite.
            if not pode_parar and escolha_livre in self._ids_parada:
                resultado = self._forcar_citacao(scores, estado)
            else:
                # Neutros são todos válidos; zera os especiais inválidos e, se ainda não é
                # possível parar (sem citação), todos os tokens de fim de geração.
                if not pode_parar:
                    for tid in self._ids_parada:
                        scores[tid] = -np.inf
                for tid in self._especiais:
                    if self._automato.rodar(estado, self._vocab[tid]) is None:
                        scores[tid] = -np.inf
                resultado = scores
        else:
            # Dentro de um número: só alguns especiais (dígitos/']') valem; tudo mais é inválido.
            resultado = np.full_like(scores, -np.inf)
            for tid in self._especiais:
                if self._automato.rodar(estado, self._vocab[tid]) is not None:
                    resultado[tid] = scores[tid]
        self.passos += 1
        if not np.isfinite(resultado[escolha_livre]):
            self.intervencoes += 1  # a máscara barrou o token que o modelo teria escolhido
        return resultado

    def _forcar_citacao(self, scores, estado):
        """Libera só os tokens que abrem ('[') ou completam ('[n]') uma citação a partir de ``estado``.

        Se nenhum token conseguir abrir citação (salvaguarda contra máscara vazia), devolve os
        ``scores`` sem alteração para não gerar NaN na amostragem.
        """
        resultado = np.full_like(scores, -np.inf)
        for tid in self._especiais:
            proximo = self._automato.rodar(estado, self._vocab[tid])
            if proximo is not None and (proximo.modo is Modo.NUMERO or proximo.viu_citacao):
                resultado[tid] = scores[tid]
        return resultado if np.isfinite(resultado).any() else scores
