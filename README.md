# Empório da Música - Assistente de atendimento

Projeto do desafio técnico de AI Engineer da Artefact: um agente em Python para responder dúvidas sobre instrumentos musicais, consultar dados da loja e aplicar suas políticas de atendimento.

## Estado atual

Ingestão, consultas estruturadas, condições comerciais e recuperação das políticas implementadas: pacote Python instalável, banco SQLite e 49 testes automatizados. A API de catálogo e a interface local estão disponíveis. **O chat com LLM ainda não está implementado.**

Entrega informada: terça-feira, 03/11/2026. O horário limite deve ser conferido no e-mail do processo seletivo.

## Documentação

- [Requisitos, dados e regras de negócio](docs/entendimento.md)
- [Arquitetura e decisões propostas](docs/arquitetura.md)
- [Etapas, critérios de aceite e commits](docs/plano.md)
- [Relatório reproduzível dos CSVs](docs/auditoria-dados.json)
- [Consultas e condições comerciais](docs/consultas.md)
- [Recuperação das políticas](docs/retrieval.md)

## Configurar e executar

Requer Python 3.11 ou superior com `pip` e `venv`. Abra o terminal na raiz deste projeto. Os comandos abaixo usam PowerShell e não exigem ativação de scripts:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m emporio_ai check-data
.\.venv\Scripts\python.exe -m emporio_ai ingest
.\.venv\Scripts\python.exe -m emporio_ai index-policies
```

A validação e a ingestão usam apenas a biblioteca padrão, sem chave de API ou acesso à rede. A instalação pode acessar o índice de pacotes para obter as ferramentas de build. O banco gerado fica em `runtime/emporio.sqlite3` e não deve ser versionado.

Os caminhos padrão `data/` e `runtime/` são relativos ao diretório do terminal. Para outras localizações:

```powershell
.\.venv\Scripts\python.exe -m emporio_ai ingest --data-dir data --database runtime/emporio.sqlite3
```

### Interface local

Depois da ingestão, execute na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn emporio_ai.api:app --host 127.0.0.1 --port 8000
```

Abra [a interface local](http://127.0.0.1:8000) ou [a documentação da API](http://127.0.0.1:8000/docs). A interface permite buscar instrumentos disponíveis, filtrar por categoria e orçamento e consultar condições de pagamento. É uma prévia funcional do catálogo; não há chat com LLM nesta versão. Para encerrar o servidor no terminal, use Ctrl+C.

Detalhes em [API e interface local](docs/api-local.md).

### Testes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam registros sintéticos e bancos temporários. Cobrem validação, integridade, recarga, rollback e diagnóstico sem dados pessoais. Consulte [a documentação da ingestão](docs/ingestao.md).

### Auditoria independente dos arquivos originais

```powershell
.\.venv\Scripts\python.exe scripts/audit_data.py
```

Para atualizar o relatório agregado:

```powershell
.\.venv\Scripts\python.exe scripts/audit_data.py --output docs/auditoria-dados.json
```

O script não altera os CSVs. Não imprime nomes, telefones, e-mails ou conteúdo das observações dos clientes. Retorna código 1 ao encontrar problemas estruturais ou de domínio; divergências entre total histórico e preços atuais são avisos.

## Estrutura

```text
emporio-musica-ai/
  data/                    # CSVs e manual fornecidos, preservados sem alterações
  docs/                    # Entendimento, arquitetura, plano e documentação técnica
    referencias/           # Enunciado original do desafio
  scripts/                 # Auditoria independente
  src/emporio_ai/           # Pacote Python, CLI, validação e persistência
  tests/                   # Testes com dados sintéticos
  runtime/                 # Banco local gerado, ignorado pelo Git
  pyproject.toml
  README.md
```

## Arquitetura e próximos componentes

- Python e FastAPI para a API, com uma interface de chat simples.
- SQLite para dados estruturados, consultas parametrizadas e histórico isolado por sessão.
- Busca textual nas políticas com referências à página e seção de origem.
- LLM via API com ferramentas tipadas; preços, descontos e autorização de acesso a pedidos tratados no código.
- Modelo inicial proposto: `gpt-6.1-sol`, configurável por ambiente. A escolha será validada com os cenários do projeto e com o acesso disponível na conta.
- Testes locais sem credenciais e avaliação separada com o modelo real.

O comando do agente será adicionado quando a integração com LLM estiver implementada. O modelo ainda não foi chamado nem avaliado neste projeto.

## Histórico de desenvolvimento

Cada etapa deve produzir uma alteração funcional ou documental verificável antes do próximo commit. O Codex prepara, testa e executa os commits e pushes conforme autorizado pelo usuário. Não reescrever histórico nem usar force-push. Consulte [o plano](docs/plano.md) para a sequência proposta.

## Uso de assistência de IA

O Codex foi utilizado na leitura dos materiais, auditoria dos CSVs, levantamento de ambiguidades, proposta técnica, implementação da ingestão, consultas de atendimento, condições comerciais, API, interface local e elaboração/execução dos testes. O usuário orienta o desenvolvimento e autorizou a execução dos commits pelo assistente. Este registro será atualizado nas etapas seguintes. O candidato deve revisar as alterações e compreender as decisões para explicá-las na avaliação.

## Limitações atuais e entrega

Os CSVs são um retrato dos dados fornecidos, sem integração com ERP ou transportadora. Consulta ao banco local não equivale a atualização externa em tempo real. O manual contém ambiguidades registradas na documentação.

Ao final do desenvolvimento, a entrega incluirá o repositório público, este README completo, documentação técnica, 3 a 5 conversas produzidas pelo agente e um PDF gerado a partir da versão final do README e da documentação. **O PDF final ainda não foi gerado.**
