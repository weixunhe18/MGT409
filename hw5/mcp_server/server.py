"""Campus Customs MCP server.

Shared tool server for every agent in HW5. Talks to data/campus_customs_new.db,
a working copy of the original data/campus_customs.db (created on first use so
the original stays untouched).
"""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import os
import shutil
import sqlite3

from fastmcp import FastMCP


HW_ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_DB = HW_ROOT / "data" / "campus_customs.db"
DB_PATH = Path(os.environ.get("CAMPUS_DB_PATH", HW_ROOT / "data" / "campus_customs_new.db"))

START_DISCOUNT = 0.10
SPEND_LIMIT_SHARE = 0.80  # agents may spend up to 80% of an account's balance without boss sign-off
MAX_DISCOUNT = 0.50
MIN_MARKUP_OVER_COST = 0.25  # never sell below unit_cost * 1.25

# Which vendor restocks which product line (vendor ids from the vendors table).
VENDOR_BY_SKU_PREFIX = {
    "CC-HOOD": 1,  # Bulldog Print Co — apparel reprint
    "CC-TEE": 1,
    "CC-HAT": 1,
    "CC-MUG": 2,  # Elm City Gifts — mugs and small goods
}

mcp = FastMCP("campus-customs")


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        shutil.copy(ORIGINAL_DB, DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Payments agents have prepared, waiting for a human to approve. Not in the original DB.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pending_payments ("
        " id INTEGER PRIMARY KEY, tool TEXT NOT NULL, args TEXT NOT NULL, amount REAL NOT NULL,"
        " purpose TEXT, prepared_by TEXT NOT NULL, ticket_id INTEGER, status TEXT NOT NULL,"
        " created_at TEXT NOT NULL, decided_by TEXT, decided_at TEXT, result TEXT)"
    )
    return conn


def shop_today(conn: sqlite3.Connection) -> date:
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    return date.fromisoformat(row["date_today"])


def add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(f"cannot add {months} months to {d}")


def vendor_for_sku(conn: sqlite3.Connection, sku: str) -> sqlite3.Row | None:
    for prefix, vendor_id in VENDOR_BY_SKU_PREFIX.items():
        if sku.startswith(prefix):
            return conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
    return None


def update_ticket(conn: sqlite3.Connection, ticket_id: int | None, status: str, note: str) -> None:
    if ticket_id is None:
        return
    conn.execute(
        "UPDATE tickets SET status = ?, notes = COALESCE(notes, '') || ' | ' || ? WHERE id = ?",
        (status, note, ticket_id),
    )


def _place_reorder(conn: sqlite3.Connection, sku: str, size: str, qty: int) -> dict:
    """Order qty units from the right vendor, or reuse an open order for the same item."""
    vendor = vendor_for_sku(conn, sku)
    if vendor is None:
        return {"status": "error", "message": f"No vendor mapped for {sku}"}

    today = shop_today(conn)
    expected = today + timedelta(days=vendor["lead_days"])

    # Reuse an open reorder invoice for this item instead of ordering twice.
    existing = conn.execute(
        "SELECT * FROM invoices WHERE vendor_id = ? AND status = 'open' AND description LIKE ?",
        (vendor["id"], f"%{sku} {size}%"),
    ).fetchone()
    if existing is not None:
        invoice_id = existing["id"]
        message = f"Existing open vendor order (invoice {invoice_id}) already covers {sku} {size}"
        status = "existing_order"
    else:
        pricing = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        amount = round(pricing["unit_cost"] * qty, 2)
        cur = conn.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) "
            "VALUES (?, ?, ?, 'open', ?)",
            (vendor["id"], amount, expected.isoformat(), f"Reorder {qty} x {sku} {size}"),
        )
        invoice_id = cur.lastrowid
        message = f"Placed order with {vendor['name']} for {qty} x {sku} {size} (invoice {invoice_id})"
        status = "ordered"

    return {"status": status, "vendor": vendor["name"], "invoice_id": invoice_id,
            "lead_days": vendor["lead_days"], "expected_date": expected.isoformat(), "message": message}


