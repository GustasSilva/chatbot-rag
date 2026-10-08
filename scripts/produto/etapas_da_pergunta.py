"""Mostra a pergunta atravessando as quatro fases do núcleo, uma de cada vez.

É o `assistente_institucional.py` aberto: em vez de só a resposta, imprime o que cada fase do
front-end de compilador produziu, com o tempo que levou. Serve à demonstração da defesa, onde a
afirmação a sustentar não é "o assistente responde", e sim **como** ele responde: texto vira
símbolos, símbolos viram intenção, intenção vira consulta canônica, e é a consulta, e nunca a
frase do aluno, que vai ao Manual.

Monta só o núcleo (`com_plano_b=False` equivalente): sem Ollama, sem cross-encoder, sobe em
segundos. Quando a gramática não reconhece, o script diz onde o plano B entraria e para, porque
o que ele tem a mostrar é o caminho sem IA.

Uso::

    python scripts/produto/etapas_da_pergunta.py                  # pergunta a pergunta
    python scripts/produto/etapas_da_pergunta.py "quantas faltas posso ter?"
    python scripts/produto/etapas_da_pergunta.py --demo           # o roteiro da defesa

No `--demo` cada pergunta espera um Enter, para a fala acompanhar a tela. Encerra com 'sair',
Ctrl-C ou EOF. A saída é ASCII no que é decoração, como nos demais scripts, para não quebrar em
terminal cp1252 no meio da apresentação.
"""
from __future__ import annotations

import sys
import textwrap
import time

from core_chatbot.nucleo.base_conhecimento import BaseConhecimento
from core_chatbot.nucleo.fase1_lexica import AnalisadorLexico, TipoToken
from core_chatbot.nucleo.fase3_semantica import AnalisadorSemantico
from core_chatbot.nucleo.fase2_sintatica import AnalisadorSintatico
from core_chatbot.config import Config
from core_chatbot.corpus import indexar_manual
from core_chatbot.recuperacao import montar_esparsa

LARGURA = 78
SAIR = {"sair", "exit", "quit"}

# O roteiro da defesa: cada pergunta existe para mostrar uma coisa, e a ordem importa.
ROTEIRO = [
    ("Quantas faltas posso ter em Calculo?", "o nucleo reconhece e responde, sem IA nenhuma"),
    ("Quantas faltas posso ter em Cálculo?", "com acento: mesmos simbolos, mesma resposta"),
    ("Qual a capital da Franca?", "fora do Manual: nenhuma regra casa, e nada e aproximado"),
    ("Quantas faltas posso ter e como faco para trancar?", "duas intencoes na mesma frase"),
]

NOMES = {
    TipoToken.PALAVRA_CHAVE: "palavra-chave",
    TipoToken.NUMERO: "numero",
    TipoToken.RUIDO: "ruido (descartado)",
    TipoToken.DESCONHECIDO: "desconhecido (possivel valor de campo)",
}


class Cor:
    """ANSI quando o terminal aceita; strings vazias quando não."""

    def __init__(self, ligado: bool) -> None:
        self.azul = "\033[38;5;33m" if ligado else ""
        self.ambar = "\033[38;5;172m" if ligado else ""
        self.fraco = "\033[38;5;245m" if ligado else ""
        self.forte = "\033[1m" if ligado else ""
        self.fim = "\033[0m" if ligado else ""


def _cores_disponiveis() -> bool:
    if "--sem-cor" in sys.argv or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        import os

        os.system("")  # liga o processamento de sequencias ANSI no console do Windows
    return True


C = Cor(_cores_disponiveis())


def regra(caractere: str = "-") -> None:
    print(C.fraco + caractere * LARGURA + C.fim)


def fase(numero: int, nome: str, transformacao: str) -> None:
    esquerda = f"[{numero}] {nome}"
    espaco = LARGURA - len(esquerda) - len(transformacao)
    print(f"\n{C.forte}{C.azul}{esquerda}{C.fim}{' ' * max(espaco, 1)}{C.fraco}{transformacao}{C.fim}")


