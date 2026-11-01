# Arquitetura proposta

Status: pacote Python, ingestão transacional, consultas de catálogo/pedidos e cálculos comerciais implementados. API de catálogo e interface local também estão implementadas. Recuperação das políticas, agente com ferramentas e API de chat também estão implementados. A avaliação ampliada do modelo está em andamento. Detalhes da etapa disponível em [ingestão](ingestao.md).

## Abordagem

Um agente híbrido: ferramentas tipadas para dados estruturados e retrieval das políticas para conhecimento textual. A aplicação valida argumentos, autoriza acesso e calcula condições comerciais; o LLM interpreta a conversa, escolhe consultas e redige a resposta apoiada nas evidências.

Fluxo previsto:

```text
Chat / cliente HTTP
  -> API FastAPI: validação e contexto de sessão
  -> Serviço de conversa: histórico limitado e execução do agente
  -> LLM: seleção de ferramentas
  -> Registro fechado de ferramentas
     -> Catálogo / pedidos: consultas SQLite parametrizadas
     -> Condições comerciais: cálculo determinístico
     -> Políticas: busca textual e trechos com origem
  -> LLM: resposta fundamentada
  -> API: mensagem, fontes e metadados operacionais mínimos
```

## Decisões e alternativas

### Python, FastAPI e uma interface simples

FastAPI fornece validação por tipos e documentação OpenAPI. Uma API com um chat simples é suficiente para demonstrar integração full-stack sem desviar o prazo para um frontend complexo. O domínio e o agente devem funcionar independentemente da interface.

Referência: [documentação oficial do FastAPI](https://fastapi.tiangolo.com/).

### SQLite e consultas controladas

O volume de dados cabe confortavelmente em um banco local. SQLite reduz dependências operacionais e permite testes com banco temporário. A ingestão deve validar esquema, tipos, status, relacionamentos e duplicatas antes de publicar uma nova versão local dos dados, em transação.

Não expor SQL arbitrário ao modelo. O LLM recebe ferramentas como `search_products`, `get_product`, `get_order_status`, `quote_payment` e `search_policies`. Cada consulta possui parâmetros validados e limite de resultados. IDs e permissões vêm do contexto confiável do servidor quando necessário.

Valores financeiros devem ser convertidos com `Decimal` e persistidos em centavos inteiros. Definir e testar arredondamento em centavos. Preservar valores originais e a origem do desconto. O cálculo não deve acumular PIX com promoção.

### Retrieval textual antes de embeddings

O manual tem oito páginas. A primeira versão deve extrair texto com `pypdf`, remover cabeçalhos/rodapés repetidos e separar conteúdo por seções, preservando página e seção. Se uma seção atravessar páginas, reter todas as páginas de origem.

Busca lexical com SQLite FTS5/BM25, normalização de acentos e expansão controlada de sinônimos é uma hipótese inicial a validar. Recuperar seções relacionadas quando houver dependência, como trocas, exceções e garantia. Caso a avaliação mostre falhas relevantes de paráfrase, comparar embeddings usando os mesmos casos antes de aumentar a infraestrutura.

Evitar usar busca vetorial para calcular preços, localizar um pedido autorizado ou filtrar estoque. Os dados operacionais exigem consulta exata.

Referências: [FTS5 e BM25](https://www.sqlite.org/fts5.html), [extração de texto com pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).

### Modelo e provedor

O provedor é exclusivamente local: Ollama com `qwen3:8b`, sem chave de API, sem cobrança por tokens e sem fallback pago. O endpoint é restrito a loopback e o processo inicia com nuvem desativada. O cliente usa a API nativa de chat e chamadas de ferramentas do Ollama. A etapa final solicita um JSON estruturado, validado no servidor.

O código separa provedor, agente, registro de ferramentas e sessões. Testes usam um provedor simulado para validar o protocolo sem depender da GPU; a avaliação do modelo real é separada e identificada. A qualidade não é presumida pelo tamanho do modelo.

Detalhes de custos, limites, autenticação simulada e comportamento de falha estão em [agente local](agente.md).

### Persona, evidências e recusas

Prompt do sistema curto, versionado e em português: persona da loja, escopo, obrigação de consultar fatos comerciais, tratamento de lacunas e limites de ação. Manter conhecimento de negócio nas fontes e regras de cálculo no domínio, evitando duplicação de tabelas de preços no prompt.

Responder com fonte quando uma política fundamentar a resposta. Um identificador de fonte deve corresponder a um trecho realmente recuperado. Em ausência de evidência, pedir esclarecimento ou indicar confirmação com a equipe. Uma recusa de assunto fora de escopo deve ser educada e oferecer ajuda sobre a loja.

### Histórico, privacidade e observabilidade

Sessões isoladas, identificadores aleatórios e limite de mensagens/contexto. O protótipo local não deve expor dados de pedidos como se houvesse autenticação de produção. Ferramentas de pedidos filtram por cliente autorizado e retornam apenas o necessário; nunca listar a base de clientes ao LLM.

Logs devem conter ID de requisição, duração, ferramenta, resultado operacional, uso de tokens quando disponível e erros classificados. Não registrar conteúdo integral de conversas, e-mails, telefones ou chaves. Definir expiração e exclusão do histórico quando a persistência for implementada.

## Limites deliberados da primeira versão

Sem integração real de WhatsApp, transportadora, pagamento ou ERP. Sem alteração de estoque, cancelamento de pedido ou concessão de reembolso. Sem previsão de frete inventada. Sem múltiplos agentes ou framework de orquestração complexo no escopo inicial.

Consultar a base local significa acessar o último snapshot importado. A resposta e a documentação devem distinguir isso de uma integração externa em tempo real.
