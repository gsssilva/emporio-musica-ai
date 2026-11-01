# Consultas de atendimento e condições comerciais

## Componentes disponíveis

`StoreQueries` recebe o caminho do banco importado e oferece busca de produtos, detalhe de produto, cotação de pagamento e consulta de pedido no contexto de um cliente autorizado pelo servidor. Ainda não há exposição desses métodos ao LLM ou a uma API pública.

As conexões usam SQLite em modo somente leitura, também protegido por `PRAGMA query_only`. Identificadores usados nas consultas SQL são parâmetros. Os resultados possuem campos explícitos, para evitar entregar ao modelo uma linha inteira de dados pessoais ou notas internas.

## Catálogo

A busca admite texto, categoria, orçamento em centavos, disponibilidade e limite de 1 a 10 resultados. Normaliza acentos e alguns plurais das categorias em português. Ordena por preço atual e ID para manter resultados estáveis, informa a quantidade total encontrada e se houve truncamento.

O produto está disponível somente quando o status é `active` e o estoque é maior que zero. O detalhe preserva o status original e permite explicar produtos esgotados, descontinuados e em lançamento. Uma cotação para uma nova compra exige disponibilidade.

Somente promoções ativas entram no preço atual. A resposta inclui preço de tabela, percentual em pontos-base e preço atual, antes de condições de pagamento. O filtro de orçamento se refere a esse preço atual, sem presumir pagamento PIX.

A busca textual e o filtro de preço final são aplicados em Python ao recorte obtido por SQL. Isso evita aritmética de ponto flutuante no SQLite e é suficiente para o snapshot de 65 produtos. Para um catálogo grande, será necessário paginar e indexar a busca, preservando precisão e regras de preço.

## Pagamento

Os cálculos usam inteiros em centavos e pontos-base. Descontos são arredondados para o centavo mais próximo, com metade para cima. Parcelas distribuem os centavos restantes entre as primeiras parcelas, preservando a soma exata.

- PIX: 5% de desconto sobre a tabela quando não existe promoção ativa. Não acumula com promoção.
- Débito e boleto: pagamento à vista, pelo preço atual.
- Crédito: de 1 a 12 parcelas. De 4 a 6 parcelas, mínimo de R$ 80 por parcela. De 7 a 12, mínimo de R$ 100.
- Em 2 ou 3 parcelas, quando alguma parcela fica abaixo de R$ 50, retornar `needs_confirmation`, devido à redação ambígua da seção 3.1. O agente não deve apresentar esse resultado como condição aprovada.
- Formas combinadas de pagamento ainda não são calculadas nesta etapa.

As condições descrevem o manual recebido, seções 3, 3.1 e 6.2. Não são simulação de uma transação com adquirente, garantia de aprovação de crédito ou alteração de pedido.

## Pedidos e limite de acesso

`get_order(order_id, authorized_customer_id=...)` exige um contexto de cliente fornecido pela aplicação. A consulta SQL filtra simultaneamente o pedido e o cliente. Pedido inexistente e pedido de outro cliente retornam o mesmo diagnóstico, sem revelar a existência de um registro privado.

O resultado contém situação registrada, total histórico, forma de pagamento, rastreamento, previsão e itens. Não contém nome do cliente, e-mail, telefone, ID do cliente ou notas internas. Recebimento efetivo e canal de compra são explicitamente desconhecidos. Uma estimativa de entrega nunca é convertida em prova de recebimento.

**Esse filtro não implementa autenticação.** A futura API precisará estabelecer o contexto confiável de cliente. Não aceitar esse identificador como uma escolha livre do usuário ou como argumento gerado pelo modelo. Na demonstração, qualquer identidade simulada deverá estar claramente identificada.

## Atualidade dos dados

Cada resultado identifica a origem como `local_snapshot` e apresenta o instante de importação. Consultar novamente o SQLite acessa o snapshot atual local, sem consultar ERP ou transportadora externos.

## Verificação

Os testes adicionais cobrem status e estoque em conjunto, promoções, PIX sem cumulatividade, limites de parcelamento, arredondamento, orçamento, truncamento, entrada com texto SQL, contexto de pedido, minimização de dados e bloqueio de gravações nas conexões de consulta.
