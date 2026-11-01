# Ingestão dos dados estruturados

## Comportamento implementado

O comando `python -m emporio_ai ingest` lê os seis CSVs de `data/`, valida o conjunto completo e substitui o snapshot do banco local em uma transação. Os arquivos originais não são alterados.

Cada arquivo é lido uma vez para a memória; parsing e hash SHA-256 usam os mesmos bytes. A saída contém contagens e identificação das fontes, sem registros de clientes. O PDF será processado em uma etapa separada de retrieval.

## Validação antes da escrita

- Esquema de colunas e estrutura do CSV; UTF-8 com ou sem BOM.
- Campos obrigatórios, IDs positivos e limites de inteiros do SQLite.
- Chaves primárias e chave composta de itens `(order_id, product_id)` sem duplicatas.
- Preços e totais finitos, não negativos e representáveis em centavos sem arredondamento silencioso.
- Quantidades positivas nos itens e estoque não negativo.
- Status de produto/pedido e flags de promoção conhecidos.
- Datas válidas e especificações como objeto JSON padrão.
- Integridade dos relacionamentos e ao menos um item por pedido.
- No máximo uma promoção ativa por produto; um conflito interrompe a carga para revisão.

Chaves compostas repetidas nos itens são rejeitadas porque não há identificador de linha ou preço histórico que permita interpretar sua intenção com segurança. Caso surjam fontes diferentes, a regra precisa ser reavaliada explicitamente.

## Representação no SQLite

| Fonte CSV | Coluna no banco | Representação |
| --- | --- | --- |
| `price_brl` | `price_cents` | Inteiro em centavos |
| `total_brl` | `total_cents` | Inteiro em centavos, preservando o total do pedido |
| `discount_percent` | `discount_bps` | Inteiro em pontos-base: 10,5% corresponde a 1050 |
| `specs` | `specs_json` | JSON normalizado, mantendo o conteúdo do objeto |
| Campos opcionais vazios do pedido | Mesmos nomes | `NULL` |

Não recalcular o total do pedido usando os preços atuais. Não converter data estimada em data de recebimento. Não alterar status nem corrigir códigos de rastreamento fornecidos.

O banco contém chaves estrangeiras, restrições de domínio e índice único parcial para uma promoção ativa por produto. Há índices para categoria de produto e cliente do pedido. Esses índices apoiam as futuras consultas do agente.

## Transação e recarga

Após a validação, a carga abre uma conexão com chaves estrangeiras habilitadas e inicia `BEGIN IMMEDIATE`. Verifica a versão do banco, prepara o esquema, remove o snapshot anterior na ordem dos relacionamentos, insere as novas linhas e atualiza os metadados. Os valores são enviados por parâmetros SQL. Nomes de tabelas e colunas vêm exclusivamente dos esquemas internos da aplicação.

Somente então executa `COMMIT`. Uma falha durante a escrita produz rollback das linhas e dos metadados. Arquivos inválidos são rejeitados antes de abrir o banco. Repetir a carga substitui os registros, sem acumular cópias.

O comando recusa bancos com tabelas desconhecidas e versões incompatíveis, para evitar sobrescrever outro banco ou executar uma migração implícita. Versão atual do esquema: 1. Quando houver novas tabelas para retrieval ou sessões, a evolução desse contrato precisará ser explícita.

## Proveniência e verificações

`import_metadata` registra versão do esquema, instante de importação em UTC e manifesto com nome, hash e quantidade de linhas por fonte. Não contém o conteúdo das conversas ou das linhas pessoais. O próprio banco contém dados operacionais de clientes e permanece em `runtime/`, ignorado pelo Git.

O script independente `scripts/audit_data.py` mantém uma segunda conferência das fontes e destaca divergências entre preços atuais e totais históricos como avisos. Ele não substitui a validação obrigatória da ingestão.

Verificações executadas nesta etapa:

- 17 testes automatizados com dados sintéticos, incluindo limites de valores, rollback provocado durante uma gravação, isolamento de bancos desconhecidos e recarga.
- Ingestão dos arquivos reais do desafio: 9 categorias, 50 clientes, 65 produtos, 20 pedidos, 22 itens e 25 promoções, totalizando 191 registros operacionais.
- Conferência independente dos hashes e ausência de referências órfãs.

## Limitações

A carga substitui um snapshot inteiro e não implementa CDC ou atualização incremental de ERP. O histórico anterior do snapshot não é arquivado. A base tem poucos registros, portanto o processamento em memória é adequado ao recorte recebido.

Não há autenticação de usuários nem API nesta etapa. As futuras ferramentas devem controlar acesso e minimizar os campos enviados ao modelo. Manter o comando local de ingestão separado das interfaces de atendimento.
