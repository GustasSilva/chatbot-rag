"""Extrai os títulos de seção do Manual do Aluno pelos atributos tipográficos do PDF.

O Manual não traz sumário eletrônico nem marcadores (``doc.get_toc()`` volta vazio), e
procurar títulos pelo texto não funciona: uma expressão regular de iniciais maiúsculas devolve
sobretudo a lista de dirigentes do prefácio. O que separa título de corpo é a fonte. O corpo
está em ``Univers-CondensedLight``; os títulos de seção, em ``Univers-Bold`` e
``Univers-Black``, a família larga em negrito, que o corpo não usa.

Foi desta lista que as 77 regras da gramática de intenções foram escritas
(``docs/decisoes.md`` §8), e não das perguntas do conjunto de referência.

Uso:
    python scripts/estudo/titulos_de_secao.py
"""
from __future__ import annotations

import fitz  # PyMuPDF

from rag.config import Config

# A família larga em negrito: só os títulos a usam. As variantes condensadas ficam de fora,
# porque o corpo as emprega para destacar termos no meio do parágrafo.
FONTES_DE_TITULO = {"Univers-Bold", "Univers-Black"}
# Abaixo disso são cabeçalhos de tabela e do calendário, e não seções.
TAMANHO_MINIMO = 7.0


def linhas_de_titulo(pagina: fitz.Page) -> list[str]:
    """Os títulos da página: linhas inteiras na fonte de título, unidas quando seguidas."""
    titulos = []
    for bloco in pagina.get_text("dict")["blocks"]:
        partes: list[str] = []  # um título longo quebra em duas linhas do mesmo bloco
        for linha in bloco.get("lines", []) + [None]:
            trechos = [s for s in linha["spans"] if s["text"].strip()] if linha else []
            if trechos and all(
                s["font"] in FONTES_DE_TITULO and s["size"] >= TAMANHO_MINIMO for s in trechos
            ):
                partes.append(" ".join(s["text"].strip() for s in trechos))
                continue
            texto = " ".join(partes)
            # Números de página e marcadores soltos não são títulos.
            if any(c.isalpha() for c in texto) and len(texto) > 2:
                titulos.append(texto)
            partes = []
    return titulos


def main() -> None:
    documento = fitz.open(Config().caminho_manual)
    print(f"sumário eletrônico do PDF: {len(documento.get_toc())} entradas\n")
    vistos: set[str] = set()
    for pagina in documento:
        for titulo in linhas_de_titulo(pagina):
            chave = titulo.casefold()
            if chave not in vistos:
                vistos.add(chave)
                print(f"p.{pagina.number + 1:>3}  {titulo}")
    print(f"\n{len(vistos)} títulos distintos")


if __name__ == "__main__":
    main()
