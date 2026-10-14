# Campus Customs MCP Server

A FastMCP server that gives every HW5 agent a shared set of tools for resolving
Campus Customs tickets. Agents call these tools instead of writing SQL themselves.

## Database

`data/campus_customs_new.db`, a working copy of `data/campus_customs.db`. The
server creates the copy on first use, so the original data is never modified.

## Tools

| Tool | What it does |
|---|---|
| `get_ticket(ticket_id)` | Returns one ticket. |
| `list_open_tickets()` | Lists every ticket that isn't resolved, closed or cancelled, oldest first. |
| `update_ticket_status(ticket_id, status, note)` | Sets a ticket's status and adds a note. |
| `get_inventory(sku?)` | Stock on hand with list price and unit cost, plus everything at zero stock. |
| `fulfill_customer_order(sku, size, qty, ticket_id?)` | Ships the order from inventory if there's enough stock. Otherwise it orders the missing amount from the vendor (or reuses an open vendor order for the same item) and returns the lead days. |
| `reorder_stock(sku, size, qty, ticket_id?)` | Orders more stock from the vendor without filling a customer order, for example to cover a bulk deal that's still being negotiated. Reuses an open vendor order for the same item. |
| `receive_stock(sku, size, qty, invoice_id?)` | Adds a vendor delivery to inventory and lists the tickets waiting on that item. The invoice stays open until it's paid. |
| `negotiate_discount(sku, size, qty, pushback_rounds=0, accepted=False, ticket_id?)` | Offers 10% off and raises the offer each time the customer pushes back (raising it faster for larger orders). The discount never goes above 50% or brings the price below cost plus 25%. Once the customer accepts, it runs `fulfill_customer_order`. |
| `pay_rent(lease_id, approved_by, account="checking", ticket_id?)` | Checks the cash balance, records the rent payment, takes it out of the account, and moves the lease's next due date forward one month. |
| `get_books()` | Cash balances, open invoices, leases, recent payments and vendors. |
| `record_invoice(vendor_id, amount, due_date, description, ticket_id?)` | Records a bill the shop owes a vendor. No cash moves. |
| `pay_invoice(invoice_id, approved_by, account="checking", ticket_id?)` | Pays an open invoice: takes the money out of cash, records the payment and marks the invoice paid. |
| `record_payment(kind, amount, approved_by, description, account="checking", ticket_id?)` | Records other money going out (utilities, repairs) and takes it out of cash. |
| `record_income(amount, source, account="checking", ticket_id?)` | Records money coming in and adds it to cash. |
| `check_spend_limit(tool, account="checking", lease_id?, invoice_id?, amount?)` | Says whether a payment is over 80% of the account balance and so needs the boss's sign-off. |
| `list_tickets()` | Every ticket with its status, and whether it counts as open or resolved. |
| `prepare_payment(tool, args, amount, prepared_by, purpose, ticket_id?)` | Queues a `pay_rent` / `pay_invoice` / `record_payment` call for human approval. No cash moves. The agents' spend guard calls this instead of paying. |
| `list_pending_payments(status="pending")` | Prepared payments: pending, approved, rejected, or all. |
| `approve_payment(pending_id, approved_by)` | A human approved: runs the prepared payment. **The only path that moves cash.** |
| `reject_payment(pending_id, rejected_by, reason)` | A human rejected: nothing is paid, and the ticket is escalated. |
| `get_cash(account="checking")` | Current balance of one cash account. |
| `reset_database()` | Replaces the working database with a fresh copy of `campus_customs.db`. |

Agents never move cash themselves. When an agent calls `pay_rent`, `pay_invoice` or `record_payment`, the backend's guard turns it into `prepare_payment`; a human approves through `POST /payments/{id}/approve` (see `backend/main.py`). Prepared payments live in a `pending_payments` table that the server creates on first use.

Set `CAMPUS_DB_PATH` to point the server at a different database copy (useful for tests).

## Run

```bash
source .venv/bin/activate
python mcp_server/server.py
```
