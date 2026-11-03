# Empório da Música - Assistente de atendimento

Agente em Python para o desafio técnico de AI Engineer da Artefact. Consulta o catálogo da loja fictícia, calcula condições comerciais e recupera políticas com referências ao documento original. A demonstração principal é uma API FastAPI com Swagger, suficiente para exercitar o agente sem construir uma loja virtual.

**Execução local gratuita:** Ollama com `qwen3:8b`, SQLite e Python. Sem chave de API, assinatura, cobrança por tokens ou fallback pago. O computador fornece memória, processamento e energia; o download inicial requer internet.

## O que está implementado

- Ingestão validada e transacional dos seis CSVs, com hashes dos originais.
- Cinco ferramentas tipadas, consultas somente de leitura e cálculos em centavos.
- Recuperação lexical de 29 trechos do manual, com seção e páginas.
- Agente com limites de execução, fontes efetivamente consultadas e guardas de negócio explícitas.
- Sessões isoladas, expiração, exclusão e bloqueio de pedidos sem contexto autorizado.
- 90 testes automatizados e avaliação separada de 13 cenários com o modelo local real.
- Cinco conversas executadas, documentação técnica e geração reproduzível de PDF.

O enunciado permite diferentes interfaces. A escolha foi API documentada; `/catalogo` preserva uma visualização auxiliar já implementada. Não há integração de WhatsApp, ERP, transportadora, checkout ou execução de reembolsos.

## Decisões técnicas e justificativas

### Frameworks e abordagem do agente

Escolhi uma abordagem híbrida: function calling para consultar dados estruturados e calcular condições comerciais, combinado com RAG lexical para recuperar as políticas da loja. Separei essas responsabilidades porque preços, estoque e pedidos exigem consultas exatas, enquanto regras de atendimento precisam do contexto do manual. Mantive cálculos financeiros e autorização no código Python para reduzir a dependência da interpretação do modelo nessas operações.

Optei por um ciclo de ferramentas implementado diretamente em Python, com argumentos validados pelo Pydantic e limites de rodadas, chamadas e tempo. Essa escolha me permite inspecionar o fluxo e testar falhas sem adicionar um framework de orquestração ao recorte do desafio. Usei FastAPI para expor o agente, validar as requisições e disponibilizar a documentação interativa.

Para o retrieval, escolhi SQLite FTS5/BM25, normalização de termos e recuperação de seções relacionadas. O manual tem oito páginas; essa solução mantém a infraestrutura pequena e permite rastrear cada trecho à seção e às páginas de origem. Aceitei a limitação de recuperação lexical para paráfrases novas; compararia embeddings com os mesmos cenários antes de acrescentá-los.

Defini um prompt de sistema em português com a persona da loja, obrigação de consultar evidências, tratamento de ambiguidades e recusa de assuntos fora do escopo. Mantive preços e textos de políticas nas fontes consultadas, em vez de copiá-los para o prompt. Registrei a versão do prompt nas respostas e tratei mensagens e trechos recuperados como dados sem autoridade para alterar as instruções. As fontes são anexadas pelo servidor; reconheço que isso comprova sua consulta, mas não garante a interpretação correta de toda frase do modelo.

### Modelo e provedor

Escolhi o Qwen3 8B executado localmente pelo Ollama para atender à restrição de custo e usar chamadas de ferramentas no hardware disponível. O projeto não exige chave de API nem cobrança por tokens. Restrinjo o provedor a loopback e inicio o Ollama com a nuvem desativada, mantendo as conversas na execução local.

Considerei a contrapartida dessa escolha: download dos pesos, consumo de memória e energia e latência dependente do computador. Validei o comportamento com uma avaliação separada usando o modelo real, sem apresentar testes com provedor simulado como evidência de qualidade do LLM. O relatório registra modelo, digest, parâmetros, versão do prompt e revisão do código para permitir conferência.

### Interface de interação

Escolhi uma API FastAPI com Swagger como interface principal porque o enunciado permite API e prioriza o agente funcionando corretamente. Assim, o avaliador pode criar uma sessão, enviar mensagens e inspecionar respostas, fontes e ferramentas pela documentação interativa. Essa opção concentra o trabalho no atendimento e torna a integração HTTP verificável sem exigir um frontend extenso.

Mantive a visualização de catálogo já implementada como recurso auxiliar em `/catalogo`. Uma interface visual de chat está em discussão e ainda não faz parte da implementação entregue nesta revisão. A API permanece utilizável independentemente dessa evolução.

### Persistência do histórico de conversa