def _fulfill_order(conn: sqlite3.Connection, sku: str, size: str, qty: int, ticket_id: int | None) -> dict:
    """Shared logic for fulfill_customer_order, also used by negotiate_discount."""
    if qty <= 0:
        return {"status": "error", "message": "qty must be positive"}

    item = conn.execute(
        "SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)
    ).fetchone()
    if item is None:
        return {"status": "error", "message": f"No inventory row for {sku} size {size}"}

    if item["qty"] >= qty:
        conn.execute(
            "UPDATE inventory SET qty = qty - ? WHERE sku = ? AND size = ?", (qty, sku, size)
        )
        update_ticket(conn, ticket_id, "resolved", f"Fulfilled {qty} x {sku} {size} from {item['location']}")
        return {
            "status": "fulfilled",
            "sku": sku,
            "size": size,
            "qty": qty,
            "location": item["location"],
            "remaining_stock": item["qty"] - qty,
            "lead_days": 0,
        }

    # Not enough stock: reorder the shortfall from the right vendor.
    shortfall = qty - item["qty"]
    order = _place_reorder(conn, sku, size, shortfall)
    if order["status"] == "error":
        return order
    vendor = {"name": order["vendor"], "lead_days": order["lead_days"]}
    invoice_id, order_note, expected = order["invoice_id"], order["message"], date.fromisoformat(order["expected_date"])

    update_ticket(conn, ticket_id, "awaiting_restock", f"{order_note}; ETA {expected.isoformat()}")
    return {
        "status": "backordered",
        "sku": sku,
        "size": size,
        "qty_requested": qty,
        "in_stock": item["qty"],
        "shortfall": shortfall,
        "vendor": vendor["name"],
        "invoice_id": invoice_id,
        "lead_days": vendor["lead_days"],
        "expected_date": expected.isoformat(),
        "message": order_note,
    }


@mcp.tool
def fulfill_customer_order(sku: str, size: str, qty: int, ticket_id: int | None = None) -> dict:
    """Fulfill a customer order from inventory.

    If enough stock exists, decrement inventory and mark the ticket resolved.
    If not, place a reorder with the vendor for that product line (or reuse an
    open vendor order for the same item) and return the vendor's lead days.
    """
    with connect() as conn:
        return _fulfill_order(conn, sku, size, qty, ticket_id)


@mcp.tool
def reorder_stock(sku: str, size: str, qty: int, ticket_id: int | None = None) -> dict:
    """Order more stock from the vendor without filling a customer order.

    Use when a pending order (e.g. a bulk deal still being negotiated) needs more
    units than are on hand. Reuses an open vendor order for the same item.
    """
    if qty <= 0:
        return {"status": "error", "message": "qty must be positive"}
    with connect() as conn:
        order = _place_reorder(conn, sku, size, qty)
        if order["status"] != "error" and ticket_id is not None:
            conn.execute(
                "UPDATE tickets SET notes = COALESCE(notes, '') || ' | ' || ? WHERE id = ?",
                (f"{order['message']}; ETA {order['expected_date']}", ticket_id),
            )
        return {"sku": sku, "size": size, "qty": qty, **order}


@mcp.tool
def pay_rent(lease_id: int, approved_by: str, account: str = "checking", ticket_id: int | None = None) -> dict:
    """Pay the next rent installment on a lease, on or before its due date.

    Checks the cash balance first, records the payment, debits the account,
    and advances the lease's next_due by one month.
    """
    with connect() as conn:
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (lease_id,)).fetchone()
        if lease is None:
            return {"status": "error", "message": f"No lease {lease_id}"}

        cash = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if cash is None:
            return {"status": "error", "message": f"No cash account {account}"}

        rent = lease["monthly_rent"]
        if cash["balance"] < rent:
            return {
                "status": "insufficient_funds",
                "rent": rent,
                "balance": cash["balance"],
                "message": "Balance too low to pay rent; escalate before the due date.",
            }

        today = shop_today(conn)
        due = date.fromisoformat(lease["next_due"])
        new_balance = round(cash["balance"] - rent, 2)
        next_due = add_months(due, 1)

        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES ('rent', ?, ?, ?, ?, ?)",
            (lease_id, rent, account, today.isoformat(), approved_by),
        )
        conn.execute(
            "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
            (new_balance, today.isoformat(), account),
        )
        conn.execute(
            "UPDATE leases SET next_due = ? WHERE id = ?", (next_due.isoformat(), lease_id)
        )
        update_ticket(conn, ticket_id, "resolved", f"Paid rent {rent:.2f} for due date {due.isoformat()}")

        return {
            "status": "paid",
            "lease": lease["space_name"],
            "landlord": lease["landlord"],
            "amount": rent,
            "due_date": due.isoformat(),
            "paid_on": today.isoformat(),
            "on_time": today <= due,
            "new_balance": new_balance,
            "next_due": next_due.isoformat(),
        }


