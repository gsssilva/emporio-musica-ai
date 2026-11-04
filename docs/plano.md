# Desenvolvimento e preparação da entrega

## Escopo executado

O histórico do Git registra implementação progressiva de ingestão, consultas comerciais, API local, retrieval, agente, sessões e correções orientadas por avaliação real. Commits foram executados com autorização do candidato, sem force-push, exclusivamente no repositório `gsssilva/emporio-musica-ai`.

O recorte prioriza o agente Python, dados e políticas do desafio. A interface principal é o chat visual, com Swagger para inspeção técnica. A visualização de catálogo é auxiliar; não foi expandida para uma loja virtual. A restrição de custo levou à inferência local com Ollama, sem API paga.

## Evidências de conclusão

- Validação e importação dos seis CSVs, com preservação dos bytes originais no Git.
- Consultas somente de leitura, descontos e parcelamento calculados no código.
- Recuperação do manual por seção e página, com hash de origem.
- Agente com cinco ferramentas, limites, sessões e bloqueio de pedidos sem contexto autorizado.
- 91 testes automatizados e rodada de 13 cenários com modelo real, documentada separadamente.
- Cinco conversas extraídas da avaliação; identidades simuladas identificadas.
- README e documentação técnica como fontes do gerador de PDF.

Resultados e limites estão em [avaliação](avaliacao.md); instruções de reprodução e PDF, no [README](../README.md).

## Preparação final

As fontes Markdown devem ser commitadas antes de gerar o PDF. O gerador registra a revisão e os hashes das fontes. A preparação inclui renderizar o resultado, conferir páginas e tabelas e publicar o artefato em commit posterior, sem alterar as fontes referenciadas.

O enunciado pede o link do repositório público. O PDF é um complemento solicitado pelo candidato. Não inclui envio automático de e-mail ou publicação de serviço. Gabriel deve revisar a implementação, compreender suas decisões e enviar a entrega no canal da seleção.

Prazo informado: terça-feira, 03/11/2026. O horário exato precisa ser conferido no e-mail do processo. Após o envio, respeitar as restrições de alteração previstas no desafio.
