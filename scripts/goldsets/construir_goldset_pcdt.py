"""Constrói e valida o gold-set de saúde (Marco 3), a partir de 4 PCDTs do SUS.

Desenho central (protocolo §2, §7): perguntas em PARES leigo×técnico — as duas versões
apontam para o MESMO trecho-fonte, mudando só o vocabulário. É o que faz a diferença entre
estratégias aparecer: a busca léxica (BM25) tende a sofrer com o termo leigo, enquanto a
densa (semântica) deveria atravessar o gap.

Cada trecho-fonte é substring EXATO do PCDT correspondente (validado por count()).
"""
from __future__ import annotations

import sys

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.goldset import ItemGold, construir_relevancia, salvar_goldset
from rag.pipeline import construir_indice

PDFS = {
    "asma": "data/raw/pcdt/asma.pdf",
    "hipertensao": "data/raw/pcdt/hipertensao.pdf",
    "diabetes_t2": "data/raw/pcdt/diabetes_t2.pdf",
    "dor_cronica": "data/raw/pcdt/dor_cronica.pdf",
}
CAMINHO_GOLD = "data/goldsets/saude_pcdt.json"

# (id, doc_id, tipo, pergunta, resposta, trecho_fonte). Pares *_l (leigo) / *_t (tecnico)
# compartilham o trecho_fonte.
_T_ASMA_DEF = "A asma é uma doença respiratória crônica, heterogênea e complexa"
_T_ASMA_SINT = "sibilância, dispneia, opressão torácica e tosse"
_T_ASMA_TTO = "corticoide inalatório (CI) com formoterol em baixa dose sob demanda"
_T_HAS_DIAG = "140 mmHg /90 mmHg devem seguir os critérios para confirmação diagnóstica"
_T_HAS_BCC = "Os bloqueadores dos canais de cálcio atuam nas células musculares lisas das arteríolas"
_T_HAS_SEC = "A hipertensão arterial secundária, em contraposição à hipertensão arterial primária, ocorre devido a uma causa identificável"
_T_DM_MET = "deve-se iniciar cloridrato de metformina em monoterapia"
_T_DM_GJ = "A glicemia de jejum deve ser realizada após um período de 8 horas a 12 horas sem ingestão calórica, sendo valores inferiores a 100 mg/dL considerados normais"
_T_DM_HB = "podendo incluir a hemoglobina glicada (HbA1c) conforme disponibilidade local"
_T_DOR_DEF = "como aquela superior a três meses, independentemente do grau de recorrência"
_T_DOR_PARA = "O uso do paracetamol está associado à redução da dor e melhora da funcionalidade em pessoas com osteoartrite de joelho e de quadril"
_T_DOR_TCC = "a TCC pode ser aplicada no tratamento da dor crônica"

