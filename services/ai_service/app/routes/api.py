"""AI microservice routes — chatbot, RAG FAQs, voice/Twilio, product vision, calls.

Public paths match the monolith so the Fastify gateway can proxy without rewrites.
"""
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Query, Request, Response
from package.common.errors import ForbiddenError, NotFoundError
from pydantic import BaseModel, Field
from sqlmodel import func, select
from app.brain.agents.chatbot_agent import respond as ai_respond
from app.brain.agents.product_agent import analyze_product_images
from app.deps import AdminUser, CustomerUser, RetailerUser, AsyncSessionDep
from app.models.enums import CallStatus, CallType, UserRole
from app.models.ops import CallRecord, ChatbotFAQ, Conversation
from app.models.user import User
from app.services import calls as ai_call_service, chat as chat_service, vision as retailer_service
from app.services.security import assert_twilio_signature, enforce_chat_rate
from app.schemas.ai import AIChatIn, AIProductUploadIn, CallStartIn, CallUpdateIn, FAQIn, InsightsQuery, ReturnAssessIn
from app.controllers.ai_async import AiController

async def _domain(session: AsyncSessionDep, fn, *args, **kwargs):
    return await AiController(session).call(fn, *args, **kwargs)

customer_router = APIRouter(prefix='/customer', tags=['ai-customer'])
admin_router = APIRouter(prefix='/admin', tags=['ai-admin'])
retailer_router = APIRouter(prefix='/retailer', tags=['ai-retailer'])
root_router = APIRouter(tags=['ai-voice'])

async def _run_ai_chat(*, session, user: User, body: AIChatIn, audience: str):
    enforce_chat_rate(user.id)
    if body.conversation_id:
        await _domain(session, chat_service.require_conversation, body.conversation_id, user)
        conv_id = body.conversation_id
    elif audience == 'retailer':
        conv = await _domain(session, chat_service.get_or_create_retailer_support, user.id, ai=True)
        conv_id = conv.id
    else:
        from types import SimpleNamespace
        conv = await _domain(session, chat_service.create_conversation, user.id, SimpleNamespace(category='ai', order_id=None, return_id=None, custom_cake_id=None, is_ai=True, initial_message=None))
        conv_id = conv.id
    history = await _domain(session, chat_service.llm_history, conv_id)
    def _respond(sync_session, user_id, message, language, aud, hist):
        return ai_respond(sync_session, user_id, message, language, audience=aud, history=hist)
    result = await _domain(session, _respond, user.id, body.message, body.language, audience, history)
    role = 'retailer' if audience == 'retailer' else 'customer'
    await _domain(session, chat_service.send_message, conv_id, user.id, role, body.message, skip_guardrails=True)
    await _domain(session, chat_service.send_message, conv_id, None, 'ai', result['reply'], metadata_json={'products': result.get('products'), 'actions': result.get('actions'), 'blocked': result.get('blocked')}, skip_guardrails=True)
    if any((a.get('type') == 'handover_human' for a in result.get('actions') or [])) and (not result.get('blocked')):
        await _domain(session, chat_service.handover_to_admin, conv_id)
        result['handed_over'] = True
        result['handover_message'] = 'You are now connected to the bakery owner.' if audience == 'retailer' else 'You are now connected to the SweetCrust bakery owner.'
    result['conversation_id'] = conv_id
    return result

@customer_router.post('/ai/chat')
async def customer_ai_chat(body: AIChatIn, session: AsyncSessionDep, user: CustomerUser):
    return await _run_ai_chat(session=session, user=user, body=body, audience='customer')

@customer_router.get('/ai/conversations/{conversation_id}/messages')
async def customer_ai_messages(conversation_id: int, session: AsyncSessionDep, user: CustomerUser):
    return await _domain(session, chat_service.list_messages, conversation_id, user)

@customer_router.get('/faqs')
async def customer_faqs(session: AsyncSessionDep):
    def _sync(s):
        return list(s.exec(select(ChatbotFAQ).where(ChatbotFAQ.is_active == True)).all())
    return await _domain(session, _sync)

@customer_router.post('/calls')
async def start_call(body: CallStartIn, session: AsyncSessionDep, user: CustomerUser):
    def _sync(s, user_id, callee_id, order_id, call_type, target):
        cid = callee_id
        if target == 'bakery':
            admin = s.exec(select(User).where(User.role == UserRole.ADMIN)).first()
            cid = admin.id if admin else None
        call = CallRecord(caller_id=user_id, callee_id=cid, order_id=order_id, call_type=CallType(call_type), status=CallStatus.RINGING, masked_number='+91170000' + str(user_id % 10000).zfill(4), started_at=datetime.utcnow())
        s.add(call)
        s.commit()
        s.refresh(call)
        return call
    return await _domain(session, _sync, user.id, body.callee_id, body.order_id, body.call_type, body.target)

