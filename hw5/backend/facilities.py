"""Facilities agent: rent, utilities, repairs, and lease due dates."""

from backend.common import make_worker

agent = make_worker(
    "facilities", "get_ticket", "get_books", "pay_rent", "record_payment",
    "check_spend_limit", "update_ticket_status",
)
