# Interface visual de atendimento

## Escopo e origem do layout

O chat em `/` segue o HTML e o print fornecidos pelo candidato: tema escuro, dourado e laranja, duas colunas no desktop e adaptação para tela pequena. Na integração, o candidato ajustou a grade para `grid-template-columns: 1fr 50%`, ampliando o espaço do chat. HTML, CSS e JavaScript são puros e servidos pelo FastAPI na mesma origem das APIs. O protótipo original continha mensagens e preços simulados; esses dados foram removidos. A saudação inicial é estática e não afirma fatos comerciais.

O nome da loja usa Permanent Marker, e títulos usam Oswald. Os arquivos tipográficos são servidos localmente em `/assets/fonts`, com as licenças Apache 2.0 e SIL Open Font License junto aos arquivos. Foram obtidos do Google Fonts e do repositório oficial `google/fonts`. Não há chamada a Google Fonts durante o atendimento nem envio das mensagens para um serviço de layout.

## Sessão e histórico

Ao abrir a página, o cliente verifica `/chat/health` e cria uma sessão em `POST /sessions`, sem pedir token ao usuário. A aba mantém o token e as mensagens exibidas em `sessionStorage`, protegido com try/catch. Se o armazenamento estiver bloqueado, a conversa permanece em memória e a interface avisa sobre a perda da retomada ao recarregar.

Recarregar a mesma aba restaura os itens locais e a trilha da última resposta, com uma faixa indicando a retomada. Esse estado visual não comprova que a sessão do servidor ainda esteja válida; uma rejeição 401/403 inicia outra sessão e avisa que o histórico anterior não está disponível nela. A última mensagem só é reenviada por ação explícita do usuário.

O botão **+** abre uma confirmação inline. Cancelar preserva a conversa. Apagar chama `DELETE /sessions/current` antes de limpar o estado local e criar outra sessão. Uma falha de exclusão não é apresentada como sucesso e mantém o histórico atual na tela. Fechar a aba encerra o armazenamento da interface; no servidor, o histórico segue a expiração de 24 horas. A UI não oferece seleção de clientes nem autenticação de pedidos.

## Envio e apresentação das respostas

Enter envia e Shift+Enter insere uma nova linha. O campo limita a mensagem a 2.000 caracteres. Enquanto a solicitação está em andamento, envio, sugestões e nova conversa ficam bloqueados para evitar duplicação e troca de sessão durante uma resposta. A espera informa que o modelo é local e pode precisar carregar; não apresenta percentual ou etapas de raciocínio inventadas.

`answer` é renderizado como texto, com quebras de linha, negrito simples e destaque de valores em reais. Conteúdo do modelo, do usuário e das fontes não é interpretado como HTML. O botão de cópia usa o texto da resposta. Referências expansíveis mostram os registros recebidos em `sources`, com tipo, título, páginas, trecho e identificação quando disponíveis; a interface não gera referências por conta própria.

Quando uma resposta concluída consulta produtos e não faz cotação de pagamento, os IDs de catálogo retornados em `sources` permitem consultar `/api/products/{id}` para até cinco cartões auxiliares. Eles mostram nome, preço atual e disponibilidade efetivamente retornados por essa consulta. Uma legenda distingue esse preço das condições de pagamento. Se a consulta auxiliar falhar, o cartão é omitido e a resposta do agente permanece. Produtos descontinuados ou em lançamento não recebem rótulo de disponibilidade mesmo com quantidade positiva.

O painel de bastidores reproduz `tool_trace` com ferramenta, resultado e origem registrada. Não inventa intenção do cliente ou chamadas. Detalhes recolhidos mostram somente os metadados efetivos: requisição, modelo, provedor, prompt, modo de geração, classificação, uso e status.

## Falhas e limites

- Saúde indisponível ou falha de rede: estado visível e ação para verificar o serviço novamente.
- 401/403: sessão inválida, criação de outra e reenvio opcional, sem replay automático.
- 409 ou 429 por inferência ocupada: aviso e repetição explícita, sem duplicar a mensagem do cliente na tela.
- 429 por limite de sessão: orientação para nova conversa, sujeita à confirmação inline.
- Falha de modelo, resposta inválida ou timeout: aviso sem fabricar resposta; o reenvio exige ação do usuário. Uma interrupção de rede não comprova que o servidor deixou de processar a mensagem.
- HTTP 200 com `status` diferente de `completed`: a orientação do agente é exibida com aviso de consulta não concluída.

A checagem de saúde é repetida a cada 30 segundos fora de uma resposta em andamento. Ela verifica serviço e modelo instalado; não promete que toda inferência será bem-sucedida. O timeout do chat é de 250 segundos, acima do orçamento de 240 segundos do agente; demais solicitações têm limite menor.

## Acessibilidade e reprodução

Os controles usam botões, formulário e textarea, com rótulos, foco visível e estados de espera anunciados. A animação do equalizador respeita `prefers-reduced-motion`. O breakpoint de 860 px organiza a página em uma coluna. Não há carrinho, checkout, upload, áudio ou mensagens simuladas de atendimento.

Na raiz, com modelo e API iniciados conforme o README:

1. Abra `http://127.0.0.1:8000/` e confira o estado do serviço.
2. Use uma pergunta sugerida e aguarde a resposta real.
3. Expanda as fontes e compare a trilha com a última resposta.
4. Faça uma pergunta de acompanhamento; recarregue para verificar a retomada.
5. Teste Shift+Enter, envio com Enter e cópia.
6. Para uma conversa descartável de teste, use **+**, confirme a exclusão e verifique a nova saudação.

Os testes Python verificam o shell e os assets servidos junto da API. Dez testes JavaScript, com DOM e HTTP substitutos explicitamente identificados, verificam sessão automática, evidência como texto, concorrência, retomada, expiração, ocupação, limite de turnos, cancelamento/exclusão, falha de exclusão e armazenamento bloqueado. São testes do cliente; não medem qualidade do LLM nem substituem a inspeção no navegador.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
node --test tests/test_chat_ui.cjs
```

Node é necessário somente para esses testes de frontend, sem `npm install` ou dependências adicionais. A execução do projeto continua exigindo Python e Ollama. A verificação no navegador usa o modelo real para catálogo e horário, além de conferir fontes, cópia, retomada e envio pelo teclado. O layout também é inspecionado nos tamanhos desktop e celular.
