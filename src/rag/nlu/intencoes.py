"""Vocabulário do Manual do Aluno — os **dados** que alimentam o front-end de compilador.

Só definição, sem lógica: o mecanismo está em ``lexico`` (fase 1) e ``gramatica`` (fase 2). A
separação é o que permite ampliar vocabulário e intenções sem tocar em código — e ampliar é a
rotina prevista no plano, olhando o que cai no plano B.

Três tabelas, na ordem em que o compilador as usa: o **léxico** (palavra escrita pelo aluno →
símbolo), a **gramática de intenções** (sequência de símbolos → intenção) e as **ações**
(intenção → consulta ao Manual). Cada uma é conferida contra a anterior no momento em que é
construída, então erro de definição aparece na importação, não em produção.

Cada símbolo nomeia um **assunto ou marcador**, não uma palavra: ``FALTA`` cobre "faltas",
"ausências" e "frequência" porque, para a gramática, as três apontam para a mesma regra do
Manual. Quem decide o que fazer com a combinação de símbolos é a fase sintática.

O recorte inicial sai das 50 perguntas do gold-set institucional
(``data/goldsets/institucional.json``), escritas em linguagem de aluno real — é vocabulário
observado, não imaginado. Ampliar olhando o que cai no plano B é o passo 8 do plano.
"""
from __future__ import annotations

from .gramatica import Gramatica
from .lexico import Lexico, TipoToken
from .semantico import Acao, AnalisadorSemantico, Campo

# Marcadores: dizem QUE TIPO de resposta o aluno quer (definição, procedimento, quantidade),
# não o assunto. São eles que separam "o que é trancamento" de "como faço o trancamento".
MARCADORES: dict[str, list[str]] = {
    "QUAL": ["qual", "quais"],
    "COMO": ["como"],
    "QUANDO": ["quando"],
    "ONDE": ["onde"],
    "QUE": ["que"],
    "QUEM": ["quem"],
    "LOCALIZAR": ["encontro", "encontrar", "acho", "achar", "vejo", "ver",
                  "consulto", "consultar"],
    "NEGACAO": ["não", "nem"],  # inverte o sentido da regra; nunca é ruído
    "QUANTIDADE": [
        "quanto", "quanta", "quantos", "quantas",
        "limite", "máximo", "mínimo", "percentual", "porcentagem",
    ],
    "PODER": ["posso", "pode", "podem", "permitido", "permitida"],
    "PRECISAR": ["preciso", "precisa", "precisam"],
    "CONSEQUENCIA": ["acontece", "consequência", "consequências"],
}

