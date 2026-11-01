# Avaliação do agente e limitações

## Método

A validação separa três níveis: testes determinísticos de domínio e protocolo; cenários com o modelo real; revisão das mensagens e suas evidências. Um teste com provedor simulado não mede qualidade do LLM. Uma verificação automática de fonte e palavras também não demonstra correção semântica completa.

Foram executados 90 testes automatizados com `unittest`, cobrindo ingestão e rollback, valores financeiros, status e estoque, promoção inativa, acesso a pedidos, retrieval, sessões, HTTP, limites, falhas de provedor e guardas. Os testes usam CSVs sintéticos e bancos temporários; os de retrieval também usam o manual fornecido. O ambiente registra um aviso de depreciação do cliente de testes do framework, sem falha dos testes.

`scripts/evaluate_agent.py` executa os 13 cenários de `evals/cases.json` com o provedor real. Se o modelo não estiver disponível, a execução falha; não há substituição silenciosa por resposta simulada. O relatório contém texto integral, fontes, trilha, checks, duração e modo de geração por cenário. Os cinco exemplos são extraídos dessa execução.

## Ambiente e reprodução

Modelo `qwen3:8b` no Ollama 0.40.13, execução local em Windows com 16 GB de RAM e RTX 4060 de 8 GB. Temperatura zero, seed 42, contexto de 8.192 tokens e saída limitada a 1.200 tokens. Digest do modelo:

```text
500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
```

O hash do prompt, a revisão exata do código e uma hora de referência única para a rodada estão em `evals/results.json`. O relógio fixado contextualiza as respostas; datas do snapshot permanecem históricas. Valores e hashes das fontes são verificáveis na auditoria. Diferentes versões do modelo, runtime, GPU ou dados podem alterar os resultados, mesmo com seed fixa.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --output runtime/evaluation.json
```

O avaliador não depende do servidor FastAPI: chama o mesmo serviço de agente e suas ferramentas. A integração HTTP é verificada separadamente com criação de sessão, mensagem ao modelo real, exclusão e rejeição do token revogado.

## Resultados por cenário

| Cenário | Critério principal | Responsabilidade |
| --- | --- | --- |
| Violões até R$ 1.000 | Categoria, disponibilidade, orçamento e evidência | Busca selecionada pelo LLM; filtro no servidor |
| Takamine GD20 | Preço e características do produto consultado | Ferramenta e redação pelo LLM |
| Produto 96 | Sem estoque; alternativas reais | LLM consulta; servidor garante disponibilidade e alternativas |
| Produto 136 | Descontinuado mesmo com 13 unidades | LLM consulta; guarda de status/estoque |
| Produto 90 no PIX | Total R$ 1.967,18; sem somar 5% à promoção | Cotação e explicação determinísticas |
| Endereço e sábado | Fonte institucional e horário | Retrieval e redação pelo LLM |
| Arrependimento | Pedir canal e recebimento real | Retrieval e guarda de contexto ausente |
| Pedido 8 autorizado | Identidade simulada; previsão passada | Consulta filtrada; contexto histórico e encaminhamento |
| Pedido sem identidade | Nenhum dado privado exposto | Bloqueio no servidor antes da inferência |
| Defeito após 35 dias | Considerar 90 dias desde recebimento | Políticas relacionadas e guarda de garantia |
| Pergunta sobre Napoleão | Redirecionar para atendimento da loja | Recusa pelo LLM |
| Injeção para listar clientes/SQL | Não ampliar acesso ou executar código | Registro fechado e recusa pelo LLM |
| Frete exatamente R$ 500 | Manual não define igualdade | Retrieval e guarda de ambiguidade |

Na rodada final, os 13 cenários passaram nos checks automáticos (13/13). Revisão do código: `986e4e63339539b80168e2d969af94bfc48eee27`; início em `2026-11-01T20:55:51.208910+00:00`. Entre as 12 respostas com inferência, a mediana foi 5.72 segundos, com mínimo de 2.69 e máximo de 14.31; o caso de autorização foi bloqueado antes do modelo. Esses tempos são desta execução e não incluem um benchmark separado de partida fria. A contagem e os tempos completos estão no relatório versionado. O resultado deve ser descrito como aprovação das verificações desses cenários, nunca como precisão universal. Bloqueio de autorização não é uma inferência do modelo; sua latência quase nula não deve entrar na estimativa de geração.

## Revisão das respostas

A revisão verifica produtos, preços, condições, fontes e ausência de afirmações comerciais sem autorização. Ela é necessária porque checks de palavras podem aprovar uma mensagem contraditória. Dois exemplos concretos motivaram regressões: o modelo chegou a dizer que o total incluía promoção e PIX somados apesar de a cotação estar correta; também presumiu prazo de arrependimento sem conhecer canal e recebimento. O servidor agora deriva a explicação do PIX da cotação e pede o contexto da devolução. Outra regressão verifica que mencionar 90 dias não basta sem o marco do recebimento.

Essas correções tratam comportamento do domínio, não memorizam IDs dos cenários: aplicam-se à cotação consultada e às seções relevantes. Guardas são identificadas em `tool_trace` e `generation_mode`. Perguntas de catálogo, informações da loja, seleção de ferramentas e recusas continuam exercitando o LLM real.

Os exemplos preservam as mensagens executadas. Não foram reescritos para esconder falhas do modelo. A conversa de pedido usa identidade fictícia explicitamente simulada no servidor. A avaliação utiliza somente arquivos do desafio e não envia mensagens para serviços externos de inferência.

## Limitações observadas

- A busca lexical pode perder paráfrases e intenções não reconhecidas. Os 13 cenários não cobrem toda a linguagem de clientes.
- O LLM pode oferecer sugestões fora da fonte ou omitir condições; validação de IDs não prova cada frase. As guardas cobrem restrições explícitas e falhas observadas, sem garantia geral de ausência de alucinação.
- As alternativas são da mesma categoria, sem demonstrar equivalência técnica completa entre instrumentos.
- A recusa fora de escopo pode oferecer ajuda adicional desnecessária; ela não executa buscas externas nem responde o assunto geral.
- O aquecimento e o hardware afetam latência. Não há benchmark de concorrência ou SLA; uma inferência por vez protege a execução local.
- Pedidos não têm canal de compra ou recebimento real. Não há base suficiente para aprovar direitos ou negar garantia automaticamente.
- Os dados e as políticas são snapshots; não existe estoque ou rastreamento externo em tempo real.
- A identidade de demonstração não é autenticação de produção. O serviço foi preparado para uso local.

## Custos

Nenhuma chamada paga foi feita na avaliação. O runtime usa modelo local, sem chave de API, login em provedor de inferência ou fallback comercial. Dependências e pesos exigem download; armazenamento, processamento e energia são fornecidos pelo computador. Não foi contratado serviço de hospedagem.
