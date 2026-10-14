"""Inventory agent: stock counts, out-of-stock flags, vendor reorders."""

from backend.common import make_worker

agent = make_worker(
    "inventory", "get_ticket", "get_inventory", "fulfill_customer_order", "reorder_stock", "receive_stock",
    "update_ticket_status",
)
