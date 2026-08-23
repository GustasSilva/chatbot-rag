"""Tela de chat do Assistente do Manual do Aluno (interface web do produto).

Mesma pilha do REPL `scripts/produto/assistente_institucional.py`, agora numa interface visual. Quem
responde é o **controlador** (`rag.nlu.dialogo`): o núcleo de compilador entende a pergunta
(léxico → gramática de intenções → parser → semântica) e responde direto do Manual, **sem
passar por modelo de linguagem**; o que a gramática não reconhece cai no **plano B**, o chatbot
RAG de sempre — recuperação **híbrida + reranker**, **piso de score** (recusa fora-de-escopo
antes do LLM) e gerador local no **perfil institucional** do guardrail. Cada resposta mostra de
onde veio. Não é um serviço oficial — mostra um disclaimer e cita o trecho do Manual.

O backend do gerador é escolhido pela `construir_gerador`: com um GGUF configurado (env
`GGUF_MODEL` ou `geracao.caminho_modelo_gguf`), usa o llama-cpp com **saída JSON garantida por
gramática** (a intervenção); senão, usa o Ollama. Uso:
    streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from rag.apresentacao import fontes_de
from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.generation.chatbot import ChatbotRAG
from rag.generation.fabrica import construir_gerador
from rag.nlu.base_conhecimento import BaseConhecimento
from rag.nlu.dialogo import Dialogo, Origem
from rag.pipeline import construir_indice, montar_recuperador_produto

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
DISCLAIMER = (
    "Assistente **não-oficial**, baseado apenas no Manual do Aluno. Pode errar; confirme "
    "informações importantes (prazos, valores, datas) na secretaria ou no Manual oficial."
)
# Como a resposta foi produzida — exibido sob cada mensagem, para o aluno (e para a banca)
# saberem quando houve modelo de linguagem no caminho e quando não houve.
# Os ícones são Material Symbols, que o Streamlit resolve internamente: sem emoji e sem
# requisição de rede.
RODAPE_ORIGEM = {
    Origem.NUCLEO: ":material/menu_book: Trecho do Manual, localizado pela gramática de "
                   "intenções (sem IA).",
    Origem.PLANO_B: ":material/smart_toy: Redigida pelo assistente a partir dos trechos "
                    "consultados.",
}
AVATAR = {"user": ":material/person:", "assistant": ":material/school:"}


@st.cache_resource(show_spinner="Carregando índice e modelos (só na primeira vez)...")
def carregar_dialogo() -> Dialogo:
    """Monta o controlador uma única vez e reaproveita entre perguntas e sessões.

    `@st.cache_resource` garante que o PDF, os embeddings e os modelos (e5 + reranker)
    são carregados apenas na primeira execução — as perguntas seguintes usam o cache.

    O núcleo (léxico → gramática → parser → semântico → Manual) responde o que a gramática
    reconhece; o `ChatbotRAG` entra como **plano B** para o resto, mantendo o guardrail do
    piso de score, o perfil institucional e as saudações exatamente como antes.
    """
    cfg = carregar_config()
    # calcular_densa=False: o produto não usa embeddings, então nem carrega o modelo.
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg, calcular_densa=False)
    recuperador = montar_recuperador_produto(indice, cfg)
    gerador = construir_gerador(cfg.geracao, perfil="institucional")
    plano_b = ChatbotRAG(
        recuperador,
        indice.chunks,
        gerador,
        cfg.geracao.top_k_contexto,
        piso_score=cfg.geracao.piso_score_reranker,
        saudar=True,  # produto de chat livre: responde saudações de forma amigável
    )
    return Dialogo.de_manual(BaseConhecimento(recuperador, indice.chunks), plano_b)


def render_mensagem(msg: dict) -> None:
    """Desenha uma mensagem do histórico (com os trechos consultados, se houver)."""
    with st.chat_message(msg["papel"], avatar=AVATAR[msg["papel"]]):
        st.markdown(msg["texto"])
        if msg.get("origem"):
            st.caption(msg["origem"])
        fontes = msg.get("fontes")
        if fontes:
            rotulo = f"Fontes · {len(fontes)} trechos consultados"
            with st.expander(rotulo, icon=":material/description:"):
                for f in fontes:
                    marca = ":material/check_circle: " if f["citada"] else ""
                    st.markdown(f"{marca}**[{f['n']}]**")
                    st.markdown(f"> {f['texto']}")
                st.caption(
                    ":material/info: O trecho marcado é o que embasou a resposta. "
                    "Confirme no Manual oficial antes de decidir algo importante."
                )


def historico_de(mensagens: list[dict], max_turnos: int = 4) -> list[tuple[str, str]]:
    """Pares (pergunta, resposta) dos últimos turnos, para dar contexto aos follow-ups."""
    pares, pendente = [], None
    for m in mensagens:
        if m["papel"] == "user":
            pendente = m["texto"]
        elif m["papel"] == "assistant" and pendente is not None:
            pares.append((pendente, m["texto"]))
            pendente = None
    return pares[-max_turnos:]


def main() -> None:
    st.set_page_config(
        page_title="Assistente do Manual do Aluno",
        page_icon=":material/menu_book:",
        layout="centered",
    )
    st.title("Assistente do Manual do Aluno")
    st.warning(DISCLAIMER, icon=":material/warning:")

    dialogo = carregar_dialogo()

    # Histórico da conversa vive na sessão do navegador.
    if "mensagens" not in st.session_state:
        st.session_state.mensagens = []
    for msg in st.session_state.mensagens:
        render_mensagem(msg)

    pergunta = st.chat_input("Faça uma pergunta sobre o Manual do Aluno")
    if not pergunta:
        return

    # Histórico dos turnos anteriores (antes de anexar a pergunta atual).
    historico = historico_de(st.session_state.mensagens)
    usuario = {"papel": "user", "texto": pergunta}
    st.session_state.mensagens.append(usuario)
    render_mensagem(usuario)

    with st.chat_message("assistant", avatar=AVATAR["assistant"]):
        with st.spinner("Consultando o Manual..."):
            try:
                resp = dialogo.responder(pergunta, historico=historico)
            except RuntimeError as erro:  # Ollama fora do ar, modelo ausente, etc.
                st.error(str(erro))
                return

    # Toda resposta real mostra os trechos consultados (citando ou não); recusa e saudação
    # ficam sem fontes — montar_fontes já trata esses casos.
    fontes = fontes_de(resp)
    st.session_state.mensagens.append(
        {
            "papel": "assistant",
            "texto": resp.texto,
            # Sem fontes não houve consulta ao Manual (recusa do piso, saudação, não
            # entendi): nesse caso o rodapé de origem só confundiria.
            "origem": RODAPE_ORIGEM[resp.origem] if fontes else "",
            "fontes": fontes,
        }
    )
    st.rerun()


if __name__ == "__main__":
    main()