@customer_router.patch('/calls/{call_id}')
async def update_call(call_id: int, body: CallUpdateIn, session: AsyncSessionDep, user: CustomerUser):
    def _sync(s, cid, user_id, status, duration_seconds, notes):
        call = s.get(CallRecord, cid)
        if not call:
            raise NotFoundError('Call not found')
        if call.caller_id != user_id and call.callee_id != user_id:
            raise ForbiddenError('Not your call')
        call.status = CallStatus(status)
        if duration_seconds is not None:
            call.duration_seconds = duration_seconds
        if notes:
            call.notes = notes
        if status in ('completed', 'missed', 'rejected', 'failed'):
            call.ended_at = datetime.utcnow()
        s.add(call)
        s.commit()
        s.refresh(call)
        return call
    return await _domain(session, _sync, call_id, user.id, body.status, body.duration_seconds, body.notes)

@customer_router.get('/calls')
async def call_history(session: AsyncSessionDep, user: CustomerUser):
    def _sync(s, user_id):
        return list(s.exec(select(CallRecord).where((CallRecord.caller_id == user_id) | (CallRecord.callee_id == user_id)).order_by(CallRecord.created_at.desc())).all())
    return await _domain(session, _sync, user.id)

class AiRequestIn(BaseModel):
    purpose: str = 'customer_request'

@customer_router.post('/calls/ai-request')
async def customer_ai_request(body: AiRequestIn, session: AsyncSessionDep, user: CustomerUser):
    call = await _domain(session, ai_call_service.request_ai_call_for_user, user, body.purpose)
    return {'id': call.id, 'status': call.status.value if hasattr(call.status, 'value') else call.status, 'message': 'SweetCrust AI will call your registered mobile number shortly.', 'to_phone': call.masked_number}

class AiOutboundIn(BaseModel):
    user_id: Optional[int] = None
    phone: Optional[str] = None
    purpose: str = 'admin_outreach'

@admin_router.post('/calls/ai-outbound')
async def admin_ai_outbound(body: AiOutboundIn, session: AsyncSessionDep, admin: AdminUser):
    call = await _domain(session, ai_call_service.admin_ai_call, admin, user_id=body.user_id, phone=body.phone, purpose=body.purpose)
    return {'id': call.id, 'status': call.status.value if hasattr(call.status, 'value') else call.status, 'provider_call_sid': call.provider_call_sid, 'to_phone': call.to_phone, 'direction': call.direction}

@admin_router.post('/products/ai-upload')
async def ai_upload(body: AIProductUploadIn, _: AdminUser):
    result = await asyncio.to_thread(analyze_product_images, body.image_urls, body.notes)
    result.setdefault('vision', False)
    result.setdefault('stub', result.get('provider') == 'rules')
    return result

@admin_router.post('/categories/ai-image')
async def ai_category_image(body: dict, _: AdminUser):
    from app.services.category_image import generate_category_image
    name = body.get('name', 'Bakery')
    # DALL·E can take 10–30s — keep the event loop free
    return await asyncio.to_thread(generate_category_image, name)

@admin_router.post('/coupons/ai-suggest')
def coupon_ai(_: AdminUser):
    return {'stub': True, 'title': 'Weekend Treat 15% Off', 'description': 'Sweet savings on cakes this Saturday–Sunday', 'discount_amount': 15, 'coupon_type': 'percentage', 'target_products': ['Birthday Cakes', 'Cupcakes'], 'best_offer_time': 'Fri 6 PM – Sun 10 PM', 'expected_impact': '+12% weekend orders', 'note': 'Heuristic template — not live model output.'}

@admin_router.get('/chatbot/faqs')
async def get_faqs(session: AsyncSessionDep, _: AdminUser):
    def _sync(s):
        return list(s.exec(select(ChatbotFAQ)).all())
    return await _domain(session, _sync)

@admin_router.post('/chatbot/faqs')
async def add_faq(body: FAQIn, session: AsyncSessionDep, _: AdminUser):
    def _sync(s, data):
        faq = ChatbotFAQ(**data)
        s.add(faq)
        s.commit()
        s.refresh(faq)
        return faq
    return await _domain(session, _sync, body.model_dump())

@admin_router.patch('/chatbot/faqs/{faq_id}')
async def patch_faq(faq_id: int, body: FAQIn, session: AsyncSessionDep, _: AdminUser):
    def _sync(s, fid, data):
        faq = s.get(ChatbotFAQ, fid)
        if not faq:
            raise NotFoundError('FAQ not found')
        for k, v in data.items():
            setattr(faq, k, v)
        s.add(faq)
        s.commit()
        s.refresh(faq)
        return faq
    return await _domain(session, _sync, faq_id, body.model_dump())

@admin_router.delete('/chatbot/faqs/{faq_id}')
async def delete_faq(faq_id: int, session: AsyncSessionDep, _: AdminUser):
    def _sync(s, fid):
        faq = s.get(ChatbotFAQ, fid)
        if not faq:
            raise NotFoundError('FAQ not found')
        s.delete(faq)
        s.commit()
        return {'ok': True}
    return await _domain(session, _sync, faq_id)