@mcp.tool
def negotiate_discount(
    sku: str,
    size: str,
    qty: int,
    pushback_rounds: int = 0,
    accepted: bool = False,
    ticket_id: int | None = None,
) -> dict:
    """Propose a bulk discount for a customer request.

    Starts at 10% and steps up each time the customer pushes back
    (pushback_rounds = number of times they've said no). Bigger orders step up
    faster. Never exceeds 50%, and never prices below unit cost plus a 25%
    markup. When the customer accepts, passes the order to fulfill_customer_order.
    """
    with connect() as conn:
        pricing = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if pricing is None:
            return {"status": "error", "message": f"No pricing for {sku}"}

        list_price = pricing["list_price"]
        unit_cost = pricing["unit_cost"]
        floor_price = unit_cost * (1 + MIN_MARKUP_OVER_COST)
        margin_cap = max(0.0, 1 - floor_price / list_price)
        cap = min(MAX_DISCOUNT, margin_cap)

        step = 0.10 if qty >= 20 else 0.075 if qty >= 10 else 0.05
        discount = min(START_DISCOUNT + step * pushback_rounds, cap)
        discount = round(discount, 4)
        unit_price = round(list_price * (1 - discount), 2)

        stock = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        in_stock = stock["qty"] if stock else 0

        offer = {
            "sku": sku,
            "size": size,
            "qty": qty,
            "list_price": list_price,
            "discount_pct": round(discount * 100, 1),
            "unit_price": unit_price,
            "order_total": round(unit_price * qty, 2),
            "margin_pct_after_discount": round((unit_price - unit_cost) / unit_price * 100, 1),
            "at_max_discount": discount >= cap,
            "in_stock": in_stock,
            "enough_stock": in_stock >= qty,
        }

        if not accepted:
            update_ticket(
                conn, ticket_id, "negotiating",
                f"Offered {offer['discount_pct']}% off ({unit_price:.2f}/unit) after {pushback_rounds} pushback(s)",
            )
            offer["status"] = "offer"
            if offer["at_max_discount"]:
                offer["message"] = "This is the final offer; the discount cannot go higher."
            return offer

        # Customer accepted: hand off to the order-fulfillment logic.
        offer["status"] = "accepted"
        offer["fulfillment"] = _fulfill_order(conn, sku, size, qty, ticket_id)
        return offer


# --- Read-only lookups -------------------------------------------------------


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Look up one ticket by id."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return dict(row) if row else {"status": "error", "message": f"No ticket {ticket_id}"}


@mcp.tool
def get_inventory(sku: str | None = None) -> dict:
    """List stock on hand with list price and unit cost, optionally for one SKU."""
    with connect() as conn:
        sql = (
            "SELECT i.sku, i.name, i.size, i.qty, i.location, p.list_price, p.unit_cost "
            "FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku"
        )
        rows = conn.execute(sql + " WHERE i.sku = ?" if sku else sql, (sku,) if sku else ()).fetchall()
        items = [dict(r) for r in rows]
        return {"shop_date": shop_today(conn).isoformat(), "items": items,
                "out_of_stock": [f"{r['sku']} {r['size']}" for r in items if r["qty"] == 0]}


@mcp.tool
def get_books() -> dict:
    """Snapshot of the books: cash balances, open invoices, leases, recent payments."""
    with connect() as conn:
        q = lambda sql: [dict(r) for r in conn.execute(sql).fetchall()]
        return {
            "shop_date": shop_today(conn).isoformat(),
            "cash_accounts": q("SELECT * FROM cash_accounts"),
            "open_invoices": q(
                "SELECT i.*, v.name AS vendor FROM invoices i JOIN vendors v ON v.id = i.vendor_id "
                "WHERE i.status = 'open' ORDER BY due_date"
            ),
            "leases": q("SELECT * FROM leases"),
            "payments": q("SELECT * FROM payments ORDER BY id DESC LIMIT 20"),
            "vendors": q("SELECT * FROM vendors"),
        }


