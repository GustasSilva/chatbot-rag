"""Testes da gramática de intenções (fase 2): a notação compila e é conferida contra o léxico."""
from __future__ import annotations

import pytest

from rag.nlu.gramatica import Gramatica, compilar_elementos
from rag.nlu.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, REGRAS
from rag.nlu.lexico import Lexico

LEXICO_FALSO = Lexico.de_grupos(
    grupos={
        "QUANTIDADE": ["quantas"],
        "FALTA": ["faltas"],
        "DISCIPLINA": ["disciplina"],
        "PRAZO": ["prazo"],
    },
    ruido=["de"],
)


def test_compila_sequencia_com_opcional():
    elementos = compilar_elementos("QUANTIDADE FALTA DISCIPLINA?")
    assert [e.alternativas for e in elementos] == [{"QUANTIDADE"}, {"FALTA"}, {"DISCIPLINA"}]
    assert [e.opcional for e in elementos] == [False, False, True]


def test_compila_alternativa_como_um_unico_elemento():
    """"QUANTIDADE|PRAZO" é UMA posição da sequência que aceita dois símbolos."""
    (elemento,) = compilar_elementos("QUANTIDADE|PRAZO")
    assert elemento.alternativas == {"QUANTIDADE", "PRAZO"}
    assert not elemento.opcional


def test_obrigatorios_ignora_os_opcionais():
    regra = Gramatica.de_notacao(
        {"teste": "QUANTIDADE FALTA DISCIPLINA?"}, LEXICO_FALSO
    ).regras[0]
    assert regra.obrigatorios == 2  # o peso da regra no desempate entre intenções


@pytest.mark.parametrize("notacao", ["FALTA|", "|FALTA", "?", "FALTA ?"])
def test_elemento_malformado_falha_alto(notacao):
    with pytest.raises(ValueError, match="malformado"):
        compilar_elementos(notacao)


def test_simbolo_fora_do_lexico_falha_alto():
    """O análogo do identificador não declarado: a regra nunca casaria, e em silêncio."""
    with pytest.raises(ValueError, match="fora do lexico"):
        Gramatica.de_notacao({"teste": "QUANTIDADE BOLACHA"}, LEXICO_FALSO)


def test_simbolo_repetido_na_mesma_regra_falha_alto():
    """A condição que torna exato o casamento guloso da fase sintática (sem retrocesso)."""
    with pytest.raises(ValueError, match="repete simbolo"):
        Gramatica.de_notacao({"teste": "FALTA? FALTA"}, LEXICO_FALSO)


def test_regra_so_de_opcionais_falha_alto():
    with pytest.raises(ValueError, match="opcionais"):
        Gramatica.de_notacao({"teste": "FALTA? DISCIPLINA?"}, LEXICO_FALSO)


def test_gramatica_do_manual_compila_e_usa_o_lexico_do_manual():
    assert len(GRAMATICA_MANUAL.regras) == len(REGRAS)
    definidos = LEXICO_MANUAL.simbolos_definidos
    for regra in GRAMATICA_MANUAL.regras:
        assert regra.obrigatorios >= 1
        for elemento in regra.elementos:
            assert elemento.alternativas <= definidos


def test_definicao_e_procedimento_diferem_so_pelo_marcador():
    """O par sobre o mesmo assunto: quem separa "o que é" de "como faço" é o marcador."""
    por_intencao = {regra.intencao: regra for regra in GRAMATICA_MANUAL.regras}
    definicao = por_intencao["definicao_trancamento"].elementos
    procedimento = por_intencao["como_trancar"].elementos

    assert definicao[0].alternativas == {"QUE"}
    assert procedimento[0].alternativas == {"COMO"}
    assert definicao[1:] == procedimento[1:]
