# Arquitetura e decisões

O sistema implementa um agente híbrido: ferramentas para fatos estruturados e recuperação de trechos para políticas. O LLM interpreta a pergunta e escolhe consultas. A aplicação controla acesso, valida argumentos, calcula valores e aplica restrições explícitas do domínio.

## Fluxo implementado

```text
Cliente HTTP / Swagger
  -> FastAPI: validação e token de sessão
  -> histórico limitado + contexto de cliente definido no servidor
  -> recuperação preventiva de políticas quando pertinente
  -> Ollama: seleção de ferramentas
  -> registro fechado: Pydantic + consultas parametrizadas
     -> catálogo / pedido autorizado: SQLite somente de leitura
     -> condições comerciais: centavos e pontos-base
     -> políticas: FTS5/BM25 com seção e página
  -> Ollama: redação final em linguagem natural
  -> validação de referências + guardas de negócio identificadas
  -> resposta, fontes reais, trilha, modelo e versão do prompt
```

## Python e API documentada

FastAPI fornece validação e OpenAPI; `/docs` demonstra criação de sessão e atendimento sem um frontend extenso. O enunciado admite alternativas de interface e não exige simulação de e-commerce. `/catalogo` é uma visualização secundária já existente. O domínio funciona sem a interface HTTP, como mostra o avaliador de cenários.

## SQLite e regras determinísticas

O conjunto recebido contém 191 registros operacionais, compatíveis com banco local. A ingestão valida esquema, relacionamentos, domínios e valores antes de publicar o snapshot em transação. Valores monetários usam `Decimal` na entrada e centavos inteiros nos cálculos; descontos usam pontos-base e arredondamento explícito.

Catálogo, políticas e sessões ficam em três bancos distintos. Reimportar dados não elimina conversas nem o índice de políticas. Consultas de atendimento usam conexão somente de leitura, SQL parametrizado e projeções com campos mínimos. Não existe ferramenta que aceite SQL livre ou escreva em pedidos.

As ferramentas são `search_products`, `get_product`, `quote_payment`, `search_policies` e `get_order_status`. Argumentos extras e tipos incorretos são rejeitados. Categorias são resolvidas pelo servidor a partir do catálogo, sem exigir que o modelo invente IDs. A identidade autorizada de cliente não é um argumento do modelo.

## Retrieval lexical

O manual tem oito páginas. `pypdf` extrai o texto e o indexador agrupa 29 trechos por seção, preservando páginas e hash do original. SQLite FTS5/BM25, normalização de acentos e expansão controlada de termos recuperam texto com baixa complexidade operacional. Seções relacionadas evitam interpretar troca sem garantia ou exceções.

Embeddings não foram necessários para os cenários avaliados. A busca lexical pode falhar em paráfrases novas; uma evolução deve comparar recuperação com o mesmo conjunto de perguntas antes de adicionar infraestrutura. Catálogo e pedidos exigem consultas exatas, não busca vetorial para calcular preços ou autorizar acesso.

## Modelo local e custo

Ollama com `qwen3:8b` executa chamadas de ferramentas no próprio computador. O cliente aceita somente loopback, ignora proxies e recusa modelos de nuvem; o script configura nuvem desativada. Sem API paga, chave, cobrança por tokens ou fallback externo. O custo operacional é o uso do hardware e da energia existentes.

O provedor é separado do agente. Testes de protocolo usam um substituto explicitamente identificado; a avaliação real registra digest, versão do servidor, prompt, parâmetros e revisão. Temperatura zero e seed fixa reduzem variação, sem prometer igualdade entre diferentes GPUs ou versões.

## Evidências e guardas

O prompt em português define persona, escopo e obrigação de consultar fatos. Conteúdo recuperado e mensagens do usuário permanecem dados, sem autoridade de sistema. Fontes são anexadas pelo servidor a partir das ferramentas; referências inexistentes são rejeitadas.

Preços, PIX, disponibilidade por status/estoque, contexto de devolução e ambiguidades conhecidas recebem guardas determinísticas. A trilha distingue chamadas do modelo, recuperação preventiva e regras de negócio. Essa separação preserva auditabilidade: uma resposta com guarda não é apresentada como geração livre do modelo.

Validar a origem não comprova a interpretação de toda frase. O relatório separa checks automáticos de revisão semântica. Faltas de informação levam a esclarecimento ou confirmação humana, sem aprovar devolução, concessão comercial ou pagamento.

## Sessões, privacidade e operação

Tokens aleatórios de conversa têm apenas hashes persistidos; expiram em 24 horas e permitem exclusão. Lease transacional impede concorrência na mesma sessão; um semáforo limita a inferência local a uma por vez. Há limites de mensagens, contexto, rodadas, ferramentas e tempo.

O token de conversa não autentica cliente da loja. Sem identidade confiável, pedidos são bloqueados. A demonstração admite identidade fixa no ambiente do servidor, explicitamente simulada. Ferramentas de pedido filtram simultaneamente pedido e cliente e omitem dados pessoais.

Logs operacionais registram requisição, modelo, prompt, duração e quantidade de chamadas; não registram mensagens completas ou tokens de conversa. Bancos e configurações locais são ignorados pelo Git. A API fica vinculada a `127.0.0.1`.

## Limites do recorte

Sem ERP, WhatsApp, transportadora, processamento de pagamento, alteração de estoque, cancelamento ou reembolso. Os dados são snapshots. Autenticação real, publicação externa, monitoramento de produção e escalabilidade exigiriam outro trabalho. A decisão mantém o foco no agente, nas fontes e na reprodução do desafio.