PERGUNTAS = [
    # ---- ASMA ----
    ("as1_l", "asma", "leigo",   "O que é a asma? É uma doença dos pulmões que não tem cura?", "Doença respiratória crônica.", _T_ASMA_DEF),
    ("as1_t", "asma", "tecnico", "Qual a definição de asma quanto à sua natureza crônica e heterogênea?", "Doença respiratória crônica, heterogênea e complexa.", _T_ASMA_DEF),
    ("as2_l", "asma", "leigo",   "Quais os sinais da asma? Aquele chiado no peito e falta de ar?", "Sibilância, dispneia, opressão torácica e tosse.", _T_ASMA_SINT),
    ("as2_t", "asma", "tecnico", "Quais os sintomas respiratórios recorrentes característicos da asma?", "Sibilância, dispneia, opressão torácica e tosse.", _T_ASMA_SINT),
    ("as3_l", "asma", "leigo",   "Qual bombinha usar quando a asma é fraca?", "Corticoide inalatório com formoterol em baixa dose sob demanda.", _T_ASMA_TTO),
    ("as3_t", "asma", "tecnico", "Qual o tratamento de baixa intensidade indicado na asma leve?", "Corticoide inalatório (CI) com formoterol em baixa dose sob demanda.", _T_ASMA_TTO),

    # ---- HIPERTENSÃO ----
    ("ha1_l", "hipertensao", "leigo",   "A partir de quanto a pressão é considerada alta?", "PA a partir de 140/90 mmHg segue confirmação diagnóstica.", _T_HAS_DIAG),
    ("ha1_t", "hipertensao", "tecnico", "A partir de que valor de PA se seguem os critérios de confirmação diagnóstica?", "≥ 140/90 mmHg.", _T_HAS_DIAG),
    ("ha2_l", "hipertensao", "leigo",   "Como funcionam os remédios de pressão que relaxam os vasos?", "Reduzem o cálcio nas células musculares das arteríolas, vasodilatando.", _T_HAS_BCC),
    ("ha2_t", "hipertensao", "tecnico", "Qual o mecanismo de ação dos bloqueadores dos canais de cálcio?", "Atuam nas células musculares lisas das arteríolas.", _T_HAS_BCC),
    ("ha3_l", "hipertensao", "leigo",   "Existe pressão alta que tem uma causa específica e tratável?", "Sim, a hipertensão secundária.", _T_HAS_SEC),
    ("ha3_t", "hipertensao", "tecnico", "O que caracteriza a hipertensão arterial secundária?", "Decorre de causa identificável e tratável.", _T_HAS_SEC),

    # ---- DIABETES TIPO 2 ----
    ("dm1_l", "diabetes_t2", "leigo",   "Qual o primeiro remédio para o diabetes tipo 2?", "Metformina em monoterapia.", _T_DM_MET),
    ("dm1_t", "diabetes_t2", "tecnico", "Qual fármaco iniciar em monoterapia no diabetes melito tipo 2?", "Cloridrato de metformina.", _T_DM_MET),
    ("dm2_l", "diabetes_t2", "leigo",   "Quanto tempo de jejum para o exame de açúcar e qual valor é normal?", "8 a 12 horas; abaixo de 100 mg/dL é normal.", _T_DM_GJ),
    ("dm2_t", "diabetes_t2", "tecnico", "Qual o período de jejum para a glicemia de jejum e o valor de referência normal?", "8 a 12 horas; < 100 mg/dL.", _T_DM_GJ),
    ("dm3_l", "diabetes_t2", "leigo",   "Que exame de sangue mostra a média do açúcar dos últimos meses?", "A hemoglobina glicada (HbA1c).", _T_DM_HB),
    ("dm3_t", "diabetes_t2", "tecnico", "Qual exame pode complementar a glicemia de jejum conforme disponibilidade local?", "Hemoglobina glicada (HbA1c).", _T_DM_HB),

    # ---- DOR CRÔNICA ----
    ("dc1_l", "dor_cronica", "leigo",   "A partir de quanto tempo a dor é considerada crônica?", "Quando dura mais de três meses.", _T_DOR_DEF),
    ("dc1_t", "dor_cronica", "tecnico", "Qual o critério temporal que define a dor crônica?", "Duração superior a três meses.", _T_DOR_DEF),
    ("dc2_l", "dor_cronica", "leigo",   "O remédio de febre (paracetamol) ajuda na dor do joelho gasto?", "Sim, reduz a dor na osteoartrite de joelho e quadril.", _T_DOR_PARA),
    ("dc2_t", "dor_cronica", "tecnico", "Qual o efeito do paracetamol na osteoartrite de joelho e quadril?", "Redução da dor e melhora da funcionalidade.", _T_DOR_PARA),
    ("dc3_l", "dor_cronica", "leigo",   "A terapia com psicólogo ajuda a lidar com a dor que não passa?", "Sim, a TCC é aplicada no tratamento da dor crônica.", _T_DOR_TCC),
    ("dc3_t", "dor_cronica", "tecnico", "A terapia cognitivo-comportamental tem indicação no tratamento da dor crônica?", "Sim.", _T_DOR_TCC),
]


def main() -> int:
    cfg = carregar_config()
    corpora = {doc_id: carregar_pdf(caminho) for doc_id, caminho in PDFS.items()}

    itens = [
        ItemGold(id=i, pergunta=p, resposta=r, trecho_fonte=t, tipo=tipo, doc_id=doc)
        for (i, doc, tipo, p, r, t) in PERGUNTAS
    ]

    faltando = []
    print("Validação dos trechos-fonte:")
    for item in itens:
        n = corpora[item.doc_id].count(item.trecho_fonte)
        if n == 0:
            faltando.append(item.id)
        print(f"  [{'OK' if n else '!!'}] {item.id} ({item.doc_id}): {n}x")
    if faltando:
        print(f"\nERRO: trechos não encontrados: {faltando}")
        return 1

    indice = construir_indice(corpora, cfg, calcular_densa=False)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    print(f"\n{len(indice.chunks)} chunks | {len(itens)} perguntas "
          f"({sum(i.tipo=='leigo' for i in itens)} leigo / "
          f"{sum(i.tipo=='tecnico' for i in itens)} técnico)")

    salvar_goldset(itens, CAMINHO_GOLD, corpus="saude_pcdt")
    print(f"Gold-set salvo em {CAMINHO_GOLD}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
