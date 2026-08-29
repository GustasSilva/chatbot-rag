"""Testes da análise sintática: tokens -> intenção, por casamento de ilha."""
from __future__ import annotations

from rag.compilador.gramatica import Gramatica
from rag.compilador.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL
from rag.compilador.lexico import AnalisadorLexico, Lexico, TipoToken
from rag.compilador.sintatico import AnalisadorSintatico

LEXICO_FALSO = Lexico.de_grupos(
    grupos={
        "QUANTIDADE": ["quantas"],
        "FALTA": ["faltas"],
        "DISCIPLINA": ["disciplina"],
        "COMO": ["como"],
        "TRANCAR": ["trancar"],
        "NEGACAO": ["não"],
        "MATRICULA": ["matrícula"],
    },
    ruido=["de", "eu", "na"],
)
GRAMATICA_FALSA = Gramatica.de_notacao(
    {
        "limite_faltas": "QUANTIDADE FALTA DISCIPLINA?",
        "trancamento": "TRANCAR",
        "como_trancar": "COMO TRANCAR",
    },
    LEXICO_FALSO,
)
GRAMATICA_NEGACAO = Gramatica.de_notacao(
    {
        "sem_trancar": "COMO NEGACAO+TRANCAR",
        "sem_matricula": "COMO NEGACAO+MATRICULA",
        "com_trancar": "COMO TRANCAR !NEGACAO",
    },
    LEXICO_FALSO,
)

LEXER = AnalisadorLexico(LEXICO_FALSO)
PARSER = AnalisadorSintatico(GRAMATICA_FALSA)


def reconhecer(pergunta: str, lexer=LEXER, parser=PARSER):
    return parser.analisar(lexer.analisar(pergunta))


def test_casa_regra_com_opcional_ausente():
    resultado = reconhecer("quantas faltas")
    assert resultado is not None and resultado.intencao == "limite_faltas"
    assert [t.valor for t in resultado.casados] == ["QUANTIDADE", "FALTA"]


def test_casa_regra_com_opcional_presente():
    resultado = reconhecer("quantas faltas na disciplina")
    assert [t.valor for t in resultado.casados] == ["QUANTIDADE", "FALTA", "DISCIPLINA"]


def test_ignora_o_que_nao_faz_parte_da_regra():
    """Casamento por ilha: o resto da frase é pulado e fica na sobra."""
    resultado = reconhecer("quantas faltas eu posso ter em cálculo")
    assert resultado.intencao == "limite_faltas"
    assert [t.valor for t in resultado.sobra] == ["posso", "ter", "em", "calculo"]
    assert all(t.tipo is TipoToken.DESCONHECIDO for t in resultado.sobra)


def test_ordem_dos_elementos_importa():
    assert reconhecer("faltas quantas") is None


def test_duas_perguntas_dao_duas_intencoes():
    """``pergunta := regra+``: cada intenção é reconhecida no que a anterior não consumiu."""
    tokens = LEXER.analisar("quantas faltas e como trancar")
    assert [r.intencao for r in PARSER.analisar_todas(tokens)] == [
        "limite_faltas",
        "como_trancar",
    ]


def test_pergunta_simples_nao_inventa_segunda_intencao():
    tokens = LEXER.analisar("quantas faltas na disciplina")
    assert [r.intencao for r in PARSER.analisar_todas(tokens)] == ["limite_faltas"]


def test_simbolo_repetido_nao_alimenta_intencao_extra():
    """Duas palavras que dão o MESMO símbolo são uma menção só, não duas perguntas.

    Sem isso, "trancar trancamento" reconhecia trancamento duas vezes: consumir um símbolo
    leva junto as outras ocorrências dele (``docs/decisoes.md`` §22).
    """
    tokens = LEXER.analisar("trancar trancar")
    assert [r.intencao for r in PARSER.analisar_todas(tokens)] == ["trancamento"]


def test_teto_limita_quantas_intencoes_saem():
    tokens = LEXER.analisar("quantas faltas e como trancar")
    assert len(PARSER.analisar_todas(tokens, maximo=1)) == 1


