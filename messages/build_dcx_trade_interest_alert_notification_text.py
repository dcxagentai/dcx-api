"""
CONTEXT:
This file formats one cross-surface notification for a confirmed/published trade that matches a
trader's saved material interests.
It exists so email and WhatsApp use the same compact investor-demo alert text.

CONTRACT:
preconditions:
- trade_publication_id is the market-deal publication the recipient can open.
- trade_snapshot contains the current published trade terms.
postconditions:
- Returns one plain text notification suitable for email and WhatsApp.
side_effects: []
idempotent: true
retry_safe: true
async: false

NARRATIVE:
WHY this exists:
  Interested-trade alerts should be short and action-oriented. The matching logic belongs elsewhere;
  this file only renders the notification body.
WHEN TO USE it:
  Use it when a saved material interest overlaps with a confirmed, published trade.
WHEN NOT TO USE it:
  Do not use it for private trade chats or topic AI responses; those have their own reference formats.
WHAT CAN GO WRONG:
  Some trade terms can be missing. The formatter omits missing pieces rather than inventing values.
WHAT COMES NEXT:
  A WhatsApp template variant can reuse the same core terms once the template is approved.

TESTS:
- send_dcx_trade_interest_alert_notifications_test.py verifies the resulting notification body.

ERRORS:
- none

CODE:
"""

from __future__ import annotations

from users.account_phone.dcx_whatsapp_phone_link_challenge_support import read_dcx_app_base_url


def build_dcx_trade_interest_alert_notification_text(
    trade_publication_id: int,
    trade_snapshot: dict,
) -> str:
    material = str(trade_snapshot.get("normalized_material_name") or "Trade").strip()
    trade_side = str(trade_snapshot.get("normalized_trade_side") or "").strip()
    quantity_value = trade_snapshot.get("normalized_quantity_value")
    quantity_unit = str(trade_snapshot.get("normalized_quantity_unit") or "").strip()
    price_value = trade_snapshot.get("normalized_price_value")
    currency_code = str(trade_snapshot.get("normalized_currency_code") or "").strip()
    price_basis = str(trade_snapshot.get("normalized_price_unit_basis") or "").strip()
    destination = str(trade_snapshot.get("normalized_destination_location") or "").strip()
    origin = str(trade_snapshot.get("normalized_origin_location") or "").strip()
    app_trade_url = f"{read_dcx_app_base_url().rstrip('/')}/trades/board/{trade_publication_id}"

    terms: list[str] = []
    if trade_side:
        terms.append(trade_side.title())
    if quantity_value is not None and quantity_unit:
        terms.append(f"{_format_number(quantity_value)} {quantity_unit}")
    if price_value is not None and currency_code:
        price_text = f"{_format_number(price_value)} {currency_code}"
        if price_basis:
            price_text = f"{price_text} / {price_basis}"
        terms.append(price_text)

    route_text = ""
    if origin and destination:
        route_text = f"{origin} -> {destination}"
    elif destination:
        route_text = destination
    elif origin:
        route_text = origin

    message_parts = [
        "New DCX trade matching your interests",
        material,
    ]
    if terms:
        message_parts.append(" | ".join(terms))
    if route_text:
        message_parts.append(route_text)
    message_parts.append(f"Open: {app_trade_url}")

    return "\n\n".join(message_parts)


def _format_number(value: object) -> str:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return str(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return f"{numeric_value:g}"
