"""Experimento (REJEITADO): âncora de atribuição no prompt corrige o erro n14 sem regredir?

n14 = atribuição errada (respondeu "professor" onde o gabarito é "aluno"). Hipótese: uma âncora
de atribuição no prompt ("ao dizer QUEM/QUANDO/QUANTO, confirme que o trecho afirma isso sobre o
sujeito; senão recuse") corrigiria. RISCO: reintroduzir over-refusal (o motivo de o perfil
institucional existir). Por isso mede as 50 do gold-set, não só n14.

**RESULTADO: rejeitado.** n14 NÃO foi corrigido (seguiu "professor") e as recusas subiram de
1 (só n07) para 5 (m18, n08, n11, n26 passaram a recusar apesar de terem resposta correta no
baseline). Confirma que n14 é limite de compreensão do 8B (o modelo não está "em dúvida", está
confiantemente errado), não de prompt. Script mantido como registro; a âncora NÃO virou padrão.

Compare com o baseline em outputs/institucional_respostas.txt. Uso: python scripts/exp_prompt_n14.py
"""
from __future__ import annotations

import unicodedata

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.evaluation.goldset import carregar_goldset, construir_relevancia
from rag.generation.chatbot import ChatbotRAG
from rag.generation.generator import GeradorOllama
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
CAMINHO_GOLD = "data/goldsets/institucional.json"
DESTAQUE = {"n14", "n07", "n17", "n04"}

# Prompt testado (âncora de atribuição). Definido aqui, não como perfil do produto, porque foi
# rejeitado — o generator de produção fica só com 'estrito' e 'institucional'.
_PROMPT_ANCORADO = (
    "Você é um assistente sobre o Manual do Aluno. Responda com base nos trechos fornecidos, "
    "podendo sintetizar e inferir a partir do que eles dizem — desde que a resposta se apoie "
    "neles. Não invente dados (datas, números, prazos) que não estejam nos trechos. "
    "Ao afirmar QUEM é responsável por algo, QUANDO algo acontece ou QUANTO vale, verifique que "
    "um trecho afirma isso exatamente sobre o sujeito da pergunta; não transfira a resposta de "
    "um trecho que fala de outra pessoa, papel ou situação. Se nenhum trecho atribuir isso "
    "claramente ao sujeito perguntado, responda 'Não encontrei essa informação nos documentos.' "
    "em vez de deduzir. "
    "Fora esse caso, só responda 'Não encontrei essa informação nos documentos.' se os trechos "
    "realmente não tratarem do assunto perguntado. "
    "Cite a(s) fonte(s) usada(s) indicando o número do trecho entre colchetes, por exemplo [1]. "
    "Responda em português, de forma clara e objetiva."
)


def _recusou(texto: str) -> bool:
    n = "".join(c for c in unicodedata.normalize("NFKD", texto.lower())
                if not unicodedata.combining(c))
    return "nao encontrei" in n


def main() -> int:
    cfg = carregar_config()
    itens = carregar_goldset(CAMINHO_GOLD)
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg)
    relevancia = construir_relevancia(itens, indice.chunks, indice.textos_doc,
                                      cfg.recuperacao.limiar_relevancia)
    rer = montar_reranker(montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"], indice, cfg)
    gerador = GeradorOllama.de_config(cfg.geracao, perfil="institucional")
    gerador._sistema = _PROMPT_ANCORADO  # override do prompt só para este experimento
    chatbot = ChatbotRAG(rer, indice.chunks, gerador, cfg.geracao.top_k_contexto,
                         piso_score=cfg.geracao.piso_score_reranker)

    print(f"Experimento n14 (prompt ancorado) | {len(itens)} perguntas\n")

    recusou_ids, hit = [], 0
    linhas, destaques = [], []
    for item in itens:
        r = chatbot.responder(item.pergunta)
        recuperados = {c.id for c in r.contextos}
        if recuperados & relevancia[item.id]:
            hit += 1
        if _recusou(r.resposta.texto):
            recusou_ids.append(item.id)
        linhas.append(f"[{item.id}] {r.resposta.texto}\n  gabarito: {item.resposta}\n")
        if item.id in DESTAQUE:
            destaques.append(f"[{item.id}] {item.pergunta}\n  Gerada: {r.resposta.texto}\n"
                             f"  Gabarito: {item.resposta}\n")

    with open("outputs/exp_ancorado_respostas.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))

    n = len(itens)
    print(f"recuperação (chunk gold no top-5): {hit}/{n}   (baseline: 49/50)")
    print(f"recusas: {len(recusou_ids)}/{n} -> {recusou_ids}   (baseline institucional: ['n07'])")
    print("\nCasos de destaque (revisar conteúdo):")
    for d in destaques:
        print(d)
    print("Respostas completas em outputs/exp_ancorado_respostas.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
