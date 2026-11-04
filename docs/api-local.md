# API local e demonstração

## Executar

Na raiz do projeto, após instalar dependências, importar os CSVs, indexar o manual e iniciar o Ollama com o modelo baixado:

```powershell
.\.venv\Scripts\python.exe -m uvicorn emporio_ai.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

`/` serve o chat visual integrado; `/docs` mantém o Swagger para demonstração técnica do contrato HTTP. O bind limita acesso ao computador local. A aplicação é um protótipo sem autenticação de clientes de produção.

## Interface visual

O chat cria a sessão automaticamente, mostra as fontes realmente retornadas e a trilha da última resposta. CSS, JavaScript e fontes são servidos em `/assets`, na mesma origem da API. Veja [comportamento, limites e testes da interface](interface.md).

## Atendimento

| Método e rota | Comportamento |
| --- | --- |
| `POST /sessions` | Cria conversa, retorna `session_id`; corpo vazio ou `{}` |
| `POST /chat` | Recebe `message`, exige Bearer da conversa |
| `DELETE /sessions/current` | Exclui a conversa e seu histórico |
| `GET /chat/health` | Verifica disponibilidade do modelo, sem inferência |

No Swagger, execute a criação da sessão e copie o token para **Authorize**. Depois envie:

```json
{"message":"Quanto fica o produto 90 no PIX? Posso acumular com a promoção?"}
```

A resposta contém `answer`, `kind`, `sources`, `tool_trace`, `generation_mode`, `request_id`, `provider`, `model`, `prompt_version`, `usage` e `status`. As fontes de política incluem seção, páginas, texto e hash do manual. As de catálogo/pedido identificam o snapshot, sem afirmar integração externa ao vivo.

O campo `generation_mode` identifica geração com LLM, uso de guardas, bloqueio de autorização ou fallback seguro. `trigger=retrieval` indica recuperação preventiva; `trigger=business_rule`, regra explícita de atendimento; chamadas sem esses marcadores foram selecionadas pelo modelo.

Token de conversa não é uma chave de serviço pago nem identidade de cliente. `customer_id` é rejeitado no corpo da sessão e não existe entre os argumentos da ferramenta de pedido. `EMPORIO_DEMO_CUSTOMER_ID` permite identidade fixa simulada somente no servidor; o padrão deixa pedidos bloqueados. Não há rota pública para listar clientes ou consultar pedidos diretamente.

## Erros e limites

Argumentos inválidos retornam 422. Sessões inválidas ou expiradas retornam 401; falta de Bearer é tratada pela segurança do framework. Sessão ocupada retorna 409; limite de uso ou inferência já ocupada, 429. Falhas de modelo ou banco retornam 503 com diagnóstico controlado.

Uma falha de provedor não grava uma resposta inventada no histórico e libera a sessão. Limites do agente podem produzir resposta controlada com status específico, em envelope HTTP válido. Examine também `status`, em vez de interpretar HTTP 200 como garantia de conclusão.

## Catálogo auxiliar

| Rota GET | Comportamento |
| --- | --- |
| `/catalogo` | Visualização HTML secundária |
| `/health` | Disponibilidade do banco e origem do snapshot |
| `/api/categories` | Categorias da fonte |
| `/api/products` | Busca, categoria, orçamento e disponibilidade |
| `/api/products/{product_id}` | Detalhes e preço atual |
| `/api/products/{product_id}/quote` | Cotação determinística |

Filtros da API de catálogo: `query`, `category_id`, `max_price_brl`, `available_only` e `limit`. Cotações aceitam `method` e `installments`, sujeitos às regras do domínio. Orçamento admite até duas casas decimais. Produtos ausentes retornam 404 e indisponíveis para cotação, 409.

O HTML usa recursos locais e insere conteúdo do catálogo com `textContent`. Não representa checkout, atendimento de WhatsApp ou loja publicada.

## Verificação

Testes de integração usam bancos temporários, provedor simulado e cliente HTTP do framework. A avaliação real executa o mesmo serviço de agente com Ollama. A demonstração local também deve verificar saúde, criação de sessão, chat, exclusão e rejeição do token após exclusão.
