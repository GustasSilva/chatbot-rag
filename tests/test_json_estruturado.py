"""Testes do validador de saída estruturada (puro, sem LLM)."""
from __future__ import annotations

from rag.ia.json_estruturado import construir_gbnf, validar


def test_json_valido():
    ok, obj, motivo = validar('{"resposta": "trancamento suspende os estudos", "fontes": [1, 2]}', 3)
    assert ok and obj["fontes"] == [1, 2], motivo


def test_preambulo_ou_cerca_invalida():
    # Casos típicos de baseline que a gramática elimina: texto antes ou cerca de markdown.
    assert not validar('Claro! Aqui esta: {"resposta": "x", "fontes": [1]}', 3)[0]
    assert not validar('```json\n{"resposta": "x", "fontes": [1]}\n```', 3)[0]


def test_fonte_fora_do_intervalo():
    assert not validar('{"resposta": "x", "fontes": [9]}', 3)[0]  # 9 > 3
    assert not validar('{"resposta": "x", "fontes": [0]}', 3)[0]  # 0 < 1


def test_fontes_vazio_ou_chaves_erradas():
    assert not validar('{"resposta": "x", "fontes": []}', 3)[0]          # precisa de >= 1
    assert not validar('{"resposta": "x"}', 3)[0]                        # falta 'fontes'
    assert not validar('{"resposta": "x", "fontes": [1], "extra": 1}', 3)[0]  # chave a mais


def test_tipos_errados():
    assert not validar('{"resposta": 10, "fontes": [1]}', 3)[0]     # resposta nao-string
    assert not validar('{"resposta": "x", "fontes": [true]}', 3)[0]  # bool nao conta como int


def test_gbnf_restringe_fontes_a_faixa():
    gbnf = construir_gbnf(5)
    assert 'fonte  ::= "1" | "2" | "3" | "4" | "5"' in gbnf  # só 1..5, nada de "6"/"13"
    assert '"6"' not in gbnf
    assert "resposta" in gbnf and "fontes" in gbnf
