# Policy retrieval

I index the supplied manual with `python -m emporio_ai index-policies`. `pypdf` extracts text into a separate policy database so catalogue imports cannot remove the index.

## Preparing the source

I segment by document section, preserve lists, and retain all source pages when a section crosses a page break. I remove repeated headers and footers without rewriting policy content. The eight-page manual produces 29 chunks: its cover and 28 sections. I retain the cover because its contact details differ from the institutional table.

Each source includes a stable ID, section, title, pages, document name, and SHA-256 hash of the original bytes. Indexing builds a temporary database and replaces the existing index only after the new version is complete.

## Search strategy

I use SQLite FTS5/BM25 with stronger title weighting, accent normalization, stop-word filtering, and controlled Portuguese term expansion. Search terms are sanitized before forming an FTS expression. Search returns at most five primary matches plus related sections, with a total cap of ten.

I explicitly relate return eligibility to exceptions, defects to warranty, payment to promotion rules, and contact sections to the cover and WhatsApp channel. Complaint wording also retrieves the complaint procedure and its related context. These relationships supply evidence; they do not approve a customer's claim.

An unmatched query returns an empty list. A lexical ranking score is not a probability of correctness. I would evaluate relevant-section recall on unseen paraphrases before adopting embeddings or a hybrid retriever.

## Verification and limits

I test provenance, section boundaries, cross-page continuity, numbered procedures, related context, invalid queries, rebuilds without duplicates, and complaint paraphrases. Indexing does not call an LLM. The approach remains sensitive to vocabulary, so a retrieved source must still be checked for relevance and correctly interpreted in the final answer.
