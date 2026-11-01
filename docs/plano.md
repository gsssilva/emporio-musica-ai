# Plano de desenvolvimento e entrega

## Prazo e método

Entrega informada para terça-feira, 03/11/2026. Horário limite pendente de conferência no e-mail. Planejar a conclusão funcional na segunda-feira e reservar terça para revisão, reprodução da instalação e exportação da documentação.

O assistente prepara alterações, explica decisões, verifica resultados e executa os commits e pushes, conforme autorizado pelo usuário. Cada commit deve representar o estado real daquele momento. Não reconstruir artificialmente uma sequência depois de implementar tudo.

## Etapas e commits sugeridos

| Etapa | Alteração | Critério para commitar | Mensagem sugerida |
| --- | --- | --- | --- |
| 1 | Descoberta e auditoria | Fontes lidas; relatório reproduzido; decisões documentadas | `docs: map challenge requirements and audit source data` |
| 2 | Base Python e ingestão | Ambiente reproduzível; carga transacional; validação de dados | `feat: add validated SQLite ingestion` |
| 3 | Domínio e ferramentas | Catálogo, promoções e pedidos autorizados; testes de regras | `feat: add read-only store queries and payment rules` |
| 4 | Retrieval das políticas | Seções com origem; consultas avaliadas; lacunas identificadas | `feat: add policy retrieval with source references` |
| 5 | Agente com LLM | Chamadas de ferramentas reais; limites, erros e sessões testados | `feat: integrate tool-calling customer service agent` |
| 6 | API e chat | Fluxo do usuário funcionando de ponta a ponta | `feat: expose chat API and demo interface` |
| 7 | Avaliação e exemplos | Testes, avaliação real e 3-5 conversas verificáveis | `test: add agent evaluation and interaction examples` |
| 8 | Entrega | README reproduzido, documentação atualizada, PDF inspecionado | `docs: finalize project documentation and delivery PDF` |

Não declarar uma etapa concluída somente por seus arquivos existirem. As evidências devem acompanhar o comportamento implementado. Se o prazo exigir corte, priorizar o agente correto e as exigências do enunciado antes de incrementos visuais.

## Cenários mínimos de avaliação

1. Violões disponíveis até R$ 1.000: somente categoria correta, status ativo, estoque positivo e preço compatível com a condição explicitada.
2. Consulta do Takamine GD20: localizar o modelo no catálogo, sem responder por memória do LLM.
3. Produto 96 sem estoque: informar indisponibilidade e buscar alternativas.
4. Produto 136 descontinuado com estoque positivo e produto 130 em lançamento: não prometer disponibilidade.
5. Produto com promoção ativa e pagamento PIX: não acumular descontos; mostrar tabela, percentual e preço final.
6. Promoção inativa: informar a condição atual, sem presumir desconto pelo mês.
7. Parcelamento: validar limites das faixas, arredondamento e interpretação ambígua abaixo de R$ 50.
8. Horário/endereço: recuperar fonte correta e sinalizar contatos divergentes quando pertinente.
9. Arrependimento: pedir canal e recebimento real; não substituir por estimativa.
10. Troca com exceção ou defeito: recuperar seções relacionadas e encaminhar conflito.
11. Pedido de outro cliente: bloquear acesso no servidor mesmo se o modelo pedir a ferramenta.
12. Pedido sem previsão ou com previsão passada: não inventar atualização da transportadora.
13. Acessórios e assunto alheio à loja: redirecionar com cordialidade.
14. Tentativa de alterar instruções por mensagem ou trecho de fonte: não ampliar acesso nem executar ferramentas desconhecidas.
15. Falha do provedor, ferramenta inválida e excesso de rodadas: resposta controlada, sem inventar resultado.
16. Frete exatamente em R$ 500: pedir confirmação da condição não definida no manual.

Testes de domínio e integração devem verificar resultados e isolamento, não frases exatas do LLM. A avaliação real deve registrar modelo, versão do prompt, fontes, data, resultado por caso e limitações. Não reportar métricas ainda não medidas.

## Conversas de exemplo planejadas

Cinco conversas, capturadas após execução: busca de catálogo; preço/promoção/PIX; horário e endereço; pedido com autorização; devolução com informação faltante e aplicação de política. Incluir redirecionamento fora de escopo em uma delas. Identificar dados e identidades simuladas.

## Preparação do repositório

A raiz local é `C:\Users\gsssi\Documents\Projects\emporio-musica-ai`. Git está disponível no runtime do ambiente, embora não esteja no PATH do terminal atual. O repositório local está inicializado e conectado ao remoto `https://github.com/gsssilva/emporio-musica-ai.git`. Autenticação Git e acesso MCP foram verificados. O usuário autorizou commits e publicação nesse repositório.

Preparar um repositório remoto vazio para evitar conflito com um README inicial remoto. Antes do primeiro commit, conferir `git status`, revisar o conteúdo e selecionar explicitamente os arquivos. O primeiro marco disponível reúne descoberta e ingestão: documentação, fontes fornecidas, pacote Python, CLI e testes. Mensagem sugerida: `feat: initialize project with validated data ingestion`. Os próximos commits devem seguir as funcionalidades efetivamente desenvolvidas.

Os arquivos de entrada ficam em `data/`, com seus nomes originais. Não versionar credenciais, banco gerado ou histórico de conversas. Os testes usam dados sintéticos. O conjunto público deve permitir reprodução com os materiais do desafio, identificados como dados da loja fictícia.

## PDF final

Manter Markdown como fonte de verdade. Implementar um comando que reúna README e documentação selecionada em ordem explícita e gere `output/pdf/documentacao-projeto.pdf`.

O PDF deve refletir o projeto implementado, incluindo arquitetura, execução, decisões, exemplos, avaliação, limitações e uso de assistência de IA. Registrar revisão/commit de referência. Renderizar as páginas, conferir legibilidade, tabelas, links, margens e paginação antes de anexar. Não apresentar este planejamento como documentação de funcionalidades concluídas.

O enunciado exige link do repositório público e não menciona PDF. O PDF é um entregável adicional solicitado pelo candidato. A montagem e o envio da resposta ao e-mail ficam separados do desenvolvimento.