# --- Accounting --------------------------------------------------------------


def _debit(conn: sqlite3.Connection, account: str, amount: float) -> dict | None:
    """Take money out of a cash account. Returns an error dict if it can't."""
    cash = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if cash is None:
        return {"status": "error", "message": f"No cash account {account}"}
    if cash["balance"] < amount:
        return {"status": "insufficient_funds", "amount": amount, "balance": cash["balance"]}
    conn.execute(
        "UPDATE cash_accounts SET balance = ROUND(balance - ?, 2), date = ? WHERE name = ?",
        (amount, shop_today(conn).isoformat(), account),
    )
    return None


@mcp.tool
def record_invoice(vendor_id: int, amount: float, due_date: str, description: str,
                   ticket_id: int | None = None) -> dict:
    """Record a bill we owe a vendor (accounts payable). No cash moves until it's paid."""
    if amount <= 0:
        return {"status": "error", "message": "amount must be positive"}
    with connect() as conn:
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"status": "error", "message": f"No vendor {vendor_id}"}
        cur = conn.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) "
            "VALUES (?, ?, ?, 'open', ?)",
            (vendor_id, round(amount, 2), date.fromisoformat(due_date).isoformat(), description),
        )
        update_ticket(conn, ticket_id, "recorded", f"Recorded invoice {cur.lastrowid} from {vendor['name']}")
        return {"status": "recorded", "invoice_id": cur.lastrowid, "vendor": vendor["name"],
                "amount": round(amount, 2), "due_date": due_date}


@mcp.tool
def pay_invoice(invoice_id: int, approved_by: str, account: str = "checking",
                ticket_id: int | None = None) -> dict:
    """Pay an open vendor invoice: debit cash, log the payment, mark the invoice paid."""
    with connect() as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if inv is None:
            return {"status": "error", "message": f"No invoice {invoice_id}"}
        if inv["status"] != "open":
            return {"status": "error", "message": f"Invoice {invoice_id} is {inv['status']}, not open"}
        if (err := _debit(conn, account, inv["amount"])) is not None:
            return err
        today = shop_today(conn).isoformat()
        conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES ('invoice', ?, ?, ?, ?, ?)",
            (invoice_id, inv["amount"], account, today, approved_by),
        )
        conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (invoice_id,))
        update_ticket(conn, ticket_id, "resolved", f"Paid invoice {invoice_id} ({inv['amount']:.2f})")
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
        return {"status": "paid", "invoice_id": invoice_id, "amount": inv["amount"],
                "paid_on": today, "on_time": today <= inv["due_date"], "new_balance": balance}


@mcp.tool
def record_payment(kind: str, amount: float, approved_by: str, description: str,
                   account: str = "checking", ticket_id: int | None = None) -> dict:
    """Record money going out that isn't rent or a vendor invoice (e.g. utilities, repairs)."""
    if amount <= 0:
        return {"status": "error", "message": "amount must be positive"}
    with connect() as conn:
        if (err := _debit(conn, account, amount)) is not None:
            return err
        today = shop_today(conn).isoformat()
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
            "VALUES (?, NULL, ?, ?, ?, ?)",
            (kind, round(amount, 2), account, today, approved_by),
        )
        update_ticket(conn, ticket_id, "resolved", f"Paid {kind} {amount:.2f}: {description}")
        balance = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()[0]
        return {"status": "paid", "payment_id": cur.lastrowid, "kind": kind, "amount": round(amount, 2),
                "paid_on": today, "new_balance": balance}


@mcp.tool
def record_income(amount: float, source: str, account: str = "checking",
                  ticket_id: int | None = None) -> dict:
    """Record money coming in (e.g. a customer payment) and credit the cash account."""
    if amount <= 0:
        return {"status": "error", "message": "amount must be positive"}
    with connect() as conn:
        cash = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if cash is None:
            return {"status": "error", "message": f"No cash account {account}"}
        today = shop_today(conn).isoformat()
        conn.execute(
            "UPDATE cash_accounts SET balance = ROUND(balance + ?, 2), date = ? WHERE name = ?",
            (amount, today, account),
        )
        update_ticket(conn, ticket_id, "resolved", f"Received {amount:.2f} from {source}")
        return {"status": "received", "amount": round(amount, 2), "source": source,
                "new_balance": round(cash["balance"] + amount, 2)}