@admin_router.get('/chatbot/analytics')
async def chatbot_analytics(session: AsyncSessionDep, _: AdminUser):
    from app.brain.monitor import monitor_status, recent_runs
    def _sync(s):
        ai_total = s.exec(select(func.count()).select_from(Conversation).where(Conversation.is_ai == True)).one()
        handed = s.exec(select(func.count()).select_from(Conversation).where(Conversation.ai_handed_over == True)).one()
        faqs = s.exec(select(func.count()).select_from(ChatbotFAQ).where(ChatbotFAQ.is_active == True)).one()
        return int(ai_total or 0), int(handed or 0), int(faqs or 0)
    ai_total, handed, faqs = await _domain(session, _sync)
    mon = monitor_status()
    return {'total_ai_conversations': ai_total, 'transferred_to_admin': handed, 'active_faqs': faqs, 'stack': {'langchain': True, 'langgraph': True, 'agentic_rag': True, 'langsmith': mon.get('langsmith'), 'project': mon.get('project')}, 'monitor': mon, 'recent_runs': recent_runs(30)}

@admin_router.get('/chatbot/runs')
def chatbot_runs(_: AdminUser, limit: int=Query(40, ge=1, le=100)):
    from app.brain.monitor import recent_runs
    return recent_runs(limit)

@admin_router.get('/insights')
async def admin_insights(session: AsyncSessionDep, _: AdminUser, use_llm: bool=Query(False)):
    from app.brain.agents.insights_agent import business_insights
    return {'insights': await _domain(session, business_insights, use_llm=use_llm)}

@admin_router.post('/insights')
async def admin_insights_post(body: InsightsQuery, session: AsyncSessionDep, _: AdminUser):
    from app.brain.agents.insights_agent import business_insights
    return {'insights': await _domain(session, business_insights, use_llm=body.use_llm)}

@admin_router.post('/returns/ai-assess')
def admin_return_assess(body: ReturnAssessIn, _: AdminUser):
    from app.brain.agents.return_agent import assess_return
    return assess_return(body.issue_type, body.evidence_urls, body.description)

class ProductAiSuggestIn(BaseModel):
    image_urls: list[str] = Field(default_factory=list)
    notes: Optional[str] = None

@retailer_router.post('/ai/chat')
async def retailer_ai_chat(body: AIChatIn, session: AsyncSessionDep, user: RetailerUser):
    return await _run_ai_chat(session=session, user=user, body=body, audience='retailer')

@retailer_router.get('/ai/conversations/{conversation_id}/messages')
async def retailer_ai_messages(conversation_id: int, session: AsyncSessionDep, user: RetailerUser):
    return await _domain(session, chat_service.list_messages, conversation_id, user)

@retailer_router.post('/products/ai-suggest')
def product_ai_suggest(body: ProductAiSuggestIn, user: RetailerUser):
    result = retailer_service.ai_suggest_product(body.image_urls, body.notes)
    result.setdefault('vision', False)
    result.setdefault('stub', result.get('provider') == 'rules')
    return result

@root_router.post('/api/v1/voice/twilio/voice')
async def twilio_voice(request: Request, call_id: int=Query(...)):
    await assert_twilio_signature(request)
    xml = ai_call_service.voice_twiml_welcome(call_id)
    return Response(content=xml, media_type='application/xml')

@root_router.post('/api/v1/voice/twilio/gather')
async def twilio_gather(request: Request, session: AsyncSessionDep, call_id: int=Query(...)):
    form = await assert_twilio_signature(request)
    speech = form.get('SpeechResult') or form.get('Digits')
    xml = await _domain(session, ai_call_service.voice_twiml_gather, call_id, speech)
    return Response(content=xml, media_type='application/xml')

@root_router.post('/api/v1/voice/twilio/status')
async def twilio_status(request: Request, session: AsyncSessionDep, call_id: Optional[int]=Query(None)):
    form = await assert_twilio_signature(request)
    sid = form.get('CallSid')
    status = form.get('CallStatus') or 'completed'
    cid = call_id
    if cid is None and form.get('call_id'):
        try:
            cid = int(form['call_id'])
        except (TypeError, ValueError):
            cid = None
    if cid is None:
        return {'ok': False}
    call = await _domain(session, ai_call_service.update_call_status, cid, str(status), str(sid) if sid else None)
    return {'ok': bool(call), 'status': status}

@root_router.get('/api/v1/ai/status')
def ai_stack_status():
    from app.brain.monitor import monitor_status
    from app.config import get_settings
    s = get_settings()
    status = s.integration_status()
    return {'service': 'ai', 'ok': True, 'llm': status.get('llm'), 'embeddings': status.get('embeddings'), 'vector_store': status.get('vector_store'), 'pinecone': status.get('pinecone'), 'twilio_voice': status.get('twilio_voice'), 'langsmith': status.get('langsmith'), 'guardrails': status.get('guardrails'), 'monitor': monitor_status()}
