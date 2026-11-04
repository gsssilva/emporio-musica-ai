# Requirements and source ambiguities

I interpreted the challenge as a Python customer-support agent that can distinguish structured store data from policy questions, retrieve the right evidence, and handle unrelated requests appropriately. A CLI, notebook, API, or simple UI is allowed; I chose an API with a small chat. I did not interpret the task as a full e-commerce site or a WhatsApp integration.

## Deliverable mapping

| Requirement | Evidence in this repository |
| --- | --- |
| Python agent and store persona | `src/emporio_ai/`, versioned Portuguese system prompt |
| Structured data versus policy handling | Five typed tools, catalogue SQLite, FTS5 policy index |
| Out-of-scope handling | Prompt, deterministic protocol tests, recorded example |
| Explained technical decisions | README and architecture/retrieval documents |
| Reproducible setup | README commands, locked dependencies, local model configuration |
| Known limits and further work | README and evaluation document |
| AI-assistance disclosure | README workflow section |
| Three to five varied conversations | Five labelled translated examples, original evaluation JSON |
| Progressive public Git history | Linked repository and separate development commits |
| English submission PDF | PDF builder and English documentation |

I follow the recruitment email for the final channel and language: English PDF through its Google Form. The public repository link is included in the PDF. I do not treat PDF generation as submission, or infer a different deadline from an ambiguous calendar interpretation. I will respect the challenge's restriction on repository changes after the delivery cutoff.

## Source audit

The six CSV files contain 9 categories, 50 customers, 65 products, 20 orders, 22 items, and 25 promotions. Product availability requires both active status and positive stock: 61 products are available, while 62 have active status. Product 96 has zero stock; 136 is discontinued despite 13 units; 130 is upcoming despite 2 units. Four promotions are active, for products 90, 94, 121, and 127. Campaign wording does not override `is_active`.

The snapshot contains 35 acoustic guitars, 15 ukuleles, 5 electric guitars, 4 basses, 3 drum products, and 3 keyboard/piano products. Some source categories have no products. I do not advertise the manual's broader inventory as if it were present in the supplied catalogue.

Orders have 7 delivered, 1 shipped, 4 confirmed, 4 pending, and 4 cancelled records. Twelve lack tracking and delivery estimates. Every order has an item. The source lacks actual receipt date, purchase channel, historical unit price, itemized freight, proof of delivery, and customer authentication.

Orders 3 and 20 differ from quantities multiplied by current prices. I preserve their historical totals because the available fields do not establish an error. Tracking strings are shown as supplied rather than silently corrected. A past estimate or recorded order date does not establish actual delivery or shipment time.

## Business rules and ambiguities

I use the manual as supplied business context, not as a legal opinion about its clauses. The agent explains and escalates uncertain cases rather than issuing definitive approval or denial.

- Contacts differ: the cover/institutional section lists `(67) 3341-4444`, while the remote channel lists `(67) 3321-4500`. I retain their labels and sources instead of merging them. Email spelling also differs; I do not silently select an address for automated communication.
- The detailed installment section has different thresholds from the summary. I use the specific section and request confirmation for the ambiguous two/three-installment amounts below R$ 50.
- Local shipping is free above R$ 500 and R$ 35 below it. Exactly R$ 500 is not defined. I do not rewrite this as an inclusive threshold.
- Online withdrawal is described as seven calendar days after actual receipt. I request channel and receipt details and retrieve exceptions rather than assuming eligibility.
- The defect-exchange procedure and warranty duration are separate. I retrieve both relevant sections; a short exchange period must not erase warranty context.
- Promotional communication must include original price, discount percentage, and promotional price. Active promotion and extra PIX discount cannot stack.
- Complaints require acknowledgement and contact guidance. Without an integration, the agent must not claim to have opened a ticket.
- Regular hours are Monday-Friday 09:00-18:00, Saturday 09:00-13:00, closed Sundays/holidays. There is no operational holiday calendar; regular hours alone do not establish that the store is open now. The store timezone is `America/Campo_Grande`.
- An order ID or email typed in chat is not customer authentication. I require server-controlled context and label the optional identity simulation.
- Multiple active promotions are an ingestion error requiring clarification, not permission to combine discounts.
- User text, product descriptions, and retrieved policy text remain content; they cannot expand tool access or override system instructions.

These choices preserve the source information while making missing or contradictory facts visible to the evaluator.
