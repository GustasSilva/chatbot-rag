"""Front-end de compilador da pergunta do aluno: análise léxica → sintática → semântica.

Núcleo do chatbot na arquitetura nova: quem **entende a pergunta** é esta pipeline, e a LLM
fica como **plano B** (só entra quando a gramática não reconhece a pergunta). Cada fase é um
módulo curto, sem dependência de modelo, testável sozinho.

- ``lexico``:    fase 1 — tokeniza, normaliza e canoniza sinônimos (mecanismo).
- ``gramatica``: fase 2 — a notação das regras de intenção e o que elas denotam (mecanismo).
- ``sintatico``: fase 2 — casa os tokens com as regras e devolve a intenção (mecanismo).
- ``semantico``: fase 3 — preenche campos e monta a consulta canônica (mecanismo).
- ``base_conhecimento``: executa a consulta no Manual pela recuperação já existente.
- ``intencoes``: os dados — léxico, gramática e ações do Manual do Aluno.
"""