def test_analisar_devolve_a_mesma_intencao_principal():
    """``analisar`` continua sendo o primeiro de ``analisar_todas``: nada mudou para quem só
    quer a intenção principal."""
    for pergunta in ["quantas faltas", "como trancar", "quantas faltas e como trancar"]:
        tokens = LEXER.analisar(pergunta)
        assert PARSER.analisar(tokens).intencao == PARSER.analisar_todas(tokens)[0].intencao


def test_sem_regra_que_case_devolve_none():
    """O sinal de que a pergunta tem de ir para o plano B."""
    assert reconhecer("bandejão feriado") is None


def test_desempate_fica_com_a_regra_mais_especifica():
    """"trancamento" e "como_trancar" casam; vence a de mais símbolos obrigatórios."""
    resultado = reconhecer("como trancar")
    assert resultado.intencao == "como_trancar"

    assert reconhecer("trancar").intencao == "trancamento"  # sozinha, a genérica vale


def test_guloso_pega_a_ocorrencia_mais_a_esquerda():
    resultado = reconhecer("faltas quantas faltas")
    assert [t.inicio for t in resultado.casados] == [7, 15]  # "quantas" e a 2ª "faltas"
    assert [t.inicio for t in resultado.sobra] == [0]        # a 1ª "faltas" sobrou


def test_adjacencia_prende_a_negacao_ao_que_ela_nega():
    """"como não trancar a matrícula": o "não" nega TRANCAR, não MATRICULA."""
    parser = AnalisadorSintatico(GRAMATICA_NEGACAO)
    resultado = reconhecer("como não trancar a matrícula", parser=parser)
    assert resultado.intencao == "sem_trancar"

    # Sem símbolo entre os dois, a outra regra é que casa.
    assert reconhecer("como não matrícula", parser=parser).intencao == "sem_matricula"


def test_adjacencia_ignora_palavra_desconhecida_no_meio():
    """Adjacência é no fluxo de símbolos: "fizer" não é símbolo, então não separa os dois."""
    parser = AnalisadorSintatico(GRAMATICA_NEGACAO)
    assert reconhecer("como não fizer matrícula", parser=parser).intencao == "sem_matricula"


def test_exclusao_descarta_a_regra_quando_o_simbolo_proibido_aparece():
    parser = AnalisadorSintatico(GRAMATICA_NEGACAO)
    assert reconhecer("como trancar", parser=parser).intencao == "com_trancar"
    # Com a negação presente, com_trancar sai de cena e sobra a regra do "não trancar".
    assert reconhecer("como não trancar", parser=parser).intencao == "sem_trancar"


def test_perguntas_reais_do_goldset():
    lexer = AnalisadorLexico(LEXICO_MANUAL)
    parser = AnalisadorSintatico(GRAMATICA_MANUAL)
    casos = {
        "O que é o trancamento de matrícula?": "definicao_trancamento",
        "Por quanto tempo o trancamento de matrícula pode ser concedido?": "prazo_trancamento",
        "Como o aluno solicita o cancelamento de matrícula?": "como_cancelar",
        "Qual é o percentual mínimo de frequência obrigatória em cada disciplina?":
            "limite_faltas",
        # Casam três regras: limite_faltas ("limite ... ausências"), abono_falta_atleta e
        # limite_atleta. Vence a mais específica pelos 4 obrigatórios — sem isso, a resposta
        # vinha da regra geral de frequência, que é outro trecho do Manual.
        "Até que limite o aluno-atleta pode ter as ausências compensadas?": "limite_atleta",
        "As faltas do aluno-atleta são abonadas?": "abono_falta_atleta",
    }
    for pergunta, esperada in casos.items():
        assert reconhecer(pergunta, lexer, parser).intencao == esperada

    # Fora do escopo da gramática: vai para o plano B em vez de casar errado.
    assert reconhecer("O bandejão abre no feriado?", lexer, parser) is None