# --- Tickets -----------------------------------------------------------------

CLOSED_STATUSES = ("resolved", "closed", "cancelled")
WAITING_STATUSES = ("awaiting_restock", "awaiting_approval", "negotiating")


@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that isn't resolved, closed, or cancelled, oldest first."""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM tickets WHERE status NOT IN ({','.join('?' * len(CLOSED_STATUSES))}) "
            "ORDER BY created_at",
            CLOSED_STATUSES,
        ).fetchall()
        return {"shop_date": shop_today(conn).isoformat(), "tickets": [dict(r) for r in rows]}


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str) -> dict:
    """Set a ticket's status and append a note (e.g. 'escalated', 'waiting_on_customer', 'resolved').

    A ticket waiting on a process (restock, human approval, negotiation) keeps that status
    unless it's being escalated; the note is still added.
    """
    with connect() as conn:
        row = conn.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return {"status": "error", "message": f"No ticket {ticket_id}"}
        if row["status"] in WAITING_STATUSES and status not in ("escalated", "cancelled"):
            status = row["status"]
        update_ticket(conn, ticket_id, status, note)
        return dict(conn.execute("SELECT id, status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone())


# --- Stock receiving ---------------------------------------------------------


@mcp.tool
def receive_stock(sku: str, size: str, qty: int, invoice_id: int | None = None) -> dict:
    """Add a vendor delivery to inventory and list the tickets waiting on that item.

    The vendor invoice stays open (it's still owed) until accounting pays it.
    """
    if qty <= 0:
        return {"status": "error", "message": "qty must be positive"}
    with connect() as conn:
        item = conn.execute("SELECT * FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            return {"status": "error", "message": f"No inventory row for {sku} size {size}"}
        conn.execute("UPDATE inventory SET qty = qty + ? WHERE sku = ? AND size = ?", (qty, sku, size))
        waiting = conn.execute(
            "SELECT id, requester, qty FROM tickets WHERE sku = ? AND size = ? AND status = 'awaiting_restock'",
            (sku, size),
        ).fetchall()
        return {"status": "received", "sku": sku, "size": size, "qty_received": qty,
                "new_stock": item["qty"] + qty, "invoice_id": invoice_id,
                "tickets_waiting": [dict(r) for r in waiting]}


# --- Spend limit -------------------------------------------------------------


@mcp.tool
def check_spend_limit(tool: str, account: str = "checking", lease_id: int | None = None,
                      invoice_id: int | None = None, amount: float | None = None) -> dict:
    """Would this payment need boss sign-off? Limit is 80% of the account's current balance.

    tool is pay_rent (needs lease_id), pay_invoice (needs invoice_id), or record_payment (needs amount).
    """
    with connect() as conn:
        if tool == "pay_rent":
            row = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (lease_id,)).fetchone()
            amount = row[0] if row else None
        elif tool == "pay_invoice":
            row = conn.execute("SELECT amount FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            amount = row[0] if row else None
        cash = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if amount is None or cash is None:
            return {"status": "error", "message": "Unknown lease, invoice, amount, or account"}
        limit = round(cash[0] * SPEND_LIMIT_SHARE, 2)
        return {"tool": tool, "amount": amount, "balance": cash[0], "limit": limit,
                "needs_boss_approval": amount > limit}


# --- Human approval of payments ----------------------------------------------

PAYMENT_TOOLS = {"pay_rent": pay_rent, "pay_invoice": pay_invoice, "record_payment": record_payment}


@mcp.tool
def list_tickets() -> dict:
    """Every ticket with its status, and whether it counts as open or resolved."""
    with connect() as conn:
        rows = conn.execute("SELECT id, type, requester, subject, status FROM tickets ORDER BY id").fetchall()
        return {"tickets": [{**dict(r), "state": "resolved" if r["status"] in CLOSED_STATUSES else "open"}
                            for r in rows]}


@mcp.tool
def prepare_payment(tool: str, args: dict, amount: float, prepared_by: str, purpose: str,
                    ticket_id: int | None = None) -> dict:
    """Queue a payment for human approval. No cash moves until approve_payment runs."""
    if tool not in PAYMENT_TOOLS:
        return {"status": "error", "message": f"{tool} is not a payment tool"}
    with connect() as conn:
        dup = conn.execute(
            "SELECT id FROM pending_payments WHERE tool = ? AND args = ? AND status = 'pending'",
            (tool, json.dumps(args, sort_keys=True)),
        ).fetchone()
        if dup:
            return {"status": "already_pending", "pending_id": dup["id"],
                    "message": "This payment is already waiting for human approval."}
        cur = conn.execute(
            "INSERT INTO pending_payments (tool, args, amount, purpose, prepared_by, ticket_id, status, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)",
            (tool, json.dumps(args, sort_keys=True), amount, purpose, prepared_by, ticket_id,
             datetime.now().isoformat(timespec="seconds")),
        )
        update_ticket(conn, ticket_id, "awaiting_approval",
                      f"Prepared {tool} for {amount:.2f} (pending payment {cur.lastrowid}); waiting for human approval")
        return {"status": "prepared", "pending_id": cur.lastrowid, "tool": tool, "amount": amount,
                "message": "Payment prepared. A human must approve it before any cash moves."}


@mcp.tool
def list_pending_payments(status: str = "pending") -> dict:
    """Payments agents have prepared (status: pending, approved, rejected, or all)."""
    with connect() as conn:
        sql = "SELECT * FROM pending_payments" + ("" if status == "all" else " WHERE status = ?") + " ORDER BY id"
        rows = conn.execute(sql, () if status == "all" else (status,)).fetchall()
        return {"payments": [{**dict(r), "args": json.loads(r["args"]),
                              "result": json.loads(r["result"]) if r["result"] else None} for r in rows]}


@mcp.tool
def approve_payment(pending_id: int, approved_by: str) -> dict:
    """A human approved a prepared payment: run it now. This is the only path that moves cash."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending_payments WHERE id = ?", (pending_id,)).fetchone()
    if row is None:
        return {"status": "error", "message": f"No pending payment {pending_id}"}
    if row["status"] != "pending":
        return {"status": "error", "message": f"Payment {pending_id} is already {row['status']}"}
    args = {**json.loads(row["args"]), "approved_by": approved_by, "ticket_id": row["ticket_id"]}
    result = PAYMENT_TOOLS[row["tool"]](**args)
    ok = result.get("status") == "paid"
    with connect() as conn:
        conn.execute(
            "UPDATE pending_payments SET status = ?, decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
            ("approved" if ok else "pending", approved_by, datetime.now().isoformat(timespec="seconds"),
             json.dumps(result), pending_id),
        )
    return {"pending_id": pending_id, "ticket_id": row["ticket_id"], "executed": ok, "result": result}


@mcp.tool
def reject_payment(pending_id: int, rejected_by: str, reason: str) -> dict:
    """A human rejected a prepared payment. No cash moves."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM pending_payments WHERE id = ?", (pending_id,)).fetchone()
        if row is None or row["status"] != "pending":
            return {"status": "error", "message": f"No pending payment {pending_id}"}
        conn.execute(
            "UPDATE pending_payments SET status = 'rejected', decided_by = ?, decided_at = ?, result = ? WHERE id = ?",
            (rejected_by, datetime.now().isoformat(timespec="seconds"), json.dumps({"reason": reason}), pending_id),
        )
        update_ticket(conn, row["ticket_id"], "escalated", f"Payment {pending_id} rejected by {rejected_by}: {reason}")
        return {"status": "rejected", "pending_id": pending_id, "ticket_id": row["ticket_id"]}


@mcp.tool
def get_cash(account: str = "checking") -> dict:
    """Current balance of one cash account."""
    with connect() as conn:
        row = conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        return dict(row) if row else {"status": "error", "message": f"No cash account {account}"}


@mcp.tool
def reset_database() -> dict:
    """Replace the working database with a fresh copy of the original campus_customs.db."""
    shutil.copy(ORIGINAL_DB, DB_PATH)
    with connect() as conn:
        cash = conn.execute("SELECT * FROM cash_accounts").fetchall()
        return {"status": "reset", "database": DB_PATH.name, "cash_accounts": [dict(r) for r in cash]}


if __name__ == "__main__":
    mcp.run()
