"""Outbound AI bot phone calls via Twilio Voice + Gather loop."""

from __future__ import annotations

from package.logger import get_logger
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape as xml_escape

from package.common.errors import BadGatewayError, BadRequestError, NotFoundError, ServiceUnavailableError
from sqlmodel import Session, select

from app.brain.agents.chatbot_agent import respond as ai_respond
from app.brain.guardrails import filter_ai_reply, filter_user_message
from app.config import get_settings
from app.models.enums import CallStatus, CallType
from app.models.ops import CallRecord
from app.models.user import User

logger = get_logger(__name__)


def _twilio_client():
    settings = get_settings()
    if not settings.twilio_configured:
        raise ServiceUnavailableError("Twilio voice is not configured")
    from twilio.rest import Client

    return Client(settings.twilio_account_sid, settings.twilio_auth_token), settings


def _e164(phone: str) -> str:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 10:
        return "+91" + digits
    if phone.startswith("+"):
        return phone
    return "+" + digits


def start_ai_outbound(
    session: Session,
    *,
    to_phone: str,
    callee_user_id: Optional[int] = None,
    initiator_id: Optional[int] = None,
    purpose: str = "bakery_support",
) -> CallRecord:
    client, settings = _twilio_client()
    to_phone = _e164(to_phone)
    record = CallRecord(
        caller_id=initiator_id,
        callee_id=callee_user_id,
        call_type=CallType.PHONE,
        status=CallStatus.RINGING,
        direction="outbound_ai",
        provider="twilio",
        to_phone=to_phone,
        purpose=purpose,
        transcript=[],
        masked_number=to_phone[:7] + "****",
        started_at=datetime.utcnow(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)

    base = settings.twilio_webhook_base_url.rstrip("/")
    voice_url = f"{base}/api/v1/voice/twilio/voice?call_id={record.id}"
    status_url = f"{base}/api/v1/voice/twilio/status?call_id={record.id}"

    try:
        call = client.calls.create(
            to=to_phone,
            from_=settings.twilio_from_number,
            url=voice_url,
            status_callback=status_url,
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            method="POST",
        )
        record.provider_call_sid = call.sid
        record.status = CallStatus.RINGING
        session.add(record)
        session.commit()
        session.refresh(record)
    except Exception as exc:
        logger.exception("Twilio call create failed")
        record.status = CallStatus.FAILED
        record.notes = str(exc)[:500]
        session.add(record)
        session.commit()
        session.refresh(record)
        raise BadGatewayError(f"Failed to place AI call: {exc}") from exc
    return record


def request_ai_call_for_user(session: Session, user: User, purpose: str = "customer_request") -> CallRecord:
    return start_ai_outbound(
        session,
        to_phone=user.phone,
        callee_user_id=user.id,
        initiator_id=user.id,
        purpose=purpose,
    )


def admin_ai_call(
    session: Session,
    admin: User,
    *,
    user_id: Optional[int] = None,
    phone: Optional[str] = None,
    purpose: str = "admin_outreach",
) -> CallRecord:
    target: User | None = None
    if user_id:
        target = session.get(User, user_id)
        if not target:
            raise NotFoundError("Customer not found")
        phone = target.phone
    if not phone:
        raise BadRequestError("user_id or phone required")
    return start_ai_outbound(
        session,
        to_phone=phone,
        callee_user_id=target.id if target else None,
        initiator_id=admin.id,
        purpose=purpose,
    )


def _append_transcript(session: Session, call: CallRecord, role: str, text: str) -> None:
    rows = list(call.transcript or [])
    rows.append({"role": role, "text": text, "at": datetime.utcnow().isoformat()})
    call.transcript = rows
    session.add(call)
    session.commit()


def voice_twiml_welcome(call_id: int) -> str:
    settings = get_settings()
    base = (settings.twilio_webhook_base_url or "").rstrip("/")
    action = f"{base}/api/v1/voice/twilio/gather?call_id={call_id}"
    say = (
        f"Hello, this is the {settings.bakery_name} AI assistant. "
        "I can help with cakes, orders, delivery, and returns. "
        "Please tell me how I can help after the beep."
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Aditi" language="en-IN">{xml_escape(say)}</Say>
  <Gather input="speech" action="{xml_escape(action)}" method="POST" speechTimeout="auto" language="en-IN">
    <Say voice="Polly.Aditi" language="en-IN">I am listening.</Say>
  </Gather>
  <Say voice="Polly.Aditi" language="en-IN">I did not catch that. Goodbye.</Say>
  <Hangup/>
</Response>
"""


def voice_twiml_gather(session: Session, call_id: int, speech: str | None) -> str:
    settings = get_settings()
    base = (settings.twilio_webhook_base_url or "").rstrip("/")
    action = f"{base}/api/v1/voice/twilio/gather?call_id={call_id}"
    call = session.get(CallRecord, call_id)
    if not call:
        return """<?xml version="1.0" encoding="UTF-8"?><Response><Say>Call not found.</Say><Hangup/></Response>"""

    call.status = CallStatus.ONGOING
    session.add(call)
    session.commit()

    speech = (speech or "").strip()
    if not speech:
        reply = "Sorry, I could not hear you. Please say your question about SweetCrust Bakery."
    else:
        _append_transcript(session, call, "user", speech)
        gate = filter_user_message(speech)
        if not gate.get("allowed"):
            reply = gate.get("reply") or "I can only help with SweetCrust Bakery topics."
        else:
            user_id = call.callee_id or call.caller_id
            if user_id:
                result = ai_respond(session, user_id, gate.get("text") or speech, "en")
                reply = filter_ai_reply(result.get("reply") or "")
            else:
                reply = (
                    "Thanks for calling SweetCrust. Please open the app and sign in "
                    "so I can check your orders. How else can I help with cakes or delivery?"
                )
        _append_transcript(session, call, "assistant", reply)

    # Hang up if user says goodbye
    if speech and any(w in speech.lower() for w in ("bye", "goodbye", "stop", "thank you bye")):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Aditi" language="en-IN">{xml_escape(reply)} Goodbye from SweetCrust.</Say>
  <Hangup/>
</Response>
"""

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Aditi" language="en-IN">{xml_escape(reply)}</Say>
  <Gather input="speech" action="{xml_escape(action)}" method="POST" speechTimeout="auto" language="en-IN">
    <Say voice="Polly.Aditi" language="en-IN">Anything else about your bakery order?</Say>
  </Gather>
  <Say voice="Polly.Aditi" language="en-IN">Thank you for calling SweetCrust. Goodbye.</Say>
  <Hangup/>
</Response>
"""


def update_call_status(session: Session, call_id: int, twilio_status: str, call_sid: str | None = None) -> CallRecord | None:
    call = session.get(CallRecord, call_id)
    if not call:
        if call_sid:
            call = session.exec(select(CallRecord).where(CallRecord.provider_call_sid == call_sid)).first()
    if not call:
        return None
    mapping = {
        "queued": CallStatus.RINGING,
        "initiated": CallStatus.RINGING,
        "ringing": CallStatus.RINGING,
        "in-progress": CallStatus.ONGOING,
        "answered": CallStatus.ONGOING,
        "completed": CallStatus.COMPLETED,
        "busy": CallStatus.FAILED,
        "failed": CallStatus.FAILED,
        "no-answer": CallStatus.MISSED,
        "canceled": CallStatus.REJECTED,
    }
    call.status = mapping.get(twilio_status.lower(), call.status)
    if call_sid and not call.provider_call_sid:
        call.provider_call_sid = call_sid
    if call.status in (CallStatus.COMPLETED, CallStatus.FAILED, CallStatus.MISSED, CallStatus.REJECTED):
        call.ended_at = datetime.utcnow()
        if call.started_at:
            call.duration_seconds = int((call.ended_at - call.started_at).total_seconds())
    session.add(call)
    session.commit()
    session.refresh(call)
    return call
