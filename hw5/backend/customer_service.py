"""Customer service agent: discounts, order status, complaints. Iron Man voice."""

from backend.common import make_worker

agent = make_worker("customer_service", "get_ticket", "get_inventory", "negotiate_discount", "update_ticket_status")
