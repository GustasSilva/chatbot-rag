"""Tela de chat do Assistente do Manual do Aluno (interface web do produto).

Mesma pilha do REPL `scripts/assistente_institucional.py`, agora numa interface visual:
recuperação **híbrida + reranker**, **piso de score** (recusa fora-de-escopo antes do LLM) e
gerador local (Ollama, temperatura 0) no **perfil institucional** do guardrail. Não é um
serviço oficial — mostra um disclaimer e cita o trecho do Manual em cada resposta.

Exige Ollama no ar + o modelo do config. Uso:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.chatbot import ChatbotRAG
from rag.generation.generator import GeradorOllama
from rag.pipeline import construir_indice, montar_reranker, montar_recuperadores

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
DISCLAIMER = (
    "Assistente **não-oficial**, baseado apenas no Manual do Aluno. Pode errar; confirme "
    "informações importantes (prazos, valores, datas) na secretaria ou no Manual oficial."
)


@st.cache_resource(show_spinner="Carregando índice e modelos (só na primeira vez)...")
def carregar_chatbot() -> ChatbotRAG:
    """Monta o chatbot uma única vez e reaproveita entre perguntas e sessões.

    `@st.cache_resource` garante que o PDF, os embeddings e os modelos (e5 + reranker)
    são carregados apenas na primeira execução — as perguntas seguintes usam o cache.
    """
    cfg = carregar_config()
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg)
    hibrida = montar_recuperadores(indice, cfg, incluir=["hibrida"])["hibrida"]
    recuperador = montar_reranker(hibrida, indice, cfg)
    gerador = GeradorOllama.de_config(cfg.geracao, perfil="institucional")
    return ChatbotRAG(
        recuperador,
        indice.chunks,
        gerador,
        cfg.geracao.top_k_contexto,
        piso_score=cfg.geracao.piso_score_reranker,
        saudar=True,  # produto de chat livre: responde saudações de forma amigável
    )


def preview(texto: str, n: int = 320) -> str:
    """Compacta um trecho do Manual para exibição na lista de fontes."""
    t = " ".join(texto.split())
    return t if len(t) <= n else t[:n].rstrip() + "..."


def eh_recusa(texto: str) -> bool:
    """True para a recusa canônica — nesse caso não há fonte a exibir."""
    return "não encontrei essa informação" in texto.strip().lower()


def montar_fontes(resp) -> list[dict]:
    """Lista os trechos consultados na resposta, numerados como o `[n]` que o LLM cita.

    Mostra TODOS os trechos recuperados (o contexto que o modelo viu), não só os citados —
    assim o `[n]` do texto aponta para o trecho de mesmo número e a evidência fica completa.
    Em recusa não há o que embasar, então devolve vazio (nenhum painel de fontes).
    """
    if eh_recusa(resp.resposta.texto):
        return []
    citados = set(resp.resposta.fontes)
    return [
        {"n": n, "citada": ctx.id in citados, "texto": preview(ctx.texto)}
        for n, ctx in enumerate(resp.contextos, start=1)
    ]


def render_mensagem(msg: dict) -> None:
    """Desenha uma mensagem do histórico (com os trechos consultados, se houver)."""
    with st.chat_message(msg["papel"]):
        st.markdown(msg["texto"])
        fontes = msg.get("fontes")
        if fontes:
            with st.expander(f"Fontes — {len(fontes)} trechos consultados (✓ = citado na resposta)"):
                for f in fontes:
                    marca = "✓ " if f["citada"] else ""
                    st.markdown(f"**{marca}[{f['n']}]**")
                    st.markdown(f"> {f['texto']}")
                st.caption("Confirme no Manual oficial antes de decidir algo importante.")


def main() -> None:
    st.set_page_config(page_title="Assistente do Manual do Aluno", page_icon="📘")
    st.title("📘 Assistente do Manual do Aluno")
    st.warning(DISCLAIMER, icon="⚠️")

    chatbot = carregar_chatbot()

    # Histórico da conversa vive na sessão do navegador.
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []
    for msg in st.session_state.mensagens:
        render_mensagem(msg)

    pergunta = st.chat_input("Faça uma pergunta sobre o Manual do Aluno")
    if not pergunta:
        return

    usuario = {"papel": "user", "texto": pergunta}
    st.session_state.mensagens.append(usuario)
    render_mensagem(usuario)

    with st.chat_message("assistant"):
        with st.spinner("Consultando o Manual..."):
            try:
                resp = chatbot.responder(pergunta)
            except RuntimeError as erro:  # Ollama fora do ar, modelo ausente, etc.
                st.error(str(erro))
                return

    # Toda resposta real mostra os trechos consultados (citando ou não); recusa e saudação
    # ficam sem fontes — montar_fontes já trata esses casos.
    st.session_state.mensagens.append(
        {"papel": "assistant", "texto": resp.resposta.texto, "fontes": montar_fontes(resp)}
    )
    st.rerun()


if __name__ == "__main__":
    main()
