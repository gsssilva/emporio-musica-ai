# Recuperação das políticas

O comando `python -m emporio_ai index-policies` extrai o manual com pypdf e cria `runtime/policies.sqlite3`. O índice é separado do catálogo para que uma recarga dos CSVs não elimine as políticas.

A segmentação segue as seções do documento, preserva listas e mantém páginas múltiplas quando uma seção atravessa uma quebra. Cabeçalhos e rodapés repetidos são removidos. O manual fornecido produz 29 trechos: capa e 28 seções. A capa é mantida porque contém informações de contato que divergem da tabela institucional.

Cada fonte contém identificador estável, seção, título, páginas, nome do documento e SHA-256 dos bytes de origem. Os trechos não são reescritos pelo modelo. A indexação constrói um arquivo temporário e substitui o índice somente após finalizar a nova versão.

A busca usa SQLite FTS5 e BM25, com peso maior no título, normalização de acentos, remoção de palavras pouco informativas e expansão pequena de sinônimos em português. Termos são sanitizados antes da expressão FTS. Retorna até cinco resultados primários, acrescidos de seções relacionadas, com limite total de dez.

As relações explícitas preservam contexto importante: arrependimento e exceções; defeito e garantia; pagamento e cumulatividade; contatos institucionais, capa e canal de WhatsApp. Essas relações não decidem direitos do cliente: apenas entregam contexto para uma resposta cuidadosa.

Uma consulta sem correspondência retorna uma lista vazia. Correspondência lexical não é probabilidade de correção. A avaliação inclui perguntas com paráfrases e casos fora de escopo; embeddings só devem ser adicionados se trouxerem melhora demonstrável sobre essa base.

Os testes verificam proveniência, seções, continuidade entre páginas, preservação dos procedimentos numerados, contexto relacionado, consultas inválidas e reconstrução sem duplicatas. O índice não chama um LLM.
