# API e interface local

## Executar

Na raiz do projeto, com o ambiente instalado e os CSVs importados:

```powershell
.\.venv\Scripts\python.exe -m uvicorn emporio_ai.api:app --host 127.0.0.1 --port 8000
```

A aplicação fica em `http://127.0.0.1:8000` e a documentação OpenAPI em `/docs`. O bind em `127.0.0.1` limita o acesso ao computador local. O servidor não implementa autenticação ou configuração de produção nesta etapa.

O caminho padrão do banco é `runtime/emporio.sqlite3`, relativo ao diretório do terminal. Pode ser alterado pela variável `EMPORIO_DATABASE`. A factory `create_app(database=...)` permite testar com um banco temporário isolado.

## Rotas disponíveis

| Rota GET | Comportamento |
| --- | --- |
| `/` | Interface HTML do catálogo |
| `/health` | Verifica a disponibilidade do banco e informa a origem do snapshot |
| `/api/categories` | Categorias disponíveis na fonte |
| `/api/products` | Busca, categoria, orçamento, disponibilidade e limite |
| `/api/products/{product_id}` | Detalhe de produto com preço, promoção e estoque |
| `/api/products/{product_id}/quote` | Calcula condição de pagamento e parcelamento |

Os filtros de catálogo são `query`, `category_id`, `max_price_brl`, `available_only` e `limit`. O orçamento aceita até duas casas decimais. As cotações aceitam `method` (`pix`, `credit`, `debit` ou `boleto`) e `installments` de 1 a 12, sujeitos às regras comerciais.

Resultados não encontrados retornam 404; argumentos inválidos retornam 422; produto indisponível para nova compra retorna 409. Falhas do banco retornam 503 com diagnóstico controlado, sem caminhos locais ou linhas pessoais.

Não existem rotas públicas para pedidos ou clientes. A exposição de pedidos fica pendente de um contexto de autenticação definido no servidor.

## Interface

A página usa HTML, CSS e JavaScript sem serviços externos, bibliotecas frontend ou fontes remotas. Exibe somente instrumentos ativos com estoque, preço atual, preço original em promoção e condições calculadas no backend. Limita a lista a dez resultados e informa o total encontrado, permitindo refinar a busca.

Conteúdo vindo do catálogo é inserido com `textContent`, sem interpretar HTML. Requisições antigas de busca/cotação não devem substituir resultados mais recentes quando o usuário muda os filtros rapidamente.

## Dependências e verificações

`requirements.lock` registra as versões do ambiente Python validado, incluindo dependências dos testes. As faixas de compatibilidade diretas ficam no `pyproject.toml`.

Foram executados 38 testes de ingestão, consultas, cálculos e API, além de verificações HTTP com o snapshot fornecido e inspeção visual da página local. A integração com LLM e o retrieval do manual ainda não foram implementados.