# Assuntos do Manual: o "sobre o que" da pergunta.
ASSUNTOS: dict[str, list[str]] = {
    "FALTA": ["falta", "faltas", "faltar", "faltei", "ausência", "ausências",
              "frequência", "presença"],
    "ABONO": ["abono", "abonada", "abonadas", "abonado", "abonados",
              "compensada", "compensadas", "compensar"],
    "MATRICULA": ["matrícula", "matrículas", "matricular", "rematrícula"],
    # Símbolo próprio, não variante de MATRICULA: o Manual fala em renovar a matrícula e em
    # renovar o empréstimo da biblioteca. Quem compõe é a gramática.
    "RENOVACAO": ["renovação", "renovar", "renovada", "renovado"],
    "TRANCAR": ["trancar", "trancamento", "trancada", "trancado",
                "interromper", "interrupção"],
    "CANCELAR": ["cancelar", "cancelamento"],
    "TRANSFERENCIA": ["transferência", "transferir"],
    "DISCIPLINA": ["disciplina", "disciplinas", "matéria", "matérias"],
    "DEPENDENCIA": ["dependência", "dependências", "dp"],
    "NOTA": ["nota", "notas", "média", "médias"],
    "PROVA": ["prova", "provas", "substitutiva"],
    "EXAME": ["exame", "exames"],
    "APROVACAO": ["aprovado", "aprovada", "aprovação", "aprovar"],
    "REPROVACAO": ["reprovado", "reprovada", "reprovação"],
    "ESTAGIO": ["estágio", "estágios"],
    "OBRIGATORIO": ["obrigatório", "obrigatória", "obrigatoriedade"],
    "BIBLIOTECA": ["biblioteca"],
    "EMPRESTIMO": ["empréstimo", "emprestar", "devolução", "devolver"],
    "CARTEIRINHA": ["carteirinha", "carteira"],
    "DIPLOMA": ["diploma"],
    "COLACAO": ["colação", "colar", "grau", "formatura", "formar"],
    "REQUERIMENTO": ["requerimento", "requerimentos", "solicitação", "solicitações",
                     "solicitar", "solicita", "solicito", "pedido", "pedir", "peço", "pede"],
    "PENALIDADE": ["penalidade", "penalidades", "punição", "punições",
                   "multa", "sanção", "sanções"],
    "PRAZO": ["prazo", "prazos", "data", "datas", "dia", "dias"],
    "ALUNO": ["aluno", "aluna", "alunos", "estudante", "estudantes"],
    # Símbolo próprio, não variante de ALUNO: "aluno-atleta" chega como ALUNO ATLETA e é a
    # gramática que compõe os dois — mesma lógica de qualquer qualificador do Manual.
    "ATLETA": ["atleta", "atletas"],
    "PERIODO": ["período", "períodos", "semestre", "semestres", "bimestre", "bimestres"],
    "INSTITUICAO": ["faculdade", "universidade", "unip", "instituição", "instituições"],

    # --- situações de matrícula (seções "Normas acadêmicas/administrativas") ---
    "JUBILAMENTO": ["jubilamento", "jubilado"],
    "DESLIGAMENTO": ["desligamento", "desligado", "abandono"],
    "REABERTURA": ["reabertura", "reabrir"],
    "REOPCAO": ["reopção"],
    "REMANEJAMENTO": ["remanejamento", "remanejar"],
    "PORTADOR": ["portador"],
    "CURSO": ["curso", "cursos"],
    "CAMPUS": ["campus"],
    "TURNO": ["turno", "turnos"],
    "TURMA": ["turma", "turmas"],
    "REGULAR": ["regular", "regularmente"],

    # --- vida acadêmica ---
    "APROVEITAMENTO": ["aproveitamento"],
    "ADAPTACAO": ["adaptação", "adaptações", "adaptada"],
    "ANTECIPACAO": ["antecipação", "antecipar", "adiantar"],
    "OPTATIVA": ["optativa", "optativas"],
    "INSCRICAO": ["inscrição", "inscrever"],
    "PLANO": ["plano", "planos"],
    "ENSINO": ["ensino"],
    "AULA": ["aula", "aulas"],
    "HORARIO": ["horário", "horários", "pontualidade"],
    "ONLINE": ["online"],
    "ENADE": ["enade"],

    # --- secretaria, documentos e financeiro ---
    "SECRETARIA": ["secretaria"],
    "TESOURARIA": ["tesouraria"],
    "DOCUMENTO": ["documento", "documentos", "histórico", "certidão", "certidões",
                  "atestado", "atestados", "declaração", "declarações", "expedição"],
    "CADASTRO": ["cadastro", "cadastral", "cadastrais"],
    "RECURSO": ["recurso", "recursos", "reanálise", "discordar"],
    "SIGILO": ["sigilo", "privacidade", "confidencial"],
    "MENSALIDADE": ["mensalidade", "mensalidades", "boleto", "pagamento", "pagar"],
    "RECIBO": ["recibo"],
    "FIES": ["fies", "financiamento"],

    # --- oportunidades oferecidas pela instituição ---
    "MONITORIA": ["monitoria", "monitor"],
    "INICIACAO": ["iniciação"],
    "EXTENSAO": ["extensão"],
    "INTERCAMBIO": ["internacionalização", "intercâmbio", "exterior"],
    "REPRESENTACAO": ["representante", "representação", "representar"],
    "PALESTRA": ["palestra", "palestras", "visita", "visitas"],

    # --- espaços, equipamentos e conduta ---
    "RESERVA": ["reserva", "reservar"],
    "GUARDAVOLUMES": ["volumes"],
    "INTERNET": ["internet", "wifi"],
    "COMPUTADOR": ["computador", "computadores"],
    "EQUIPAMENTO": ["equipamento", "equipamentos"],
    "UNIFORME": ["uniforme", "uniformes"],
    "LABORATORIO": ["laboratório", "laboratórios"],
    "SALA": ["sala", "salas"],
    "FERIAS": ["férias", "recesso"],
    "FUMAR": ["fumar", "cigarro"],
    "ARMA": ["arma", "armas"],
    "TROTE": ["trote"],
}

