"""Testes do núcleo de CC da decodificação restrita (autômato + máscara), sem LLM."""
from __future__ import annotations

import numpy as np

from rag.ia.gramatica_citacao import (
    AutomatoCitacao,
    RestritorCitacao,
    tokens_permitidos,
)

# Vocabulário falso: cobre texto neutro, dígitos, colchetes e citações inteiras num só token.
VOCAB = {
    0: "",        # EOS
    1: "Olá",
    2: " mundo",
    3: "[",
    4: "1",
    5: "2",
    6: "3",
    7: "]",
    8: "[1]",
    9: "[3]",
    10: " ",
}
IDS_PARADA = {0}  # id 0 = token de fim de geração no vocab falso
ESPECIAIS = {tid for tid, txt in VOCAB.items() if any(c in "[]0123456789" for c in txt)}


def test_reconhece_citacao_valida():
    a = AutomatoCitacao(num_fontes=3)
    est = a.rodar(a.inicial(), "veja o trecho [2] para detalhes")
    assert est is not None and a.aceita_fim(est)


def test_rejeita_numero_fora_do_intervalo():
    a = AutomatoCitacao(num_fontes=3)
    assert a.rodar(a.inicial(), "[9]") is None
    assert a.rodar(a.inicial(), "[0]") is None


def test_rejeita_colchete_solto_e_incompleto():
    a = AutomatoCitacao(num_fontes=3)
    assert a.rodar(a.inicial(), "abc]") is None          # ']' sem '[' aberto
    est = a.rodar(a.inicial(), "abc [1")                 # aberto, sem fechar
    assert est is not None and not a.aceita_fim(est)     # não pode terminar no meio da citação


def test_exige_ao_menos_uma_citacao():
    estrito = AutomatoCitacao(num_fontes=2, exigir_citacao=True)
    assert not estrito.aceita_fim(estrito.rodar(estrito.inicial(), "resposta sem fonte"))
    livre = AutomatoCitacao(num_fontes=2, exigir_citacao=False)
    assert livre.aceita_fim(livre.rodar(livre.inicial(), "resposta sem fonte"))


def test_numero_de_dois_digitos_com_muitas_fontes():
    a = AutomatoCitacao(num_fontes=12)
    assert a.aceita_fim(a.rodar(a.inicial(), "ver [12]"))
    assert a.rodar(a.inicial(), "[13]") is None  # 13 > 12


def _indices_finitos(restritor: RestritorCitacao, ids: list[int], n_vocab: int) -> set[int]:
    scores = np.zeros(n_vocab, dtype=np.float32)
    scores[1] = 1.0  # token neutro ("Olá") como argmax -> NÃO dispara o lever de citação forçada
    saida = restritor(np.array(ids, dtype=np.intc), scores)
    return {i for i in range(n_vocab) if np.isfinite(saida[i])}


def test_lever_forca_citacao_ao_tentar_parar():
    """Se o modelo tenta PARAR (argmax = token de parada) sem citar, só sobram abridores de citação."""
    a = AutomatoCitacao(num_fontes=2)
    restritor = RestritorCitacao(a, VOCAB, ESPECIAIS, IDS_PARADA)
    n_vocab = max(VOCAB) + 1
    scores = np.zeros(n_vocab, dtype=np.float32)  # tudo 0 -> argmax = id 0 (token de parada)
    saida = restritor(np.array([500, 501], dtype=np.intc), scores)
    finitos = {i for i in range(n_vocab) if np.isfinite(saida[i])}
    assert finitos == {3, 8}  # só "[" (abre) e "[1]" (completa); "[3]" é inválido (3 > 2)
    assert restritor.intervencoes == 1  # a parada pretendida foi bloqueada


def test_mascara_otimizada_bate_com_a_referencia():
    """A máscara do RestritorCitacao deve ser idêntica ao padrão-ouro em cada estado."""
    a = AutomatoCitacao(num_fontes=2)
    restritor = RestritorCitacao(a, VOCAB, ESPECIAIS, IDS_PARADA)
    n_vocab = max(VOCAB) + 1
    prompt = [500, 501]  # ids fora do vocab falso: ficam na região do prompt, nunca decodificados
    gerados = [3, 4, 7]  # "[", "1", "]"  -> percorre TEXTO -> NUMERO -> TEXTO(viu citação)

    ids = list(prompt)
    texto = ""
    esperado = tokens_permitidos(a, a.rodar(a.inicial(), texto), VOCAB, IDS_PARADA)
    assert _indices_finitos(restritor, ids, n_vocab) == esperado
    for token in gerados:
        ids = ids + [token]
        texto += VOCAB[token]
        estado = a.rodar(a.inicial(), texto)
        assert _indices_finitos(restritor, ids, n_vocab) == tokens_permitidos(
            a, estado, VOCAB, IDS_PARADA
        )