def tempo(ms: float) -> None:
    texto = f"{ms:.1f} ms"
    print(f"{' ' * (LARGURA - len(texto))}{C.fraco}{texto}{C.fim}")


def bloco(texto: str, recuo: str = "      ") -> None:
    for linha in textwrap.wrap(texto.strip(), LARGURA - len(recuo)):
        print(recuo + linha)


def montar_nucleo():
    """Etapas 1, 2 e 4 do controlador, sem o plano B: e o caminho que responde sem IA."""
    from core_chatbot.nucleo.tabelas_do_manual import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL

    cfg = Config()
    indice = indexar_manual(cfg)
    base = BaseConhecimento(montar_esparsa(indice, cfg), indice.chunks, cfg.top_k_nucleo)
    return (
        AnalisadorLexico(LEXICO_MANUAL),
        AnalisadorSintatico(GRAMATICA_MANUAL),
        SEMANTICA_MANUAL,
        base,
        cfg.max_intencoes,
    )


def percorrer(pergunta: str, lexico, sintatico, semantico: AnalisadorSemantico, base, maximo: int) -> None:
    """Uma pergunta, fase a fase, com o tempo de cada uma."""
    print()
    regra("=")
    print(f"  {C.forte}PERGUNTA{C.fim}   {pergunta}")
    regra("=")
    total = time.perf_counter()

    # ------------------------------------------------------------------ 1. lexica
    fase(1, "ANALISE LEXICA", "texto -> simbolos")
    t = time.perf_counter()
    todos = lexico.analisar(pergunta, descartar_ruido=False)
    uteis = [tk for tk in todos if tk.tipo is not TipoToken.RUIDO]
    ms_lexico = (time.perf_counter() - t) * 1000
    for tk in todos:
        cor = C.azul if tk.tipo is TipoToken.PALAVRA_CHAVE else C.fraco
        print(f"    {tk.lexema:<16}{cor}{tk.valor:<18}{C.fim}{C.fraco}{NOMES[tk.tipo]}{C.fim}")
    simbolos = sum(1 for tk in todos if tk.tipo is TipoToken.PALAVRA_CHAVE)
    descartados = sum(1 for tk in todos if tk.tipo is TipoToken.RUIDO)
    print(
        f"\n    {C.fraco}{len(todos)} tokens, {simbolos} simbolos do Manual, "
        f"{descartados} descartados como ruido{C.fim}"
    )
    print(f"    {C.fraco}a variacao de escrita morre aqui: acento e caixa sao normalizados{C.fim}")
    tempo(ms_lexico)

    # --------------------------------------------------------------- 2. sintatica
    fase(2, "ANALISE SINTATICA", "simbolos -> intencao")
    t = time.perf_counter()
    reconhecidas = sintatico.analisar_todas(uteis, maximo)
    ms_sintatico = (time.perf_counter() - t) * 1000
    if not reconhecidas:
        print(f"    {C.ambar}nenhuma regra da gramatica casou com esses simbolos{C.fim}")
        print(f"\n    {C.fraco}a pergunta nao pertence a linguagem descrita. No sistema completo{C.fim}")
        print(f"    {C.fraco}ela iria ao plano B, que tem piso de score e pode recusar antes{C.fim}")
        print(f"    {C.fraco}de chamar o modelo. Aqui o percurso termina: e o caminho sem IA.{C.fim}")
        tempo(ms_sintatico)
        regra()
        print(f"  {C.forte}{C.ambar}SEM RESPOSTA PELO NUCLEO{C.fim}   nada foi aproximado")
        regra()
        return
    for r in reconhecidas:
        casados = " ".join(tk.valor for tk in r.casados)
        sobra = " ".join(tk.valor for tk in r.sobra) or "(nada)"
        print(f"    intencao   {C.forte}{C.azul}{r.intencao}{C.fim}")
        print(f"    casaram    {casados}")
        print(f"    sobra      {C.fraco}{sobra}{C.fim}")
        if r is not reconhecidas[-1]:
            print()
    if len(reconhecidas) > 1:
        print(f"\n    {C.fraco}{len(reconhecidas)} intencoes na mesma frase, respondidas na ordem perguntada{C.fim}")
    tempo(ms_sintatico)

    # --------------------------------------------------------------- 3. semantica
    fase(3, "ANALISE SEMANTICA", "intencao -> consulta canonica")
    t = time.perf_counter()
    consultas = [semantico.analisar(r) for r in reconhecidas]
    ms_semantico = (time.perf_counter() - t) * 1000
    for consulta in consultas:
        print(f'    consulta   {C.azul}"{consulta.texto}"{C.fim}')
        for nome, valor in consulta.campos.items():
            print(f"    campo      {nome} = {valor}")
    print(f"\n    {C.fraco}nenhuma palavra do aluno vai para a busca: quem consulta o Manual{C.fim}")
    print(f"    {C.fraco}e a consulta canonica, escrita no vocabulario do documento{C.fim}")
    tempo(ms_semantico)

    # ------------------------------------------------------- 4. consulta ao Manual
    fase(4, "CONSULTA AO MANUAL", "consulta -> trecho")
    t = time.perf_counter()
    respostas = [base.consultar(c) for c in consultas]
    ms_base = (time.perf_counter() - t) * 1000
    achou = False
    for resposta in respostas:
        if not resposta.encontrou:
            print(f"    {C.ambar}a consulta nao trouxe trecho nenhum{C.fim}")
            continue
        achou = True
        ids = ", ".join(str(c.id) for c in resposta.trechos)
        print(f"    {len(resposta.trechos)} trechos recuperados do indice BM25   {C.fraco}(ids {ids}){C.fim}")
        print(f"\n    {C.forte}destaque{C.fim}   {C.fraco}a frase do 1o trecho com mais termos da consulta{C.fim}")
        bloco(resposta.destaque)
        if resposta is not respostas[-1]:
            print()
    tempo(ms_base)

    ms_total = (time.perf_counter() - total) * 1000
    print()
    regra()
    if achou:
        print(
            f"  {C.forte}{C.azul}RESPOSTA PELO NUCLEO{C.fim}   sem modelo de linguagem   "
            f"{C.fraco}total {ms_total:.1f} ms{C.fim}"
        )
    else:
        print(f"  {C.forte}{C.ambar}SEM TRECHO{C.fim}   reconheceu, mas o Manual nao respondeu")
    regra()


