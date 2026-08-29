"""Assistente de perguntas e respostas cujo núcleo é um front-end de compilador.

Quem entende a pergunta é o pacote ``compilador``: análise léxica, sintática e semântica sobre
a frase do aluno, em Python puro, sem modelo e sem peso treinado. É a intervenção de Ciência da
Computação do trabalho. O modelo de linguagem, em ``ia``, é o **plano B**, e só entra quando a
gramática não reconhece a pergunta.

O resto é infraestrutura que os dois usam: ``recuperacao`` (BM25 e reranker), ``corpus`` (o PDF
em trechos), ``config``, ``pipeline``, ``apresentacao`` e ``goldset``.

As decisões, com as medições que as sustentam, estão em ``docs/decisoes.md``.
"""
