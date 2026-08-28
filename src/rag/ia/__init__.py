"""O modelo de linguagem, plano B do assistente.

Só entra quando o pacote ``compilador`` não reconhece a pergunta. Reúne a interface do
gerador e o backend Ollama (``generator``), a fábrica que o monta (``fabrica``) e a
montagem da resposta a partir dos trechos recuperados (``chatbot``).
"""
