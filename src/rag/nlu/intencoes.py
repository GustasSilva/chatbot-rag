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
    "MATRICULA": ["matrícula", "matrículas", "matricular",
                  "rematrícula", "renovação", "renovar", "renovada", "renovado"],
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
# Recorte inicial (marco 2 do plano): as intenções mais frequentes do Manual, escolhidas pelos
# símbolos que as perguntas do gold-set de fato produzem. O par definição × procedimento sobre
# o MESMO assunto (trancamento) é proposital: mostra que quem separa as duas é o marcador, não
# o assunto — que é o motivo de a fase léxica classificar marcadores à parte.
REGRAS: dict[str, str] = {
    "limite_faltas":         "QUANTIDADE FALTA DISCIPLINA?",
    # As três regras abaixo casam a mesma pergunta do aluno-atleta e são desempatadas pelo
    # número de obrigatórios (maximal munch), da mais específica para a mais geral. Sem elas, a
    # pergunta do atleta caía em limite_faltas e vinha a regra geral de frequência — trecho
    # errado, medido no gold-set. O Manual trata os dois fatos em frases separadas: quanto pode
    # ser compensado (limite) e que não há abono — daí duas intenções, não uma.
    "limite_atleta":         "QUANTIDADE ALUNO ATLETA ABONO",
    "abono_falta_atleta":    "ALUNO ATLETA ABONO",
    "definicao_trancamento": "QUE TRANCAR MATRICULA?",
    "como_trancar":          "COMO TRANCAR MATRICULA?",
    "prazo_trancamento":     "QUANTIDADE|PRAZO TRANCAR MATRICULA?",
    "como_cancelar":         "COMO CANCELAR MATRICULA?",
    "prazo_rematricula":     "QUANDO|PRAZO MATRICULA",
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
    "prazo_rematricula": Acao("prazo de renovação de matrícula"),
}

SEMANTICA_MANUAL = AnalisadorSemantico.de_tabela(ACOES, GRAMATICA_MANUAL)
