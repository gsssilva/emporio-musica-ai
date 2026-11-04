# Structured-data ingestion

I preserve the original six CSV files and import a validated snapshot with `python -m emporio_ai ingest`. Parsing and SHA-256 hashing use the same bytes, so the provenance refers to exactly what was imported. The original files are not edited.

## Validation before writing

I validate column schemas, CSV structure, UTF-8 encoding, required values, positive IDs, SQLite integer limits, duplicate keys, finite non-negative money, cent precision, item quantities, stock, status domains, dates, JSON specifications, and foreign keys. Every order must have an item. More than one active promotion for a product stops the import for clarification.

I reject duplicate `(order_id, product_id)` item keys because the source has no separate line ID or historical unit-price field that would make their meaning unambiguous.

| Source field | Stored field | Representation |
| --- | --- | --- |
| `price_brl` | `price_cents` | Integer cents |
| `total_brl` | `total_cents` | Preserved historical total in cents |
| `discount_percent` | `discount_bps` | Integer basis points; 10.5% becomes 1050 |
| `specs` | `specs_json` | Normalized JSON object with its content preserved |
| Empty optional order fields | Same field names | `NULL` |

I do not turn an estimated delivery date into a receipt date, correct tracking strings, or recalculate order totals from current prices.

## Transaction and repeatability

After validation, I enable foreign keys and start `BEGIN IMMEDIATE`. The loader checks the database version, prepares the schema, replaces the snapshot in relationship order, inserts parameterized values, and updates metadata. Only then does it commit. A write failure rolls back both data and metadata. Invalid input is rejected before opening the database.

I reject unknown tables and incompatible schema versions rather than overwriting an unrelated database or performing an implicit migration. The current catalogue schema version is 1. Repeating ingestion replaces records instead of accumulating copies. Policies and sessions use separate databases.

## Provenance and checks

`import_metadata` records the schema version, UTC import time, source names, hashes, and row counts. It does not contain conversation text. The operational database itself contains customer records and stays in ignored `runtime/` storage.

The received snapshot contains 9 categories, 50 customers, 65 products, 20 orders, 22 order items, and 25 promotions: 191 records. I use `scripts/audit_data.py` as an independent source check, not a replacement for ingestion validation. Differences between historical totals and current catalogue sums are warnings rather than automatic corrections.

Tests cover invalid inputs, induced write failure and rollback, incompatible databases, and repeat imports. I mark CSVs as `-text` in `.gitattributes` to prevent line-ending normalization from changing their original hashes on another operating system.

## Limits

I load the small snapshot in memory. I did not implement incremental ERP ingestion, change-data capture, or an archive of prior snapshots. Those would require a different data lifecycle and are unnecessary for the supplied volume.
