"""Front-end de compilador da pergunta do aluno: léxico -> sintático -> semântico.

É o núcleo do assistente: quem **entende a pergunta** é esta pipeline, e a LLM fica como plano
B. Cada fase é um módulo curto, sem modelo, testável sozinho; ``intencoes`` traz os dados
(vocabulário, regras e consultas do Manual) e ``dialogo`` orquestra tudo.
"""