Implementei sessões e histórico em SQLite porque perguntas de acompanhamento fazem parte da experiência de atendimento. Defini um banco separado para conversas, evitando que a reimportação do catálogo apague o histórico. Cada sessão tem token aleatório, com apenas seu hash persistido, expiração em 24 horas e possibilidade de exclusão.

Limitei o contexto enviado ao modelo aos três pares recentes de mensagens para controlar seu tamanho e o custo computacional local. Aceitei que conversas longas podem perder detalhes antigos. Separei também sessão de conversa de identidade de cliente: o token permite acessar o histórico, mas não autentica pedidos. A identidade usada na demonstração é fixa no servidor e explicitamente simulada.

### Tratamento dos dados

Preservei os arquivos originais e seus hashes para manter a proveniência dos dados. Antes da importação, valido colunas, tipos, IDs, relacionamentos, status, valores monetários e outros domínios. Escolhi uma carga transacional do snapshot completo porque o volume recebido é pequeno; uma falha provoca rollback, sem publicar uma carga parcial.

Converti valores monetários para centavos inteiros e descontos para pontos-base, com regras explícitas de arredondamento. Trato status e quantidade em conjunto na disponibilidade e preservo o total histórico dos pedidos, sem recalculá-lo com preços atuais. As ferramentas usam consultas parametrizadas, conexões somente de leitura e projeções com os campos necessários ao atendimento.

No PDF, extraí e agrupei o texto por seção, preservando páginas e hash do documento. Documentei ambiguidades e lacunas, como frete exatamente em R$ 500, contatos divergentes e ausência de recebimento real nos pedidos. Nesses casos, defini esclarecimento ou confirmação com a equipe, evitando preencher informações ausentes por suposição.

## Preparar o ambiente

Requer Python 3.11+, Git, Ollama e espaço para o modelo de aproximadamente 5,2 GB. Ambiente validado: Windows, 16 GB de RAM e RTX 4060 com 8 GB de VRAM. Máquinas diferentes podem apresentar latência maior; os testes determinísticos não exigem GPU.

```powershell
git clone https://github.com/gsssilva/emporio-musica-ai.git
cd emporio-musica-ai
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m emporio_ai check-data
.\.venv\Scripts\python.exe -m emporio_ai ingest
.\.venv\Scripts\python.exe -m emporio_ai index-policies
```

Execute sempre na raiz do projeto. `data/` contém os originais; bancos, modelo e conversas locais ficam em `runtime/`, ignorado pelo Git. A ingestão substitui o snapshot em uma transação e recusa bancos desconhecidos.

### Iniciar o modelo

