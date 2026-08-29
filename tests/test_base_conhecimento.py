"""Testes da base de conhecimento — inclusive o caminho completo do núcleo, sem LLM."""
from __future__ import annotations

from rag.corpus import Chunk
from rag.compilador.base_conhecimento import BaseConhecimento, destacar
from rag.compilador.intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL
from rag.compilador.lexico import AnalisadorLexico
from rag.compilador.semantico import Consulta
from rag.compilador.sintatico import AnalisadorSintatico
from rag.recuperacao import Recuperador, Resultado
from rag.recuperacao import RecuperadorBM25

# Corpus minúsculo no estilo do Manual: BM25 é determinístico e não baixa modelo nenhum.
CORPUS = [
    Chunk(0, "manual", "A frequência obrigatória, em cada disciplina, é de 75% das aulas "
                       "dadas e demais atividades programadas.", 0, 100, 0),
    Chunk(1, "manual", "O trancamento de matrícula é a interrupção temporária das atividades "
                       "escolares, concedido pelo prazo de até dois anos.", 100, 200, 1),
    Chunk(2, "manual", "O cancelamento de matrícula pode ser solicitado junto à Secretaria, "
                       "a qualquer tempo, quitando as mensalidades vencidas.", 200, 300, 2),
]


class RecuperadorEspiao(Recuperador):
    """Registra o que recebeu e devolve uma ordem fixa — isola a base do recuperador real."""

    nome = "espiao"

    def __init__(self, ids: list[int]) -> None:
        self.ids = ids
        self.consultas: list[str] = []
        self.ks: list[int] = []

    def buscar(self, consulta: str, k: int) -> list[Resultado]:
        self.consultas.append(consulta)
        self.ks.append(k)
        return [Resultado(i, posicao, 1.0) for posicao, i in enumerate(self.ids[:k])]


def test_busca_pelo_texto_canonico_e_nao_pela_frase_do_aluno():
    """O contrato central do desenho: o recuperador nunca vê a redação do aluno."""
    espiao = RecuperadorEspiao([1])
    base = BaseConhecimento(espiao, CORPUS)

    base.consultar(Consulta("definicao_trancamento", "trancamento de matrícula", {}))

    assert espiao.consultas == ["trancamento de matrícula"]


def test_devolve_os_trechos_na_ordem_do_recuperador():
    base = BaseConhecimento(RecuperadorEspiao([2, 0]), CORPUS)
    resposta = base.consultar(Consulta("x", "consulta", {}))
    assert [t.id for t in resposta.trechos] == [2, 0]
    assert resposta.encontrou


def test_top_k_e_repassado_ao_recuperador():
    espiao = RecuperadorEspiao([0, 1, 2])
    BaseConhecimento(espiao, CORPUS, top_k=2).consultar(Consulta("x", "consulta", {}))
    assert espiao.ks == [2]


def test_busca_vazia_devolve_resposta_sem_trecho():
    """Não é erro: o controlador decide o que fazer (plano B, ou avisar que não achou)."""
    resposta = BaseConhecimento(RecuperadorEspiao([]), CORPUS).consultar(
        Consulta("x", "consulta", {})
    )
    assert resposta.trechos == () and not resposta.encontrou


def test_destaque_escolhe_a_frase_que_responde():
    """O chunk é uma janela de tamanho fixo; a frase certa pode estar no meio dele."""
    texto = (
        "novo processo seletivo. Trancamento De Matrícula É a interrupção temporária das "
        "atividades escolares. A carteira de estudante é pessoal e intransferível."
    )
    assert destacar(texto, "trancamento de matrícula, interrupção temporária") == (
        "Trancamento De Matrícula É a interrupção temporária das atividades escolares."
    )


def test_destaque_vazio_quando_nada_foi_encontrado():
    resposta = BaseConhecimento(RecuperadorEspiao([]), CORPUS).consultar(
        Consulta("x", "consulta", {})
    )
    assert resposta.destaque == ""


def test_nucleo_responde_de_ponta_a_ponta_sem_llm():
    """Pergunta do aluno -> léxico -> parser -> semântico -> Manual, sem modelo no caminho."""
    lexer = AnalisadorLexico(LEXICO_MANUAL)
    parser = AnalisadorSintatico(GRAMATICA_MANUAL)
    base = BaseConhecimento(RecuperadorBM25(CORPUS), CORPUS, top_k=1)

    casos = {
        "poxa, quantas faltas eu posso ter em cálculo?": 0,
        "o que é trancamento de matrícula?": 1,
        "como solicito o cancelamento da matrícula?": 2,
    }
    for pergunta, chunk_esperado in casos.items():
        consulta = SEMANTICA_MANUAL.analisar(parser.analisar(lexer.analisar(pergunta)))
        resposta = base.consultar(consulta)
        assert [t.id for t in resposta.trechos] == [chunk_esperado], pergunta
