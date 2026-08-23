"""O texto de onde as respostas saem: carregamento, normalizacao e divisao em trechos.

Infraestrutura compartilhada, como ``recuperacao``. O nucleo e o plano B leem do mesmo corpus,
e por isso este pacote nao pertence a nenhum dos dois.

- ``loaders``:  le o PDF e normaliza o texto. A normalizacao e **canonica e anterior ao
  chunking**: colapsa qualquer sequencia de espaco em branco num unico espaco, deixando o
  corpus como uma cadeia continua. E isso que permite ao gold-set guardar o trecho-fonte como
  subcadeia exata, e a mudar aqui invalida todas as medicoes ja feitas.
- ``chunking``: divide o texto normalizado em ``Chunk``, a unidade que os recuperadores
  indexam e que as respostas citam.

O corpus em uso e o Manual do Aluno; os quatro PCDTs do SUS vieram do estudo comparativo. Os
arquivos ficam em ``data/`` e estao fora do Git, reconstruidos pelos scripts de ``goldsets``.
"""
