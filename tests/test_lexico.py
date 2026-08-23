"""Testes da análise léxica (fase 1 do front-end de compilador), sem modelo nem corpus."""
from __future__ import annotations

import pytest

from rag.compilador.intencoes import LEXICO_MANUAL
from rag.compilador.lexico import AnalisadorLexico, Lexico, TipoToken, normalizar, simbolos

# Léxico mínimo e isolado: os testes de mecanismo não devem quebrar quando o vocabulário
# do Manual crescer (esse é testado à parte, no fim do arquivo).
LEXICO_FALSO = Lexico.de_grupos(
    grupos={
        "FALTA": ["falta", "faltas", "ausência", "ausências"],
        "QUANTIDADE": ["quantas", "limite"],
    },
    ruido=["o", "de", "eu", "poxa"],
)
ANALISADOR = AnalisadorLexico(LEXICO_FALSO)


def test_normaliza_caixa_e_acento():
    assert normalizar("Ausências") == "ausencias"
    assert normalizar("MATRÍCULA") == "matricula"


def test_sinonimos_viram_o_mesmo_simbolo():
    """O ponto da fase léxica: a variação de escrita do aluno morre aqui."""
    for escrita in ("falta", "Faltas", "ausência", "AUSÊNCIAS"):
        (token,) = ANALISADOR.analisar(escrita)
        assert token.tipo is TipoToken.PALAVRA_CHAVE
        assert token.valor == "FALTA"


def test_ruido_descartado_por_padrao_e_visivel_sob_demanda():
    assert simbolos(ANALISADOR.analisar("poxa, quantas faltas eu")) == ["QUANTIDADE", "FALTA"]

    tipos = [t.tipo for t in ANALISADOR.analisar("poxa, quantas faltas eu", descartar_ruido=False)]
    assert tipos == [
        TipoToken.RUIDO,
        TipoToken.PALAVRA_CHAVE,
        TipoToken.PALAVRA_CHAVE,
        TipoToken.RUIDO,
    ]


def test_numero_vira_token_numero():
    (token,) = ANALISADOR.analisar("25")
    assert token.tipo is TipoToken.NUMERO and token.valor == "25"


def test_palavra_fora_do_lexico_vira_desconhecido():
    """Não é ruído: pode ser o valor de um campo (o nome da disciplina, por exemplo)."""
    (token,) = ANALISADOR.analisar("Cálculo")
    assert token.tipo is TipoToken.DESCONHECIDO
    assert token.valor == "calculo"


def test_preserva_lexema_e_posicao_do_original():
    """A fase sintática precisa disso para dizer ONDE não entendeu a pergunta."""
    (token,) = ANALISADOR.analisar("  Faltas!")
    assert token.lexema == "Faltas" and token.inicio == 2


def test_pontuacao_nao_gera_token():
    assert len(ANALISADOR.analisar("faltas???  ...")) == 1


def test_variante_ambigua_falha_alto():
    with pytest.raises(ValueError, match="ambigua"):
        Lexico.de_grupos({"A": ["prova"], "B": ["Prova"]}, ruido=[])


def test_palavra_como_ruido_e_variante_falha_alto():
    with pytest.raises(ValueError, match="ruido"):
        Lexico.de_grupos({"FALTA": ["falta"]}, ruido=["falta"])


def test_exemplo_do_plano_com_o_lexico_do_manual():
    """A pergunta usada como exemplo no desenho da arquitetura."""
    analisador = AnalisadorLexico(LEXICO_MANUAL)
    tokens = analisador.analisar("poxa, quantas faltas eu posso ter em cálculo?")

    assert simbolos(tokens) == ["QUANTIDADE", "FALTA", "PODER"]
    desconhecidos = [t.valor for t in tokens if t.tipo is TipoToken.DESCONHECIDO]
    assert desconhecidos == ["calculo"]  # sobra para virar o campo `disciplina`


def test_perguntas_reais_do_goldset_reduzem_aos_simbolos_certos():
    analisador = AnalisadorLexico(LEXICO_MANUAL)
    casos = {
        "O que é o trancamento de matrícula?": ["QUE", "TRANCAR", "MATRICULA"],
        "Qual a penalidade por atraso na devolução de material da biblioteca?":
            ["QUAL", "PENALIDADE", "EMPRESTIMO", "BIBLIOTECA"],
        "Como o aluno solicita o cancelamento de matrícula?":
            ["COMO", "ALUNO", "REQUERIMENTO", "CANCELAR", "MATRICULA"],
    }
    for pergunta, esperado in casos.items():
        assert simbolos(analisador.analisar(pergunta)) == esperado
