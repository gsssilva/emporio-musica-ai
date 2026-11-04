# Development and delivery preparation

I kept the implementation focused on the supplied store data and manual: ingestion, commercial queries, policy retrieval, bounded agent execution, conversation sessions, a small chat, and evaluation. The catalogue page is secondary, not a shopping application.

## Evidence and revision discipline

I use progressive commits for features, fixes, and documentation, with no force-push. Work is confined to `gsssilva/emporio-musica-ai`. I preserve the original source bytes and record import and retrieval provenance. Deterministic tests and recorded real-model evaluation are identified separately; their revision and scope are documented in [evaluation](avaliacao.md).

I used AI assistance substantially in implementation and documentation, as explained in the [README](../README.md). My submission should make that workflow visible and leave the technical reasoning inspectable.

## Final artifact procedure

1. Review the English Markdown sources, commands, limitations, and example translations.
2. Commit the source documents before building the PDF, so its recorded source revision is verifiable.
3. Generate the PDF using `scripts/build_docs.py`, render its pages, and inspect layout and links.
4. Commit the PDF in a subsequent artifact commit, keeping its source revision intact.
5. Submit the English PDF through the recruitment email's form with the public repository linked inside it.
6. Keep the submitted repository unchanged after the applicable cutoff.

I do not describe an artifact as submitted until the submission channel confirms it. The application remains a local demonstration; delivery does not include public hosting, external messaging, or commerce operations.
