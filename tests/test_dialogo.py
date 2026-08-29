"""Testes do controlador: quem responde o quê, e o que acontece com a IA desligada."""
from __future__ import annotations

from rag.corpus import Chunk
from rag.ia import RespostaGerada
from rag.compilador.base_conhecimento import BaseConhecimento
from rag.compilador.dialogo import NAO_ENTENDI, Dialogo, Origem
from rag.recuperacao import RecuperadorBM25

CORPUS = [
    Chunk(0, "manual", "A frequência obrigatória, em cada disciplina, é de 75% das aulas "
                       "dadas e demais atividades programadas.", 0, 100, 0),
    Chunk(1, "manual", "O trancamento de matrícula é a interrupção temporária das atividades "
                       "escolares.", 100, 200, 1),
]


class PlanoBEspiao:
    """Substitui o ChatbotRAG: registra as perguntas que chegaram até a LLM."""

    def __init__(self) -> None:
        self.perguntas: list[str] = []
        self.historicos: list[list[tuple[str, str]] | None] = []

    def responder(self, pergunta: str, historico=None) -> RespostaGerada:
        self.perguntas.append(pergunta)
        self.historicos.append(historico)
        return RespostaGerada("resposta do plano B", [1], [CORPUS[1]])


def montar(plano_b=None, corpus=CORPUS) -> Dialogo:
    return Dialogo.de_manual(BaseConhecimento(RecuperadorBM25(corpus), corpus, top_k=1), plano_b)


def test_pergunta_reconhecida_e_respondida_pelo_nucleo():_ = None


def test_duas_perguntas_recebem_duas_respostas():
    """Uma resposta por intenção, na ordem em que o aluno perguntou."""
    dialogo = montar()
    resposta = dialogo.responder(
        "quantas faltas posso ter e o que é trancamento de matrícula"
    )
    assert resposta.origem is Origem.NUCLEO
    assert len(resposta.intencoes) == 2
    assert len(resposta.texto.split("\n\n")) == 2
    assert resposta.intencoes == ("limite_faltas", "definicao_trancamento")
    assert len(resposta.fontes) == 2, "uma fonte por intenção respondida"


def test_pergunta_reconhecida_e_respondida_pelo_nucleo():
    resposta = montar().responder("poxa, quantas faltas eu posso ter?")
    assert resposta.origem is Origem.NUCLEO
    assert resposta.intencoes == ("limite_faltas",)
    assert "75%" in resposta.texto
    assert [t.id for t in resposta.trechos] == [0]
    assert resposta.fontes == (0,)  # o trecho que embasa a resposta, para a interface marcar


def test_historico_vai_para_o_plano_b_e_nao_para_o_nucleo():
    """Multi-turn continua funcionando: o follow-up elíptico não casa regra e cai no plano B."""
    espiao = PlanoBEspiao()
    dialogo = montar(espiao)
    historico = [("qual o limite de faltas?", "75% das aulas")]

    dialogo.responder("o que é o trancamento de matrícula?", historico=historico)
    assert espiao.historicos == []  # núcleo respondeu sozinho, sem estado

    dialogo.responder("e para as presenciais?", historico=historico)
    assert espiao.historicos == [historico]


def test_plano_b_nao_e_chamado_quando_o_nucleo_responde():
    """A IA não entra no caminho do que a gramática já cobre."""
    espiao = PlanoBEspiao()
    montar(espiao).responder("o que é o trancamento de matrícula?")
    assert espiao.perguntas == []


def test_pergunta_fora_da_gramatica_vai_para_o_plano_b():
    espiao = PlanoBEspiao()
    resposta = montar(espiao).responder("o bandejão abre no feriado?")
    assert resposta.origem is Origem.PLANO_B
    assert resposta.texto == "resposta do plano B"
    assert espiao.perguntas == ["o bandejão abre no feriado?"]


def test_sem_plano_b_o_nucleo_responde_o_que_conhece_e_avisa_o_resto():
    """A demonstração de que o núcleo é o compilador: com a IA desligada, ele segue de pé."""
    dialogo = montar(plano_b=None)

    reconhecida = dialogo.responder("o que é o trancamento de matrícula?")
    assert reconhecida.origem is Origem.NUCLEO
    assert "interrupção temporária" in reconhecida.texto

    desconhecida = dialogo.responder("o bandejão abre no feriado?")
    assert desconhecida.origem is Origem.NAO_ENTENDIDA
    assert desconhecida.texto == NAO_ENTENDI
    assert desconhecida.trechos == ()


def test_intencao_reconhecida_sem_trecho_cai_no_plano_b():
    """Corpus que não cobre o assunto: a pergunta é do domínio, deixar a LLM tentar é melhor."""
    vazio = [Chunk(0, "manual", "texto sem relação alguma com a pergunta", 0, 40, 0)]
    espiao = PlanoBEspiao()
    dialogo = Dialogo.de_manual(
        BaseConhecimento(RecuperadorBM25(vazio), vazio, top_k=1), espiao
    )

    resposta = dialogo.responder("o que é o trancamento de matrícula?")
    assert resposta.origem is Origem.PLANO_B