GRUPOS: dict[str, list[str]] = {**MARCADORES, **ASSUNTOS}

# Ruído: o análogo do espaço em branco de um compilador. Reconhecido para ser descartado —
# artigos, preposições, pronomes, verbos de ligação e enfeites de conversa. Palavra que não
# está aqui nem no léxico não é ruído: vira DESCONHECIDO e segue (pode ser nome de disciplina).
RUIDO: list[str] = [
    # artigos e preposições
    "o", "a", "os", "as", "um", "uma", "uns", "umas",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "ao", "aos", "à", "às", "pelo", "pela", "para", "pra", "pro",
    "por", "com", "sem", "sobre", "até", "entre", "após", "depois",
    # conjunções
    "e", "ou", "se", "mas", "então",
    # pronomes
    "eu", "me", "mim", "meu", "minha", "meus", "minhas",
    "você", "vocês", "seu", "sua", "ele", "ela", "lhe",
    "isso", "esse", "essa", "este", "esta", "aquele", "aquela",
    # verbos vazios (o sentido está no assunto, não neles)
    "ser", "é", "são", "foi", "era", "estar", "está", "estou",
    "ter", "tem", "tenho", "tinha", "há", "fazer", "faz", "faço", "fiz",
    "ficar", "fica", "vai", "vou", "ir", "dar", "dá",
    # enfeites de conversa
    "poxa", "favor", "ah", "ai", "aí", "olha", "gente", "tipo", "né",
    "muito", "mesmo", "também", "só", "ainda", "já", "agora",
    "qualquer", "algum", "alguma", "todo", "toda", "cada", "outro", "outra", "dentro",
]

LEXICO_MANUAL = Lexico.de_grupos(GRUPOS, RUIDO)


