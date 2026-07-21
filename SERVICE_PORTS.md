# Service ports

- `auth_service` :8001
- `catalog_service` :8002
- `cart_service` :8003
- `payment_service` :8004
- `rider_service` :8005
- `ai_service` :8006
- `store_ops_service` :8007
- `user_service` :8008
- `search_service` :8009
- `assortment_service` :8010
- `pricing_service` :8011
- `promotion_service` :8012
- `inventory_service` :8013
- `picking_service` :8014
- `checkout_service` :8015
- `order_service` :8016
- `invoice_service` :8017
- `location_service` :8018
- `dispatch_service` :8019
- `tracking_service` :8020
- `routing_service` :8021
- `notification_service` :8022
- `support_service` :8023
- `rating_service` :8024
- `analytics_service` :8025
- `forecast_service` :8026
- `commerce_service` :8027 — Residual commerce (wallet/referral)
- `gateway/` :8080 — api-gateway
- `realtime/` :8081

## Deprecated copies (do not run with compose)

Renamed; ports moved so they cannot collide with live services:

- `payments_service` :8104 → use `payment_service` :8004
- `delivery_service` :8105 → use `rider_service` :8005
- `admin_service` :8107 → use `store_ops_service` :8007
