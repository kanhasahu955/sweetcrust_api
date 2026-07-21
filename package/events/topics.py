"""Cross-service channel / topic names."""

ORDER_STATUS = "sc:order_status"
CHAT_MESSAGE = "sc:chat_message"
USER_PRESENCE = "sc:user_presence"
DELIVERY_LOCATION = "sc:delivery_location"
# Ops fan-out: admin console + per-user apps (shop approval, PO, etc.)
ADMIN_EVENT = "sc:admin_event"
USER_EVENT = "sc:user_event"
