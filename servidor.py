"""Servidor do Assistente do Manual do Aluno: serve a página e responde as perguntas.

Só biblioteca padrão do Python: ``http.server`` no lugar de um framework web. A página é um
arquivo único em ``web/index.html``; este módulo entrega ela e expõe um endereço que recebe a
pergunta e devolve a resposta em JSON.

    python servidor.py            (abre em http://localhost:8000)

O controlador é montado uma vez, na partida, e reaproveitado em todas as perguntas. Um cadeado
serializa as respostas: o modelo de reordenação não é feito para uso simultâneo, e um assistente
local não precisa atender duas pessoas ao mesmo tempo.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from rag.apresentacao import fontes_de
from rag.config import carregar_config
from rag.corpus.loaders import carregar_pdf
from rag.ia.chatbot import ChatbotRAG
from rag.ia.fabrica import construir_gerador
from rag.compilador.base_conhecimento import BaseConhecimento
from rag.compilador.dialogo import Dialogo
from rag.pipeline import construir_indice, montar_recuperador_produto

CAMINHO_PDF = "data/raw/manual_aluno_unip_2026.pdf"
PAGINA = Path(__file__).parent / "web" / "index.html"
PORTA = 8000


def montar_dialogo() -> Dialogo:
    """Núcleo de compilador respondendo do Manual, com o chatbot RAG como plano B."""
    cfg = carregar_config()
    indice = construir_indice({"manual": carregar_pdf(CAMINHO_PDF)}, cfg, calcular_densa=False)
    recuperador = montar_recuperador_produto(indice, cfg)
    plano_b = ChatbotRAG(
        recuperador,
        indice.chunks,
        construir_gerador(cfg.geracao, perfil="institucional"),
        cfg.geracao.top_k_contexto,
        piso_score=cfg.geracao.piso_score_reranker,
        saudar=True,
    )
    dialogo = Dialogo.de_manual(BaseConhecimento(recuperador, indice.chunks), plano_b)
    # Primeira inferência do cross-encoder custa alguns segundos. Pagando aqui, a primeira
    # pergunta de quem abre a tela já responde no tempo normal (~1,3 s).
    dialogo.responder("quantas faltas posso ter?")
    return dialogo


class Assistente(BaseHTTPRequestHandler):
    dialogo: Dialogo
    cadeado = threading.Lock()
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self._enviar(200, "text/html; charset=utf-8", PAGINA.read_bytes())
        else:
            self._enviar(404, "text/plain; charset=utf-8", b"pagina nao encontrada")

    def do_POST(self) -> None:
        if self.path != "/perguntar":
            return self._json(404, {"erro": "endereco nao encontrado"})

        try:
            corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            pedido = json.loads(corpo or b"{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"erro": "pedido malformado"})

        pergunta = (pedido.get("pergunta") or "").strip()
        if not pergunta:
            return self._json(400, {"erro": "escreva uma pergunta"})
        historico = [tuple(par) for par in pedido.get("historico") or []]

        inicio = time.perf_counter()
        try:
            with self.cadeado:
                resposta = self.dialogo.responder(pergunta, historico=historico or None)
        except RuntimeError as erro:  # gerador local fora do ar, modelo ausente
            return self._json(503, {"erro": str(erro)})

        self._json(200, {
            "texto": resposta.texto,
            "origem": resposta.origem.name,
            "intencao": resposta.intencao,
            "ms": round((time.perf_counter() - inicio) * 1000),
            "fontes": fontes_de(resposta),
        })

    def _json(self, codigo: int, dados: dict) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(codigo, "application/json; charset=utf-8", corpo)

    def _enviar(self, codigo: int, tipo: str, corpo: bytes) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def log_message(self, formato: str, *args) -> None:
        """Silencia o log de uma linha por requisição, que polui o terminal da demonstração."""


def main() -> int:
    print("Carregando índice e modelo (uma vez só)...", flush=True)
    Assistente.dialogo = montar_dialogo()
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), Assistente)
    print(f"Assistente no ar em http://localhost:{PORTA}  (Ctrl-C encerra)", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