# --------------------------------------------------------------------------------------------
# Gramática de intenções. Notação: espaço separa os elementos (a ordem importa), "?" marca
# opcional e "|" separa símbolos equivalentes. A regra casa como subsequência, ignorando o que
# sobra na frase — ver ``gramatica`` para a semântica completa.
#
# As regras derivam dos TÓPICOS DO MANUAL (os títulos de seção do documento), não das perguntas
# do gold-set. A diferença importa para a medição: escrever regra olhando as mesmas perguntas que
# depois medem a cobertura daria um número in-sample, que nada diz sobre generalização.
#
# O par definição × procedimento sobre o MESMO assunto (trancamento) é proposital: mostra que
# quem separa as duas é o marcador, não o assunto, que é o motivo de a fase léxica classificar
# marcadores à parte.
#
# Regra com um único símbolo obrigatório é reservada a termo inequívoco do documento
# ("jubilamento", "trote"), nunca a palavra que uma pergunta fora de escopo possa carregar:
# "mensalidade" e "internet", por exemplo, exigem um segundo símbolo, senão "quanto custa a
# mensalidade" e "qual a senha do wi-fi" passariam a ser respondidas em vez de recusadas.
REGRAS: dict[str, str] = {
    # --- frequência, notas e avaliação ---
    # O terceiro símbolo não é enfeite: "quantas faltas EU JÁ TENHO" é pergunta de dado pessoal,
    # que o Manual não responde, e casava com QUANTIDADE FALTA sozinho (medido no teste
    # adversarial). Exigir PODER, OBRIGATORIO ou DISCIPLINA separa a pergunta sobre a REGRA
    # ("quantas faltas posso ter") da pergunta sobre o ALUNO. A formulação genérica que perde
    # cobertura por causa disso ("qual o limite de faltas?") não fica sem resposta: cai no plano
    # B, que a responde com o guardrail de sempre.
    "limite_faltas":            "QUANTIDADE FALTA PODER|OBRIGATORIO|DISCIPLINA",
    # As duas do aluno-atleta são mais específicas que limite_faltas de propósito e vencem pelo
    # número de obrigatórios (maximal munch). O Manual trata os dois fatos em frases separadas:
    # quanto pode ser compensado e que não há abono, daí duas intenções, não uma.
    "limite_atleta":            "QUANTIDADE ALUNO ATLETA ABONO",
    "abono_falta_atleta":       "ALUNO ATLETA ABONO",
    "consulta_notas_faltas":    "LOCALIZAR NOTA|FALTA",
    "responsavel_faltas":       "QUEM FALTA",
    "media_aprovacao":          "NOTA APROVACAO",
    "consequencia_media":       "NOTA CONSEQUENCIA",
    "exame_aprovacao":          "EXAME APROVACAO",
    "material_prova":           "PROVA EXAME",
    "prova_substitutiva":       "PROVA NOTA",
    "falta_prova":              "FALTA PROVA",
    "agendamento_prova":        "QUANTIDADE PROVA DISCIPLINA",
    "horario_aulas":            "HORARIO AULA",

    # --- matrícula e situações do vínculo ---
    "matricula_ingressante":    "COMO MATRICULA",
    "definicao_trancamento":    "QUE TRANCAR MATRICULA?",
    "como_trancar":             "COMO TRANCAR MATRICULA?",
    "prazo_trancamento":        "QUANTIDADE|PRAZO TRANCAR MATRICULA?",
    "como_cancelar":            "COMO CANCELAR MATRICULA",
    "consequencia_sem_trancar": "CONSEQUENCIA NEGACAO TRANCAR",
    "consequencia_sem_matricula": "CONSEQUENCIA NEGACAO MATRICULA",
    "renovacao_matricula":      "RENOVACAO MATRICULA?",
    "remanejamento":            "REMANEJAMENTO CAMPUS|TURNO|TURMA?",
    "jubilamento":              "JUBILAMENTO",
    "desligamento":             "DESLIGAMENTO MATRICULA?",
    "reabertura_matricula":     "REABERTURA MATRICULA?",
    "reopcao_curso":            "REOPCAO CURSO?",
    "portador_curso_superior":  "PORTADOR CURSO?",

    # --- transferência ---
    "transferencia_saida":      "COMO|REQUERIMENTO TRANSFERENCIA INSTITUICAO",
    "transferencia_analise":    "QUE APROVACAO TRANSFERENCIA",
    "transferencia_recurso":    "RECURSO TRANSFERENCIA",
    "transferencia_regular":    "REGULAR TRANSFERENCIA",

    # --- disciplinas ---
    "dependencia":              "DISCIPLINA DEPENDENCIA",
    "limite_dependencias":      "QUANTIDADE DEPENDENCIA",
    "adaptacao":                "DISCIPLINA ADAPTACAO",
    "antecipacao_disciplina":   "ANTECIPACAO DISCIPLINA?",
    "aproveitamento_estudos":   "APROVEITAMENTO",
    "disciplina_optativa":      "OPTATIVA DISCIPLINA?",
    "inscricao_disciplinas":    "INSCRICAO DISCIPLINA",
    "plano_de_ensino":          "PLANO ENSINO",

    # --- estágio: a do não obrigatório vem antes porque as duas casam a mesma pergunta com o
    # mesmo peso, e o desempate por ordem de declaração deve ficar com a mais específica ---
    "estagio_nao_obrigatorio":  "ESTAGIO NEGACAO OBRIGATORIO",
    "estagio_obrigatorio":      "QUE ESTAGIO OBRIGATORIO",
    "vaga_estagio":             "LOCALIZAR ESTAGIO",
    "quem_faz_estagio":         "PRECISAR ESTAGIO",
    "prazo_documento_estagio":  "QUANTIDADE|PRAZO ESTAGIO",

    # --- biblioteca ---
    "penalidade_biblioteca":    "PENALIDADE EMPRESTIMO BIBLIOTECA",
    "computador_biblioteca":    "COMPUTADOR BIBLIOTECA",
    "renovacao_emprestimo":     "RENOVACAO EMPRESTIMO",
    "emprestimo_equipamento":   "EMPRESTIMO EQUIPAMENTO",
    "reserva_online":           "RESERVA ONLINE?",
    "guarda_volumes":           "GUARDAVOLUMES",

    # --- carteirinha ---
    "emprestar_carteirinha":    "EMPRESTIMO CARTEIRINHA",
    "sem_carteirinha":          "QUANTIDADE CARTEIRINHA",
    "carteirinha_entrada":      "PRECISAR CARTEIRINHA",

    # --- secretaria, documentos e financeiro ---
    "como_requerer":            "COMO REQUERIMENTO",
    "resposta_requerimento":    "LOCALIZAR REQUERIMENTO",
    "expedicao_documentos":     "QUANTIDADE|PRAZO DOCUMENTO",
    "alteracao_cadastral":      "CADASTRO",
    "sigilo_informacoes":       "SIGILO",
    "pagamento_mensalidade":    "COMO|ONDE MENSALIDADE",
    "recibo_empresa":           "RECIBO",
    "fies":                     "FIES",

    # --- diploma e formatura ---
    "diploma":                  "DIPLOMA",
    "colacao_enade":            "COLACAO REGULAR ENADE",
    "colacao_obrigatoria":      "PRECISAR COLACAO",

    # --- oportunidades ---
    "atribuicoes_monitor":      "MONITORIA AULA|PROVA",
    "monitoria":                "MONITORIA",
    "iniciacao_cientifica":     "INICIACAO",
    "atividades_extensao":      "EXTENSAO",
    "intercambio":              "INTERCAMBIO",
    "representacao_discente":   "REPRESENTACAO",
    "palestras_visitas":        "PALESTRA",

    # --- conduta e espaços ---
    "penalidades_disciplinares": "QUAL PENALIDADE",
    "proibicao_fumar":          "FUMAR",
    "armas":                    "ARMA",
    "trote":                    "TROTE",
    "ferias_recesso":           "FERIAS",
    "uniforme_equipamento":     "UNIFORME",
}

