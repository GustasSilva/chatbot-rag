"""Sondagem fora da amostra: perguntas que nem as regras nem o piso de score conheciam.

O gold-set e o conjunto adversarial já existiam quando as regras foram escritas, e o
adversarial serviu para ajustar uma regra (``decisoes.md`` §8 e o commit 589ab22). Esta
sondagem mede o sistema, depois de pronto, contra 30 perguntas novas em registro informal
(abreviação, sem acento, erro de digitação) e 12 presumidas fora do escopo.

Três partes, na ordem do percurso:

1. **núcleo**: quantas das 30 a gramática reconhece, e com que intenção (conferida a olho,
   porque a sondagem não tem trecho-gabarito);
2. **piso**: das legítimas que o núcleo não reconhece, quantas o piso recusaria por engano; das
   fora do escopo, quantas ele recusa;
3. **sistema completo**: as fora do escopo que passam pelo piso vão ao modelo, para ver se ele
   recusa ou responde.

Exige Ollama + o modelo só na parte 3. Uso: python scripts/produto/sondagem_fora_da_amostra.py
"""
from __future__ import annotations

from core_chatbot.nucleo.controlador import Dialogo
from core_chatbot.nucleo.tabelas_do_manual import GRAMATICA_MANUAL, LEXICO_MANUAL
from core_chatbot.nucleo.fase1_lexica import AnalisadorLexico
from core_chatbot.nucleo.fase2_sintatica import AnalisadorSintatico
from core_chatbot.config import Config
from core_chatbot.corpus import indexar_manual
from core_chatbot.recuperacao import montar_reordenado

# A: mesmo assunto do gold-set, outra redação. B: assunto do Manual que o gold-set não cobre.
LEGITIMAS = [
    ("A", "qnts faltas eu posso ter numa materia sem reprovar?"),
    ("A", "se eu faltar mais de 25% eu reprovo direto?"),
    ("A", "como faço pra trancar o curso?"),
    ("A", "trancamento vale por quanto tempo?"),
    ("A", "quero cancelar minha matricula, oq eu faço"),
    ("A", "perdi a prova, posso fazer substitutiva?"),
    ("A", "tirei 6 na media, vou pra exame?"),
    ("A", "qual nota preciso no exame pra passar"),
    ("A", "estagio é obrigatorio no meu curso?"),
    ("A", "esqueci minha carteirinha, consigo entrar na facul?"),
    ("A", "da pra pedir transferencia pra outra faculdade?"),
    ("A", "preciso ir na colação de grau pra pegar o diploma?"),
    ("A", "o diploma vem digital ou impresso?"),
    ("A", "reprovei em uma materia, posso fazer em dependencia?"),
    ("A", "quem controla minhas faltas, eu ou o professor?"),
    ("B", "como funciona o aproveitamento de materias que eu ja fiz em outra faculdade?"),
    ("B", "o que acontece se eu levar trote pesado de veterano?"),
    ("B", "posso fumar dentro do campus?"),
    ("B", "como faço pra ser monitor de uma disciplina?"),
    ("B", "tem intercambio pra outro pais?"),
    ("B", "como mudo meu endereço no cadastro?"),
    ("B", "qual o prazo pra fazer a rematricula?"),
    ("B", "como peço segunda via de documento?"),
    ("B", "posso usar bermuda na aula de laboratorio?"),
    ("B", "quanto tempo posso ficar com o livro da biblioteca?"),
    ("B", "como renovo o emprestimo do livro?"),
    ("B", "o que é jubilamento?"),
    ("B", "tem ferias no meio do ano?"),
    ("B", "como funciona a iniciação cientifica?"),
    ("B", "posso mudar de turno do noturno pro matutino?"),
]

FORA = [
    "quanto custa a mensalidade de engenharia?",
    "qual o email do coordenador de computação?",
    "a biblioteca abre no sabado?",
    "tem vaga de estacionamento pra moto?",
    "qual a data da formatura desse ano?",
    "o restaurante universitario serve almoço?",
    "quais cursos de pos a unip oferece?",
    "qual meu saldo de horas complementares?",
    "minha matricula ta ativa?",
    "quando sai minha nota da NP2?",
    "qual o telefone da secretaria de goiania?",
    "a unip tem curso de medicina?",
]


def main() -> int:
    cfg = Config()
    lexico = AnalisadorLexico(LEXICO_MANUAL)
    sintatico = AnalisadorSintatico(GRAMATICA_MANUAL)

    print("1. NUCLEO: reconhecimento das 30 legitimas novas\n")
    reconhecidas = {"A": 0, "B": 0}
    nao_reconhecidas: list[str] = []
    for grupo, pergunta in LEGITIMAS:
        intencoes = [r.intencao for r in sintatico.analisar_todas(lexico.analisar(pergunta), cfg.max_intencoes)]
        if intencoes:
            reconhecidas[grupo] += 1
        else:
            nao_reconhecidas.append(pergunta)
        print(f"  [{grupo}] {'SIM' if intencoes else 'nao'}  {pergunta}  -> {intencoes}")
    total = reconhecidas["A"] + reconhecidas["B"]
    print(f"\n  A (assunto do gold-set, outra redacao): {reconhecidas['A']}/15")
    print(f"  B (assunto fora do gold-set):           {reconhecidas['B']}/15")
    print(f"  total: {total}/30")

    print(f"\n2. PISO ({cfg.piso_score}) sobre a medida do reordenador\n")
    reordenador = montar_reordenado(indexar_manual(cfg), cfg)

    def melhor(pergunta: str) -> float:
        resultado = reordenador.buscar(pergunta, 1)
        return resultado[0].score if resultado else float("-inf")

    recusadas_indevidas = 0
    for pergunta in nao_reconhecidas:
        score = melhor(pergunta)
        recusada = score < cfg.piso_score
        recusadas_indevidas += recusada
        print(f"  legitima {score:7.2f} {'RECUSADA' if recusada else 'passa   '}  {pergunta}")
    passam: list[str] = []
    for pergunta in FORA:
        score = melhor(pergunta)
        if score >= cfg.piso_score:
            passam.append(pergunta)
        print(f"  fora     {score:7.2f} {'recusada' if score < cfg.piso_score else 'PASSA   '}  {pergunta}")
    print(f"\n  legitimas recusadas indevidamente: {recusadas_indevidas}/{len(nao_reconhecidas)}")
    print(f"  fora do escopo recusadas pelo piso: {len(FORA) - len(passam)}/{len(FORA)}")

    print("\n3. SISTEMA COMPLETO nas que passam pelo piso (revisar a mao se o Manual responde)\n")
    dialogo = Dialogo.montar(cfg, saudar=False)
    for pergunta in passam:
        resposta = dialogo.responder(pergunta)
        print(f"  [{resposta.origem.name}] {pergunta}\n      -> {resposta.texto[:300]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
