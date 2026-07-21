from app.brain.prompts.chatbot import CHATBOT_SYSTEM, CHATBOT_USER
from app.brain.prompts.guardrails import GUARDRAILS_SYSTEM_ADDON
from app.brain.prompts.insights import INSIGHTS_SYSTEM
from app.brain.prompts.product import PRODUCT_ENRICH_SYSTEM, PRODUCT_ENRICH_USER
from app.brain.prompts.return_assessment import RETURN_ASSESS_SYSTEM, RETURN_ASSESS_USER

__all__ = [
    "CHATBOT_SYSTEM",
    "CHATBOT_USER",
    "GUARDRAILS_SYSTEM_ADDON",
    "PRODUCT_ENRICH_SYSTEM",
    "PRODUCT_ENRICH_USER",
    "RETURN_ASSESS_SYSTEM",
    "RETURN_ASSESS_USER",
    "INSIGHTS_SYSTEM",
]
