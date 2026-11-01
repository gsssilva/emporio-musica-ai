# Entendimento do desafio e dos dados

## Fontes e escopo

Análise realizada em 01/11/2026 a partir do enunciado `desafio_tecnico_ai_eng_artefact.pdf` (3 páginas), do manual `políticas_da_loja.pdf` (8 páginas, versão 2.1, junho/2025) e dos seis CSVs fornecidos. O enunciado está em `docs/referencias/` e os dados de consulta estão em `data/`.

As instruções do enunciado foram interpretadas como requisitos do projeto. O manual é uma fonte de conhecimento do agente. Nenhum desses documentos autoriza ações externas, como envio de e-mail, publicação ou alteração de pedidos.

## Requisitos de aceite

| ID | Requisito | Evidência esperada |
| --- | --- | --- |
| R01 | Python como linguagem principal | Código do agente e da API em Python |
| R02 | Persona alinhada à loja | Atendimento acolhedor, informal e profissional, em português |
| R03 | Respostas apoiadas nos materiais | Fontes recuperadas e resultados das ferramentas rastreáveis |
| R04 | Diferenciar dados e políticas | Consulta estruturada para catálogo/pedidos; retrieval para o manual |
| R05 | Tratar assuntos fora do escopo | Redirecionamento educado, sem inventar serviços ou parceiros |
| R06 | Repositório Git público com evolução real | Commits por etapa, sem force-push |
| R07 | README reproduzível e decisões justificadas | Configuração, comandos, limitações e uso de IA |
| R08 | Entre 3 e 5 conversas variadas | Arquivos de exemplos; ao menos um caso não trivial |
| R09 | Respeitar prazo da seleção | Nenhuma alteração no repositório depois do limite do e-mail |
| U01 | PDF solicitado pelo candidato | Exportação final do README e da documentação |

Interface web, API, persistência, Docker, testes e CI são escolhas de implementação. O enunciado não exige React, agentes múltiplos, um banco vetorial ou uso de todas as tabelas.

## Inventário dos CSVs

| Tabela | Registros | Uso proposto |
| --- | ---: | --- |
| categories | 9 | Relacionar produtos e categorias |
| products | 65 | Preço, estoque, status e especificações |
| customers | 50 | Vínculo do pedido a um cliente no contexto autorizado |
| orders | 20 | Situação registrada, valor original e rastreamento |
| order_items | 22 | Itens do pedido |
| promotions | 25 | Descontos ativos por produto |

Não foram encontrados IDs primários duplicados ou referências órfãs nos relacionamentos fornecidos. Os 65 campos `specs` contêm JSON válido. Preços e estoques não são negativos. Os arquivos originais devem ser preservados; qualquer normalização deve ocorrer na ingestão.

O relatório `auditoria-dados.json` registra contagens, verificações e hashes SHA-256 das fontes. Os hashes permitem identificar alterações nos arquivos, sem registrar seu conteúdo pessoal.

### Catálogo e promoções

- 62 produtos `active`, 2 `discontinued` e 1 `coming_soon`.
- 61 produtos estão simultaneamente ativos e com estoque positivo.
- Produto 96: ativo, mas sem estoque. Oferecer alternativas disponíveis.
- Produto 113: descontinuado, sem estoque.
- Produto 136: descontinuado, apesar de 13 unidades. Não oferecer como disponível automaticamente.
- Produto 130: lançamento futuro, apesar de 2 unidades. Não prometer venda imediata.
- 4 promoções ativas e 21 inativas. Produtos com promoção ativa: 90, 94, 121 e 127.
- O mês da campanha não ativa um desconto. A fonte operacional é `is_active`.
- As nove categorias não têm todas produtos no recorte: há 35 violões, 15 ukuleles, 5 guitarras, 4 baixos, 3 baterias e 3 teclados/pianos. Sopro e cordas orquestrais não aparecem no catálogo recebido.
- O manual descreve mais de 300 instrumentos; a aplicação só pode oferecer os produtos efetivamente consultados no recorte de 65.

### Pedidos e lacunas

