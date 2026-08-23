"""O modelo de linguagem, plano B do assistente.

So entra quando o pacote ``compilador`` nao reconhece a pergunta. Reune a interface do
gerador (``generator``), a implementacao local (``llamacpp``), a montagem da resposta a
partir dos trechos recuperados (``chatbot``) e a saida estruturada (``json_estruturado``).

Inclui tambem ``gramatica_citacao``, a gramatica regular e o automato que restringem a
**saida** do modelo. Isso e tecnica de compilador aplicada do outro lado: foi a intervencao
anterior ao pivo de 13/08/2026 e hoje vale como resultado preliminar.
"""
