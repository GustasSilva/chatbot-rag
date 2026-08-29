"""O que se mostra ao aluno: saudação, recusa e o recorte dos trechos citados.

Nada de decisão aqui, só o preparo do que aparece na tela. Fica num módulo próprio para as
interfaces (navegador e terminal) mostrarem a mesma coisa do mesmo jeito.
"""
from __future__ import annotations

import random
import re

from .corpus import sem_acentos

# Rótulo "[intencao] " que o controlador põe quando a resposta reúne mais de uma
# intenção: sai antes de procurar o destaque dentro do trecho.
_SEM_ROTULO = re.compile(r"^\[[a-z_]+\]\s*")

RECUSA = "Não encontrei essa informação nos documentos."
# O modelo às vezes acrescenta ao final ("...nos documentos fornecidos"), então o
# reconhecimento casa só o começo da frase.
_INICIO_RECUSA = "não encontrei essa informação"

RESPOSTAS_SAUDACAO = (
    "Olá! Sou o assistente (não-oficial) do Manual do Aluno da UNIP. Posso ajudar com dúvidas "
    "sobre a vida acadêmica — matrícula, faltas, provas, aproveitamento de estudos e afins. Em "
    "que posso ajudar?",
    "Oi! Este é o assistente (não-oficial) do Manual do Aluno da UNIP. Pergunte à vontade sobre "
    "matrícula, faltas, provas, trancamento e outros temas acadêmicos.",
    "Olá, tudo bem? Tiro dúvidas sobre o Manual do Aluno da UNIP — faltas, provas, rematrícula, "
    "aproveitamento de estudos e afins. O que você quer saber?",
    "Oi, que bom te ver! Sou o assistente (não-oficial) do Manual do Aluno. Sobre qual assunto "
    "da vida acadêmica você precisa de ajuda?",
)

# Ordenadas por tamanho: as frases saem antes das palavras soltas que as compõem.
_SAUDACOES = (
    "como voce esta", "como vc esta", "como vai voce", "como vai",
    "bom dia", "boa tarde", "boa noite",
    "tudo bem", "tudo bom", "tudo certo",
    "e ai", "ola", "oi", "opa", "hey", "ei", "salve", "beleza",
)
# Ligações que podem sobrar em volta de uma saudação sem torná-la uma pergunta.
_LIGACAO = {"e", "ai", "voce", "vc", "entao", "assistente", "por", "favor", "bom", "boa"}


def eh_recusa(texto: str) -> bool:
    """True para a recusa canônica, que não tem fonte a exibir."""
    return _INICIO_RECUSA in texto.strip().lower()


def resposta_saudacao() -> str:
    """Uma das saudações, sorteada para não repetir sempre a mesma frase."""
    return random.choice(RESPOSTAS_SAUDACAO)


def eh_saudacao(texto: str) -> bool:
    """True só quando a mensagem é APENAS saudação: com pergunta junto, segue o pipeline."""
    limpo = "".join(c if c.isalnum() or c.isspace() else " " for c in sem_acentos(texto.lower()))
    resto = " " + " ".join(limpo.split()) + " "
    achou = False
    for frase in _SAUDACOES:
        alvo = f" {frase} "
        if alvo in resto:
            achou = True
            resto = resto.replace(alvo, " ")
    return achou and not [t for t in resto.split() if t not in _LIGACAO]


def janela(texto: str, destaque: str = "", n: int = 320) -> str:
    """Recorte do trecho para exibição, centrado na frase que respondeu quando ela está nele.

    Sem centrar, o recorte pega o começo de uma janela de 180 palavras, que quase sempre cai no
    assunto anterior, e a fonte parece desmentir a resposta.
    """
    inteiro = " ".join(texto.split())
    # A resposta pode reunir o destaque de mais de uma intenção; centra no primeiro que
    # estiver neste trecho.
    inicio = -1
    for parte in destaque.split("\n\n"):
        alvo = " ".join(_SEM_ROTULO.sub("", parte).split())
        if alvo and (inicio := inteiro.find(alvo)) >= 0:
            break
    abertura = max(0, inicio - 40) if inicio >= 0 else 0
    return _recortar(inteiro, abertura, min(len(inteiro), abertura + n))


def _recortar(texto: str, abertura: int, fecho: int) -> str:
    """Recorta sem partir palavra: as bordas andam até o espaço mais próximo."""
    if abertura > 0:
        avanco = texto.find(" ", abertura)
        abertura = avanco + 1 if avanco != -1 else len(texto)
    if fecho < len(texto):
        recuo = texto.rfind(" ", abertura, fecho)
        fecho = recuo if recuo > abertura else fecho

    return (
        ("... " if abertura > 0 else "")
        + texto[abertura:fecho].strip()
        + (" ..." if fecho < len(texto) else "")
    )


def fontes_de(resposta, n: int = 320) -> list[dict]:
    """Trechos consultados, numerados como o ``[n]`` da resposta, marcando os que a embasaram.

    Vazio na recusa: não há evidência a mostrar de algo que não foi respondido.
    """
    if eh_recusa(resposta.texto):
        return []
    citados = set(resposta.fontes)
    return [
        {
            "n": i,
            "citada": trecho.id in citados,
            "texto": janela(trecho.texto, resposta.texto, n),
        }
        for i, trecho in enumerate(resposta.trechos, start=1)
    ]
