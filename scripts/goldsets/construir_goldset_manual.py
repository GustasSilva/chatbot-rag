"""Constrói e valida o gold-set do Manual do Aluno (Marco 1).

Cada item tem um ``trecho_fonte`` que DEVE ser substring exato do corpus limpo. O script
valida isso (quantas vezes ocorre) e confirma que cada trecho mapeia para ao menos um
chunk sob a config atual — é o portão que pega erro de digitação/acento no gold-set antes
de qualquer medição. Salva em data/goldsets/manual_aluno.json.
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.goldset import ItemGold, construir_relevancia, salvar_goldset
from rag.pipeline import construir_indice

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLD = "data/goldsets/manual_aluno.json"
DOC_ID = "manual"

# (id, pergunta, resposta, trecho_fonte) — trecho é substring EXATO do corpus limpo.
PERGUNTAS = [
    ("m01", "Qual é o percentual mínimo de frequência obrigatória em cada disciplina?",
     "75% das aulas dadas e demais atividades programadas.",
     "frequência obrigatória, em cada disciplina, em 75% (setenta e cinco por cento) das aulas"),

    ("m02", "Até que limite o aluno-atleta pode ter as ausências compensadas?",
     "Até o limite máximo de 25% das aulas ministradas.",
     "até o limite máximo de 25% (vinte e cinco por cento) das aulas ministradas"),

    ("m03", "O que é o trancamento de matrícula?",
     "A interrupção temporária das atividades escolares.",
     "É a interrupção temporária das atividades escolares"),

    ("m04", "Por quanto tempo o trancamento de matrícula pode ser concedido?",
     "Pelo prazo de até dois anos.",
     "trancamento de matrícula será concedido pelo prazo de até dois anos"),

    ("m05", "Como o aluno solicita o cancelamento de matrícula?",
     "Junto à Secretaria, a qualquer tempo, quitando as mensalidades vencidas.",
     "Pode ser solicitado junto à Secretaria, a qualquer tempo"),

    ("m06", "Como peço transferência para outra instituição de ensino?",
     "Presencialmente, junto à Secretaria do campus onde está matriculado.",
     "deve ser solicitada presencialmente junto à Secretaria do campus"),

    ("m07", "A nota da prova substitutiva substitui a média do bimestre?",
     "Não; substitui apenas a nota da prova não realizada.",
     "não substitui a média obtida no bimestre, substitui apenas a nota da prova"),

    ("m08", "O que acontece se eu faltar à prova on-line que agendei?",
     "Não poderá reagendar e deverá fazer a prova substitutiva.",
     "Caso não compareça no dia e horário agendado, independentemente do motivo"),

    ("m09", "Posso cursar disciplinas pendentes em regime de dependência no período seguinte?",
     "Sim; o aluno aprovado pode se matricular no período subsequente e cursar as pendentes em DP.",
     "cursar as disciplinas pendentes em regime de dependência"),

    ("m10", "Com quantas dependências sou promovido do 1º para o 2º período?",
     "Com qualquer número de DPs, desde que as disciplinas tenham sido cursadas e reprovadas.",
     "do 1º para o 2º período: o aluno é promovido com qualquer número de DPs"),

    ("m11", "O que é o estágio obrigatório?",
     "É o previsto no projeto pedagógico do curso, requisito para aprovação e diploma.",
     "O Estágio Obrigatório é aquele previsto no projeto pedagógico do curso"),

    ("m12", "Em quantos dias a documentação de estágio é assinada após a postagem no site?",
     "Em até 15 dias úteis.",
     "será feita em até 15 (quinze) dias úteis"),

    ("m13", "Qual a penalidade por atraso na devolução de material da biblioteca?",
     "Suspensão de 1 dia útil por dia de atraso, multiplicado pelo número de obras.",
     "suspensão de 1 (um) dia útil para cada dia de atraso"),

    ("m14", "Posso emprestar minha carteirinha de estudante para outra pessoa?",
     "Não; é terminantemente proibido emprestá-la e divulgar a senha a terceiros.",
     "terminantemente proibidos o empréstimo da mesma e a divulgação da senha a terceiros"),

    ("m15", "Quantas autorizações de entrada a Secretaria fornece se eu estiver sem a carteirinha?",
     "Até 3 autorizações por semestre.",
     "poderá fornecer até 3 (três) autorizações de entrada por semestre"),

    ("m16", "Posso pedir reanálise se discordar do parecer da transferência?",
     "Sim; é permitida uma única reanálise do histórico.",
     "solicitar uma única reanálise do histórico"),

    ("m17", "Em que se baseia a aprovação da transferência?",
     "Na análise do histórico escolar e na disponibilidade de vaga.",
     "baseia-se na análise do histórico escolar do estudante e na disponibilidade de vaga"),

    ("m18", "Qual a consequência de não trancar a matrícula dentro do prazo?",
     "Constituição de dívida até o final do período letivo.",
     "implica constituição de dívida até o final do período letivo"),
]


def main() -> int:
    cfg = carregar_config()
    corpus = carregar_pdf(CAMINHO_PDF)

    itens = [
        ItemGold(id=i, pergunta=p, resposta=r, trecho_fonte=t, doc_id=DOC_ID)
        for (i, p, r, t) in PERGUNTAS
    ]

    # 1) Cada trecho-fonte precisa existir no corpus (e, de preferência, ser único).
    faltando = []
    print("Validação dos trechos-fonte (ocorrências no corpus):")
    for item in itens:
        n = corpus.count(item.trecho_fonte)
        marca = "OK" if n >= 1 else "!!"
        if n == 0:
            faltando.append(item.id)
        print(f"  [{marca}] {item.id}: {n}x  «{item.trecho_fonte[:60]}…»")
    if faltando:
        print(f"\nERRO: trechos não encontrados: {faltando}. Corrija antes de salvar.")
        return 1

    # 2) Cada item precisa mapear para ao menos um chunk sob a config atual.
    indice = construir_indice({DOC_ID: corpus}, cfg, calcular_densa=False)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    print(f"\ncorpus: {len(indice.chunks)} chunks")
    print("chunks relevantes por pergunta:",
          {pid: sorted(cids) for pid, cids in relevancia.items()})

    salvar_goldset(itens, CAMINHO_GOLD, corpus="manual_aluno")
    print(f"\nGold-set salvo em {CAMINHO_GOLD} ({len(itens)} perguntas).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
