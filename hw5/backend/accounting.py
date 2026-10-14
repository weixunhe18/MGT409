"""Accounting agent: keeps the books for money in and money out."""

from backend.common import make_worker

agent = make_worker(
    "accounting",
    "get_ticket", "get_books", "record_invoice", "pay_invoice", "record_payment", "record_income",
    "check_spend_limit", "update_ticket_status",
)
