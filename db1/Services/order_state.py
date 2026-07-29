from db1.exception.exceptions import InvalidOrderTransition

ALLOWED_TRANSITIONS = {
    "pending": {"paid", "cancelled"},
    "paid": {"refunded"},
    "cancelled": set(),
    "refunded": set(),
}


def transition_order_status(order, new_status: str):
    allowed = ALLOWED_TRANSITIONS.get(order.status, set())
    if new_status not in allowed:
        raise InvalidOrderTransition(
            detail=f"Cannot transition order from '{order.status}' to '{new_status}'"
        )
    order.status = new_status