Instale o [Ollama](https://ollama.com/download) ou use seu pacote portátil oficial em `runtime/tools/ollama/`. Feche outro servidor Ollama antes de iniciar o processo deste projeto na mesma porta. Em um terminal PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-model.ps1
```

O script configura somente seu processo: `127.0.0.1:11434`, nuvem desativada, contexto de 8.192 tokens e modelos em `runtime/ollama-models`. Em outro terminal, baixe o modelo uma vez:

```powershell
ollama pull qwen3:8b
```

Se estiver usando o pacote portátil sem Ollama no PATH, substitua `ollama` por `.\runtime\tools\ollama\ollama.exe`. O download é público e não requer chave ou login. Depois do download, as consultas usam os arquivos locais.

### Iniciar a API

```powershell
.\.venv\Scripts\python.exe -m uvicorn emporio_ai.api:app --host 127.0.0.1 --port 8000 --no-access-log
```

Abra [a documentação interativa local](http://127.0.0.1:8000/docs):

1. Execute `POST /sessions`, sem corpo ou com `{}`.
2. Copie o `session_id` retornado para **Authorize** como Bearer.
3. Execute `POST /chat` com `{"message":"Quais violões estão disponíveis até R$ 1000?"}`.
4. Veja `answer`, `sources`, `tool_trace` e `generation_mode` na resposta.
5. Use `DELETE /sessions/current` para excluir conversa e histórico.

Esse token é criado pelo próprio sistema para isolar a conversa, sem qualquer custo. A primeira consulta pode demorar pelo carregamento do modelo. `GET /chat/health` verifica se o modelo está disponível. Encerre os terminais com Ctrl+C.

`.env` é opcional: os padrões funcionam sem credenciais. Use `.env.example` como referência para os caminhos e o modelo. Por padrão, pedidos ficam bloqueados. Somente para demonstração, `EMPORIO_DEMO_CUSTOMER_ID=2` fixa no servidor a identidade fictícia do exemplo de pedido 8; reinicie a API após mudar a configuração. Isso **não é autenticação de produção** nem deve ser definido pelo cliente ou pelo LLM.

## Verificar e avaliar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe scripts/audit_data.py
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --output runtime/evaluation.json
```

Os 90 testes verificam regras comerciais, ingestão, retrieval, autorização, sessões, falhas e protocolo do agente com provedor simulado. A avaliação final usa Ollama real; não substitui resultados por simulação quando o modelo falha. O [relatório versionado](evals/results.json) contém modelo, digest, prompt, parâmetros, revisão, tempo, fontes e verificações por caso. Os checks automáticos e a revisão das respostas têm limites descritos em [avaliação](docs/avaliacao.md); não representam garantia de precisão em perguntas novas.

### Conversas executadas

- [Busca de catálogo](examples/01-catalogo.md)
- [Promoção e PIX sem cumulatividade](examples/02-promocao-pix.md)
- [Devolução com contexto ausente](examples/03-devolucao.md)
- [Pedido com identidade simulada](examples/04-pedido-demo.md)
- [Assunto fora do escopo](examples/05-fora-de-escopo.md)

Para gerar novamente os cinco exemplos a partir de uma nova execução real:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_agent.py --output runtime/evaluation.json --examples examples
```

## Arquitetura e documentação

```text
HTTP / Swagger -> sessão -> agente -> Ollama local
                            |-> ferramentas validadas -> SQLite de catálogo
                            |-> cálculos em centavos
                            |-> retrieval FTS5 -> políticas com seção/página
                     <- fontes reais + guardas de negócio <- resposta
```

- [Arquitetura e decisões](docs/arquitetura.md)
- [Ingestão e proveniência](docs/ingestao.md)
- [Consultas e condições comerciais](docs/consultas.md)
- [Recuperação das políticas](docs/retrieval.md)
- [Agente, privacidade e sessões](docs/agente.md)
- [Contrato HTTP e demonstração](docs/api-local.md)
- [Avaliação e limitações](docs/avaliacao.md)
- [Entendimento dos requisitos e ambiguidades](docs/entendimento.md)
- [Auditoria agregada dos CSVs](docs/auditoria-dados.json)

`src/emporio_ai/` contém o pacote; `tests/`, os testes; `scripts/`, auditoria, inicialização, avaliação e geração de documentação; `evals/`, cenários e resultados; `examples/`, conversas. O enunciado está em `docs/referencias/`.

## Gerar o PDF de entrega

Markdown é a fonte de verdade. O gerador reúne README, documentação técnica e cinco conversas em ordem explícita, com sumário, links e revisão de origem:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe scripts/build_docs.py
```

Requer Git no PATH e fontes Markdown commitadas, para registrar uma revisão verificável. O resultado fica em [PDF da documentação](output/pdf/documentacao-projeto.pdf). O manifesto com hashes das fontes fica em `runtime/pdf-sources.json`. O PDF inclui a revisão das fontes; seu próprio commit acontece depois da geração. Renderização e inspeção visual fazem parte da preparação da entrega.

## Limitações e escolhas

Os CSVs representam o último snapshot importado. Estoque, rastreamento e previsões não consultam serviços externos. Datas estimadas não comprovam recebimento. Produtos descontinuados ou em lançamento não são oferecidos automaticamente mesmo quando há estoque positivo.

O manual tem ambiguidades em contatos, parcelas pequenas e frete exatamente em R$ 500. O atendimento encaminha confirmação nesses casos. Preços e descontos são calculados no código; a elegibilidade de devolução não é presumida sem canal e recebimento real. Fontes consultadas não comprovam automaticamente cada frase do modelo: ele ainda pode omitir nuances ou redigir mal.

A API é um protótipo local, sem autenticação de clientes de produção, TLS, escalabilidade ou operação comercial real. O histórico é limitado a três pares recentes, sessões expiram em 24 horas e o processamento permite uma inferência por vez. Não expor o servidor diretamente à internet.

## Uso de assistência de IA e histórico

O Codex auxiliou na leitura dos materiais, auditoria, decisões, implementação, testes, avaliação das respostas, correções e documentação. Gabriel Silva definiu prioridades, escopo e restrição de custo, e autorizou commits e pushes. O candidato deve revisar o código e compreender as decisões para defendê-las na avaliação. As conversas de exemplo foram executadas com o modelo real; os testes com provedor simulado estão identificados separadamente.

O histórico registra o desenvolvimento progressivo e suas correções. Não foi usado force-push. A entrega solicitada pelo enunciado é o link do repositório; o PDF é um complemento pedido pelo candidato. Prazo informado: terça-feira, 03/11/2026, com horário a conferir no e-mail da seleção. O envio final é realizado pelo candidato.
