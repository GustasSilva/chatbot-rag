"""Gold-set INSTITUCIONAL ampliado (produto: assistente do Manual do Aluno).

~50 perguntas em linguagem de aluno real (não a linguagem formal do documento), cobrindo
bem as seções do Manual. Reusa os 18 trechos já validados do gold-set do Marco 1 e adiciona
~32 novos. Cada trecho-fonte é substring EXATO do Manual (validado por count()).

Diferente do gold-set científico (Recall@k): este sustenta a métrica de ACURÁCIA DE RESPOSTA
do produto (contém a info certa? cita a fonte certa?).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.goldset import ItemGold, carregar_goldset, construir_relevancia, salvar_goldset
from rag.pipeline import construir_indice

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
GOLD_MARCO1 = "data/goldsets/manual_aluno.json"
CAMINHO_GOLD = "data/goldsets/institucional.json"
DOC = "manual"

# Novos itens (id, pergunta natural, resposta, trecho_fonte exato).
NOVOS = [
    ("n01", "Se eu tirar menos de 7 na média, o que acontece?",
     "Você é submetido a um exame.", "Se MS for menor que 7,0 (sete), o aluno será submetido a um exame"),
    ("n02", "Depois do exame, quanto preciso para ser aprovado?",
     "Média final igual ou maior que 5,0.", "Se MF for igual ou maior que 5,0 (cinco)"),
    ("n03", "Quando estou aprovado sem exame, qual é a minha média final?",
     "A média final é igual à MS.", "o aluno estará aprovado com média final igual a MS"),
    ("n04", "Como é a matrícula de quem acabou de entrar na faculdade?",
     "Automaticamente no regime de progressão tutelada.",
     "será matriculado automaticamente no regime de progressão tutelada"),
    ("n05", "Posso fazer a prova de exame a lápis?",
     "Não; o exame a lápis fica com nota zero.",
     "o exame redigido a lápis não será considerado, ficando o aluno com nota zero"),
    ("n06", "O que é o estágio não obrigatório?",
     "Atividade opcional, à escolha do estudante.",
     "O Estágio Não Obrigatório é aquele realizado como atividade opcional, à escolha do estudante"),
    ("n07", "Onde encontro vaga de estágio não obrigatório?",
     "Recorrendo aos Agentes de Integração.", "poderão recorrer aos Agentes de Integração"),
    ("n08", "Quem faz licenciatura precisa fazer estágio?",
     "Sim; é o Estágio Curricular Supervisionado, obrigatório para docência.",
     "O Estágio Curricular Supervisionado é obrigatório para a formação de docentes"),
    ("n09", "O que acontece se eu não fizer a matrícula no começo do semestre?",
     "É considerado abandono de curso.",
     "A não efetivação da matrícula no início de cada semestre, dentro dos prazos estabelecidos no Calendário Escolar da UNIP, representa abandono de curso"),
    ("n10", "A matrícula pode ser renovada em outro campus ou turno?",
     "Sim, pode ser determinada para campus/turno diferente.",
     "a renovação da matrícula do aluno poderá ser determinada para um campus ou turno diferente daquele frequentado no semestre anterior"),
    ("n11", "A faculdade pode passar minhas informações para os meus pais?",
     "Não sem autorização; o aluno maior de 18 tem direito à privacidade.",
     "É garantido ao aluno (maior de 18 anos ou emancipado) o direito à privacidade"),
    ("n12", "O que é o FIES?",
     "Financiamento federal para estudantes com poucos recursos.",
     "para financiar os estudos de alunos com poucos recursos"),
    ("n13", "Existe algum programa para ex-alunos?",
     "Sim, o IAP.", "aproximar da instituição os estudantes que estão saindo da universidade, bem como os egressos"),
    ("n14", "De quem é a responsabilidade de controlar as faltas?",
     "Do próprio aluno.", "É de responsabilidade do aluno fazer controle de suas faltas"),
    ("n15", "Preciso participar da colação de grau para me formar?",
     "Sim; sem ela não é considerado formado nem tem direito ao diploma.",
     "O aluno que não participar da colação de grau oficial não será considerado formado e, portanto, não terá direito ao diploma"),
    ("n16", "Aluna grávida tem direito a afastamento?",
     "Sim, a partir do oitavo mês e por três meses.",
     "a partir do oitavo mês de gravidez e durante três meses"),
    ("n17", "Faltar por causa do serviço militar conta como falta?",
     "Não; há abono para serviço militar obrigatório.",
     "O abono é concedido, por força de lei, somente ao aluno que esteja prestando serviço militar obrigatório"),
    ("n18", "Como faço uma solicitação para a universidade?",
     "Por requerimento próprio, na Secretaria ou Secretaria On-line.",
     "Qualquer solicitação à Universidade e seus órgãos dar-se-á por meio de requerimento próprio"),
    ("n19", "Onde vejo a resposta do meu requerimento?",
     "Na Sala de Atendimento ao Aluno.",
     "O aluno deverá verificar a resposta à sua solicitação na Sala de Atendimento ao Aluno"),
    ("n20", "O diploma da UNIP é digital?",
     "Sim, diploma digital de graduação.",
     "A UNIP confere aos seus alunos diploma digital de graduação de nível superior"),
    ("n21", "Preciso da carteirinha para entrar na faculdade?",
     "Sim; a carteirinha digital é o documento de identidade do aluno.",
     "A carteirinha digital é o documento de identidade do aluno"),
    ("n22", "Quais são as punições disciplinares?",
     "Advertência, suspensão e dispensa por justa causa.",
     "I - Advertência; II - Suspensão; III - Dispensa por justa causa"),
    ("n23", "Posso adiantar uma disciplina?",
     "Sim, por antecipação de disciplina, no mesmo turno.",
     "a antecipação de disciplina(s), no mesmo turno em que estiver matriculado"),
    ("n24", "O aluno monitor pode dar aula ou corrigir prova?",
     "Não; é vedado ao monitor ministrar aulas ou corrigir provas.",
     "É vedado ao aluno monitor ministrar aulas, corrigir trabalhos ou provas, substituir o professor"),
    ("n25", "As faltas do aluno-atleta são abonadas?",
     "Não; elas não se caracterizam como falta.",
     "Não há, no caso, abono de faltas, visto que estas não se caracterizam"),
    ("n26", "Como é avaliada uma disciplina cursada em adaptação?",
     "Com critérios idênticos aos das demais disciplinas.",
     "em regime de adaptação, com critérios de avaliação e promoção idênticos às demais disciplinas"),
    ("n27", "Posso digitar meus trabalhos nos computadores da biblioteca?",
     "Não; os equipamentos são só para pesquisa acadêmica.",
     "objetivando apenas pesquisas acadêmicas, não sendo permitida a digitação de trabalhos"),
    ("n28", "Quantas vezes posso agendar a prova on-line por disciplina?",
     "Um único agendamento por disciplina.",
     "o aluno poderá efetuar um único agendamento por disciplina"),
    ("n29", "Preciso estar regular para pedir transferência?",
     "Sim; situação regular é pressuposto.",
     "considerando como pressuposto a situação regular do aluno perante a UNIP"),
    ("n30", "Para colar grau preciso estar regular no ENADE?",
     "Sim, quando for o caso.", "estejam em situação regular junto ao ENADE"),
    ("n31", "Como funciona o empréstimo de equipamentos?",
     "Pela ordem de precedência das reservas e disponibilidade.",
     "O empréstimo de equipamentos obedecerá, rigorosamente, à ordem de precedência das reservas"),
    ("n32", "O que acontece se eu tirar menos de 5 na média final?",
     "Não é aprovado (aprovação exige MF >= 5,0).", "Se MF for igual ou maior que 5,0 (cinco)"),
]


def main() -> int:
    cfg = carregar_config()
    corpus = carregar_pdf(CAMINHO_PDF)

    # 18 do Marco 1 (trechos já validados) + novos.
    itens = list(carregar_goldset(GOLD_MARCO1))
    for i, p, r, t in NOVOS:
        itens.append(ItemGold(id=i, pergunta=p, resposta=r, trecho_fonte=t, doc_id=DOC))

    faltando = [it.id for it in itens if corpus.count(it.trecho_fonte) == 0]
    if faltando:
        print("ERRO: trechos não encontrados:", faltando)
        for it in itens:
            if it.id in faltando:
                print(f"  {it.id}: «{it.trecho_fonte[:70]}»")
        return 1

    indice = construir_indice({DOC: corpus}, cfg, calcular_densa=False)
    construir_relevancia(itens, indice.chunks, indice.textos_doc, cfg.recuperacao.limiar_relevancia)

    salvar_goldset(itens, CAMINHO_GOLD, corpus="institucional")
    ids = [it.id for it in itens]
    assert len(ids) == len(set(ids)), "ids duplicados"
    print(f"OK — {len(itens)} perguntas ({len(itens)-len(NOVOS)} reusadas + {len(NOVOS)} novas) "
          f"salvas em {CAMINHO_GOLD} | {len(indice.chunks)} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
