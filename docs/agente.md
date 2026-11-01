# Agente local e API de atendimento

## Escopo e custo

A aplicação usa exclusivamente Ollama em loopback e o modelo local `qwen3:8b`. Não precisa de chave de API, cartão, assinatura ou créditos por mensagem. Não existe fallback para um provedor pago. O download inicial requer conexão à internet e espaço em disco; a inferência usa o computador onde o serviço está em execução.

O endpoint do provedor aceita somente HTTP em `127.0.0.1`, `localhost` ou `::1`, sem credenciais, caminhos remotos ou tags de modelo de nuvem. O script de inicialização configura `OLLAMA_NO_CLOUD=1`. Variáveis de proxy são ignoradas pelo cliente HTTP para manter as mensagens no serviço local.

O Qwen3 8B foi escolhido pelo suporte a ferramentas e pela possibilidade de execução na GPU disponível. O modelo distribuído pelo catálogo possui quantização Q4_K_M e download de aproximadamente 5,2 GB. Isso não garante qualidade: as respostas precisam ser avaliadas nos casos da loja. Em máquinas sem GPU ou com menos memória, a latência pode ser maior.

Referências: [Ollama local](https://docs.ollama.com/quickstart), [Qwen3 8B](https://ollama.com/library/qwen3:8b), [desabilitar nuvem](https://docs.ollama.com/faq), [chamadas de ferramentas](https://docs.ollama.com/capabilities/tool-calling).

## Fluxo do agente

1. Recebe mensagem e um histórico curto da sessão, controlado pelo servidor.
2. O modelo escolhe uma das cinco ferramentas do registro fechado.
3. Pydantic valida tipos, limites e campos extras. O servidor executa a consulta ou cálculo.
4. O resultado e suas fontes são enviados ao modelo como dados de ferramenta.
5. O modelo pode consultar novamente, dentro dos limites de execução. Uma pergunta de pagamento exige cotação; uma solicitação de alternativas exige consulta das opções disponíveis.
6. Uma etapa final sem ferramentas redige a mensagem natural. A estrutura JSON da API e a lista de fontes são montadas e validadas pelo servidor, em vez de depender da classificação do modelo.
7. A aplicação rejeita referências inexistentes, valida evidência e aplica barreiras de consistência para ambiguidades conhecidas do manual. Uma condição comercial ambígua permanece marcada para confirmação humana.

Ferramentas: `search_products`, `get_product`, `quote_payment`, `search_policies` e `get_order_status`. Não há ferramenta genérica de SQL, código, rede, escrita comercial ou listagem de clientes.

O prompt está versionado em `src/emporio_ai/prompts/system.txt`. Cada resposta identifica o hash abreviado desse prompt, modelo, provedor e ferramentas utilizadas. O prompt trata a persona, as fontes, os limites do atendimento e as ambiguidades do manual. Conteúdo de usuário e de fontes não recebe autoridade de instrução do sistema.

Antes da seleção de ferramentas, dúvidas reconhecidas sobre políticas recebem recuperação lexical preventiva. O registro diferencia esse passo por `trigger=retrieval`; ele não é apresentado como uma escolha do LLM. Perguntas de pedido sem identidade autorizada são bloqueadas pelo servidor antes da inferência.

A busca de instrumentos aceita palavras naturais em `query` e orçamento em reais em `max_price_brl`. O servidor converte valores para centavos e resolve categorias a partir dos dados. Isso evita que o modelo invente IDs de categoria ou faça conversões monetárias. IDs de produto continuam sendo validados como inteiros.

Guardas de negócio são identificadas por `trigger=business_rule`: frete exatamente em R$ 500 quando a fonte só define acima/abaixo; estoque positivo de produto descontinuado; contexto de garantia e previsões históricas. Essas barreiras implementam restrições explícitas do cenário, sem executar transações comerciais. O campo `generation_mode` distingue inferência, bloqueio de autorização e respostas com guardas.

## Limites e falhas

Máximo de seis rodadas de seleção de ferramentas e oito chamadas por mensagem, com uma etapa final de formatação. Mensagens têm limite de 2.000 caracteres. O contexto recente contém até três pares de mensagens e um limite global de caracteres. A saída do modelo possui limite de tokens.

O prazo de execução é limitado no agente, e cada requisição HTTP possui timeout. Não há retentativa automática ilimitada. Falha do provedor retorna 503, preserva o histórico anterior e libera a sessão. Estouro de ferramentas ou referências inválidas produz uma resposta controlada, sem apresentar conteúdo inventado como resultado confirmado.

O aquecimento inicial do modelo e os kernels da GPU podem tornar a primeira consulta mais lenta. A avaliação deve registrar essa diferença em vez de prometer uma latência fixa.

## Sessões e pedidos

`POST /sessions` gera um token aleatório de 256 bits. O banco armazena apenas seu hash. O token é uma capacidade de acesso à conversa e deve ser enviado como `Authorization: Bearer <session_id>` em `/chat` e na exclusão da sessão.

Sessões expiram após 24 horas, têm limite de 20 turnos e capacidade global de 500 sessões. Uma lease transacional impede duas respostas simultâneas na mesma conversa. O endpoint permite somente uma inferência local por vez para não sobrecarregar a GPU. `DELETE /sessions/current` remove a sessão e suas mensagens.

O histórico é persistido em `runtime/sessions.sqlite3`, ignorado pelo Git. Logs registram identificador de requisição, modelo, versão do prompt, duração e contagem de ferramentas, sem texto integral, argumentos, token de sessão ou credenciais.

Esse mecanismo isola conversas, mas **não autentica um cliente da loja**. Por padrão, pedidos ficam bloqueados. `EMPORIO_DEMO_CUSTOMER_ID` permite uma identidade fixa simulada, definida no ambiente do servidor, somente para demonstração. O corpo das requisições e os argumentos do modelo não podem escolher ou alterar esse cliente. Em produção, essa identidade precisaria vir de autenticação real.

## Contrato HTTP

- `POST /sessions`: cria conversa; não aceita `customer_id` no corpo.
- `POST /chat`: recebe apenas `{ "message": "..." }`, com Bearer da sessão.
- `DELETE /sessions/current`: apaga o histórico da conversa autorizada.
- `GET /chat/health`: verifica a disponibilidade do modelo instalado, sem executar inferência.

`/docs` é a interface principal de demonstração da API. A antiga vitrine fica em `/catalogo` como recurso secundário, sem novos investimentos de interface.

## Limitações de fundamentação

Validar IDs garante que uma fonte citada foi consultada; não comprova que cada frase a interpreta corretamente. O modelo ainda pode resumir mal uma política ou omitir uma condição. Por isso, testes determinísticos verificam as barreiras do sistema, e uma avaliação separada usa o LLM real para revisar a qualidade das respostas. Não apresentar testes com provedor simulado como avaliação do modelo real.