GRAMATICA_MANUAL = Gramatica.de_notacao(REGRAS, LEXICO_MANUAL)


# --------------------------------------------------------------------------------------------
# Ações: o que fazer com cada intenção reconhecida. A consulta é escrita **no vocabulário do
# Manual**, não no do aluno — é ela que vai ao recuperador, e é aí que a tradução leigo → termo
# do documento se paga (ver ``semantico``). Onde o trecho-fonte do gold-set foi conferido, as
# palavras vêm dele; onde não há trecho conferido, a consulta fica no tema, sem afirmar conteúdo.
ACOES: dict[str, Acao] = {
    "limite_faltas": Acao(
        "frequência obrigatória em cada disciplina, aulas dadas",
        campos=(Campo("disciplina", TipoToken.DESCONHECIDO),),
    ),
    "limite_atleta": Acao(
        "aluno-atleta, limite máximo das aulas ministradas, aprovação de frequência"
    ),
    "abono_falta_atleta": Acao("não há abono de faltas do aluno-atleta"),
    "definicao_trancamento": Acao(
        "trancamento de matrícula, interrupção temporária das atividades escolares"
    ),
    "como_trancar": Acao("como solicitar o trancamento de matrícula"),
    "prazo_trancamento": Acao("trancamento de matrícula será concedido pelo prazo"),
    "como_cancelar": Acao("cancelamento de matrícula solicitado junto à Secretaria"),
    "consulta_notas_faltas": Acao("notas e faltas informadas pela Internet, Secretaria On-line"),
    "responsavel_faltas": Acao("controle das faltas é de responsabilidade do aluno"),
    "media_aprovacao": Acao("média para aprovação sem exame"),
    "consequencia_media": Acao("média mínima para aprovação, exame, reprovação"),
    "exame_aprovacao": Acao("média final MF igual ou maior que 5,0 aprovado"),
    "material_prova": Acao("realização das provas, material permitido, caneta"),
    "prova_substitutiva": Acao("prova substitutiva substitui a nota, média do bimestre"),
    "falta_prova": Acao(
        "não compareça no dia e horário agendado da prova, reagendamento"
    ),
    "agendamento_prova": Acao("agendamento da prova on-line por disciplina"),
    "horario_aulas": Acao("horário das aulas, turnos manhã, tarde e noite"),

    "matricula_ingressante": Acao(
        "aluno ingressante matriculado automaticamente no regime de progressão tutelada"
    ),
    "consequencia_sem_trancar": Acao(
        "não trancar a matrícula no prazo, desligamento ou abandono de curso"
    ),
    "consequencia_sem_matricula": Acao(
        "aluno que não renova a matrícula nos prazos estabelecidos, abandono"
    ),
    "renovacao_matricula": Acao("renovação de matrícula, prazos do Calendário Escolar"),
    "remanejamento": Acao("remanejamento de campus, turno ou turma"),
    "jubilamento": Acao("jubilamento"),
    "desligamento": Acao("desligamento ou abandono de curso"),
    "reabertura_matricula": Acao("reabertura de matrícula"),
    "reopcao_curso": Acao("reopção de curso"),
    "portador_curso_superior": Acao("portador de curso superior"),

    "transferencia_saida": Acao("transferência para outra instituição de ensino"),
    "transferencia_analise": Acao(
        "análise da transferência, aproveitamento de estudos e vagas"
    ),
    "transferencia_recurso": Acao("recurso do parecer da transferência, reanálise"),
    "transferencia_regular": Acao("aluno regularmente matriculado para transferência"),

    "dependencia": Acao("disciplinas em regime de dependência"),
    "limite_dependencias": Acao("número de dependências para promoção de período"),
    "adaptacao": Acao("adaptação de disciplina"),
    "antecipacao_disciplina": Acao("antecipação de disciplina"),
    "aproveitamento_estudos": Acao("aproveitamento de estudos"),
    "disciplina_optativa": Acao("disciplinas optativas"),
    "inscricao_disciplinas": Acao("inscrição em disciplinas"),
    "plano_de_ensino": Acao("planos de ensino das disciplinas"),

    "estagio_nao_obrigatorio": Acao("estágio não obrigatório, atividade opcional"),
    "estagio_obrigatorio": Acao("estágios curriculares obrigatórios"),
    "vaga_estagio": Acao("oferta de vagas de estágio"),
    "quem_faz_estagio": Acao("obrigatoriedade do estágio curricular no curso"),
    "prazo_documento_estagio": Acao("assinatura do termo de compromisso de estágio, prazo"),

    "penalidade_biblioteca": Acao(
        "atraso na devolução de materiais da biblioteca, penalidades, suspensão"
    ),
    "computador_biblioteca": Acao("equipamentos de acesso à Internet na biblioteca"),
    "renovacao_emprestimo": Acao("renovação do empréstimo da biblioteca"),
    "emprestimo_equipamento": Acao("empréstimo de equipamentos"),
    "reserva_online": Acao("reserva on-line de material da biblioteca"),
    "guarda_volumes": Acao("uso do guarda-volumes da biblioteca"),

    "emprestar_carteirinha": Acao("carteirinha de identificação do aluno é intransferível"),
    "sem_carteirinha": Acao("autorização de entrada do aluno sem a carteirinha"),
    "carteirinha_entrada": Acao(
        "carteirinha digital, documento de identidade do aluno, entrada nas dependências"
    ),

    "como_requerer": Acao("requerimentos solicitados na Secretaria"),
    "resposta_requerimento": Acao("resposta do requerimento na Secretaria On-line"),
    "expedicao_documentos": Acao("expedição de documentos pela Secretaria, prazo em dias úteis"),
    "alteracao_cadastral": Acao("alterações cadastrais, mudança de informações pessoais"),
    "sigilo_informacoes": Acao("sigilo de informações, direito à privacidade do aluno"),
    "pagamento_mensalidade": Acao("pagamento das mensalidades por boleto bancário"),
    "recibo_empresa": Acao("recibo para a empresa"),
    "fies": Acao("Fundo de Financiamento ao Estudante do Ensino Superior"),

    "diploma": Acao("expedição do diploma"),
    "colacao_enade": Acao("colação de grau e situação regular no ENADE"),
    "colacao_obrigatoria": Acao("colação de grau, ato oficial obrigatório"),

    "atribuicoes_monitor": Acao("atribuições do monitor, o que o monitor não pode fazer"),
    "monitoria": Acao("programa de monitoria"),
    "iniciacao_cientifica": Acao("iniciação científica e iniciação tecnológica"),
    "atividades_extensao": Acao("atividades de extensão"),
    "intercambio": Acao("internacionalização acadêmica, intercâmbio"),
    "representacao_discente": Acao("representação discente, representante de classe"),
    "palestras_visitas": Acao("palestras e visitas técnicas"),

    "penalidades_disciplinares": Acao(
        "regime disciplinar, advertência, repreensão, suspensão e desligamento"
    ),
    "proibicao_fumar": Acao("é proibido fumar em sala de aula"),
    "armas": Acao("proibição de armas"),
    "trote": Acao("trote"),
    "ferias_recesso": Acao("férias e recesso escolar"),
    "uniforme_equipamento": Acao("uniformes e equipamentos de proteção"),
}

SEMANTICA_MANUAL = AnalisadorSemantico.de_tabela(ACOES, GRAMATICA_MANUAL)