def main() -> int:
    # No console, o proprio Python ja escreve Unicode pela API do Windows, e mexer na
    # codificacao so atrapalha; em pipe ou arquivo, UTF-8. Em ambos, nunca quebrar por encoding
    # no meio da demonstracao.
    if sys.stdout.isatty():
        sys.stdout.reconfigure(errors="replace")
    else:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argumentos = [a for a in sys.argv[1:] if a != "--sem-cor"]
    demo = "--demo" in argumentos
    argumentos = [a for a in argumentos if a != "--demo"]

    print("Montando o nucleo (indice do Manual e as tres tabelas)...", flush=True)
    t = time.perf_counter()
    lexico, sintatico, semantico, base, maximo = montar_nucleo()
    print(f"pronto em {time.perf_counter() - t:.1f} s. Sem Ollama e sem cross-encoder.")

    if demo:
        for pergunta, porque in ROTEIRO:
            print(f"\n{C.fraco}proxima: {porque}{C.fim}")
            try:
                input(f"{C.fraco}[Enter]{C.fim} ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            percorrer(pergunta, lexico, sintatico, semantico, base, maximo)
        print(f"\n{C.fraco}fim do roteiro. O mesmo sistema, com tela, esta em servidor.py{C.fim}")
        return 0

    if argumentos:
        percorrer(" ".join(argumentos), lexico, sintatico, semantico, base, maximo)
        return 0

    print("Faca uma pergunta (ou 'sair' para encerrar).")
    while True:
        try:
            pergunta = input("\nVoce> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not pergunta:
            continue
        if pergunta.lower() in SAIR:
            break
        percorrer(pergunta, lexico, sintatico, semantico, base, maximo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
