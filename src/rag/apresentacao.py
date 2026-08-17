"""Formatação da resposta, compartilhada pelas interfaces (navegador, tela e terminal).

Nada de lógica de decisão aqui: só o preparo do que é exibido. Fica num módulo próprio para
as três interfaces mostrarem a mesma coisa do mesmo jeito.
"""
from __future__ import annotations

RECUSA = "não encontrei essa informação"


def eh_recusa(texto: str) -> bool:
    """True para a recusa canônica, que não tem fonte a exibir."""
    return RECUSA in texto.strip().lower()


def janela(texto: str, destaque: str = "", n: int = 320) -> str:
    """Recorte do trecho para exibição, centrado na frase que respondeu quando ela está nele.

    Sem centrar, o recorte pega o começo de uma janela de 180 palavras, que quase sempre cai no
    assunto anterior, e a fonte parece desmentir a resposta.
    """
    inteiro = " ".join(texto.split())
    alvo = " ".join(destaque.split())
    inicio = inteiro.find(alvo) if alvo else -1
    abertura = max(0, inicio - 40) if inicio >= 0 else 0
    return _recortar(inteiro, abertura, min(len(inteiro), abertura + n))


def _recortar(texto: str, abertura: int, fecho: int) -> str:
    """Recorta ``texto`` sem partir palavra: as bordas andam até o espaço mais próximo."""
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

    Devolve vazio na recusa: não há evidência a mostrar de algo que não foi respondido.
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
