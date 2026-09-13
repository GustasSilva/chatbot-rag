"""Controlador: o assistente de ponta a ponta, em ordem de execução. É o arquivo para LER primeiro.

Único módulo que conhece o percurso completo. Nada aqui implementa algoritmo: cada etapa é uma
chamada às funções que fazem o trabalho, na ordem em que o sistema as executa. Quem quiser
entender o assistente inteiro sem abrir doze arquivos lê este, de cima para baixo.

Seis etapas, em dois tempos::

    Dialogo.montar()    uma vez, na partida
      1. DADOS         PDF do Manual -> texto normalizado -> trechos com posição
                       ``pipeline.indexar_manual`` -> ``corpus``
      2. RECUPERAÇÃO   índice invertido BM25 sobre os trechos, sem modelo nenhum
                       ``pipeline.montar_esparsa`` -> ``recuperacao``
      3. PLANO B       reordenador por cross-encoder e gerador local, com piso de score
                       ``pipeline.montar_reordenado`` e ``montar_plano_b`` -> ``ia``
      4. ENTENDIMENTO  as três tabelas do Manual, conferidas uma contra a outra na importação,
                       e as três fases do compilador montadas sobre elas
                       ``Dialogo.de_manual`` -> ``intencoes``, ``lexico``, ``sintatico``,
                       ``semantico``

    dialogo.atender()   uma vez por pergunta
      5. RESPOSTA      léxico, sintático, semântico, consulta ao Manual, e a decisão entre o
                       núcleo e o plano B
                       ``Dialogo.responder`` -> ``base_conhecimento``, ``ia``
      6. ENTREGA       o texto, a origem, as intenções e os trechos recortados para a tela
                       ``apresentacao.fontes_de``

A decisão da etapa 5 é o coração do trabalho: reconheceu, responde do Manual; não reconheceu, ou
reconheceu mas a busca voltou vazia, vai para o plano B. ``plano_b`` é opcional de propósito:
sem ele o assistente responde o que conhece e diz que não entendeu o resto, que é a demonstração
de que o núcleo é o compilador, e não a LLM. :class:`Origem` deixa isso auditável resposta a
resposta.

Os dois níveis de saída existem porque têm públicos diferentes. :meth:`Dialogo.responder`
devolve o que o controlador **decidiu**, e é o que as medições consomem, sem nada de
apresentação no caminho. :meth:`Dialogo.atender` devolve o que a interface **mostra**, com o
recorte das fontes e o tempo gasto, e é o que o servidor e o chat de terminal usam.

As decisões de projeto, com as medições que as sustentam, estão em ``docs/decisoes.md``.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum, auto

from ..apresentacao import ROTULO, fontes_de
from ..config import Config
from ..corpus import Chunk, indexar_manual
from ..ia import ChatbotRAG, Turno, montar_plano_b
from ..recuperacao import montar_esparsa, montar_reordenado
from .base_conhecimento import BaseConhecimento
from .lexico import AnalisadorLexico
from .semantico import AnalisadorSemantico
from .sintatico import AnalisadorSintatico

NAO_ENTENDI = "Não entendi a sua pergunta. Pode reformular?"


def _compor(respondidas: list) -> str:
    """Junta as respostas; havendo mais de uma, rotula cada qual pela sua intenção.

    Com uma só o texto sai limpo, como sempre saiu. O rótulo existe porque duas respostas
    seguidas não dizem sozinhas qual delas responde o quê. O formato vem de ``apresentacao``,
    que é quem também sabe retirá-lo antes de procurar o destaque dentro do trecho.
    """
    if len(respondidas) == 1:
        return respondidas[0][1].destaque
    return "\n\n".join(
        ROTULO.format(reconhecimento.intencao) + resposta.destaque
        for reconhecimento, resposta in respondidas
    )


class Origem(Enum):
    """De onde veio a resposta: a medida de cobertura do núcleo, resposta a resposta."""

    NUCLEO = auto()          # gramática reconheceu e o Manual respondeu, sem IA
    PLANO_B = auto()         # não reconheceu (ou não achou trecho): respondeu a LLM
    NAO_ENTENDIDA = auto()   # não reconheceu e não há plano B ligado


@dataclass(frozen=True)
class RespostaDialogo:
    """O que o controlador decidiu: a saída da etapa 5, sem nada de apresentação."""

    pergunta: str
    texto: str                    # o que se mostra ao aluno
    origem: Origem
    trechos: tuple[Chunk, ...]    # trechos consultados (vazio quando não se entendeu)
    fontes: tuple[int, ...] = ()  # ids dos trechos que embasam a resposta
    intencoes: tuple[str, ...] = ()  # uma por pergunta reconhecida, na ordem da frase


@dataclass(frozen=True)
class Atendimento:
    """O que a interface mostra: a saída da etapa 6, uma pergunta atendida.

    Difere de :class:`RespostaDialogo` em duas coisas, ambas de apresentação: os trechos vêm
    recortados e numerados para a tela, em vez de inteiros, e o tempo gasto vem medido.
    """

    pergunta: str
    texto: str                       # a resposta como o aluno a lê
    origem: Origem
    intencoes: tuple[str, ...] = ()
    fontes: list[dict] = field(default_factory=list)  # recortes, de ``apresentacao.fontes_de``
    ms: int = 0                      # etapas 5 e 6 somadas

    @property
    def sem_ia(self) -> bool:
        """A resposta saiu do Manual pela gramática, sem modelo de linguagem no caminho."""
        return self.origem is Origem.NUCLEO


class Dialogo:
    """Liga as fases do compilador à base de conhecimento, com o plano B como saída.

    Os métodos abaixo estão na ordem em que executam, e não na ordem convencional de Python:
    ``montar`` e ``de_manual`` constroem, ``__init__`` só guarda o que elas montaram, e
    ``atender`` e ``responder`` atendem. É para o arquivo se ler de cima a baixo.
    """

    @classmethod
    def montar(
        cls, cfg: Config | None = None, com_plano_b: bool = True, saudar: bool = True
    ) -> Dialogo:
        """Etapas 1 a 4: do PDF ao assistente pronto para responder.

        ``com_plano_b=False`` deixa o assistente sem modelo de linguagem nenhum, que é a
        demonstração de que quem entende a pergunta é o compilador.

        O núcleo consulta o Manual **só com o BM25**, e o cross-encoder fica no plano B. As três
        medições que levaram a essa separação estão em ``docs/decisoes.md`` §24: no núcleo o
        reordenador troca um acerto de recuperação por quatro de destaque e introduz o único
        falso positivo; no plano B ele leva a recuperação de 45/50 a 49/50 e é a única fonte da
        medida que o piso de score consome.
        """
        cfg = cfg or Config()

        # 1. DADOS: o Manual em trechos de 180 tokens com 45 de sobreposição, cada um sabendo
        #    onde começa e termina no texto original.
        indice = indexar_manual(cfg)

        # 2. RECUPERAÇÃO do núcleo: índice invertido BM25, sem modelo e sem peso treinado.
        esparsa = montar_esparsa(indice, cfg)
        base = BaseConhecimento(esparsa, indice.chunks, cfg.top_k_nucleo)

        # 3. PLANO B, montado antes porque o controlador o recebe pronto. O BM25 da etapa 2 é
        #    reaproveitado como base do reordenador, para não indexar o Manual duas vezes.
        plano_b = None
        if com_plano_b:
            plano_b = montar_plano_b(
                montar_reordenado(indice, cfg, base=esparsa), indice, cfg, saudar
            )

        # 4. ENTENDIMENTO: as três tabelas e as fases do compilador sobre elas.
        return cls.de_manual(base, plano_b, cfg.max_intencoes)

    @classmethod
    def de_manual(
        cls,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
        max_intencoes: int = 3,
    ) -> Dialogo:
        """Etapa 4 sozinha: o controlador com o léxico, a gramática e as ações do Manual.

        Separada de :meth:`montar` porque as medições trocam a etapa 2 por uma variante (só
        BM25, ou com o reordenador por cima) e precisam entrar aqui com a base já montada.
        """
        from .intencoes import GRAMATICA_MANUAL, LEXICO_MANUAL, SEMANTICA_MANUAL

        return cls(
            AnalisadorLexico(LEXICO_MANUAL),
            AnalisadorSintatico(GRAMATICA_MANUAL),
            SEMANTICA_MANUAL,
            base,
            plano_b,
            max_intencoes,
        )

    def __init__(
        self,
        lexico: AnalisadorLexico,
        sintatico: AnalisadorSintatico,
        semantico: AnalisadorSemantico,
        base: BaseConhecimento,
        plano_b: ChatbotRAG | None = None,
        max_intencoes: int = 3,
    ) -> None:
        """Guarda o que :meth:`montar` e :meth:`de_manual` construíram. Não constrói nada."""
        self._max_intencoes = max_intencoes
        self._lexico = lexico
        self._sintatico = sintatico
        self._semantico = semantico
        self._base = base
        self._plano_b = plano_b

    def atender(
        self,
        pergunta: str,
        historico: list[Turno] | None = None,
        n_janela: int = 320,
    ) -> Atendimento:
        """Etapas 5 e 6: a pergunta vira resposta, e a resposta vira o que aparece na tela.

        É o que as interfaces chamam. ``historico`` serve só ao plano B, porque o núcleo é sem
        estado por construção, e quantos turnos guardar é política de quem chama. ``n_janela``
        é o tamanho do recorte de cada trecho citado: a tela do navegador cabe mais que o
        terminal.
        """
        inicio = time.perf_counter()
        resposta = self.responder(pergunta, historico=historico or None)
        return Atendimento(
            pergunta=pergunta,
            texto=resposta.texto,
            origem=resposta.origem,
            intencoes=resposta.intencoes,
            # Vazio quando não houve consulta ao Manual: recusa do piso, saudação ou não entendi.
            fontes=fontes_de(resposta, n_janela),
            ms=round((time.perf_counter() - inicio) * 1000),
        )

    def responder(
        self, pergunta: str, historico: list[Turno] | None = None
    ) -> RespostaDialogo:
        """Etapa 5: responde pelo núcleo quando a gramática reconhece; senão, recorre ao plano B.

        Uma pergunta pode trazer mais de uma intenção; cada uma é consultada no Manual e as
        respostas saem na ordem em que foram perguntadas. Basta uma intenção encontrar trecho
        para o núcleo responder: só cai no plano B quando nenhuma encontra.

        ``historico`` serve só ao plano B: o núcleo é sem estado por construção, cada intenção
        se resolve na própria frase.
        """
        reconhecidas = self._sintatico.analisar_todas(
            self._lexico.analisar(pergunta), self._max_intencoes
        )
        respondidas = [
            (reconhecimento, resposta)
            for reconhecimento in reconhecidas
            for resposta in [self._base.consultar(self._semantico.analisar(reconhecimento))]
            if resposta.encontrou
        ]
        if not respondidas:
            return self._recorrer_ao_plano_b(pergunta, historico)

        # Ordem de leitura, e não de reconhecimento: o aluno lê na ordem em que perguntou.
        respondidas.sort(key=lambda par: min(t.inicio for t in par[0].casados))
        trechos: list[Chunk] = []
        for _, resposta in respondidas:  # sem repetir trecho que duas intenções trouxeram
            trechos += [t for t in resposta.trechos if t.id not in {x.id for x in trechos}]

        return RespostaDialogo(
            pergunta=pergunta,
            texto=_compor(respondidas),
            origem=Origem.NUCLEO,
            trechos=tuple(trechos),
            # O destaque de cada intenção sai do 1º trecho dela: são esses que embasam.
            fontes=tuple(resposta.trechos[0].id for _, resposta in respondidas),
            intencoes=tuple(r.intencao for r, _ in respondidas),
        )

    def _recorrer_ao_plano_b(
        self, pergunta: str, historico: list[Turno] | None
    ) -> RespostaDialogo:
        if self._plano_b is None:
            return RespostaDialogo(pergunta, NAO_ENTENDI, Origem.NAO_ENTENDIDA, ())
        resposta = self._plano_b.responder(pergunta, historico=historico)
        return RespostaDialogo(
            pergunta=pergunta,
            texto=resposta.texto,
            origem=Origem.PLANO_B,
            trechos=tuple(resposta.trechos),
            fontes=tuple(resposta.fontes),
        )
