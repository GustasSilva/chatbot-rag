"""Saída estruturada em JSON, no nível livre de contexto da hierarquia.

Enquanto a citação ``[n]`` (ver ``gramatica_citacao.py``) é uma linguagem **regular** reconhecida por um
AFD feito à mão, um objeto JSON é **livre de contexto**: o aninhamento de ``{}``/``[]`` exige uma
**pilha** (autômato de pilha) para casar aberturas e fechamentos. Aqui autoramos o **esquema** do
objeto de saída e deixamos o motor de gramática da ``llama.cpp`` (que realiza esse autômato de
pilha) forçá-lo na decodificação — garantindo, por construção, um JSON válido no formato:

    {"resposta": "<texto>", "fontes": [<n>, ...]}   com n inteiro em 1..K, ao menos um.

Este módulo é **puro** (esquema + validador), independente do LLM, então o validador é testável
isoladamente (ver ``tests/test_json_estruturado.py``).
"""
from __future__ import annotations

import json

# Prompt que pede o JSON tanto no baseline quanto na versão restrita (para a comparação ser justa:
# a única diferença entre os dois é a gramática ligada ou não, não o prompt).
SISTEMA_JSON = (
    "Voce e um assistente que responde com base nos trechos fornecidos. "
    "Responda EXCLUSIVAMENTE com um objeto JSON valido, sem nenhum texto, comentario ou marcacao "
    "antes ou depois, no formato exato: "
    '{"resposta": "<sua resposta em portugues>", "fontes": [<numeros dos trechos usados>]}. '
    "Use apenas os numeros dos trechos fornecidos e cite ao menos um."
)


# Gramática GBNF do objeto de saída. Autorada à mão (não derivada de um JSON Schema) por um motivo
# concreto: o conversor esquema->gramática da llama.cpp NÃO respeita minimum/maximum de inteiros —
# ele deixaria passar "fontes": [13]. Aqui ``fonte`` é a alternância explícita dos números válidos
# (1..K), então a faixa é garantida POR CONSTRUÇÃO. É uma gramática livre de contexto (o motor da
# llama.cpp a compila num autômato de pilha). ``__FONTES__`` é preenchido em ``construir_gbnf``.
_GBNF_BASE = r'''root   ::= "{" ws "\"resposta\"" ws ":" ws string ws "," ws "\"fontes\"" ws ":" ws "[" ws fonte (ws "," ws fonte)* ws "]" ws "}"
string ::= "\"" char* "\""
char   ::= [^"\\\n]
fonte  ::= __FONTES__
ws     ::= [ \t\n]*'''


def construir_gbnf(num_fontes: int) -> str:
    """GBNF do objeto ``{"resposta": "...", "fontes": [n, ...]}`` com ``n`` restrito a ``1..num_fontes``.

    ``fonte`` vira a alternância ``"1" | "2" | ... | "K"``, o que impede um índice fora da faixa já
    na decodificação (ao contrário do JSON Schema, que só garante "é inteiro").
    """
    if num_fontes < 1:
        raise ValueError("num_fontes deve ser >= 1")
    fontes = " | ".join('"%d"' % i for i in range(1, num_fontes + 1))
    return _GBNF_BASE.replace("__FONTES__", fontes)


def validar(raw: str, num_fontes: int) -> tuple[bool, dict | None, str]:
    """Valida se ``raw`` é um JSON no esquema esperado. Devolve (ok, objeto ou None, motivo).

    Estrito de propósito: mede a validade da saída *como veio* (um ``json.loads`` direto). Preâmbulo,
    cerca de markdown ```` ```json ````, vírgula sobrando etc. contam como inválido — é exatamente o
    que a gramática elimina por construção.
    """
    try:
        dados = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as erro:
        return False, None, f"JSON invalido ({erro})"
    if not isinstance(dados, dict):
        return False, None, "raiz nao e objeto"
    if set(dados) != {"resposta", "fontes"}:
        return False, None, f"chaves != {{resposta, fontes}}: {sorted(dados)}"
    if not isinstance(dados["resposta"], str):
        return False, None, "resposta nao e string"
    fontes = dados["fontes"]
    if not isinstance(fontes, list) or not fontes:
        return False, None, "fontes vazio ou nao-lista"
    if not all(
        isinstance(n, int) and not isinstance(n, bool) and 1 <= n <= num_fontes for n in fontes
    ):
        return False, None, "fonte fora de 1..K ou nao-inteiro"
    return True, dados, "ok"