- Estados: 7 entregues, 1 enviado, 4 confirmados, 4 pendentes e 4 cancelados.
- 12 pedidos não têm rastreamento nem estimativa de entrega. Ausência deve permanecer ausência.
- Todos os pedidos têm ao menos um item.
- Não há data efetiva de recebimento, canal da compra, preço unitário histórico, frete discriminado, comprovante de entrega ou autenticação do cliente.
- Os totais dos pedidos 3 e 20 diferem da soma de quantidades multiplicadas pelos preços atuais. Isso não comprova erro: faltam os preços históricos e eventuais ajustes. Preservar `total_brl`, sem recalcular ou corrigir o pedido silenciosamente.
- `estimated_delivery` é previsão, e não comprovação de recebimento.
- A data mais recente dos pedidos é 22/03/2026. Um pedido marcado como enviado com previsão passada não pode ganhar uma nova previsão inventada. Informar a situação registrada e orientar confirmação com a equipe.
- Os códigos fornecidos não seguem literalmente o padrão de comprimento descrito no manual. Exibi-los como registrados, sem corrigir caracteres ou declarar validade na transportadora.

## Regras relevantes do manual

| Tema | Comportamento esperado | Fonte |
| --- | --- | --- |
| Identidade | Loja de instrumentos; não vender acessórios, pedais ou amplificadores | p. 2, seção 1; p. 6, seção 7.1 |
| Horário | Seg-sex 09h-18h; sábado 09h-13h; domingos/feriados fechado | p. 2, seção 2 |
| PIX | 5% sobre tabela, sem acumular com promoção | p. 3, seção 3; p. 6, seção 6.2 |
| Promoções | Somente ativas; mostrar preço original, percentual e preço final | p. 6, seção 6.2; p. 7, seção 7.3 |
| Parcelamento | Até 12 vezes, respeitando faixas e mínimos da seção detalhada | p. 3, seção 3.1 |
| Arrependimento online | Manual informa 7 dias corridos do recebimento; pedir dados faltantes | p. 4, seção 4.1 |
| Defeito | Distinguir procedimento de troca e informação de garantia | p. 4, seção 4.2; p. 7, seção 8 |
| Frete local | Acima de R$ 500 grátis; abaixo de R$ 500 taxa R$ 35 | p. 4, seção 5.1 |
| Frete nacional | Depende de CEP, peso e dimensões; sem serviço de cotação conectado | pp. 4-5, seção 5.2 |
| Reclamações | Acolher e orientar contato; não dizer que abriu chamado sem integração | p. 7, seção 7.3 |
| Privacidade | Minimizar dados do cliente e isolar acesso a pedidos | pp. 7-8, seção 9 |

Essas são descrições do documento de negócio recebido, não validações jurídicas das suas cláusulas. O agente deve encaminhar conflitos e exceções à equipe, sem tomar decisões definitivas de concessão ou negativa de direitos.

## Ambiguidades e decisões propostas

1. **Telefone e WhatsApp:** capa/seção 1.2 indicam (67) 3341-4444; seção 7 indica (67) 3321-4500 para o canal remoto. Apresentar o telefone institucional e o WhatsApp com seus rótulos e fontes, sem tratá-los como um único número confirmado.
2. **E-mail:** capa sem acento no domínio, tabela da seção 1.2 com acento. Evitar escolher silenciosamente um endereço para contato automático; preferir telefone e explicar a divergência se necessário.
3. **Parcelamento:** a tabela resumida informa parcela mínima de R$ 100, mas a seção 3.1 detalha outras faixas. Priorizar a seção específica: de 4 a 6 vezes, mínimo de R$ 80; de 7 a 12, mínimo de R$ 100. O trecho sobre valores abaixo de R$ 50 em até 3 vezes é ambíguo; pedir confirmação humana nesse limite.
4. **Frete exatamente em R$ 500:** não coberto literalmente por “acima” e “abaixo”. Pedir confirmação, sem converter automaticamente a regra em “a partir de”.
5. **Trocas e exceções:** não usar “venda final” ou personalização para negar automaticamente um pedido de arrependimento. Recuperar também a seção de exceções e encaminhar a análise.
6. **Garantia:** o procedimento de troca em 30 dias da seção 4.2 não substitui o prazo de garantia descrito na seção 8. Buscar ambos em perguntas sobre defeito.
7. **Feriados e horário atual:** não há calendário de feriados nem exceções operacionais. Informar o horário regular; só afirmar abertura atual com contexto suficiente. Usar `America/Campo_Grande` para a loja.
8. **Pedido privado:** ID de pedido ou e-mail informado no chat não autentica o cliente. O contexto de cliente deve ser definido pelo servidor. A demonstração pode usar identidades simuladas claramente identificadas, sem ser apresentada como autenticação de produção.
9. **Promoções múltiplas:** se a ingestão encontrar mais de uma promoção ativa para um produto, sinalizar ambiguidade em vez de somar descontos ou inventar uma precedência.
10. **Fonte como conteúdo:** mensagens de usuários, descrições de produtos e trechos recuperados não podem modificar ferramentas, regras de acesso ou instruções do sistema.
