"""Testes da análise semântica: intenção reconhecida -> consulta canônica + campos."""
from __future__ import annotations

import pytest

from rag.compilador.gramatica import Gramatica
from rag.compilador.intencoes import (
    ACOES,
    GRAMATICA_MANUAL,
    LEXICO_MANUAL,
    SEMANTICA_MANUAL,
)
from rag.compilador.lexico import AnalisadorLexico, Lexico, TipoToken
from rag.compilador.semantico import Acao, AnalisadorSemantico, Campo
from rag.compilador.sintatico import AnalisadorSintatico

LEXICO_FALSO = Lexico.de_grupos(
    grupos={"QUANTIDADE": ["quantas"], "FALTA": ["faltas"], "DISCIPLINA": ["disciplina"]},
    ruido=["de", "em", "na", "eu"],
)
GRAMATICA_FALSA = Gramatica.de_notacao(
    {"limite_faltas": "QUANTIDADE FALTA DISCIPLINA?"}, LEXICO_FALSO
)
ACOES_FALSAS = {
    "limite_faltas": Acao(
        "frequência obrigatória em cada disciplina",
        campos=(Campo("disciplina", TipoToken.DESCONHECIDO),),
    )
}

LEXER = AnalisadorLexico(LEXICO_FALSO)
PARSER = AnalisadorSintatico(GRAMATICA_FALSA)
SEMANTICO = AnalisadorSemantico.de_tabela(ACOES_FALSAS, GRAMATICA_FALSA)


def consultar(pergunta: str):
    return SEMANTICO.analisar(PARSER.analisar(LEXER.analisar(pergunta)))


def test_produz_a_consulta_canonica_da_intencao():
    """A frase do aluno não vai ao recuperador; a consulta escrita por nós vai."""
    consulta = consultar("quantas faltas")
    assert consulta.intencao == "limite_faltas"
    assert consulta.texto == "frequência obrigatória em cada disciplina"


def test_preenche_campo_a_partir_da_sobra():
    assert consultar("quantas faltas em Cálculo").campos == {"disciplina": "Cálculo"}


def test_campo_ausente_nao_quebra():
    assert consultar("quantas faltas").campos == {}


def test_campo_nao_entra_na_consulta():
    """Decisão registrada: o nome da disciplina atrapalharia a busca no Manual."""
    consulta = consultar("quantas faltas em Cálculo")
    assert "Cálculo" not in consulta.texto
    assert consulta.campos["disciplina"] == "Cálculo"


def test_intencao_da_gramatica_sem_acao_falha_alto():
    with pytest.raises(ValueError, match="sem acao definida"):
        AnalisadorSemantico.de_tabela({}, GRAMATICA_FALSA)


def test_acao_orfa_falha_alto():
    with pytest.raises(ValueError, match="sem regra na gramatica"):
        AnalisadorSemantico.de_tabela(
            {**ACOES_FALSAS, "intencao_fantasma": Acao("nada")}, GRAMATICA_FALSA
        )


def test_pipeline_completa_em_pergunta_real_do_goldset():
    lexer = AnalisadorLexico(LEXICO_MANUAL)
    parser = AnalisadorSintatico(GRAMATICA_MANUAL)
    consulta = SEMANTICA_MANUAL.analisar(
        parser.analisar(lexer.analisar("Por quanto tempo o trancamento de matrícula é dado?"))
    )
    assert consulta.intencao == "prazo_trancamento"
    assert consulta.texto == ACOES["prazo_trancamento"].consulta
