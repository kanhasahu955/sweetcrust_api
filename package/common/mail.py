"""SMTP helpers — no-op when SMTP env keys are missing."""
from __future__ import annotations

import html
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Iterable, Optional

from package.common.settings import get_settings
from package.logger import get_logger

logger = get_logger(__name__)


def send_email(to: str, subject: str, html_body: str, text: Optional[str] = None) -> bool:
    settings = get_settings()
    if not getattr(settings, "mail_configured", False):
        logger.warning("Mail not configured — skip send to %s", to)
        return False
    addr = (to or "").strip()
    if not addr or "@" not in addr:
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.mail_from_name} <{settings.mail_from_email}>"
    msg["To"] = addr
    msg["Reply-To"] = settings.mail_from_email
    msg.set_content(text or "Please view this email in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    try:
        context = ssl.create_default_context()
        timeout = 12
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=context, timeout=timeout
            ) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_pass)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=timeout) as smtp:
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
                smtp.login(settings.smtp_user, settings.smtp_pass)
                smtp.send_message(msg)
        logger.info("Email sent to %s (%s)", addr, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", addr)
        return False


def _money(v: Any) -> str:
    try:
        return f"₹{float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return "₹0.00"


def build_invoice_email(invoice: Any) -> tuple[str, str, str]:
    """Return (subject, html, text) for an Invoice-like object."""
    number = getattr(invoice, "invoice_number", None) or "Invoice"
    bakery = getattr(invoice, "bakery_name", None) or "SweetCrust"
    kind = getattr(invoice, "kind", None) or "invoice"
    li = getattr(invoice, "line_items", None) or {}
    if not isinstance(li, dict):
        li = {}
    title = li.get("title") or number
    items = li.get("items") or []
    customer = getattr(invoice, "customer_name", None) or "Customer"
    phone = getattr(invoice, "customer_phone", None) or ""
    address = getattr(invoice, "customer_address", None) or ""
    gstin = getattr(invoice, "gstin", None) or ""
    method = getattr(invoice, "payment_method", None) or "—"
    txn = getattr(invoice, "transaction_id", None) or "—"
    notes = getattr(invoice, "notes", None) or ""

    rows_html = []
    rows_text = []
    for i in items:
        name = html.escape(str(i.get("name") or "Item"))
        qty = i.get("qty") or 1
        unit = _money(i.get("unit_price"))
        total = _money(i.get("total"))
        rows_html.append(
            f"<tr><td style='padding:8px;border-bottom:1px solid #eee'>{name}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:center'>{qty}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{unit}</td>"
            f"<td style='padding:8px;border-bottom:1px solid #eee;text-align:right'>{total}</td></tr>"
        )
        rows_text.append(f"- {i.get('name') or 'Item'} × {qty} @ {unit} = {total}")

    subject = f"{bakery} invoice {number}"
    text = (
        f"{bakery}\nInvoice {number}\n{title}\n\n"
        f"Bill to: {customer}\n{phone}\n{address}\n\n"
        + "\n".join(rows_text)
        + f"\n\nSubtotal: {_money(getattr(invoice, 'subtotal', 0))}"
        + f"\nDiscount: {_money(getattr(invoice, 'discount', 0))}"
        + f"\nGST: {_money(getattr(invoice, 'gst_amount', 0))}"
        + f"\nDelivery: {_money(getattr(invoice, 'delivery_fee', 0))}"
        + f"\nGrand total: {_money(getattr(invoice, 'grand_total', 0))}"
        + f"\nPayment: {method}\nTxn: {txn}\n"
        + (f"\nNotes: {notes}\n" if notes else "")
    )
    html_body = f"""
<!doctype html><html><body style="font-family:Georgia,serif;background:#f7f3ee;margin:0;padding:24px;color:#2a1f18">
  <div style="max-width:560px;margin:0 auto;background:#fffdf9;border:1px solid #e8d9c8;padding:28px">
    <p style="margin:0 0 4px;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:#8a6a4a">{html.escape(str(kind).replace('_', ' '))}</p>
    <h1 style="margin:0 0 8px;font-size:28px;color:#c45c26">{html.escape(str(bakery))}</h1>
    <p style="margin:0 0 20px;color:#5c4636">{html.escape(str(title))}<br>
      <strong>{html.escape(str(number))}</strong>
      {" · GSTIN " + html.escape(str(gstin)) if gstin else ""}
    </p>
    <p style="margin:0 0 16px"><strong>Bill to</strong><br>
      {html.escape(str(customer))}<br>
      {html.escape(str(phone))}
      {("<br>" + html.escape(str(address))) if address else ""}
    </p>
    <table style="width:100%;border-collapse:collapse;font-size:14px">
      <thead>
        <tr style="background:#f3ebe2">
          <th style="padding:8px;text-align:left">Item</th>
          <th style="padding:8px;text-align:center">Qty</th>
          <th style="padding:8px;text-align:right">Price</th>
          <th style="padding:8px;text-align:right">Total</th>
        </tr>
      </thead>
      <tbody>{"".join(rows_html) or "<tr><td colspan='4' style='padding:8px'>No line items</td></tr>"}</tbody>
    </table>
    <p style="margin:20px 0 0;text-align:right;line-height:1.7">
      Subtotal {_money(getattr(invoice, "subtotal", 0))}<br>
      Discount {_money(getattr(invoice, "discount", 0))}<br>
      GST {_money(getattr(invoice, "gst_amount", 0))}<br>
      Delivery {_money(getattr(invoice, "delivery_fee", 0))}<br>
      <strong style="font-size:18px">Grand total {_money(getattr(invoice, "grand_total", 0))}</strong>
    </p>
    <p style="margin:16px 0 0;font-size:13px;color:#5c4636">Payment: {html.escape(str(method))} · Txn: {html.escape(str(txn))}</p>
    {f'<p style="margin:12px 0 0;font-size:13px;color:#5c4636">{html.escape(str(notes))}</p>' if notes else ""}
  </div>
</body></html>
"""
    return subject, html_body, text


def resolve_invoice_recipient_emails(
    session,
    *,
    buyer_user_id: int | None,
    seller_user_id: int | None,
    user_model: Any,
    bakery_settings_model: Any,
    admin_role: Any,
) -> list[str]:
    """Registered party emails + bakery/admin emails."""
    from sqlmodel import select

    found: set[str] = set()

    def _add(raw: str | None) -> None:
        e = (raw or "").strip().lower()
        if e and "@" in e:
            found.add(e)

    bakery = session.exec(select(bakery_settings_model)).first()
    if bakery is not None:
        _add(getattr(bakery, "email", None))

    for uid in (buyer_user_id, seller_user_id):
        if not uid:
            continue
        user = session.get(user_model, uid)
        if user is not None:
            _add(getattr(user, "email", None))

    try:
        admins = list(session.exec(select(user_model).where(user_model.role == admin_role)).all())
    except Exception:
        admins = []
    for admin in admins:
        _add(getattr(admin, "email", None))

    return sorted(found)


def email_invoice(
    session,
    invoice: Any,
    *,
    user_model: Any,
    bakery_settings_model: Any,
    admin_role: Any,
) -> list[str]:
    """Send invoice to registered parties + admin. Returns addresses attempted."""
    emails = resolve_invoice_recipient_emails(
        session,
        buyer_user_id=getattr(invoice, "buyer_user_id", None),
        seller_user_id=getattr(invoice, "seller_user_id", None),
        user_model=user_model,
        bakery_settings_model=bakery_settings_model,
        admin_role=admin_role,
    )
    if not emails:
        logger.info("invoice %s: no recipient emails", getattr(invoice, "invoice_number", "?"))
        return []
    subject, html_body, text = build_invoice_email(invoice)
    sent: list[str] = []
    for to in emails:
        if send_email(to, subject, html_body, text=text):
            sent.append(to)
    return sent


# ponytail: assert template renders; upgrade if invoice HTML grows
if __name__ == "__main__":
    class _Inv:
        invoice_number = "INV-TEST-1"
        bakery_name = "SweetCrust"
        kind = "subscription_pack"
        customer_name = "Test Shop"
        customer_phone = "999"
        customer_address = "City"
        gstin = "GST"
        payment_method = "razorpay"
        transaction_id = "pay_x"
        notes = "ok"
        subtotal = 499
        discount = 0
        gst_amount = 0
        delivery_fee = 0
        grand_total = 499
        line_items = {
            "title": "Sell plan · monthly",
            "items": [{"name": "Sell subscription · monthly", "qty": 1, "unit_price": 499, "total": 499}],
        }

    subj, html_body, text = build_invoice_email(_Inv())
    assert "INV-TEST-1" in subj and "499" in text and "Sell plan" in html_body
    print("ok")
