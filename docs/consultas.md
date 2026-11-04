# Queries and commercial rules

I expose store facts through `StoreQueries`, using SQLite read-only connections and `PRAGMA query_only`. SQL values are parameterized, and each result projects only fields needed by the assistant.

## Catalogue

Search supports text, category, budget, availability, and a limit from 1 to 10 results. I normalize accents and selected Portuguese category plurals. Results are ordered by current price and ID, with total-match and truncation indicators.

I define availability as `status == active` and positive stock. Product detail retains the source status so the assistant can explain out-of-stock, discontinued, and upcoming items. A quote for a new purchase requires availability.

Only active promotions affect current prices. Results include list price, discount in basis points, and current price. The search budget applies to that current price without assuming PIX payment. For 65 products, applying the final text and price filters in Python avoids SQLite floating-point arithmetic without adding search infrastructure. A larger catalogue would need indexed search and pagination.

## Payment calculations

I calculate in integer cents and basis points, rounding half up. Installment remainders go to the first installments so their sum remains exact.

- PIX: 5% off list price when there is no active promotion; no additional PIX discount on an active promotion.
- Debit and bank slip: one payment at the current price.
- Credit: 1 to 12 installments; installments 4-6 require at least R$ 80 each, and 7-12 require at least R$ 100 each.
- Two or three installments with any installment below R$ 50 return `needs_confirmation`, because section 3.1 is ambiguous at this boundary.
- Combined payment methods are not calculated.

I use manual sections 3, 3.1, and 6.2 as business inputs. A quote is not credit approval or a transaction. Promotional communication must show the original price, discount percentage, and promotional price. The response safeguard and product cards make these values explicit when applicable.

## Orders and access

`get_order(order_id, authorized_customer_id=...)` requires customer context supplied by the server. The SQL filters both order and customer. A missing order and another customer's order return the same diagnostic.

I return recorded status, historical total, payment method, tracking, estimated delivery, and items. I omit customer name, email, phone, customer ID, and internal notes. Actual receipt and purchase channel remain unknown. A past estimate does not authorize an invented update.

This filter is authorization logic, not customer authentication. The optional fixed environment identity is a clearly labelled simulation; neither model arguments nor the browser can choose it.

## Freshness and verification

Results identify `local_snapshot` and import time. Repeating a query reads the imported database, not an external ERP or carrier.

Tests cover stock and status together, active promotions, non-stacking PIX, installment boundaries and rounding, budgets, truncation, SQL-like text input, order filtering, minimized fields, and blocked writes.
